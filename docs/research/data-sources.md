# Data Sources Research

## Overview

This document evaluates data sources for building a fantasy football analytics
pipeline. Each source is assessed on cost, data availability, format, update
frequency, ease of integration, and terms of use. The recommendation is to
prioritize free, API-accessible, Python-friendly sources.

## Primary Recommended Sources

### nfl_data_py (nflverse)

- **Cost:** Free and open source.
- **Python Package:** `pip install nfl_data_py`
- **Data Available:**
  - Play-by-play data (every play since 1999).
  - Weekly player statistics (passing, rushing, receiving).
  - Roster data with player metadata (position, team, draft info).
  - Snap counts and participation data.
  - Next Gen Stats (speed, separation, etc.) where available.
  - Draft picks and combine results.
  - Injury reports and depth charts.
  - Schedule and game results.
- **Format:** Returns pandas DataFrames directly. No parsing needed.
- **Update Frequency:** Weekly during the season, typically by Tuesday.
- **Terms of Use:** Open source under MIT license. Data sourced from nflverse,
  a community project that aggregates publicly available NFL data.
- **Integration Notes:** This is the single best source for historical and
  current NFL statistics. The Python API is clean and well-documented.

```python
import nfl_data_py as nfl

# Example: load play-by-play data
pbp = nfl.import_pbp_data([2024, 2025])

# Example: load weekly player stats
weekly = nfl.import_weekly_data([2024, 2025])

# Example: load roster data
rosters = nfl.import_rosters([2025])
```

**Recommendation:** Use as the primary data source for all historical and
in-season statistical data.

### ESPN API (espn-api package)

- **Cost:** Free.
- **Python Package:** `pip install espn-api`
- **Data Available:**
  - League-specific data (rosters, standings, matchups, transactions).
  - Player projections from ESPN.
  - Box scores with detailed player statistics per matchup week.
  - Free agent listings with ownership percentages.
  - Player info including eligibility, injury status, and projected points.
  - Power rankings computed from league data.
- **Currently Used Methods:** League initialization, team rosters, standings.
- **Unused Methods Worth Exploring:**
  - `league.box_scores(week)` - Detailed scoring breakdowns per matchup.
  - `league.free_agents(position_id, size)` - Available players with stats.
  - `league.player_info(playerId)` - Extended player metadata.
  - `league.power_rankings(week)` - Algorithmic team strength ratings.
  - `league.recent_activity(size, msg_type)` - Transaction history.
  - `team.schedule` - Full season schedule with results.
- **Format:** Python objects with attribute access. Requires some transformation
  to integrate with pandas workflows.
- **Update Frequency:** Real-time during games, finalized shortly after.
- **Terms of Use:** Unofficial API. ESPN does not publish a public API contract,
  but the community package has been stable for several years. Rate limiting
  is not formally documented; keep requests reasonable.

**Recommendation:** Continue using for league-specific data. Expand usage of
box_scores and free_agents methods for richer league context.

## Secondary Sources

### Pro Football Reference

- **Cost:** Free to access. No API available.
- **Data Available:**
  - Comprehensive historical statistics dating back decades.
  - Advanced metrics (ANY/A, DVOA-adjacent stats, approximate value).
  - Game logs, splits, and situational statistics.
  - Draft history and combine data.
  - Snap counts and red zone statistics.
- **Format:** HTML tables. Requires web scraping with BeautifulSoup or similar.
- **Update Frequency:** Updated within hours of game completion.
- **Terms of Use:** Owned by Sports Reference LLC. Their terms permit personal,
  non-commercial use. Automated scraping should be done respectfully with
  delays between requests (2-3 seconds minimum). They provide a rate limit
  of 20 requests per minute.
- **Integration Notes:** The `sportsreference` Python package
  (`pip install sportsreference`) provides a wrapper, though it can lag behind
  site changes. Manual scraping with `requests` + `pandas.read_html()` is
  more reliable.

**Recommendation:** Use as a supplementary source for advanced metrics and
historical data not available through nfl_data_py. Avoid heavy scraping.

### FantasyPros

- **Cost:** Free tier with basic rankings. Premium tiers ($10-30/month) for
  advanced tools and projections.
- **Data Available:**
  - Expert Consensus Rankings (ECR) aggregated from 100+ analysts.
  - Rest-of-season and weekly projections.
  - ADP data from major platforms.
  - Strength of schedule analysis.
  - Snap count and target data.
- **Format:** CSV downloads (free tier), API access (premium tier).
- **Update Frequency:** Rankings updated multiple times daily during season.
- **Terms of Use:** Free tier allows personal use. API access requires a paid
  subscription. Scraping is prohibited in their terms of service.

**Recommendation:** Use free-tier CSV downloads for consensus rankings and ADP
data. This provides valuable "wisdom of the crowd" context for our models.

### Sleeper API

- **Cost:** Free.
- **Data Available:**
  - Player database with metadata.
  - ADP and rankings.
  - Trending players (add/drop activity).
  - League data (if using Sleeper platform).
- **Format:** REST API returning JSON.
- **Update Frequency:** Real-time.
- **Terms of Use:** Public API with no authentication required for most
  endpoints. Undocumented rate limits.

**Recommendation:** Useful for trending player data and ADP. Lower priority
than primary sources.

### Vegas Odds Data

- **Cost:** Free via the-odds-api.com (500 requests/month free tier).
- **Data Available:**
  - Game spreads, over/under totals, and moneylines.
  - Implied team totals (derived from spread + total).
  - Player props (touchdown scorer, yardage, etc.).
- **Format:** REST API returning JSON.
- **Update Frequency:** Real-time as lines move.
- **Terms of Use:** Free tier available. API key required.

**Recommendation:** Implied team totals are among the strongest predictive
features for fantasy scoring. Worth integrating even at the free tier.

## Data Source Comparison Matrix

| Source              | Cost    | Historical | Real-Time | Python API | Reliability |
|---------------------|---------|------------|-----------|------------|-------------|
| nfl_data_py         | Free    | Excellent  | Weekly    | Native     | High        |
| ESPN API            | Free    | Limited    | Yes       | Package    | Medium      |
| Pro Football Ref    | Free    | Excellent  | Daily     | Scraping   | High        |
| FantasyPros         | Freemium| Good       | Daily     | CSV/API    | High        |
| Sleeper API         | Free    | Limited    | Yes       | REST       | Medium      |
| Vegas Odds API      | Freemium| Limited    | Yes       | REST       | High        |

## Recommended Integration Priority

1. **nfl_data_py** - Primary statistical data source. Implement first.
2. **ESPN API (expanded)** - League-specific context. Already partially integrated.
3. **Vegas Odds API** - Implied team totals for matchup features.
4. **FantasyPros CSV** - Consensus rankings for draft and weekly decisions.
5. **Pro Football Reference** - Supplementary advanced metrics as needed.
6. **Sleeper API** - Trending data for waiver wire recommendations.

## Data Storage Considerations

All ingested data should be normalized and stored in MongoDB collections to
avoid repeated API calls and to maintain historical records. Raw data should
be preserved alongside transformed/cleaned versions. See the analytics
implementation plan for the proposed collection schema.

## Rate Limiting and Caching Strategy

- Cache all API responses locally with a TTL appropriate to update frequency.
- For nfl_data_py, cache weekly data files and only re-fetch after Tuesday updates.
- For ESPN API, cache league data with a 15-minute TTL during game days,
  longer during the week.
- For scraped sources, implement polite delays and respect robots.txt.
