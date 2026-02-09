import os
from types import SimpleNamespace
from unittest.mock import patch

import mongomock
import pytest
from bson import ObjectId

# Set required env vars before importing app
os.environ.setdefault("SECRET_KEY", "test-secret")

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


def make_espn_league(teams):
    return SimpleNamespace(teams=teams)


@pytest.fixture
def mock_db():
    """Provide a mongomock database for testing."""
    client = mongomock.MongoClient()
    db = client["fantasy_football_test"]
    db.users.create_index("username", unique=True)
    db.leagues.create_index(
        [("user_id", 1), ("espn_league_id", 1), ("espn_year", 1)],
        unique=True,
    )
    return db


@pytest.fixture
def client(mock_db):
    app.config["TESTING"] = True
    app._db = mock_db
    with app.test_client() as client:
        yield client


@pytest.fixture
def logged_in_client(client, mock_db):
    """A test client that is already logged in."""
    from db import UserRepository
    repo = UserRepository(db=mock_db)
    repo.create_user("testuser", "testpass")
    client.post("/login", data={"username": "testuser", "password": "testpass"})
    return client


@pytest.fixture
def user_with_league(mock_db):
    """Create a user and a league, return (user_doc, league_doc)."""
    from db import UserRepository, LeagueRepository
    user_repo = UserRepository(db=mock_db)
    league_repo = LeagueRepository(db=mock_db)
    user = user_repo.create_user("testuser", "testpass")
    league = league_repo.create_league(
        user_id=user["_id"],
        name="Test League",
        espn_league_id=12345,
        espn_year=2024,
        espn_s2="fake_s2",
        espn_swid="{fake-swid}",
    )
    return user, league


@pytest.fixture
def logged_in_with_league(client, user_with_league):
    """A logged-in client with a league already created."""
    client.post("/login", data={"username": "testuser", "password": "testpass"})
    _, league = user_with_league
    return client, league


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


# --- Auth route tests ---


class TestAuthRoutes:
    def test_login_page_renders(self, client):
        response = client.get("/login")
        assert response.status_code == 200
        html = response.data.decode()
        assert "Login" in html
        assert "username" in html
        assert "password" in html

    def test_login_success(self, client, mock_db):
        from db import UserRepository
        repo = UserRepository(db=mock_db)
        repo.create_user("alice", "secret123")
        response = client.post("/login", data={"username": "alice", "password": "secret123"})
        assert response.status_code == 302

    def test_login_failure(self, client, mock_db):
        from db import UserRepository
        repo = UserRepository(db=mock_db)
        repo.create_user("alice", "secret123")
        response = client.post("/login", data={"username": "alice", "password": "wrong"})
        assert response.status_code == 200
        assert b"Invalid username or password" in response.data

    def test_login_nonexistent_user(self, client):
        response = client.post("/login", data={"username": "ghost", "password": "pass"})
        assert response.status_code == 200
        assert b"Invalid username or password" in response.data

    def test_logout(self, logged_in_client):
        response = logged_in_client.get("/logout")
        assert response.status_code == 302
        response = logged_in_client.get("/leagues")
        assert response.status_code == 302  # redirects to login

    def test_register_page_renders(self, client):
        response = client.get("/register")
        assert response.status_code == 200
        html = response.data.decode()
        assert "Register" in html or "Create Account" in html

    def test_register_success(self, client):
        response = client.post("/register", data={
            "username": "newuser",
            "password": "pass123",
            "confirm": "pass123",
        })
        assert response.status_code == 302

    def test_register_password_mismatch(self, client):
        response = client.post("/register", data={
            "username": "newuser",
            "password": "pass123",
            "confirm": "different",
        })
        assert response.status_code == 200
        assert b"Passwords do not match" in response.data

    def test_register_duplicate_username(self, client, mock_db):
        from db import UserRepository
        repo = UserRepository(db=mock_db)
        repo.create_user("taken", "pass")
        response = client.post("/register", data={
            "username": "taken",
            "password": "pass123",
            "confirm": "pass123",
        })
        assert response.status_code == 200
        assert b"Username already taken" in response.data

    def test_register_empty_username(self, client):
        response = client.post("/register", data={
            "username": "",
            "password": "pass123",
            "confirm": "pass123",
        })
        assert response.status_code == 200
        assert b"Username is required" in response.data

    def test_register_empty_password(self, client):
        response = client.post("/register", data={
            "username": "newuser",
            "password": "",
            "confirm": "",
        })
        assert response.status_code == 200
        assert b"Password is required" in response.data


