# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run Commands

```bash
# Install dependencies (use venv at .venv)
pip install -r requirements-dev.txt

# Run the app locally (starts on http://127.0.0.1:8000)
python app.py

# Run all unit tests
python -m pytest test_app.py test_db.py test_analytics.py test_models.py -v

# Run a single test file
python -m pytest test_app.py -v

# Run a single test by name
python -m pytest test_app.py -v -k "test_name"

# Load NFL stats data into MongoDB
python scripts/load_stats.py --years 2024

# Load all data types (seasonal, weekly, schedules, snap counts)
python scripts/load_stats.py --years 2022 2023 2024 --all

# Train ML models for player projections
python scripts/train_models.py --seasons 2022 2023 --evaluate-on 2024

# Docker build & run
docker build -t fantasy-football:latest .
docker compose up --build        # app at http://localhost:3001
```

## Architecture

Flask app with MongoDB (pymongo), Flask-Login auth, and ESPN Fantasy Football API integration via `espn-api`.

**Core layers:**
- `app.py` — All Flask routes: auth (login/register/logout), league CRUD, ESPN-backed views (standings, roster), and analytics pages
- `db.py` — MongoDB connection factory (`get_db()`) and repository classes (`UserRepository`, `LeagueRepository`). Uses `MONGODB_URI` env var, defaults to `mongodb://localhost:27017/fantasy_football`
- `models.py` — `User` class wrapping MongoDB docs for Flask-Login's `UserMixin`
- `analytics/` — NFL stats analysis module:
  - `data_pipeline.py` — Ingests seasonal/weekly stats, schedules, and snap counts from `nfl_data_py` into MongoDB
  - `basic_stats.py` — Query functions for rankings, player summaries, roster analysis with start/sit suggestions
  - `matchup_stats.py` — Defensive rankings, opponent lookup, matchup difficulty ratings
  - `models.py` — ML models: `PointProjector` (Ridge+RF ensemble), `PlayerClusterer` (K-Means archetypes)
  - `projections.py` — Projection orchestrator: caching, risk adjustment, Monte Carlo simulation

**Data flow:** Users register, add ESPN league credentials, then view standings/rosters via live ESPN API calls. Analytics features query pre-loaded NFL stats from MongoDB (populated via `scripts/load_stats.py`).

**ESPN slot mapping:** `OP` displays as `QB`, `RB/WR/TE` displays as `FLEX`. Starters sort by: QB, RB, WR, TE, FLEX, K, D/ST.

## Testing

Unit tests use `mongomock` for MongoDB and `unittest.mock.patch` with `SimpleNamespace` objects to simulate ESPN API responses — no real ESPN credentials or MongoDB needed.

E2E tests live in `tests/e2e/` and require a running app instance + MongoDB. API tests use `requests.Session` for cookie-based auth; Selenium tests use `webdriver-manager`.

## Environment Variables

Required: `SECRET_KEY`, `MONGODB_URI`
ESPN credentials stored per-league in MongoDB (not env vars).
`MONGO_TIMEOUT_MS` controls connection timeouts (default 500ms, use 5000ms in K8s).

## Deployment

- **Docker Compose:** Maps port 3001→8000, MongoDB on 27017. Requires `MONGO_USERNAME` and `MONGO_PASSWORD` in `.env`.
- **Kubernetes:** NodePort 30500, secrets in `k8s/secret.yaml`. MongoDB deployed separately with PVC. Env vars in `k8s/deployment.yaml` must be ordered so `MONGODB_URI` comes after `MONGO_USERNAME`/`MONGO_PASSWORD` (K8s interpolation depends on definition order).
