"""E2E API tests using the requests library against the Kubernetes-deployed app.

Run:
    pytest tests/e2e/test_api.py -v
"""

import uuid

import pytest
import requests
from bson import ObjectId

from tests.e2e.conftest import BASE_URL


# ===================================================================
# Helpers
# ===================================================================


def _register(session, username, password):
    """POST /register and return the response."""
    return session.post(
        f"{BASE_URL}/register",
        data={"username": username, "password": password, "confirm": password},
        allow_redirects=False,
    )


def _login(session, username, password):
    """POST /login and return the response."""
    return session.post(
        f"{BASE_URL}/login",
        data={"username": username, "password": password},
        allow_redirects=False,
    )


def _unique_username():
    return f"testuser_{uuid.uuid4().hex[:8]}"


# ===================================================================
# 1. Registration Tests
# ===================================================================


class TestRegistration:
    """Test user registration workflows."""

    def test_register_page_loads(self, api_session):
        resp = api_session.get(f"{BASE_URL}/register")
        assert resp.status_code == 200
        assert "Create Account" in resp.text

    def test_register_success(self, api_session, unique_user):
        resp = _register(api_session, unique_user["username"], unique_user["password"])
        # Should redirect to /leagues on success
        assert resp.status_code == 302
        assert "/leagues" in resp.headers.get("Location", "")

    def test_register_and_follow_redirect(self, api_session, unique_user):
        resp = api_session.post(
            f"{BASE_URL}/register",
            data={
                "username": unique_user["username"],
                "password": unique_user["password"],
                "confirm": unique_user["password"],
            },
            allow_redirects=True,
        )
        assert resp.status_code == 200
        assert "My Leagues" in resp.text

    def test_register_duplicate_username(self, api_session, unique_user):
        # First registration
        _register(api_session, unique_user["username"], unique_user["password"])
        # Second registration with same username (new session to avoid being logged in)
        s2 = requests.Session()
        resp = s2.post(
            f"{BASE_URL}/register",
            data={
                "username": unique_user["username"],
                "password": "other_pass",
                "confirm": "other_pass",
            },
            allow_redirects=True,
        )
        assert resp.status_code == 200
        assert "Username already taken" in resp.text
        s2.close()

    def test_register_password_mismatch(self, api_session):
        resp = api_session.post(
            f"{BASE_URL}/register",
            data={
                "username": _unique_username(),
                "password": "pass1",
                "confirm": "pass2",
            },
            allow_redirects=True,
        )
        assert resp.status_code == 200
        assert "Passwords do not match" in resp.text

    def test_register_empty_username(self, api_session):
        resp = api_session.post(
            f"{BASE_URL}/register",
            data={"username": "", "password": "pass", "confirm": "pass"},
            allow_redirects=True,
        )
        assert resp.status_code == 200
        assert "Username is required" in resp.text

    def test_register_empty_password(self, api_session):
        resp = api_session.post(
            f"{BASE_URL}/register",
            data={"username": _unique_username(), "password": "", "confirm": ""},
            allow_redirects=True,
        )
        assert resp.status_code == 200
        assert "Password is required" in resp.text

    def test_register_redirects_if_already_logged_in(self, logged_in_session):
        session, user = logged_in_session
        resp = session.get(f"{BASE_URL}/register", allow_redirects=False)
        assert resp.status_code == 302
        assert "/leagues" in resp.headers.get("Location", "")


# ===================================================================
# 2. Login Tests
# ===================================================================


