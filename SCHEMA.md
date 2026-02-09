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
