# Fantasy Football Analyzer - Implementation Plan

## Context

The project is a single-file Flask app (`app.py`, 57 lines) that displays ESPN Fantasy Football league standings and rosters. It has 34 passing tests, 3 Jinja2 templates, and no database, no containerization, and no authentication. The `TODO.txt` outlines 5 phases to evolve it into a full-featured, containerized, multi-user application with advanced analytics. This plan implements all 5 phases with a multi-agent handoff protocol.

---

## Multi-Agent Handoff Protocol

Every step produces two tracking artifacts:

### `PROGRESS.md` (status tracker)
```
| Step | Status | Commit | Notes |
|------|--------|--------|-------|
| 1a   | done   | abc123 | ...   |
| 1b   | in_progress | - | ...  |
```

### `HANDOFF.md` (latest step details)
```
# Handoff: [Step ID] - [Title]
## What Was Done (files created/modified, decisions made)
## Verification Results (test output, manual checks)
## Known Issues / Deferred Items
## Next Step Prerequisites
```

### Branch Strategy
- Phase 1: `feature/phase-1-containerize`
- Phase 2: `feature/phase-2-persistence`
- Phase 3: `feature/phase-3-auth`
- Phase 4: `feature/phase-4-multi-league`
- Phase 5: `feature/phase-5-analytics`
- Each phase ends with a PR to `main`

---

## Phase 1: Containerize the Service

### Step 1a: Create requirements.txt
- **Create:** `requirements.txt` (flask, espn-api, python-dotenv - pinned versions from `pip freeze`)
- **Create:** `requirements-dev.txt` (`-r requirements.txt` + pytest)
- **Verify:** Fresh venv install + `python -m pytest test_app.py -v` passes 34/34
- **Iterate:** If versions drift from what's in `.venv`, use actual installed versions

### Step 1b: Create Dockerfile
- **Create:** `Dockerfile` (python:3.11-slim, COPY requirements + install, COPY app, `flask run --host=0.0.0.0`)
- **Create:** `.dockerignore` (exclude .venv, .git, .env, __pycache__, .idea, .pytest_cache)
- **Modify:** `app.py` - no changes needed; `flask run` auto-detects the `app` object
- **Verify:** `docker build -t fantasy-football:latest .` succeeds; `docker run --env-file .env -p 5000:5000 fantasy-football:latest` serves the app at localhost:5000
- **Iterate:** If espn-api needs C deps that fail on slim, switch to `python:3.11`

### Step 1c: Create Docker Compose setup
- **Create:** `docker-compose.yaml` - Flask app service with env_file, port 5000, for simple local dev
- **Verify:** `docker compose up` starts the app successfully

### Step 1d: Create Kubernetes configuration
- **Create:** `k8s/deployment.yaml` - single-replica Deployment, `imagePullPolicy: Never` (uses local Docker image)
- **Create:** `k8s/service.yaml` - NodePort service on port 30500
- **Create:** `k8s/secret.yaml.example` - template for ESPN credentials (no real secrets committed)
- **Modify:** `.gitignore` - add `k8s/secret.yaml`
- **Verify:** `kubectl apply --dry-run=client -f k8s/` validates YAML

### Step 1e: Update README with Docker/K8s/Compose instructions
- **Modify:** `README.md` - add sections: "Running with Docker", "Running with Docker Compose", "Running with Kubernetes (Docker Desktop)"
- Prerequisites: Docker Desktop for Mac with Kubernetes enabled
- Step-by-step: build image, create secret from example, apply configs, verify pod, access at localhost:30500, teardown

### Step 1f: End-to-end validation
- Follow README instructions from scratch on all three methods (direct Docker, Compose, K8s)
- Fix any gaps found in configs or instructions
- Run `python -m pytest test_app.py -v` to confirm 34/34 still pass
- **Gate:** All three deployment methods work, all tests pass, PR to main

---

## Phase 2: Add a Simple Persistence Layer

### Step 2a: Add MongoDB to Docker Compose and Kubernetes
- **Modify:** `docker-compose.yaml` - add MongoDB service (mongo:7), volume for persistence, environment for root credentials
- **Create:** `k8s/mongodb-deployment.yaml` - MongoDB pod with PVC
- **Create:** `k8s/mongodb-service.yaml` - ClusterIP service (cluster-internal only)
- **Create:** `k8s/mongodb-pvc.yaml` - 1Gi PersistentVolumeClaim
- **Create:** `k8s/mongodb-secret.yaml.example` - template for MongoDB credentials
- **Modify:** `.gitignore` - add `k8s/mongodb-secret.yaml`
- **Verify:** `docker compose up` starts both Flask and MongoDB; `kubectl apply` deploys MongoDB pod

### Step 2b: Add MongoDB connection to Flask app
- **Modify:** `requirements.txt` - add `pymongo`
- **Modify:** `docker-compose.yaml` - add `MONGODB_URI` env var to Flask service, depends_on MongoDB
- **Modify:** `k8s/deployment.yaml` - add MongoDB connection env vars
- **Modify:** `.env.example` - add `MONGODB_URI=mongodb://localhost:27017`
- **Verify:** Flask pod can reach MongoDB (test with temporary health endpoint or kubectl exec)

