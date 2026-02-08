import os

from dotenv import load_dotenv
from espn_api.football import League
from flask import Flask, render_template, abort

load_dotenv()

app = Flask(__name__)

LEAGUE_ID = int(os.environ["ESPN_LEAGUE_ID"])
YEAR = int(os.environ["ESPN_YEAR"])
ESPN_S2 = os.environ["ESPN_S2"]
SWID = os.environ["ESPN_SWID"]


def get_league():
    return League(league_id=LEAGUE_ID, year=YEAR, espn_s2=ESPN_S2, swid=SWID)


@app.route("/")
def teams():
    league = get_league()
    sorted_teams = sorted(league.teams, key=lambda t: t.standing)
    return render_template("teams.html", league=league, teams=sorted_teams)


@app.route("/team/<int:team_id>")
def roster(team_id):
    league = get_league()
    team = next((t for t in league.teams if t.team_id == team_id), None)
    if team is None:
        abort(404)
    starters = [p for p in team.roster if p.lineupSlot not in ("BE", "IR")]
    bench = [p for p in team.roster if p.lineupSlot == "BE"]
    ir = [p for p in team.roster if p.lineupSlot == "IR"]
    return render_template("roster.html", team=team, starters=starters, bench=bench, ir=ir)


if __name__ == "__main__":
    app.run(debug=True)
