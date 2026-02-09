# Scripts

## init_db.py

Initializes MongoDB collections and indexes. Run against a local or remote MongoDB instance. Creates `users`, `leagues`, `seasonal_stats`, and `weekly_stats` collections with appropriate indexes.

```bash
# Uses MONGODB_URI from .env or defaults to mongodb://localhost:27017/fantasy_football
python scripts/init_db.py
```

## load_stats.py

Ingests NFL player stats from [nfl_data_py](https://github.com/nflverse/nfl_data_py) into MongoDB. This populates the `seasonal_stats` and `weekly_stats` collections used by the analytics features. Records are upserted so it is safe to re-run during the season for updated stats.

```bash
# Load a single season
python scripts/load_stats.py --years 2024

# Load multiple seasons
python scripts/load_stats.py --years 2022 2023 2024
```

Requires a running MongoDB instance. Uses `MONGODB_URI` from `.env` or defaults to `mongodb://localhost:27017/fantasy_football`.

## create_test_user.py

Seeds a test user for development.

```bash
python scripts/create_test_user.py
```
