"""MongoDB persistence layer using the repository pattern."""

import os
from datetime import datetime, timezone

from bson import ObjectId
from pymongo import MongoClient
from werkzeug.security import check_password_hash, generate_password_hash


def get_db(uri=None, **client_kwargs):
    """Get a MongoDB database connection with small timeouts for dev."""
    uri = uri or os.environ.get("MONGODB_URI", "mongodb://localhost:27017/fantasy_football")
    timeout_ms = int(os.environ.get("MONGO_TIMEOUT_MS", "500"))
    client_kwargs.setdefault("serverSelectionTimeoutMS", timeout_ms)
    client_kwargs.setdefault("connectTimeoutMS", timeout_ms)
    client_kwargs.setdefault("socketTimeoutMS", timeout_ms)
    client = MongoClient(uri, **client_kwargs)
    return client.get_default_database()


class UserRepository:
    def __init__(self, db=None):
        self.db = db

    def _collection(self):
        return self.db["users"]

    def create_user(self, username, password):
        now = datetime.now(timezone.utc)
        doc = {
            "username": username,
            "password_hash": generate_password_hash(password),
            "created_at": now,
            "updated_at": now,
        }
        result = self._collection().insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    def find_by_username(self, username):
        return self._collection().find_one({"username": username})

    def find_by_id(self, user_id):
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        return self._collection().find_one({"_id": user_id})

    def verify_password(self, username, password):
        user = self.find_by_username(username)
        if user and check_password_hash(user["password_hash"], password):
            return user
        return None


class LeagueRepository:
    def __init__(self, db=None):
        self.db = db

    def _collection(self):
        return self.db["leagues"]

    def create_league(self, user_id, name, espn_league_id, espn_year, espn_s2, espn_swid):
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        now = datetime.now(timezone.utc)
        doc = {
            "user_id": user_id,
            "name": name,
            "espn_league_id": espn_league_id,
            "espn_year": espn_year,
            "espn_s2": espn_s2,
            "espn_swid": espn_swid,
            "created_at": now,
            "updated_at": now,
        }
        result = self._collection().insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    def find_by_user(self, user_id):
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        return list(self._collection().find({"user_id": user_id}))

    def find_by_id(self, league_id):
        if isinstance(league_id, str):
            league_id = ObjectId(league_id)
        return self._collection().find_one({"_id": league_id})

    def update_league(self, league_id, **fields):
        if isinstance(league_id, str):
            league_id = ObjectId(league_id)
        fields["updated_at"] = datetime.now(timezone.utc)
        return self._collection().update_one(
            {"_id": league_id},
            {"$set": fields},
        )

    def delete_league(self, league_id):
        if isinstance(league_id, str):
            league_id = ObjectId(league_id)
        return self._collection().delete_one({"_id": league_id})
