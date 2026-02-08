import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest

# Set required env vars before importing app
os.environ.setdefault("ESPN_LEAGUE_ID", "1")
os.environ.setdefault("ESPN_YEAR", "2024")
os.environ.setdefault("ESPN_S2", "fake_s2")
os.environ.setdefault("ESPN_SWID", "{fake-swid}")

from app import app, display_slot, slot_sort_key, SLOT_ORDER


def make_player(**kwargs):
    defaults = {
        "name": "Test Player",
        "playerId": 1,
        "position": "QB",
        "lineupSlot": "QB",
        "proTeam": "KC",
        "injuryStatus": "ACTIVE",
        "total_points": 150.0,
        "avg_points": 15.0,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def make_team(**kwargs):
    defaults = {
        "team_id": 1,
        "team_name": "Team One",
        "team_abbrev": "T1",
        "wins": 10,
        "losses": 4,
        "ties": 0,
        "points_for": 1500.5,
        "points_against": 1300.2,
        "standing": 1,
        "streak_type": "WIN",
        "streak_length": 3,
        "logo_url": "https://example.com/logo.png",
        "roster": [],
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def make_league(teams):
    return SimpleNamespace(teams=teams)


# --- display_slot tests ---


class TestDisplaySlot:
    def test_op_displays_as_qb(self):
        assert display_slot("OP") == "QB"

    def test_rb_wr_te_displays_as_flex(self):
        assert display_slot("RB/WR/TE") == "FLEX"

    def test_regular_slots_unchanged(self):
        for slot in ("QB", "RB", "WR", "TE", "K", "D/ST", "BE", "IR"):
            assert display_slot(slot) == slot


# --- slot_sort_key tests ---


class TestSlotSortKey:
    def test_standard_slot_ordering(self):
        slots = ["K", "WR", "QB", "TE", "RB", "D/ST", "FLEX"]
        players = [make_player(lineupSlot=s) for s in slots]
        sorted_players = sorted(players, key=slot_sort_key)
        result = [p.lineupSlot for p in sorted_players]
        assert result == ["QB", "RB", "WR", "TE", "FLEX", "K", "D/ST"]

    def test_op_sorts_with_qb(self):
        players = [make_player(lineupSlot="RB"), make_player(lineupSlot="OP")]
        sorted_players = sorted(players, key=slot_sort_key)
        assert sorted_players[0].lineupSlot == "OP"
        assert sorted_players[1].lineupSlot == "RB"

    def test_rb_wr_te_sorts_as_flex(self):
        players = [
            make_player(lineupSlot="K"),
            make_player(lineupSlot="RB/WR/TE"),
            make_player(lineupSlot="TE"),
        ]
        sorted_players = sorted(players, key=slot_sort_key)
        result = [p.lineupSlot for p in sorted_players]
        assert result == ["TE", "RB/WR/TE", "K"]

    def test_unknown_slot_sorts_last(self):
        players = [
            make_player(lineupSlot="UNKNOWN"),
            make_player(lineupSlot="QB"),
        ]
        sorted_players = sorted(players, key=slot_sort_key)
        assert sorted_players[0].lineupSlot == "QB"
        assert sorted_players[1].lineupSlot == "UNKNOWN"


# --- SLOT_ORDER coverage ---


class TestSlotOrder:
    def test_op_and_qb_share_order(self):
        assert SLOT_ORDER["OP"] == SLOT_ORDER["QB"]

    def test_rb_wr_te_and_flex_share_order(self):
        assert SLOT_ORDER["RB/WR/TE"] == SLOT_ORDER["FLEX"]


# --- Route tests ---


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


class TestTeamsRoute:
    def test_standings_page_renders(self, client):
        teams = [
            make_team(team_id=1, team_name="First Place", standing=1, wins=10, losses=4),
            make_team(team_id=2, team_name="Second Place", standing=2, wins=8, losses=6),
        ]
        with patch("app.get_league", return_value=make_league(teams)):
            response = client.get("/")
        assert response.status_code == 200
        html = response.data.decode()
        assert "League Standings" in html
        assert "First Place" in html
        assert "Second Place" in html

    def test_teams_sorted_by_standing(self, client):
        teams = [
            make_team(team_id=2, team_name="Second", standing=2),
            make_team(team_id=1, team_name="First", standing=1),
        ]
        with patch("app.get_league", return_value=make_league(teams)):
            response = client.get("/")
        html = response.data.decode()
        first_pos = html.index("First")
        second_pos = html.index("Second")
        assert first_pos < second_pos

    def test_team_record_displayed(self, client):
        teams = [make_team(wins=10, losses=4, ties=0)]
        with patch("app.get_league", return_value=make_league(teams)):
            response = client.get("/")
        html = response.data.decode()
        assert "10-4" in html

    def test_team_record_with_ties(self, client):
        teams = [make_team(wins=9, losses=4, ties=1)]
        with patch("app.get_league", return_value=make_league(teams)):
            response = client.get("/")
        html = response.data.decode()
        assert "9-4-1" in html

    def test_points_displayed(self, client):
        teams = [make_team(points_for=1500.5, points_against=1300.2)]
        with patch("app.get_league", return_value=make_league(teams)):
            response = client.get("/")
        html = response.data.decode()
        assert "1500.5" in html
        assert "1300.2" in html

    def test_win_streak_displayed(self, client):
        teams = [make_team(streak_type="WIN", streak_length=3)]
        with patch("app.get_league", return_value=make_league(teams)):
            response = client.get("/")
        assert b"W3" in response.data

    def test_loss_streak_displayed(self, client):
        teams = [make_team(streak_type="LOSS", streak_length=2)]
        with patch("app.get_league", return_value=make_league(teams)):
            response = client.get("/")
        assert b"L2" in response.data

    def test_team_logo_rendered(self, client):
        teams = [make_team(logo_url="https://example.com/logo.png")]
        with patch("app.get_league", return_value=make_league(teams)):
            response = client.get("/")
        assert b"https://example.com/logo.png" in response.data

    def test_team_link_points_to_roster(self, client):
        teams = [make_team(team_id=5)]
        with patch("app.get_league", return_value=make_league(teams)):
            response = client.get("/")
        assert b"/team/5" in response.data

    def test_rank_badges(self, client):
        teams = [
            make_team(team_id=i, standing=i)
            for i in range(1, 5)
        ]
        with patch("app.get_league", return_value=make_league(teams)):
            response = client.get("/")
        html = response.data.decode()
        assert "rank-1" in html
        assert "rank-2" in html
        assert "rank-3" in html
        assert "rank-default" in html


class TestRosterRoute:
    def _team_with_roster(self):
        roster = [
            make_player(name="Patrick Mahomes", lineupSlot="QB", position="QB", proTeam="KC", total_points=250.0, avg_points=18.0, injuryStatus="ACTIVE"),
            make_player(name="Travis Kelce", lineupSlot="TE", position="TE", proTeam="KC", total_points=120.0, avg_points=10.0, injuryStatus="ACTIVE"),
            make_player(name="Derrick Henry", lineupSlot="RB", position="RB", proTeam="BAL", total_points=180.0, avg_points=14.0, injuryStatus="ACTIVE"),
            make_player(name="Ja'Marr Chase", lineupSlot="WR", position="WR", proTeam="CIN", total_points=200.0, avg_points=16.0, injuryStatus="ACTIVE"),
            make_player(name="Flex Guy", lineupSlot="RB/WR/TE", position="WR", proTeam="BUF", total_points=90.0, avg_points=8.0, injuryStatus="ACTIVE"),
            make_player(name="Tyler Bass", lineupSlot="K", position="K", proTeam="BUF", total_points=80.0, avg_points=6.0, injuryStatus="ACTIVE"),
            make_player(name="Cowboys D", lineupSlot="D/ST", position="D/ST", proTeam="DAL", total_points=70.0, avg_points=5.0, injuryStatus="ACTIVE"),
            make_player(name="Bench Player", lineupSlot="BE", position="RB", proTeam="NYG", total_points=40.0, avg_points=3.0, injuryStatus="ACTIVE"),
            make_player(name="IR Player", lineupSlot="IR", position="WR", proTeam="LAR", total_points=10.0, avg_points=2.0, injuryStatus="OUT"),
        ]
        return make_team(team_id=1, roster=roster)

    def test_roster_page_renders(self, client):
        team = self._team_with_roster()
        with patch("app.get_league", return_value=make_league([team])):
            response = client.get("/team/1")
        assert response.status_code == 200
        html = response.data.decode()
        assert team.team_name in html

    def test_invalid_team_returns_404(self, client):
        team = make_team(team_id=1)
        with patch("app.get_league", return_value=make_league([team])):
            response = client.get("/team/999")
        assert response.status_code == 404

    def test_starters_section_displayed(self, client):
        team = self._team_with_roster()
        with patch("app.get_league", return_value=make_league([team])):
            response = client.get("/team/1")
        html = response.data.decode()
        assert "Starters" in html
        assert "Patrick Mahomes" in html
        assert "Travis Kelce" in html

    def test_bench_section_displayed(self, client):
        team = self._team_with_roster()
        with patch("app.get_league", return_value=make_league([team])):
            response = client.get("/team/1")
        html = response.data.decode()
        assert "Bench" in html
        assert "Bench Player" in html

    def test_ir_section_displayed(self, client):
        team = self._team_with_roster()
        with patch("app.get_league", return_value=make_league([team])):
            response = client.get("/team/1")
        html = response.data.decode()
        assert "Injured Reserve" in html
        assert "IR Player" in html

    def test_starters_sorted_by_position(self, client):
        team = self._team_with_roster()
        with patch("app.get_league", return_value=make_league([team])):
            response = client.get("/team/1")
        html = response.data.decode()
        qb_pos = html.index("Patrick Mahomes")
        rb_pos = html.index("Derrick Henry")
        wr_pos = html.index("JaMarr Chase")
        te_pos = html.index("Travis Kelce")
        flex_pos = html.index("Flex Guy")
        k_pos = html.index("Tyler Bass")
        dst_pos = html.index("Cowboys D")
        assert qb_pos < rb_pos < wr_pos < te_pos < flex_pos < k_pos < dst_pos

    def test_op_slot_displays_as_qb(self, client):
        roster = [
            make_player(name="QB One", lineupSlot="QB"),
            make_player(name="QB Two", lineupSlot="OP", position="QB"),
        ]
        team = make_team(team_id=1, roster=roster)
        with patch("app.get_league", return_value=make_league([team])):
            response = client.get("/team/1")
        html = response.data.decode()
        assert "QB Two" in html
        # The slot badge should say QB, not OP
        assert ">OP<" not in html

    def test_rb_wr_te_slot_displays_as_flex(self, client):
        roster = [make_player(name="Flex Man", lineupSlot="RB/WR/TE", position="WR")]
        team = make_team(team_id=1, roster=roster)
        with patch("app.get_league", return_value=make_league([team])):
            response = client.get("/team/1")
        html = response.data.decode()
        assert "Flex Man" in html
        assert ">FLEX<" in html
        assert ">RB/WR/TE<" not in html

    def test_injury_status_shown(self, client):
        roster = [
            make_player(name="Hurt Guy", lineupSlot="RB", injuryStatus="QUESTIONABLE"),
        ]
        team = make_team(team_id=1, roster=roster)
        with patch("app.get_league", return_value=make_league([team])):
            response = client.get("/team/1")
        html = response.data.decode()
        assert "QUESTIONABLE" in html
        assert "injury-QUESTIONABLE" in html

    def test_active_injury_status_hidden(self, client):
        roster = [
            make_player(name="Healthy Guy", lineupSlot="RB", injuryStatus="ACTIVE"),
        ]
        team = make_team(team_id=1, roster=roster)
        with patch("app.get_league", return_value=make_league([team])):
            response = client.get("/team/1")
        html = response.data.decode()
        assert '<span class="injury-badge' not in html

    def test_player_points_displayed(self, client):
        roster = [make_player(lineupSlot="QB", total_points=250.3, avg_points=18.5)]
        team = make_team(team_id=1, roster=roster)
        with patch("app.get_league", return_value=make_league([team])):
            response = client.get("/team/1")
        html = response.data.decode()
        assert "250.3" in html
        assert "18.5" in html

    def test_high_scorer_highlighted(self, client):
        roster = [make_player(lineupSlot="QB", total_points=150.0)]
        team = make_team(team_id=1, roster=roster)
        with patch("app.get_league", return_value=make_league([team])):
            response = client.get("/team/1")
        assert b"pts-high" in response.data

    def test_low_scorer_not_highlighted(self, client):
        roster = [make_player(lineupSlot="QB", total_points=50.0)]
        team = make_team(team_id=1, roster=roster)
        with patch("app.get_league", return_value=make_league([team])):
            response = client.get("/team/1")
        html = response.data.decode()
        assert 'class="pts pts-high"' not in html

    def test_back_link_present(self, client):
        team = make_team(team_id=1, roster=[])
        with patch("app.get_league", return_value=make_league([team])):
            response = client.get("/team/1")
        html = response.data.decode()
        assert 'href="/"' in html
        assert "Back to standings" in html

    def test_empty_roster_no_sections(self, client):
        team = make_team(team_id=1, roster=[])
        with patch("app.get_league", return_value=make_league([team])):
            response = client.get("/team/1")
        html = response.data.decode()
        assert "Starters" not in html
        assert "Bench" not in html
        assert "Injured Reserve" not in html