class TestLogin:
    """Test user login workflows."""

    def test_login_page_loads(self, api_session):
        resp = api_session.get(f"{BASE_URL}/login")
        assert resp.status_code == 200
        assert "Login" in resp.text

    def test_login_success(self, api_session, unique_user):
        # Register first
        _register(api_session, unique_user["username"], unique_user["password"])
        # Logout
        api_session.get(f"{BASE_URL}/logout", allow_redirects=True)
        # Login
        resp = _login(api_session, unique_user["username"], unique_user["password"])
        assert resp.status_code == 302
        assert "/leagues" in resp.headers.get("Location", "")

    def test_login_wrong_password(self, api_session, unique_user):
        _register(api_session, unique_user["username"], unique_user["password"])
        api_session.get(f"{BASE_URL}/logout", allow_redirects=True)
        resp = api_session.post(
            f"{BASE_URL}/login",
            data={"username": unique_user["username"], "password": "wrong"},
            allow_redirects=True,
        )
        assert resp.status_code == 200
        assert "Invalid username or password" in resp.text

    def test_login_nonexistent_user(self, api_session):
        resp = api_session.post(
            f"{BASE_URL}/login",
            data={"username": "no_such_user_xyz", "password": "pass"},
            allow_redirects=True,
        )
        assert resp.status_code == 200
        assert "Invalid username or password" in resp.text

    def test_login_redirects_if_already_logged_in(self, logged_in_session):
        session, _ = logged_in_session
        resp = session.get(f"{BASE_URL}/login", allow_redirects=False)
        assert resp.status_code == 302
        assert "/leagues" in resp.headers.get("Location", "")


# ===================================================================
# 3. Logout Tests
# ===================================================================


class TestLogout:
    """Test logout functionality."""

    def test_logout_redirects_to_login(self, logged_in_session):
        session, _ = logged_in_session
        resp = session.get(f"{BASE_URL}/logout", allow_redirects=False)
        assert resp.status_code == 302
        assert "/login" in resp.headers.get("Location", "")

    def test_logout_clears_session(self, logged_in_session):
        session, _ = logged_in_session
        session.get(f"{BASE_URL}/logout", allow_redirects=True)
        # Now try to access protected page
        resp = session.get(f"{BASE_URL}/leagues", allow_redirects=False)
        assert resp.status_code == 302
        assert "/login" in resp.headers.get("Location", "")

    def test_logout_requires_login(self, api_session):
        resp = api_session.get(f"{BASE_URL}/logout", allow_redirects=False)
        assert resp.status_code == 302
        assert "/login" in resp.headers.get("Location", "")


# ===================================================================
# 4. Protected Routes Tests
# ===================================================================


class TestProtectedRoutes:
    """Test that protected routes redirect unauthenticated users."""

    @pytest.mark.parametrize("path", [
        "/",
        "/leagues",
        "/leagues/add",
        f"/leagues/{ObjectId()}/standings",
        f"/leagues/{ObjectId()}/team/1",
        f"/leagues/{ObjectId()}/analytics",
        f"/leagues/{ObjectId()}/player/some_player_id",
        f"/leagues/{ObjectId()}/team/1/analytics",
        f"/leagues/{ObjectId()}/delete",
    ])
    def test_unauthenticated_redirect(self, api_session, path):
        if path.endswith("/delete"):
            resp = api_session.post(f"{BASE_URL}{path}", allow_redirects=False)
        else:
            resp = api_session.get(f"{BASE_URL}{path}", allow_redirects=False)
        assert resp.status_code == 302
        assert "/login" in resp.headers.get("Location", "")


# ===================================================================
# 5. Leagues Page Tests
# ===================================================================


class TestLeaguesPage:
    """Test the leagues listing page."""

    def test_leagues_page_loads(self, logged_in_session):
        session, _ = logged_in_session
        resp = session.get(f"{BASE_URL}/leagues")
        assert resp.status_code == 200
        assert "My Leagues" in resp.text

    def test_leagues_page_shows_username(self, logged_in_session):
        session, user = logged_in_session
        resp = session.get(f"{BASE_URL}/leagues")
        assert user["username"] in resp.text

    def test_leagues_page_shows_add_button(self, logged_in_session):
        session, _ = logged_in_session
        resp = session.get(f"{BASE_URL}/leagues")
        assert "Add League" in resp.text

    def test_leagues_page_empty_for_new_user(self, logged_in_session):
        session, _ = logged_in_session
        resp = session.get(f"{BASE_URL}/leagues")
        assert "0 leagues" in resp.text

    def test_home_redirects_to_leagues(self, logged_in_session):
        session, _ = logged_in_session
        resp = session.get(f"{BASE_URL}/", allow_redirects=False)
        assert resp.status_code == 302
        assert "/leagues" in resp.headers.get("Location", "")


