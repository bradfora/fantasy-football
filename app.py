import os

from dotenv import load_dotenv
from espn_api.football import League
from flask import Flask, render_template, abort, redirect, url_for, request, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

from db import get_db, UserRepository
from models import User

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

LEAGUE_ID = int(os.environ["ESPN_LEAGUE_ID"])
YEAR = int(os.environ["ESPN_YEAR"])
ESPN_S2 = os.environ["ESPN_S2"]
SWID = os.environ["ESPN_SWID"]

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


def _get_user_repo():
    if not hasattr(app, "_db"):
        app._db = get_db()
    return UserRepository(db=app._db)


@login_manager.user_loader
def load_user(user_id):
    repo = _get_user_repo()
    doc = repo.find_by_id(user_id)
    if doc:
        return User(doc)
    return None


SLOT_ORDER = {"QB": 0, "OP": 0, "RB": 1, "WR": 2, "TE": 3, "FLEX": 4, "RB/WR/TE": 4, "K": 5, "D/ST": 6}
SLOT_DISPLAY = {"OP": "QB", "RB/WR/TE": "FLEX"}


def get_league():
    return League(league_id=LEAGUE_ID, year=YEAR, espn_s2=ESPN_S2, swid=SWID)


def display_slot(slot):
    return SLOT_DISPLAY.get(slot, slot)


def slot_sort_key(player):
    return SLOT_ORDER.get(player.lineupSlot, 99)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("teams"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        repo = _get_user_repo()
        user_doc = repo.verify_password(username, password)
        if user_doc:
            login_user(User(user_doc))
            next_page = request.args.get("next")
            return redirect(next_page or url_for("teams"))
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
        return redirect(url_for("teams"))
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
                return redirect(url_for("teams"))
    return render_template("register.html")


@app.route("/")
@login_required
def teams():
    league = get_league()
    sorted_teams = sorted(league.teams, key=lambda t: t.standing)
    return render_template("teams.html", league=league, teams=sorted_teams)


@app.route("/team/<int:team_id>")
@login_required
def roster(team_id):
    league = get_league()
    team = next((t for t in league.teams if t.team_id == team_id), None)
    if team is None:
        abort(404)
    starters = sorted(
        [p for p in team.roster if p.lineupSlot not in ("BE", "IR")],
        key=slot_sort_key,
    )
    bench = [p for p in team.roster if p.lineupSlot == "BE"]
    ir = [p for p in team.roster if p.lineupSlot == "IR"]
    return render_template("roster.html", team=team, starters=starters, bench=bench, ir=ir, display_slot=display_slot)


if __name__ == "__main__":
    app.run(debug=True)
