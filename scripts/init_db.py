"""Initialize MongoDB collections and indexes."""

import os
import sys

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()


def init_db(uri=None):
    uri = uri or os.environ.get("MONGODB_URI", "mongodb://localhost:27017/fantasy_football")
    client = MongoClient(uri)
    db = client.get_default_database()

    # Create collections (no-op if they exist)
    existing = db.list_collection_names()
    for name in ("users", "leagues"):
        if name not in existing:
            db.create_collection(name)
            print(f"Created collection: {name}")
        else:
            print(f"Collection already exists: {name}")

    # Create indexes
    db.users.create_index("username", unique=True)
    print("Created unique index on users.username")

    db.leagues.create_index(
        [("user_id", 1), ("espn_league_id", 1), ("espn_year", 1)],
        unique=True,
    )
    print("Created compound unique index on leagues.(user_id, espn_league_id, espn_year)")

    print("Database initialization complete.")
    return db


if __name__ == "__main__":
    init_db()
