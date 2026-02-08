# Fantasy Football Analyzer

A Flask webapp that connects to ESPN Fantasy Football via the [`espn-api`](https://github.com/cwendt94/espn-api) package to display league standings and team rosters.

## Prerequisites

- Python 3.9+
- An ESPN Fantasy Football league (private leagues require authentication cookies)

## Setup

1. **Create a virtual environment and install dependencies:**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install flask espn-api python-dotenv
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

## Project Structure

```
.
├── app.py              # Flask application (routes, helpers)
├── test_app.py         # Test suite (34 tests)
├── .env.example        # Template for required environment variables
├── .env                # Your credentials (git-ignored)
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
pip install pytest
python -m pytest test_app.py -v
```

Tests mock the ESPN API via `unittest.mock.patch` on `get_league()`, using `SimpleNamespace` objects to simulate ESPN's Team/Player/League models. No ESPN credentials are needed to run tests.
