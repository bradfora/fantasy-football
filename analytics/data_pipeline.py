"""Data pipeline for ingesting NFL stats from nfl_data_py into MongoDB."""

import nfl_data_py as nfl
import pandas as pd


def fetch_seasonal_data(years):
    """Fetch seasonal player stats for the given years."""
    df = nfl.import_seasonal_data(years)
    return df


def fetch_weekly_data(years):
    """Fetch weekly player stats for the given years."""
    df = nfl.import_weekly_data(years)
    return df


def ingest_seasonal_stats(db, years):
    """Ingest seasonal stats into MongoDB.

    Args:
        db: MongoDB database instance
        years: list of years to import (e.g., [2022, 2023, 2024])

    Returns:
        Number of records inserted
    """
    df = fetch_seasonal_data(years)
    if df.empty:
        return 0

    collection = db["seasonal_stats"]
    records = df.to_dict("records")

    # Clean NaN values (MongoDB doesn't handle NaN well)
    for record in records:
        for key, value in record.items():
            if pd.isna(value):
                record[key] = None

    # Upsert by player_id + season
    count = 0
    for record in records:
        player_id = record.get("player_id")
        season = record.get("season")
        if player_id and season:
            collection.update_one(
                {"player_id": player_id, "season": season},
                {"$set": record},
                upsert=True,
            )
            count += 1
    return count


def ingest_weekly_stats(db, years):
    """Ingest weekly stats into MongoDB.

    Args:
        db: MongoDB database instance
        years: list of years to import

    Returns:
        Number of records inserted
    """
    df = fetch_weekly_data(years)
    if df.empty:
        return 0

    collection = db["weekly_stats"]
    records = df.to_dict("records")

    for record in records:
        for key, value in record.items():
            if pd.isna(value):
                record[key] = None

    count = 0
    for record in records:
        player_id = record.get("player_id")
        season = record.get("season")
        week = record.get("week")
        if player_id and season and week:
            collection.update_one(
                {"player_id": player_id, "season": season, "week": week},
                {"$set": record},
                upsert=True,
            )
            count += 1
    return count
