"""CLI script to ingest NFL stats into MongoDB via the analytics data pipeline."""

import argparse
import os
import sys
from urllib.parse import quote_plus

from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

load_dotenv()

from analytics.data_pipeline import (
    ingest_seasonal_stats, ingest_weekly_stats,
    ingest_schedules, ingest_snap_counts,
)
from db import get_db


def _build_uri():
    """Build MongoDB URI from env vars, falling back to credentials if needed."""
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        username = os.environ.get("MONGO_USERNAME")
        password = os.environ.get("MONGO_PASSWORD")
        if username and password:
            uri = (
                f"mongodb://{quote_plus(username)}:{quote_plus(password)}"
                f"@localhost:27017/fantasy_football?authSource=admin"
            )
    return uri


def main():
    parser = argparse.ArgumentParser(description="Load NFL stats into MongoDB")
    parser.add_argument(
        "--years",
        type=int,
        nargs="+",
        required=True,
        help="NFL seasons to import (e.g., --years 2023 2024 2025)",
    )
    parser.add_argument(
        "--schedules",
        action="store_true",
        help="Also load NFL schedule data",
    )
    parser.add_argument(
        "--snap-counts",
        action="store_true",
        help="Also load player snap count data",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Load all data types (seasonal, weekly, schedules, snap counts)",
    )
    args = parser.parse_args()

    db = get_db(uri=_build_uri())
    years = args.years

    print(f"Loading stats for seasons: {years}")

    print("Ingesting seasonal stats...")
    seasonal_count = ingest_seasonal_stats(db, years)
    print(f"  Seasonal stats: {seasonal_count} records upserted")

    print("Ingesting weekly stats...")
    weekly_count = ingest_weekly_stats(db, years)
    print(f"  Weekly stats: {weekly_count} records upserted")

    if args.schedules or args.all:
        print("Ingesting schedules...")
        schedule_count = ingest_schedules(db, years)
        print(f"  Schedules: {schedule_count} records upserted")

    if args.snap_counts or args.all:
        print("Ingesting snap counts...")
        snap_count = ingest_snap_counts(db, years)
        print(f"  Snap counts: {snap_count} records upserted")

    print("Done.")


if __name__ == "__main__":
    main()