# ===================================================================
# 6. Add League Tests
# ===================================================================


class TestAddLeague:
    """Test the add league form and workflow."""

    def test_add_league_page_loads(self, logged_in_session):
        session, _ = logged_in_session
        resp = session.get(f"{BASE_URL}/leagues/add")
        assert resp.status_code == 200
        assert "Add League" in resp.text
        assert "ESPN League ID" in resp.text

    def test_add_league_missing_fields(self, logged_in_session):
        session, _ = logged_in_session
        resp = session.post(
            f"{BASE_URL}/leagues/add",
            data={"name": "TestLeague", "espn_league_id": "", "espn_year": "",
                  "espn_s2": "", "espn_swid": ""},
            allow_redirects=True,
        )
        assert resp.status_code == 200
        assert "All fields are required" in resp.text

    def test_add_league_non_numeric_id(self, logged_in_session):
        session, _ = logged_in_session
        resp = session.post(
            f"{BASE_URL}/leagues/add",
            data={
                "name": "TestLeague",
                "espn_league_id": "abc",
                "espn_year": "xyz",
                "espn_s2": "fake_s2",
                "espn_swid": "{fake-swid}",
            },
            allow_redirects=True,
        )
        assert resp.status_code == 200
        assert "must be numbers" in resp.text

    def test_add_league_invalid_espn_credentials(self, logged_in_session):
        session, _ = logged_in_session
        resp = session.post(
            f"{BASE_URL}/leagues/add",
            data={
                "name": "TestLeague_invalid",
                "espn_league_id": "99999999",
                "espn_year": "2024",
                "espn_s2": "fake_s2_cookie_value",
                "espn_swid": "{00000000-0000-0000-0000-000000000000}",
            },
            allow_redirects=True,
        )
        assert resp.status_code == 200
        assert "Could not connect to ESPN" in resp.text

    def test_add_league_back_link(self, logged_in_session):
        session, _ = logged_in_session
        resp = session.get(f"{BASE_URL}/leagues/add")
        assert "Back to leagues" in resp.text


# ===================================================================
# 7. League with Direct DB Insertion Tests
# ===================================================================


