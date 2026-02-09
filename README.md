# Fantasy Football Analyzer

A Flask webapp that connects to ESPN Fantasy Football via the [`espn-api`](https://github.com/cwendt94/espn-api) package to display league standings and team rosters.

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

   The app starts at `http://127.0.0.1:5000` with debug mode enabled.

## Running with Docker

1. **Build the image:**

   ```bash
   docker build -t fantasy-football:latest .
   ```

2. **Run the container:**

   ```bash
   docker run --env-file .env -p 5000:5000 fantasy-football:latest
   ```

3. Access the app at `http://localhost:5000`.

## Running with Docker Compose

1. **Start the app:**

   ```bash
   docker compose up --build
   ```

2. Access the app at `http://localhost:5000`.

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

Initialize the database:
```bash
python scripts/init_db.py
```

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

## Project Structure

```
.
├── app.py              # Flask application (routes, helpers)
├── test_app.py         # Test suite (34 tests)
├── requirements.txt    # Production dependencies
├── requirements-dev.txt # Dev dependencies (includes pytest)
├── Dockerfile          # Container image definition
├── docker-compose.yaml # Docker Compose configuration
├── .env.example        # Template for required environment variables
├── .env                # Your credentials (git-ignored)
├── k8s/                # Kubernetes configurations
│   ├── deployment.yaml # App deployment (single replica)
│   ├── service.yaml    # NodePort service (port 30500)
│   └── secret.yaml.example # Template for ESPN credentials
├── templates/
│   ├── base.html       # Shared layout, CSS, nav
│   ├── teams.html      # League standings page
│   └── roster.html     # Team roster page
└── static/             # Static assets (currently empty)
```

## Routes

| Route | Description |
|---|---|
| `GET /` | League standings sorted by rank |
| `GET /team/<team_id>` | Roster for a specific team, split into Starters, Bench, and IR |

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
python -m pytest test_app.py -v
```

Tests mock the ESPN API via `unittest.mock.patch` on `get_league()`, using `SimpleNamespace` objects to simulate ESPN's Team/Player/League models. No ESPN credentials are needed to run tests.