# --- Protected route tests ---


class TestProtectedRoutes:
    def test_unauthenticated_home_redirects(self, client):
        response = client.get("/")
        assert response.status_code == 302
        assert "login" in response.headers["Location"]

    def test_unauthenticated_leagues_redirects(self, client):
        response = client.get("/leagues")
        assert response.status_code == 302
        assert "login" in response.headers["Location"]

    def test_unauthenticated_standings_redirects(self, client):
        response = client.get(f"/leagues/{ObjectId()}/standings")
        assert response.status_code == 302
        assert "login" in response.headers["Location"]

    def test_unauthenticated_roster_redirects(self, client):
        response = client.get(f"/leagues/{ObjectId()}/team/1")
        assert response.status_code == 302
        assert "login" in response.headers["Location"]

    def test_home_redirects_to_leagues(self, logged_in_client):
        response = logged_in_client.get("/")
        assert response.status_code == 302
        assert "leagues" in response.headers["Location"]


# --- League management tests ---


class TestLeagueManagement:
    def test_leagues_page_renders(self, logged_in_client):
        response = logged_in_client.get("/leagues")
        assert response.status_code == 200
        assert b"My Leagues" in response.data

    def test_leagues_page_shows_user_leagues(self, logged_in_with_league):
        client, league = logged_in_with_league
        response = client.get("/leagues")
        assert response.status_code == 200
        assert b"Test League" in response.data

    def test_add_league_page_renders(self, logged_in_client):
        response = logged_in_client.get("/leagues/add")
        assert response.status_code == 200
        assert b"Add League" in response.data

    def test_add_league_missing_fields(self, logged_in_client):
        response = logged_in_client.post("/leagues/add", data={
            "name": "",
            "espn_league_id": "",
            "espn_year": "",
            "espn_s2": "",
            "espn_swid": "",
        })
        assert response.status_code == 200
        assert b"All fields are required" in response.data

    def test_add_league_invalid_numbers(self, logged_in_client):
        response = logged_in_client.post("/leagues/add", data={
            "name": "Test",
            "espn_league_id": "abc",
            "espn_year": "xyz",
            "espn_s2": "s2",
            "espn_swid": "swid",
        })
        assert response.status_code == 200
        assert b"League ID and Year must be numbers" in response.data

    def test_add_league_success(self, logged_in_client):
        with patch("app.League"):
            response = logged_in_client.post("/leagues/add", data={
                "name": "New League",
                "espn_league_id": "99999",
                "espn_year": "2024",
                "espn_s2": "s2_value",
                "espn_swid": "{swid_value}",
            })
        assert response.status_code == 302
        # Verify it was created
        response = logged_in_client.get("/leagues")
        assert b"New League" in response.data

    def test_delete_league(self, logged_in_with_league):
        client, league = logged_in_with_league
        response = client.post(f"/leagues/{league['_id']}/delete")
        assert response.status_code == 302
        # Verify it was deleted
        response = client.get("/leagues")
        assert b"Test League" not in response.data

    def test_delete_other_users_league_forbidden(self, logged_in_client, mock_db):
        from db import UserRepository, LeagueRepository
        user_repo = UserRepository(db=mock_db)
        league_repo = LeagueRepository(db=mock_db)
        other_user = user_repo.create_user("other", "pass")
        other_league = league_repo.create_league(
            other_user["_id"], "Other's League", 999, 2024, "s2", "swid"
        )
        response = logged_in_client.post(f"/leagues/{other_league['_id']}/delete")
        assert response.status_code == 403


# --- League-scoped route tests (authenticated) ---


