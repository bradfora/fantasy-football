"""CLI script to ingest NFL stats into MongoDB via the analytics data pipeline."""

import argparse
import os
import sys

from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

load_dotenv()

from analytics.data_pipeline import ingest_seasonal_stats, ingest_weekly_stats
from db import get_db


def main():
    parser = argparse.ArgumentParser(description="Load NFL stats into MongoDB")
    parser.add_argument(
        "--years",
        type=int,
        nargs="+",
        required=True,
        help="NFL seasons to import (e.g., --years 2023 2024 2025)",
    )
    args = parser.parse_args()

    db = get_db()
    years = args.years

    print(f"Loading stats for seasons: {years}")

    print("Ingesting seasonal stats...")
    seasonal_count = ingest_seasonal_stats(db, years)
    print(f"  Seasonal stats: {seasonal_count} records upserted")

    print("Ingesting weekly stats...")
    weekly_count = ingest_weekly_stats(db, years)
    print(f"  Weekly stats: {weekly_count} records upserted")

    print("Done.")


if __name__ == "__main__":
    main()