### Step 2c: Update README for MongoDB setup
- **Modify:** `README.md` - add "MongoDB Setup" section (Docker Compose auto-setup, K8s manual setup, local development with `mongosh`)

### Step 2d: Design data schema and create init script
- **Create:** `SCHEMA.md` - document all collections, fields, types, indexes
- **Create:** `scripts/init_db.py` - creates collections and indexes
- **Create:** `scripts/README.md` - documents available scripts

**Schema design (forward-looking for Phases 3-4):**

**Collection: `users`**
```
{ _id, username (unique), password_hash, created_at, updated_at }
Index: unique on username
```

**Collection: `leagues`**
```
{ _id, user_id, name, espn_league_id, espn_year, espn_s2, espn_swid, created_at, updated_at }
Index: compound on (user_id, espn_league_id, espn_year)
```

- **Verify:** `python scripts/init_db.py` runs against local MongoDB, indexes created
- **Iterate:** If schema doesn't accommodate future phases after review, revise before proceeding

### Step 2e: Create persistence layer code
- **Create:** `db.py` - repository pattern with `get_db()`, `UserRepository`, `LeagueRepository`
  - `UserRepository`: create_user, find_by_username, find_by_id
  - `LeagueRepository`: create_league, find_by_user, find_by_id, delete_league
  - Constructor accepts optional `db` param for dependency injection (testing)
- **Create:** `test_db.py` - unit tests using `mongomock` (~12+ tests for CRUD operations)
- **Modify:** `requirements-dev.txt` - add `mongomock`
- **Verify:** `python -m pytest test_db.py test_app.py -v` - all pass, db.py is NOT imported by app.py yet
- **Iterate:** If mongomock lacks needed features, use pytest with a real MongoDB container
- **Gate:** MongoDB runs in both Compose and K8s, schema documented, persistence layer exists but not wired, PR to main

---

## Phase 3: Create a Simple Authentication Flow

### Step 3a: Create User model and password handling
- **Modify:** `requirements.txt` - add `flask-login`
- **Create:** `models.py` - `User(UserMixin)` class wrapping MongoDB user documents
- **Modify:** `db.py` - add `verify_password(username, password)` using `werkzeug.security`
- **Create:** `scripts/create_test_user.py` - seed a test user for development
- **Modify:** `.env.example` - add `SECRET_KEY`
- **Verify:** New tests for password hashing/verification pass

### Step 3b: Create login page and routes
- **Create:** `templates/login.html` - username + password form, extends base.html
- **Modify:** `app.py` - initialize Flask-Login (`LoginManager`, `user_loader`), add `GET/POST /login`, `GET /logout`
- **Modify:** `templates/base.html` - add login/logout links to nav bar
- **Modify:** `test_app.py` - add tests for login page render, successful/failed login, logout
- **Verify:** Login flow works end-to-end; new tests pass alongside existing 34

### Step 3c: Create registration page
- **Create:** `templates/register.html` - username + password + confirm password form
- **Modify:** `app.py` - add `GET/POST /register` routes with validation (unique username, password match, non-empty)
- **Modify:** `test_app.py` - add tests for registration success, duplicate username, password mismatch
- **Verify:** Registration creates user, auto-logs in, redirects to `/`

### Step 3d: Protect existing endpoints
- **Modify:** `app.py` - add `@login_required` to `teams()` and `roster()` routes
- **Modify:** `test_app.py` - update existing 34 tests to use authenticated client fixture; add tests that unauthenticated requests redirect to `/login`
- **Key concern:** This changes behavior of all existing routes. Create a `logged_in_client` fixture that handles session auth. Existing content assertions reuse with auth.
- **Verify:** All existing test content assertions still pass (just with auth); unauthenticated access redirects to login
- **Iterate:** If tests break, the issue is auth state in the test client. Debug via `current_user.is_authenticated`

### Step 3e: Pass user context to templates
- **Modify:** `templates/base.html` - display logged-in username in nav (Flask-Login provides `current_user` automatically in Jinja2)
- **Modify:** `test_app.py` - verify username appears in rendered HTML
- **Gate:** Auth works end-to-end, all routes protected, ~55-60 total tests, PR to main

---

## Phase 4: Multiple Leagues Support

### Step 4a: Wire LeagueRepository into the app
- **Modify:** `db.py` - ensure `LeagueRepository` has full CRUD: `create_league`, `find_by_user`, `find_by_id`, `update_league`, `delete_league`
- **Modify:** `test_db.py` - add tests for multi-league scenarios (multiple leagues per user, isolation between users, duplicate prevention)
- **Verify:** All repository tests pass

### Step 4b: Add league management UI
- **Create:** `templates/leagues.html` - list of user's leagues with add/delete actions
- **Create:** `templates/add_league.html` - form for ESPN credentials (name, league ID, year, S2, SWID)
- **Modify:** `app.py` - add routes:
  - `GET /leagues` - list current user's leagues
  - `GET/POST /leagues/add` - add a new league (validate by attempting ESPN API connection)
  - `POST /leagues/<league_id>/delete` - remove a league
