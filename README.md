# Fantasy Football Analyzer

A Flask webapp that connects to ESPN Fantasy Football via the [`espn-api`](https://github.com/cwendt94/espn-api) package to display league standings, team rosters, and player analytics powered by [nfl_data_py](https://github.com/nflverse/nfl_data_py).

## Prerequisites

- Python 3.9+
- An ESPN Fantasy Football league (private leagues require authentication cookies)

## Setup (Local Development)

1. **Create a virtual environment and install dependencies:**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements-dev.txt
   ```

2. **Configure environment variables:**

   ```bash
   cp .env.example .env
   ```

   Edit `.env` with your league credentials (see [User Guide](USER_GUIDE.md) for how to find these).

3. **Run the app:**

   ```bash
   python app.py
   ```

   The app starts at `http://127.0.0.1:8000` with debug mode enabled.

## Running with Docker

1. **Build the image:**

   ```bash
   docker build -t fantasy-football:latest .
   ```

2. **Run the container:**

   ```bash
   docker run --env-file .env -p 3000:8000 fantasy-football:latest
   ```

3. Access the app at `http://localhost:3000`.

## Running with Docker Compose

1. **Start the app:**

   ```bash
   docker compose up --build
   ```

2. Access the app at `http://localhost:3000`.

3. **Stop the app:**

   ```bash
   docker compose down
   ```

## MongoDB Setup

### With Docker Compose

MongoDB starts automatically with `docker compose up`. The Flask app connects via the `MONGODB_URI` environment variable configured in `docker-compose.yaml`.

### With Kubernetes

1. Create MongoDB secret: `cp k8s/mongodb-secret.yaml.example k8s/mongodb-secret.yaml`
2. Apply MongoDB resources:
   ```bash
   kubectl apply -f k8s/mongodb-secret.yaml
   kubectl apply -f k8s/mongodb-pvc.yaml
   kubectl apply -f k8s/mongodb-deployment.yaml
   kubectl apply -f k8s/mongodb-service.yaml
   ```

### Local Development

For local development without Docker, install MongoDB and set `MONGODB_URI` in your `.env` file:
```
MONGODB_URI=mongodb://localhost:27017/fantasy_football
```

Initialize the database and load analytics data:
```bash
python scripts/init_db.py
python scripts/load_stats.py --years 2024
```

See [Populating Analytics Data](#populating-analytics-data) below for details.

## Running with Kubernetes (Docker Desktop)

### Prerequisites

- Docker Desktop for Mac with Kubernetes enabled (Settings > Kubernetes > Enable Kubernetes)

### Steps

1. **Build the Docker image** (Kubernetes uses the local Docker image):

   ```bash
   docker build -t fantasy-football:latest .
   ```

2. **Create your secret from the example template:**

   ```bash
   cp k8s/secret.yaml.example k8s/secret.yaml
   ```

   Edit `k8s/secret.yaml` with your real ESPN credentials.

3. **Apply the Kubernetes configurations:**

   ```bash
   kubectl apply -f k8s/secret.yaml
   kubectl apply -f k8s/deployment.yaml
   kubectl apply -f k8s/service.yaml
   ```

4. **Verify the pod is running:**

   ```bash
   kubectl get pods -l app=fantasy-football
   ```

5. Access the app at `http://localhost:30500`.

### Teardown

```bash
kubectl delete -f k8s/service.yaml
kubectl delete -f k8s/deployment.yaml
kubectl delete -f k8s/secret.yaml
```

## Populating Analytics Data

Analytics features (positional rankings, player detail pages, team analysis, start/sit suggestions) require NFL stats data in MongoDB. This data comes from [nfl_data_py](https://github.com/nflverse/nfl_data_py).

1. **Initialize the database** (creates collections and indexes -- only needed once):

   ```bash
   python scripts/init_db.py
   ```

2. **Load player stats** for the season(s) matching your leagues:

   ```bash
   python scripts/load_stats.py --years 2024
   ```

   Multiple seasons can be loaded at once:

   ```bash
   python scripts/load_stats.py --years 2022 2023 2024
   ```

   This ingests seasonal totals and week-by-week stats into the `seasonal_stats` and `weekly_stats` collections. Records are upserted, so it is safe to re-run during the season to pick up updated stats.

3. Analytics pages will show data once stats are loaded. If no data is available for a season, the analytics page displays a message with instructions.

## Routes

| Route | Description |
|---|---|
| `GET /` | Redirects to leagues list |
| `GET /leagues` | User's saved leagues |
| `GET /leagues/add` | Add a new ESPN league |
| `GET /leagues/<id>/standings` | League standings sorted by rank |
| `GET /leagues/<id>/team/<team_id>` | Team roster (Starters, Bench, IR) |
| `GET /leagues/<id>/analytics` | Top players by position for the season |
| `GET /leagues/<id>/player/<player_id>` | Individual player detail and weekly trend |
| `GET /leagues/<id>/team/<team_id>/analytics` | Team roster analysis with start/sit suggestions |

## Key Concepts

**Slot mapping** -- ESPN uses internal slot names that differ from common fantasy terminology. The app maps these for display:

| ESPN Slot | Displayed As |
|---|---|
| `OP` | `QB` (used in 2-QB / Superflex leagues) |
| `RB/WR/TE` | `FLEX` |

Starters are sorted in this order: QB, RB, WR, TE, FLEX, K, D/ST.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest test_app.py test_db.py test_analytics.py -v
```

Tests mock the ESPN API via `unittest.mock.patch` with `SimpleNamespace` objects and use `mongomock` for MongoDB. No ESPN credentials or running MongoDB instance are needed for unit tests.

E2E tests in `tests/e2e/` require a running app and MongoDB instance. See `tests/e2e/conftest.py` for setup details.