class TestStandingsRoute:
    def test_standings_page_renders(self, logged_in_with_league):
        client, league = logged_in_with_league
        teams = [
            make_team(team_id=1, team_name="First Place", standing=1, wins=10, losses=4),
            make_team(team_id=2, team_name="Second Place", standing=2, wins=8, losses=6),
        ]
        with patch("app.get_espn_league", return_value=make_espn_league(teams)):
            response = client.get(f"/leagues/{league['_id']}/standings")
        assert response.status_code == 200
        html = response.data.decode()
        assert "League Standings" in html
        assert "First Place" in html
        assert "Second Place" in html

    def test_teams_sorted_by_standing(self, logged_in_with_league):
        client, league = logged_in_with_league
        teams = [
            make_team(team_id=2, team_name="Second", standing=2),
            make_team(team_id=1, team_name="First", standing=1),
        ]
        with patch("app.get_espn_league", return_value=make_espn_league(teams)):
            response = client.get(f"/leagues/{league['_id']}/standings")
        html = response.data.decode()
        first_pos = html.index("First")
        second_pos = html.index("Second")
        assert first_pos < second_pos

    def test_team_record_displayed(self, logged_in_with_league):
        client, league = logged_in_with_league
        teams = [make_team(wins=10, losses=4, ties=0)]
        with patch("app.get_espn_league", return_value=make_espn_league(teams)):
            response = client.get(f"/leagues/{league['_id']}/standings")
        html = response.data.decode()
        assert "10-4" in html

    def test_team_record_with_ties(self, logged_in_with_league):
        client, league = logged_in_with_league
        teams = [make_team(wins=9, losses=4, ties=1)]
        with patch("app.get_espn_league", return_value=make_espn_league(teams)):
            response = client.get(f"/leagues/{league['_id']}/standings")
        html = response.data.decode()
        assert "9-4-1" in html

    def test_points_displayed(self, logged_in_with_league):
        client, league = logged_in_with_league
        teams = [make_team(points_for=1500.5, points_against=1300.2)]
        with patch("app.get_espn_league", return_value=make_espn_league(teams)):
            response = client.get(f"/leagues/{league['_id']}/standings")
        html = response.data.decode()
        assert "1500.5" in html
        assert "1300.2" in html

    def test_win_streak_displayed(self, logged_in_with_league):
        client, league = logged_in_with_league
        teams = [make_team(streak_type="WIN", streak_length=3)]
        with patch("app.get_espn_league", return_value=make_espn_league(teams)):
            response = client.get(f"/leagues/{league['_id']}/standings")
        assert b"W3" in response.data

    def test_loss_streak_displayed(self, logged_in_with_league):
        client, league = logged_in_with_league
        teams = [make_team(streak_type="LOSS", streak_length=2)]
        with patch("app.get_espn_league", return_value=make_espn_league(teams)):
            response = client.get(f"/leagues/{league['_id']}/standings")
        assert b"L2" in response.data

    def test_team_logo_rendered(self, logged_in_with_league):
        client, league = logged_in_with_league
        teams = [make_team(logo_url="https://example.com/logo.png")]
        with patch("app.get_espn_league", return_value=make_espn_league(teams)):
            response = client.get(f"/leagues/{league['_id']}/standings")
        assert b"https://example.com/logo.png" in response.data

    def test_team_link_points_to_league_scoped_roster(self, logged_in_with_league):
        client, league = logged_in_with_league
        teams = [make_team(team_id=5)]
        with patch("app.get_espn_league", return_value=make_espn_league(teams)):
            response = client.get(f"/leagues/{league['_id']}/standings")
        html = response.data.decode()
        assert f"/leagues/{league['_id']}/team/5" in html

    def test_rank_badges(self, logged_in_with_league):
        client, league = logged_in_with_league
        teams = [make_team(team_id=i, standing=i) for i in range(1, 5)]
        with patch("app.get_espn_league", return_value=make_espn_league(teams)):
            response = client.get(f"/leagues/{league['_id']}/standings")
        html = response.data.decode()
        assert "rank-1" in html
        assert "rank-2" in html
        assert "rank-3" in html
        assert "rank-default" in html

    def test_username_displayed_in_nav(self, logged_in_with_league):
        client, league = logged_in_with_league
        teams = [make_team()]
        with patch("app.get_espn_league", return_value=make_espn_league(teams)):
            response = client.get(f"/leagues/{league['_id']}/standings")
        html = response.data.decode()
        assert "testuser" in html

    def test_other_users_league_forbidden(self, logged_in_client, mock_db):
        from db import UserRepository, LeagueRepository
        user_repo = UserRepository(db=mock_db)
        league_repo = LeagueRepository(db=mock_db)
        other_user = user_repo.create_user("other", "pass")
        other_league = league_repo.create_league(
            other_user["_id"], "Other's League", 999, 2024, "s2", "swid"
        )
        response = logged_in_client.get(f"/leagues/{other_league['_id']}/standings")
        assert response.status_code == 403

    def test_nonexistent_league_returns_404(self, logged_in_client):
        response = logged_in_client.get(f"/leagues/{ObjectId()}/standings")
        assert response.status_code == 404


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

    def test_roster_page_renders(self, logged_in_with_league):
        client, league = logged_in_with_league
        team = self._team_with_roster()
        with patch("app.get_espn_league", return_value=make_espn_league([team])):
            response = client.get(f"/leagues/{league['_id']}/team/1")
        assert response.status_code == 200
        html = response.data.decode()
        assert team.team_name in html

    def test_invalid_team_returns_404(self, logged_in_with_league):
        client, league = logged_in_with_league
        team = make_team(team_id=1)
        with patch("app.get_espn_league", return_value=make_espn_league([team])):
            response = client.get(f"/leagues/{league['_id']}/team/999")
        assert response.status_code == 404

    def test_starters_section_displayed(self, logged_in_with_league):
        client, league = logged_in_with_league
        team = self._team_with_roster()
        with patch("app.get_espn_league", return_value=make_espn_league([team])):
            response = client.get(f"/leagues/{league['_id']}/team/1")
        html = response.data.decode()
        assert "Starters" in html
        assert "Patrick Mahomes" in html
        assert "Travis Kelce" in html

    def test_bench_section_displayed(self, logged_in_with_league):
        client, league = logged_in_with_league
        team = self._team_with_roster()
        with patch("app.get_espn_league", return_value=make_espn_league([team])):
            response = client.get(f"/leagues/{league['_id']}/team/1")
        html = response.data.decode()
        assert "Bench" in html
        assert "Bench Player" in html

    def test_ir_section_displayed(self, logged_in_with_league):
        client, league = logged_in_with_league
        team = self._team_with_roster()
        with patch("app.get_espn_league", return_value=make_espn_league([team])):
            response = client.get(f"/leagues/{league['_id']}/team/1")
        html = response.data.decode()
        assert "Injured Reserve" in html
        assert "IR Player" in html

    def test_starters_sorted_by_position(self, logged_in_with_league):
        client, league = logged_in_with_league
        team = self._team_with_roster()
        with patch("app.get_espn_league", return_value=make_espn_league([team])):
            response = client.get(f"/leagues/{league['_id']}/team/1")
        html = response.data.decode()
        qb_pos = html.index("Patrick Mahomes")
        rb_pos = html.index("Derrick Henry")
        wr_pos = html.index("Ja&#39;Marr Chase")
        te_pos = html.index("Travis Kelce")
        flex_pos = html.index("Flex Guy")
        k_pos = html.index("Tyler Bass")
        dst_pos = html.index("Cowboys D")
        assert qb_pos < rb_pos < wr_pos < te_pos < flex_pos < k_pos < dst_pos

    def test_op_slot_displays_as_qb(self, logged_in_with_league):
        client, league = logged_in_with_league
        roster = [
            make_player(name="QB One", lineupSlot="QB"),
            make_player(name="QB Two", lineupSlot="OP", position="QB"),
        ]
        team = make_team(team_id=1, roster=roster)
        with patch("app.get_espn_league", return_value=make_espn_league([team])):
            response = client.get(f"/leagues/{league['_id']}/team/1")
        html = response.data.decode()
        assert "QB Two" in html
        assert ">OP<" not in html

    def test_rb_wr_te_slot_displays_as_flex(self, logged_in_with_league):
        client, league = logged_in_with_league
        roster = [make_player(name="Flex Man", lineupSlot="RB/WR/TE", position="WR")]
        team = make_team(team_id=1, roster=roster)
        with patch("app.get_espn_league", return_value=make_espn_league([team])):
            response = client.get(f"/leagues/{league['_id']}/team/1")
        html = response.data.decode()
        assert "Flex Man" in html
        assert ">FLEX<" in html
        assert ">RB/WR/TE<" not in html

    def test_injury_status_shown(self, logged_in_with_league):
        client, league = logged_in_with_league
        roster = [make_player(name="Hurt Guy", lineupSlot="RB", injuryStatus="QUESTIONABLE")]
        team = make_team(team_id=1, roster=roster)
        with patch("app.get_espn_league", return_value=make_espn_league([team])):
            response = client.get(f"/leagues/{league['_id']}/team/1")
        html = response.data.decode()
        assert "QUESTIONABLE" in html
        assert "injury-QUESTIONABLE" in html

    def test_active_injury_status_hidden(self, logged_in_with_league):
        client, league = logged_in_with_league
        roster = [make_player(name="Healthy Guy", lineupSlot="RB", injuryStatus="ACTIVE")]
        team = make_team(team_id=1, roster=roster)
        with patch("app.get_espn_league", return_value=make_espn_league([team])):
            response = client.get(f"/leagues/{league['_id']}/team/1")
        html = response.data.decode()
        assert '<span class="injury-badge' not in html

    def test_player_points_displayed(self, logged_in_with_league):
        client, league = logged_in_with_league
        roster = [make_player(lineupSlot="QB", total_points=250.3, avg_points=18.5)]
        team = make_team(team_id=1, roster=roster)
        with patch("app.get_espn_league", return_value=make_espn_league([team])):
            response = client.get(f"/leagues/{league['_id']}/team/1")
        html = response.data.decode()
        assert "250.3" in html
        assert "18.5" in html

    def test_high_scorer_highlighted(self, logged_in_with_league):
        client, league = logged_in_with_league
        roster = [make_player(lineupSlot="QB", total_points=150.0)]
        team = make_team(team_id=1, roster=roster)
        with patch("app.get_espn_league", return_value=make_espn_league([team])):
            response = client.get(f"/leagues/{league['_id']}/team/1")
        assert b"pts-high" in response.data

    def test_low_scorer_not_highlighted(self, logged_in_with_league):
        client, league = logged_in_with_league
        roster = [make_player(lineupSlot="QB", total_points=50.0)]
        team = make_team(team_id=1, roster=roster)
        with patch("app.get_espn_league", return_value=make_espn_league([team])):
            response = client.get(f"/leagues/{league['_id']}/team/1")
        html = response.data.decode()
        assert 'class="pts pts-high"' not in html

    def test_back_link_to_standings(self, logged_in_with_league):
        client, league = logged_in_with_league
        team = make_team(team_id=1, roster=[])
        with patch("app.get_espn_league", return_value=make_espn_league([team])):
            response = client.get(f"/leagues/{league['_id']}/team/1")
        html = response.data.decode()
        assert f"/leagues/{league['_id']}/standings" in html
        assert "Back to standings" in html

    def test_empty_roster_no_sections(self, logged_in_with_league):
        client, league = logged_in_with_league
        team = make_team(team_id=1, roster=[])
        with patch("app.get_espn_league", return_value=make_espn_league([team])):
            response = client.get(f"/leagues/{league['_id']}/team/1")
        html = response.data.decode()
        assert "Starters" not in html
        assert "Bench" not in html
        assert "Injured Reserve" not in html

    def test_other_users_league_forbidden(self, logged_in_client, mock_db):
        from db import UserRepository, LeagueRepository
        user_repo = UserRepository(db=mock_db)
        league_repo = LeagueRepository(db=mock_db)
        other_user = user_repo.create_user("other", "pass")
        other_league = league_repo.create_league(
            other_user["_id"], "Other's League", 999, 2024, "s2", "swid"
        )
        response = logged_in_client.get(f"/leagues/{other_league['_id']}/team/1")
        assert response.status_code == 403