- **Modify:** `templates/base.html` - add "My Leagues" nav link
- **Verify:** Can add, view, delete leagues; ESPN credentials validated on submission

### Step 4c: Refactor routes to be league-scoped
- **Modify:** `app.py` - major refactor:
  - `GET /` redirects to `/leagues`
  - `GET /leagues/<league_id>/standings` - standings (replaces old `GET /`)
  - `GET /leagues/<league_id>/team/<team_id>` - roster (replaces old `GET /team/<id>`)
  - Replace `get_league()` with `get_espn_league(league_doc)` that reads credentials from DB
  - Remove module-level ESPN env var reads (lines 11-14 of current app.py)
- **Modify:** `templates/teams.html`, `templates/roster.html` - update URLs for new route structure
- **Modify:** `.env.example` - remove ESPN_* vars, keep only `SECRET_KEY` and `MONGODB_URI`
- **Modify:** `k8s/deployment.yaml` - remove ESPN credential env vars
- **Modify:** `test_app.py` - significant updates: mock LeagueRepository, update URLs, add authorization tests (user A can't access user B's leagues)
- **Iterate:** If refactor is too large, split into: (1) add new routes alongside old, (2) update tests, (3) remove old routes
- **Gate:** ESPN credentials from DB only, routes league-scoped, all tests pass (~75-80 total), PR to main

---

## Phase 5: Advanced Analytics (Research + Prototype)

### Step 5a: Research player performance modeling
- **Create:** `docs/research/player-performance-modeling.md`
- Topics: statistical approaches (regression, ML, Bayesian), key prediction features (matchups, snap counts, weather), fantasy-specific metrics (VORP, positional scarcity), start/sit decision frameworks, draft strategy optimization
- Recommend starting with simpler models first (linear regression) before ML

### Step 5b: Research data sources
- **Create:** `docs/research/data-sources.md`
- Evaluate: `nfl_data_py` (free play-by-play data), unused `espn-api` methods (box_scores, free_agents, player_info, power_rankings - see `AGENT_README.md` lines 18-27), Pro Football Reference, FantasyPros
- For each source: cost, data available, format, update frequency, terms of use
- Recommend free, API-accessible, Python-friendly sources to start

### Step 5c: Propose analytics implementation plan
- **Create:** `docs/research/analytics-implementation-plan.md`
- Phased approach: data pipeline -> basic analytics -> predictive models -> decision support -> draft tools
- Technology recommendations (pandas, scikit-learn, nfl_data_py)
- New schema/collections needed for historical data
- Architecture diagram: data sources -> ingestion -> storage -> analysis -> UI

### Step 5d: Build initial data prototype
- **Modify:** `requirements.txt` - add `nfl_data_py`, `pandas`
- **Create:** `analytics/data_pipeline.py` - ingest historical data from nfl_data_py into MongoDB
- **Create:** `analytics/basic_stats.py` - simple player ranking/scoring trends
- **Create:** `test_analytics.py` - tests for data pipeline and basic stats
- **Modify:** `app.py` - add a basic `/leagues/<id>/analytics` route showing player trends
- **Create:** `templates/analytics.html` - simple table/chart display
- **Verify:** Data pipeline runs, basic analytics endpoint returns data, tests pass
- **Gate:** Research docs complete, prototype working, PR to main

---

## Verification Checklist (End-to-End)

After all phases:
1. `docker compose up` starts Flask + MongoDB, app accessible at localhost:5000
2. `kubectl apply -f k8s/` deploys everything, app at localhost:30500
3. Register a new user, log in
4. Add a league with real ESPN credentials
5. View standings and rosters for that league
6. Add a second league, switch between them
7. View basic analytics page
8. `python -m pytest -v` passes all tests (~80+)

## Critical Files Reference

| File | Role | Modified In |
|------|------|-------------|
| `app.py` | Flask routes, core logic | Phases 1-5 |
| `test_app.py` | Route tests (34 currently) | Phases 3-5 |
| `db.py` | MongoDB persistence layer | Created Phase 2, used Phases 3-5 |
| `models.py` | User model (Flask-Login) | Created Phase 3 |
| `templates/base.html` | Layout + CSS + nav | Phases 3-4 |
| `docker-compose.yaml` | Local dev orchestration | Created Phase 1, modified Phase 2 |
| `k8s/deployment.yaml` | K8s app deployment | Created Phase 1, modified Phases 2, 4 |
| `PROGRESS.md` | Step-by-step tracking | Updated every step |
| `HANDOFF.md` | Agent handoff details | Updated every step |

## Environment Variable Evolution

| Phase | `.env` contains |
|-------|----------------|
| Current | ESPN_LEAGUE_ID, ESPN_YEAR, ESPN_S2, ESPN_SWID |
| Phase 1 | Same (passed via Docker/K8s) |
| Phase 2 | Add MONGODB_URI |
| Phase 3 | Add SECRET_KEY |
| Phase 4 | Remove ESPN_* vars (now in DB). Keep SECRET_KEY, MONGODB_URI |
