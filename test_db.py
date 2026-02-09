import pytest
import mongomock
from bson import ObjectId

from db import UserRepository, LeagueRepository


@pytest.fixture
def db():
    client = mongomock.MongoClient()
    database = client["fantasy_football_test"]
    # Create indexes to match production
    database.users.create_index("username", unique=True)
    database.leagues.create_index(
        [("user_id", 1), ("espn_league_id", 1), ("espn_year", 1)],
        unique=True,
    )
    yield database
    client.close()


@pytest.fixture
def user_repo(db):
    return UserRepository(db=db)


@pytest.fixture
def league_repo(db):
    return LeagueRepository(db=db)


# --- UserRepository tests ---


class TestUserRepository:
    def test_create_user(self, user_repo):
        user = user_repo.create_user("alice", "password123")
        assert user["username"] == "alice"
        assert "_id" in user
        assert "password_hash" in user
        assert user["password_hash"] != "password123"

    def test_find_by_username(self, user_repo):
        user_repo.create_user("bob", "secret")
        found = user_repo.find_by_username("bob")
        assert found is not None
        assert found["username"] == "bob"

    def test_find_by_username_not_found(self, user_repo):
        assert user_repo.find_by_username("nonexistent") is None

    def test_find_by_id(self, user_repo):
        user = user_repo.create_user("charlie", "pass")
        found = user_repo.find_by_id(user["_id"])
        assert found is not None
        assert found["username"] == "charlie"

    def test_find_by_id_string(self, user_repo):
        user = user_repo.create_user("dave", "pass")
        found = user_repo.find_by_id(str(user["_id"]))
        assert found is not None
        assert found["username"] == "dave"

    def test_find_by_id_not_found(self, user_repo):
        assert user_repo.find_by_id(ObjectId()) is None

    def test_duplicate_username_raises(self, user_repo):
        user_repo.create_user("alice", "pass1")
        with pytest.raises(Exception):
            user_repo.create_user("alice", "pass2")

    def test_verify_password_correct(self, user_repo):
        user_repo.create_user("eve", "correct_password")
        result = user_repo.verify_password("eve", "correct_password")
        assert result is not None
        assert result["username"] == "eve"

    def test_verify_password_wrong(self, user_repo):
        user_repo.create_user("eve", "correct_password")
        result = user_repo.verify_password("eve", "wrong_password")
        assert result is None

    def test_verify_password_no_user(self, user_repo):
        result = user_repo.verify_password("ghost", "password")
        assert result is None

    def test_created_at_set(self, user_repo):
        user = user_repo.create_user("frank", "pass")
        assert user["created_at"] is not None
        assert user["updated_at"] is not None


# --- LeagueRepository tests ---


class TestLeagueRepository:
    def _create_user(self, user_repo, username="testuser"):
        return user_repo.create_user(username, "password")

    def test_create_league(self, league_repo, user_repo):
        user = self._create_user(user_repo)
        league = league_repo.create_league(
            user_id=user["_id"],
            name="My League",
            espn_league_id=12345,
            espn_year=2024,
            espn_s2="s2_cookie",
            espn_swid="{swid}",
        )
        assert league["name"] == "My League"
        assert league["espn_league_id"] == 12345
        assert "_id" in league

    def test_find_by_user(self, league_repo, user_repo):
        user = self._create_user(user_repo)
        league_repo.create_league(user["_id"], "League 1", 111, 2024, "s2", "swid")
        league_repo.create_league(user["_id"], "League 2", 222, 2024, "s2", "swid")
        leagues = league_repo.find_by_user(user["_id"])
        assert len(leagues) == 2

    def test_find_by_user_isolation(self, league_repo, user_repo):
        user_a = self._create_user(user_repo, "user_a")
        user_b = self._create_user(user_repo, "user_b")
        league_repo.create_league(user_a["_id"], "A's League", 111, 2024, "s2", "swid")
        league_repo.create_league(user_b["_id"], "B's League", 222, 2024, "s2", "swid")
        assert len(league_repo.find_by_user(user_a["_id"])) == 1
        assert len(league_repo.find_by_user(user_b["_id"])) == 1

    def test_find_by_id(self, league_repo, user_repo):
        user = self._create_user(user_repo)
        league = league_repo.create_league(user["_id"], "Test", 111, 2024, "s2", "swid")
        found = league_repo.find_by_id(league["_id"])
        assert found is not None
        assert found["name"] == "Test"

    def test_find_by_id_string(self, league_repo, user_repo):
        user = self._create_user(user_repo)
        league = league_repo.create_league(user["_id"], "Test", 111, 2024, "s2", "swid")
        found = league_repo.find_by_id(str(league["_id"]))
        assert found is not None

    def test_update_league(self, league_repo, user_repo):
        user = self._create_user(user_repo)
        league = league_repo.create_league(user["_id"], "Old Name", 111, 2024, "s2", "swid")
        league_repo.update_league(league["_id"], name="New Name")
        updated = league_repo.find_by_id(league["_id"])
        assert updated["name"] == "New Name"

    def test_delete_league(self, league_repo, user_repo):
        user = self._create_user(user_repo)
        league = league_repo.create_league(user["_id"], "To Delete", 111, 2024, "s2", "swid")
        league_repo.delete_league(league["_id"])
        assert league_repo.find_by_id(league["_id"]) is None

    def test_find_by_id_not_found(self, league_repo):
        assert league_repo.find_by_id(ObjectId()) is None

    def test_find_by_user_string_id(self, league_repo, user_repo):
        user = self._create_user(user_repo)
        league_repo.create_league(user["_id"], "Test", 111, 2024, "s2", "swid")
        leagues = league_repo.find_by_user(str(user["_id"]))
        assert len(leagues) == 1
