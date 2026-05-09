# Database Schema

MongoDB database: `fantasy_football`

## Collection: `users`

| Field | Type | Description |
|-------|------|-------------|
| `_id` | ObjectId | Auto-generated primary key |
| `username` | string | Unique username |
| `password_hash` | string | Werkzeug-generated password hash |
| `created_at` | datetime | Account creation timestamp |
| `updated_at` | datetime | Last update timestamp |

**Indexes:**
- Unique index on `username`

## Collection: `leagues`

| Field | Type | Description |
|-------|------|-------------|
| `_id` | ObjectId | Auto-generated primary key |
| `user_id` | ObjectId | Reference to users._id |
| `name` | string | User-chosen display name for this league |
| `espn_league_id` | int | ESPN league identifier |
| `espn_year` | int | Season year |
| `espn_s2` | string | ESPN S2 authentication cookie |
| `espn_swid` | string | ESPN SWID authentication cookie |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last update timestamp |

**Indexes:**
- Compound index on `(user_id, espn_league_id, espn_year)` (unique)

## Collection: `schedules`

NFL game schedule data from nfl_data_py.

| Field | Type | Description |
|-------|------|-------------|
| `_id` | ObjectId | Auto-generated primary key |
| `game_id` | string | Unique game identifier (e.g. `2024_01_KC_BAL`) |
| `season` | int | NFL season year |
| `week` | int | Week number |
| `home_team` | string | Home team abbreviation |
| `away_team` | string | Away team abbreviation |

**Indexes:**
- Unique index on `game_id`
- Compound index on `(season, week)`

## Collection: `snap_counts`

Per-player weekly snap count data from nfl_data_py.

| Field | Type | Description |
|-------|------|-------------|
| `_id` | ObjectId | Auto-generated primary key |
| `player` | string | Player name |
| `season` | int | NFL season year |
| `week` | int | Week number |
| `offense_pct` | float | Percentage of offensive snaps played |

**Indexes:**
- Unique index on `(player, season, week)`

## Collection: `projections`

Cached ML model predictions for player performance.

| Field | Type | Description |
|-------|------|-------------|
| `_id` | ObjectId | Auto-generated primary key |
| `player_id` | string | nflverse player ID |
| `season` | int | NFL season year |
| `week` | int | Week number |
| `projected_points` | float | Model's projected fantasy points (PPR) |
| `confidence_low` | float | Lower bound of confidence interval |
| `confidence_high` | float | Upper bound of confidence interval |

**Indexes:**
- Compound index on `(player_id, season, week)`
- Compound index on `(season, week, position)`

## Collection: `model_metadata`

Tracking info for trained ML models.

| Field | Type | Description |
|-------|------|-------------|
| `_id` | ObjectId | Auto-generated primary key |
| `model_name` | string | Model identifier (e.g. `point_projector`, `clusterer_qb`) |
| `season` | int | Primary season the model was trained for |
| `training_seasons` | array | List of seasons used for training |
| `metrics` | object | Training metrics (MAE, RMSE, R2, etc.) |

**Indexes:**
- Compound index on `(model_name, season)`
