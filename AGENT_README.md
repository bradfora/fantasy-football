# Agent Reference

Notes for AI agents working on this codebase.

## Architecture

This is a single-file Flask app (`app.py`) with Jinja2 templates. There is no database, no JavaScript framework, and no build step. The ESPN API is accessed via the `espn-api` package, which handles all HTTP communication with ESPN's servers.

**Data flow:** Each route calls `get_league()` which creates a fresh `League` object from `espn_api.football`. This makes a live API call to ESPN on every page load. There is currently no caching.

## ESPN API (`espn-api` package)

- **Docs/source:** https://github.com/cwendt94/espn-api
- **Import:** `from espn_api.football import League`
- **Key objects:** `League` has `.teams` (list of `Team`). Each `Team` has `.roster` (list of `Player`).
- **Private league auth:** requires `espn_s2` and `swid` cookies passed to the `League` constructor.

### Useful League methods not yet used

| Method | Returns | Description |
|---|---|---|
| `league.box_scores(week)` | `list[BoxScore]` | Detailed weekly scoring with `BoxPlayer` objects that have `.points`, `.projected_points`, `.points_breakdown` |
| `league.free_agents(week, size, position)` | `list[Player]` | Available free agents |
| `league.player_info(name)` | `Player` | Lookup a single player |
| `league.power_rankings(week)` | `list[tuple]` | Power rankings |
| `league.recent_activity(size)` | `list` | Recent transactions (trades, adds, drops) |
| `league.standings()` | `list[Team]` | Teams sorted by final standing |

### Slot name quirks

ESPN uses non-standard slot names in its API. The app maintains two dicts in `app.py` to handle this:

- `SLOT_ORDER` -- maps slot names to sort position (int). Both `"OP"` and `"QB"` map to `0`; both `"RB/WR/TE"` and `"FLEX"` map to `4`.
- `SLOT_DISPLAY` -- maps ESPN slot names to display names (`"OP"` -> `"QB"`, `"RB/WR/TE"` -> `"FLEX"`).

If new slot types are introduced (e.g. `"RB/WR"` for a restricted flex, or `"DL"` for IDP leagues), both dicts need updating.

## Testing Approach

Tests are in `test_app.py` and use `pytest`. The ESPN API is never called in tests.

**Key patterns:**

- **Environment variables** are set via `os.environ.setdefault()` at the top of the test file, before the app module is imported (since `app.py` reads env vars at module level).
- **`get_league()` is patched** in every route test via `unittest.mock.patch("app.get_league", return_value=...)`.
- **Fake objects** use `SimpleNamespace` via three factory functions:
  - `make_player(**kwargs)` -- creates a fake Player with sensible defaults
  - `make_team(**kwargs)` -- creates a fake Team (defaults include an empty roster)
  - `make_league(teams)` -- wraps a list of teams in a namespace with a `.teams` attribute
- **Route tests** use Flask's test client and assert against the rendered HTML string.
- When checking that a CSS class is *not applied* to an element, be specific (e.g. `'<span class="injury-badge'`) rather than checking the class name as a substring, since class names also appear in `<style>` blocks.

**Running tests:**

```bash
python -m pytest test_app.py -v
```

## Styling

All CSS lives in `templates/base.html` as a `<style>` block. There are no external CSS files. The design uses:

- **Nunito** font loaded from Google Fonts
- Card-based layout with 16px border-radius
- Color-coded injury badges: red (OUT/DOUBTFUL), yellow (QUESTIONABLE), green (PROBABLE)
- Gold/silver/bronze rank badges for standings positions 1-3
- Green highlight for players with 100+ total points (`pts-high` class)

## Known Limitations / Future Work

- **No caching** -- every page load makes a fresh API call to ESPN, which is slow (~1-2s). A natural improvement would be to cache the `League` object (e.g. in-memory with a TTL, or Flask-Caching).
- **No error handling** for bad/expired credentials -- the app will crash with an `espn_api` exception if cookies are invalid.
- **No week-by-week views** -- rosters and scores are season totals only. `league.box_scores(week)` and `league.load_roster_week(week)` could power weekly breakdowns.
- **No free agent or waiver analysis** -- `league.free_agents()` is available but unused.
- **No player comparison or trade analysis** features yet.
- **`static/` directory is empty** -- CSS is inline. If styling grows, it should be extracted to a static CSS file.