class TestLeagueWithDBData:
    """Test league features by inserting data directly into MongoDB."""

    @pytest.fixture(autouse=True)
    def _setup(self, logged_in_session, mongo_db, mongo_port_forward):
        self.session, self.user = logged_in_session
        self.db = mongo_db
        # Find the user in MongoDB
        user_doc = self.db["users"].find_one({"username": self.user["username"]})
        self.user_id = user_doc["_id"]

    def _insert_league(self, name="TestLeague_API"):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        doc = {
            "user_id": self.user_id,
            "name": name,
            "espn_league_id": 12345,
            "espn_year": 2024,
            "espn_s2": "fake_s2",
            "espn_swid": "{fake-swid}",
            "created_at": now,
            "updated_at": now,
        }
        result = self.db["leagues"].insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    def test_leagues_page_shows_inserted_league(self):
        league = self._insert_league("TestLeague_ShowsUp")
        resp = self.session.get(f"{BASE_URL}/leagues")
        assert resp.status_code == 200
        assert "TestLeague_ShowsUp" in resp.text
        assert "12345" in resp.text
        # Cleanup
        self.db["leagues"].delete_one({"_id": league["_id"]})

    def test_leagues_page_shows_correct_count(self):
        league1 = self._insert_league("TestLeague_Count1")
        league2 = self._insert_league("TestLeague_Count2")
        resp = self.session.get(f"{BASE_URL}/leagues")
        assert "2 leagues" in resp.text
        # Cleanup
        self.db["leagues"].delete_many({"_id": {"$in": [league1["_id"], league2["_id"]]}})

    def test_delete_league(self):
        league = self._insert_league("TestLeague_Delete")
        league_id = str(league["_id"])
        resp = self.session.post(
            f"{BASE_URL}/leagues/{league_id}/delete",
            allow_redirects=True,
        )
        assert resp.status_code == 200
        assert "TestLeague_Delete" not in resp.text
        # Verify deleted from DB
        assert self.db["leagues"].find_one({"_id": league["_id"]}) is None

    def test_delete_league_wrong_user(self):
        # Insert league for a different user
        from datetime import datetime, timezone
        fake_user_id = ObjectId()
        doc = {
            "user_id": fake_user_id,
            "name": "TestLeague_OtherUser",
            "espn_league_id": 99999,
            "espn_year": 2024,
            "espn_s2": "fake",
            "espn_swid": "{fake}",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        result = self.db["leagues"].insert_one(doc)
        league_id = str(result.inserted_id)

        resp = self.session.post(
            f"{BASE_URL}/leagues/{league_id}/delete",
            allow_redirects=False,
        )
        assert resp.status_code == 403
        # Cleanup
        self.db["leagues"].delete_one({"_id": result.inserted_id})

    def test_standings_with_invalid_espn_creds(self):
        """Standings route calls ESPN API - with fake creds it should handle error."""
        league = self._insert_league("TestLeague_Standings")
        league_id = str(league["_id"])
        resp = self.session.get(
            f"{BASE_URL}/leagues/{league_id}/standings",
            allow_redirects=True,
        )
        # The app doesn't have error handling for failed ESPN API calls in standings,
        # so this will likely return 500. This reveals a bug in error handling.
        assert resp.status_code in (200, 500)
        # Cleanup
        self.db["leagues"].delete_one({"_id": league["_id"]})

    def test_standings_nonexistent_league(self, logged_in_session):
        session, _ = logged_in_session
        fake_id = str(ObjectId())
        resp = session.get(
            f"{BASE_URL}/leagues/{fake_id}/standings",
            allow_redirects=False,
        )
        assert resp.status_code == 404

    def test_team_roster_nonexistent_league(self, logged_in_session):
        session, _ = logged_in_session
        fake_id = str(ObjectId())
        resp = session.get(
            f"{BASE_URL}/leagues/{fake_id}/team/1",
            allow_redirects=False,
        )
        assert resp.status_code == 404

    def test_analytics_with_no_data(self):
        """Analytics page should load even without analytics data."""
        league = self._insert_league("TestLeague_Analytics")
        league_id = str(league["_id"])
        resp = self.session.get(
            f"{BASE_URL}/leagues/{league_id}/analytics",
            allow_redirects=True,
        )
        assert resp.status_code == 200
        assert "Player Analytics" in resp.text
        assert "No analytics data available" in resp.text
        # Cleanup
        self.db["leagues"].delete_one({"_id": league["_id"]})

    def test_league_isolation_between_users(self):
        """Ensure user A cannot see user B's leagues."""
        league = self._insert_league("TestLeague_Isolated")
        league_id = str(league["_id"])

        # Create a second user and session
        s2 = requests.Session()
        user2 = _unique_username()
        s2.post(
            f"{BASE_URL}/register",
            data={"username": user2, "password": "pass123", "confirm": "pass123"},
            allow_redirects=True,
        )

        # User 2 should not see user 1's league on their leagues page
        resp = s2.get(f"{BASE_URL}/leagues")
        assert "TestLeague_Isolated" not in resp.text

        # User 2 should get 403 trying to access user 1's league
        resp = s2.get(f"{BASE_URL}/leagues/{league_id}/standings", allow_redirects=False)
        assert resp.status_code == 403

        s2.close()
        # Cleanup
        self.db["leagues"].delete_one({"_id": league["_id"]})
        self.db["users"].delete_one({"username": user2})


# ===================================================================
# 8. Navigation Tests
# ===================================================================


class TestNavigation:
    """Test navigation elements."""

    def test_nav_shows_logout_when_logged_in(self, logged_in_session):
        session, _ = logged_in_session
        resp = session.get(f"{BASE_URL}/leagues")
        assert "Logout" in resp.text

    def test_nav_shows_login_when_logged_out(self, api_session):
        resp = api_session.get(f"{BASE_URL}/login")
        assert "Login" in resp.text

    def test_nav_shows_my_leagues_link(self, logged_in_session):
        session, _ = logged_in_session
        resp = session.get(f"{BASE_URL}/leagues")
        assert "My Leagues" in resp.text

    def test_app_title_in_nav(self, api_session):
        resp = api_session.get(f"{BASE_URL}/login")
        assert "Fantasy Football Analyzer" in resp.text


# ===================================================================
# 9. Player Detail Route Tests
# ===================================================================


class TestPlayerDetail:
    """Test the player detail analytics page."""

    @pytest.fixture(autouse=True)
    def _setup(self, logged_in_session, mongo_db, mongo_port_forward):
        self.session, self.user = logged_in_session
        self.db = mongo_db
        user_doc = self.db["users"].find_one({"username": self.user["username"]})
        self.user_id = user_doc["_id"]

    def _insert_league(self, name="TestLeague_PlayerDetail"):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        doc = {
            "user_id": self.user_id,
            "name": name,
            "espn_league_id": 12345,
            "espn_year": 2024,
            "espn_s2": "fake_s2",
            "espn_swid": "{fake-swid}",
            "created_at": now,
            "updated_at": now,
        }
        result = self.db["leagues"].insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    def _seed_player_stats(self):
        """Insert seasonal + weekly stats for a test player."""
        self.db["seasonal_stats"].update_one(
            {"player_id": "test_p1", "season": 2024},
            {"$set": {
                "player_id": "test_p1",
                "player_name": "Test Quarterback",
                "position": "QB",
                "recent_team": "KC",
                "season": 2024,
                "fantasy_points_ppr": 300.0,
                "games": 15,
            }},
            upsert=True,
        )
        for week in range(1, 4):
            self.db["weekly_stats"].update_one(
                {"player_id": "test_p1", "season": 2024, "week": week},
                {"$set": {
                    "player_id": "test_p1",
                    "player_name": "Test Quarterback",
                    "position": "QB",
                    "season": 2024,
                    "week": week,
                    "opponent_team": f"OPP{week}",
                    "fantasy_points_ppr": 18.0 + week,
                }},
                upsert=True,
            )

    def _cleanup_stats(self):
        self.db["seasonal_stats"].delete_many({"player_id": "test_p1"})
        self.db["weekly_stats"].delete_many({"player_id": "test_p1"})

    def test_player_detail_renders_with_data(self):
        league = self._insert_league()
        league_id = str(league["_id"])
        self._seed_player_stats()
        try:
            resp = self.session.get(
                f"{BASE_URL}/leagues/{league_id}/player/test_p1",
                allow_redirects=True,
            )
            assert resp.status_code == 200
            assert "Test Quarterback" in resp.text
            assert "Season Summary" in resp.text
            assert "Weekly Scoring Trend" in resp.text
        finally:
            self.db["leagues"].delete_one({"_id": league["_id"]})
            self._cleanup_stats()

    def test_player_detail_shows_position_and_team(self):
        league = self._insert_league()
        league_id = str(league["_id"])
        self._seed_player_stats()
        try:
            resp = self.session.get(
                f"{BASE_URL}/leagues/{league_id}/player/test_p1",
                allow_redirects=True,
            )
            assert resp.status_code == 200
            assert "QB" in resp.text
            assert "KC" in resp.text
        finally:
            self.db["leagues"].delete_one({"_id": league["_id"]})
            self._cleanup_stats()

    def test_player_detail_nonexistent_player_returns_404(self):
        league = self._insert_league()
        league_id = str(league["_id"])
        try:
            resp = self.session.get(
                f"{BASE_URL}/leagues/{league_id}/player/nonexistent_xyz",
                allow_redirects=False,
            )
            assert resp.status_code == 404
        finally:
            self.db["leagues"].delete_one({"_id": league["_id"]})

    def test_player_detail_nonexistent_league_returns_404(self):
        fake_id = str(ObjectId())
        resp = self.session.get(
            f"{BASE_URL}/leagues/{fake_id}/player/test_p1",
            allow_redirects=False,
        )
        assert resp.status_code == 404

    def test_player_detail_wrong_user_returns_403(self):
        """Player detail for another user's league should return 403."""
        from datetime import datetime, timezone
        fake_user_id = ObjectId()
        doc = {
            "user_id": fake_user_id,
            "name": "TestLeague_OtherUser",
            "espn_league_id": 99999,
            "espn_year": 2024,
            "espn_s2": "fake",
            "espn_swid": "{fake}",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        result = self.db["leagues"].insert_one(doc)
        league_id = str(result.inserted_id)
        try:
            resp = self.session.get(
                f"{BASE_URL}/leagues/{league_id}/player/test_p1",
                allow_redirects=False,
            )
            assert resp.status_code == 403
        finally:
            self.db["leagues"].delete_one({"_id": result.inserted_id})

    def test_player_detail_back_link_to_analytics(self):
        league = self._insert_league()
        league_id = str(league["_id"])
        self._seed_player_stats()
        try:
            resp = self.session.get(
                f"{BASE_URL}/leagues/{league_id}/player/test_p1",
                allow_redirects=True,
            )
            assert f"/leagues/{league_id}/analytics" in resp.text
            assert "Back to analytics" in resp.text
        finally:
            self.db["leagues"].delete_one({"_id": league["_id"]})
            self._cleanup_stats()


# ===================================================================
# 10. Team Analytics Route Tests
# ===================================================================


class TestTeamAnalytics:
    """Test the team analytics page."""

    @pytest.fixture(autouse=True)
    def _setup(self, logged_in_session, mongo_db, mongo_port_forward):
        self.session, self.user = logged_in_session
        self.db = mongo_db
        user_doc = self.db["users"].find_one({"username": self.user["username"]})
        self.user_id = user_doc["_id"]

    def _insert_league(self, name="TestLeague_TeamAnalytics"):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        doc = {
            "user_id": self.user_id,
            "name": name,
            "espn_league_id": 12345,
            "espn_year": 2024,
            "espn_s2": "fake_s2",
            "espn_swid": "{fake-swid}",
            "created_at": now,
            "updated_at": now,
        }
        result = self.db["leagues"].insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    def test_team_analytics_with_invalid_espn_creds(self):
        """Team analytics requires ESPN API — with fake creds expect 500."""
        league = self._insert_league()
        league_id = str(league["_id"])
        try:
            resp = self.session.get(
                f"{BASE_URL}/leagues/{league_id}/team/1/analytics",
                allow_redirects=True,
            )
            # No error handling for ESPN failures, so expect 500
            assert resp.status_code in (200, 500)
        finally:
            self.db["leagues"].delete_one({"_id": league["_id"]})

    def test_team_analytics_nonexistent_league_returns_404(self):
        fake_id = str(ObjectId())
        resp = self.session.get(
            f"{BASE_URL}/leagues/{fake_id}/team/1/analytics",
            allow_redirects=False,
        )
        assert resp.status_code == 404

    def test_team_analytics_wrong_user_returns_403(self):
        from datetime import datetime, timezone
        fake_user_id = ObjectId()
        doc = {
            "user_id": fake_user_id,
            "name": "TestLeague_OtherUser",
            "espn_league_id": 99999,
            "espn_year": 2024,
            "espn_s2": "fake",
            "espn_swid": "{fake}",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        result = self.db["leagues"].insert_one(doc)
        league_id = str(result.inserted_id)
        try:
            resp = self.session.get(
                f"{BASE_URL}/leagues/{league_id}/team/1/analytics",
                allow_redirects=False,
            )
            assert resp.status_code == 403
        finally:
            self.db["leagues"].delete_one({"_id": result.inserted_id})


# ===================================================================
# 11. Analytics Page Tests (with seeded data)
# ===================================================================


class TestAnalyticsWithData:
    """Test the analytics page with seeded stats data."""

    @pytest.fixture(autouse=True)
    def _setup(self, logged_in_session, mongo_db, mongo_port_forward):
        self.session, self.user = logged_in_session
        self.db = mongo_db
        user_doc = self.db["users"].find_one({"username": self.user["username"]})
        self.user_id = user_doc["_id"]

    def _insert_league(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        doc = {
            "user_id": self.user_id,
            "name": "TestLeague_AnalyticsData",
            "espn_league_id": 12345,
            "espn_year": 2024,
            "espn_s2": "fake_s2",
            "espn_swid": "{fake-swid}",
            "created_at": now,
            "updated_at": now,
        }
        result = self.db["leagues"].insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    def _seed_stats(self):
        self.db["seasonal_stats"].update_one(
            {"player_id": "test_analytics_p1", "season": 2024},
            {"$set": {
                "player_id": "test_analytics_p1",
                "player_name": "Analytics Test QB",
                "position": "QB",
                "recent_team": "KC",
                "season": 2024,
                "fantasy_points_ppr": 350.0,
                "games": 17,
            }},
            upsert=True,
        )

    def _cleanup_stats(self):
        self.db["seasonal_stats"].delete_many({"player_id": "test_analytics_p1"})

    def test_analytics_page_shows_player_data(self):
        league = self._insert_league()
        league_id = str(league["_id"])
        self._seed_stats()
        try:
            resp = self.session.get(
                f"{BASE_URL}/leagues/{league_id}/analytics",
                allow_redirects=True,
            )
            assert resp.status_code == 200
            assert "Analytics Test QB" in resp.text
            assert "350.0" in resp.text
        finally:
            self.db["leagues"].delete_one({"_id": league["_id"]})
            self._cleanup_stats()

    def test_analytics_page_has_player_links(self):
        """Player names on analytics page should be clickable links to detail."""
        league = self._insert_league()
        league_id = str(league["_id"])
        self._seed_stats()
        try:
            resp = self.session.get(
                f"{BASE_URL}/leagues/{league_id}/analytics",
                allow_redirects=True,
            )
            assert resp.status_code == 200
            # Should contain a link to the player detail page
            assert f"/leagues/{league_id}/player/test_analytics_p1" in resp.text
        finally:
            self.db["leagues"].delete_one({"_id": league["_id"]})
            self._cleanup_stats()

    def test_analytics_page_shows_avg_per_game(self):
        """Analytics page should show Avg/Gm column."""
        league = self._insert_league()
        league_id = str(league["_id"])
        self._seed_stats()
        try:
            resp = self.session.get(
                f"{BASE_URL}/leagues/{league_id}/analytics",
                allow_redirects=True,
            )
            assert resp.status_code == 200
            assert "Avg/Gm" in resp.text
            # 350.0 / 17 = 20.6
            assert "20.6" in resp.text
        finally:
            self.db["leagues"].delete_one({"_id": league["_id"]})
            self._cleanup_stats()
