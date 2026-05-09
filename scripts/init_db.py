"""Initialize MongoDB collections and indexes."""

import os
import sys
from urllib.parse import quote_plus

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()


def init_db(uri=None):
    uri = uri or os.environ.get("MONGODB_URI")
    if not uri:
        username = os.environ.get("MONGO_USERNAME")
        password = os.environ.get("MONGO_PASSWORD")
        if username and password:
            uri = (
                f"mongodb://{quote_plus(username)}:{quote_plus(password)}"
                f"@localhost:27017/fantasy_football?authSource=admin"
            )
        else:
            uri = "mongodb://localhost:27017/fantasy_football"
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

    # Analytics collection indexes
    db.seasonal_stats.create_index(
        [("player_id", 1), ("season", 1)], unique=True
    )
    print("Created unique index on seasonal_stats.(player_id, season)")

    db.seasonal_stats.create_index(
        [("season", 1), ("position", 1), ("fantasy_points_ppr", -1)]
    )
    print("Created index on seasonal_stats.(season, position, fantasy_points_ppr)")

    db.weekly_stats.create_index(
        [("player_id", 1), ("season", 1), ("week", 1)], unique=True
    )
    print("Created unique index on weekly_stats.(player_id, season, week)")

    db.weekly_stats.create_index(
        [("season", 1), ("position", 1)]
    )
    print("Created index on weekly_stats.(season, position)")

    # Schedule indexes
    db.schedules.create_index("game_id", unique=True)
    print("Created unique index on schedules.game_id")

    db.schedules.create_index([("season", 1), ("week", 1)])
    print("Created index on schedules.(season, week)")

    # Snap count indexes
    db.snap_counts.create_index(
        [("player", 1), ("season", 1), ("week", 1)], unique=True
    )
    print("Created unique index on snap_counts.(player, season, week)")

    # Projection cache indexes
    db.projections.create_index(
        [("player_id", 1), ("season", 1), ("week", 1)]
    )
    print("Created index on projections.(player_id, season, week)")

    db.projections.create_index(
        [("season", 1), ("week", 1), ("position", 1)]
    )
    print("Created index on projections.(season, week, position)")

    # Model metadata indexes
    db.model_metadata.create_index(
        [("model_name", 1), ("season", 1)]
    )
    print("Created index on model_metadata.(model_name, season)")

    print("Database initialization complete.")
    return db


if __name__ == "__main__":
    init_db()
