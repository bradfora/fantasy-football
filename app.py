import os

from bson import ObjectId
from dotenv import load_dotenv
from espn_api.football import League
from flask import Flask, render_template, abort, redirect, url_for, request, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

from db import get_db, UserRepository, LeagueRepository
from models import User

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


def _get_db():
    if not hasattr(app, "_db"):
        try:
            app._db = get_db()
        except Exception as e:
            # Fallback to mongomock for local development without MongoDB
            import mongomock
            app._db = mongomock.MongoClient()["fantasy_football"]
    return app._db


def _get_user_repo():
    return UserRepository(db=_get_db())


def _get_league_repo():
    return LeagueRepository(db=_get_db())


@login_manager.user_loader
def load_user(user_id):
    repo = _get_user_repo()
    doc = repo.find_by_id(user_id)
    if doc:
        return User(doc)
    return None


SLOT_ORDER = {"QB": 0, "OP": 0, "RB": 1, "WR": 2, "TE": 3, "FLEX": 4, "RB/WR/TE": 4, "K": 5, "D/ST": 6}
SLOT_DISPLAY = {"OP": "QB", "RB/WR/TE": "FLEX"}


def get_espn_league(league_doc):
    """Create an ESPN League from a league document's stored credentials."""
    return League(
        league_id=league_doc["espn_league_id"],
        year=league_doc["espn_year"],
        espn_s2=league_doc["espn_s2"],
        swid=league_doc["espn_swid"],
    )


def display_slot(slot):
    return SLOT_DISPLAY.get(slot, slot)


def slot_sort_key(player):
    return SLOT_ORDER.get(player.lineupSlot, 99)


def _get_user_league(league_id):
    """Get a league document, ensuring it belongs to the current user."""
    repo = _get_league_repo()
    league_doc = repo.find_by_id(league_id)
    if not league_doc:
        abort(404)
    if str(league_doc["user_id"]) != current_user.get_id():
        abort(403)
    return league_doc


# --- Auth routes ---


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("leagues"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        repo = _get_user_repo()
        user_doc = repo.verify_password(username, password)
        if user_doc:
            login_user(User(user_doc))
            next_page = request.args.get("next")
            return redirect(next_page or url_for("leagues"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("leagues"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        if not username:
            flash("Username is required.", "error")
        elif not password:
            flash("Password is required.", "error")
        elif password != confirm:
            flash("Passwords do not match.", "error")
        else:
            repo = _get_user_repo()
            if repo.find_by_username(username):
                flash("Username already taken.", "error")
            else:
                user_doc = repo.create_user(username, password)
                login_user(User(user_doc))
                return redirect(url_for("leagues"))
    return render_template("register.html")


# --- League management routes ---


@app.route("/")
@login_required
def index():
    return redirect(url_for("leagues"))


@app.route("/leagues")
@login_required
def leagues():
    repo = _get_league_repo()
    user_leagues = repo.find_by_user(current_user.get_id())
    return render_template("leagues.html", leagues=user_leagues)


@app.route("/leagues/add", methods=["GET", "POST"])
@login_required
def add_league():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        espn_league_id = request.form.get("espn_league_id", "").strip()
        espn_year = request.form.get("espn_year", "").strip()
        espn_s2 = request.form.get("espn_s2", "").strip()
        espn_swid = request.form.get("espn_swid", "").strip()

        if not all([name, espn_league_id, espn_year, espn_s2, espn_swid]):
            flash("All fields are required.", "error")
        else:
            try:
                espn_league_id = int(espn_league_id)
                espn_year = int(espn_year)
            except ValueError:
                flash("League ID and Year must be numbers.", "error")
                return render_template("add_league.html")

            # Validate ESPN credentials by attempting connection
            try:
                League(league_id=espn_league_id, year=espn_year, espn_s2=espn_s2, swid=espn_swid)
            except Exception:
                flash("Could not connect to ESPN league. Check your credentials.", "error")
                return render_template("add_league.html")

            repo = _get_league_repo()
            repo.create_league(
                user_id=current_user.get_id(),
                name=name,
                espn_league_id=espn_league_id,
                espn_year=espn_year,
                espn_s2=espn_s2,
                espn_swid=espn_swid,
            )
            return redirect(url_for("leagues"))
    return render_template("add_league.html")


@app.route("/leagues/<league_id>/delete", methods=["POST"])
@login_required
def delete_league(league_id):
    league_doc = _get_user_league(league_id)
    repo = _get_league_repo()
    repo.delete_league(league_doc["_id"])
    return redirect(url_for("leagues"))


# --- League-scoped content routes ---


@app.route("/leagues/<league_id>/standings")
@login_required
def standings(league_id):
    league_doc = _get_user_league(league_id)
    espn_league = get_espn_league(league_doc)
    sorted_teams = sorted(espn_league.teams, key=lambda t: t.standing)
    return render_template("teams.html", league=espn_league, teams=sorted_teams, league_doc=league_doc)


@app.route("/leagues/<league_id>/team/<int:team_id>")
@login_required
def roster(league_id, team_id):
    league_doc = _get_user_league(league_id)
    espn_league = get_espn_league(league_doc)
    team = next((t for t in espn_league.teams if t.team_id == team_id), None)
    if team is None:
        abort(404)
    starters = sorted(
        [p for p in team.roster if p.lineupSlot not in ("BE", "IR")],
        key=slot_sort_key,
    )
    bench = [p for p in team.roster if p.lineupSlot == "BE"]
    ir = [p for p in team.roster if p.lineupSlot == "IR"]
    return render_template("roster.html", team=team, starters=starters, bench=bench, ir=ir, display_slot=display_slot, league_doc=league_doc)


@app.route("/leagues/<league_id>/analytics")
@login_required
def analytics(league_id):
    league_doc = _get_user_league(league_id)
    season = league_doc["espn_year"]

    from analytics.basic_stats import get_positional_rankings
    rankings = get_positional_rankings(_get_db(), season)

    return render_template("analytics.html", league_doc=league_doc, rankings=rankings, season=season)


if __name__ == "__main__":
    app.run(debug=True)
