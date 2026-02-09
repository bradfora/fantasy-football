# Analytics Implementation Plan

## Overview

This document describes a phased plan for adding analytics capabilities to the
fantasy football application. The approach is incremental: each phase delivers
usable functionality while building toward a full predictive analytics system.

## Architecture

```
+------------------+     +------------------+     +------------------+
|   Data Sources   |     |    Ingestion     |     |     Storage      |
|                  |     |     Layer        |     |                  |
|  nfl_data_py     +---->+  Fetchers        +---->+  MongoDB         |
|  ESPN API        |     |  Transformers    |     |                  |
|  Vegas Odds API  |     |  Validators      |     |  player_stats    |
|  FantasyPros CSV |     |  Schedulers      |     |  weekly_scores   |
+------------------+     +------------------+     |  projections     |
                                                  |  matchup_data    |
                                                  |  odds_data       |
                                                  +--------+---------+
                                                           |
                                                           v
                         +------------------+     +------------------+
                         |   Presentation   |     |    Analysis      |
                         |     Layer        |     |     Engine       |
                         |                  |     |                  |
                         |  Flask Routes    +<----+  Ranking Models  |
                         |  Templates       |     |  Projections     |
                         |  REST API        |     |  Recommendations |
                         |  Charts          |     |  Draft Optimizer |
                         +------------------+     +------------------+
```

Data flows left to right: external sources are ingested, transformed, and
stored in MongoDB. The analysis engine reads from storage, runs models, and
produces outputs consumed by the presentation layer.

## Technology Stack

| Component         | Technology                  | Rationale                         |
|-------------------|-----------------------------|-----------------------------------|
| Data ingestion    | nfl_data_py, requests       | Native Python, pandas integration |
| Data storage      | MongoDB (existing)          | Already in use, flexible schema   |
| Data manipulation | pandas, numpy               | Standard data science stack       |
| Modeling          | scikit-learn                | Broad algorithm support, mature   |
| Gradient boosting | xgboost or lightgbm         | Best accuracy for tabular data    |
| Visualization     | matplotlib, Chart.js        | Backend charts + interactive UI   |
| Scheduling        | APScheduler or cron         | Automated weekly data refreshes   |
| Testing           | pytest (existing)           | Already in use                    |

## Phase 1: Data Pipeline (Weeks 1-3)

### Objective
Build automated ingestion of historical and weekly NFL data into MongoDB.

### Tasks

1. **Create data fetcher modules:**
   - `services/data/nfl_stats_fetcher.py` - Wraps nfl_data_py for historical
     and weekly stat imports.
   - `services/data/espn_extended_fetcher.py` - Extends current ESPN integration
     with box_scores, free_agents, and player_info methods.
   - `services/data/odds_fetcher.py` - Fetches game odds and implied totals.

2. **Define MongoDB collections:**
   - `player_stats` - Season-level aggregated statistics per player.
   - `weekly_scores` - Per-player, per-week fantasy point breakdowns.
   - `play_by_play` - Raw play-level data (subset of key columns to manage size).
   - `matchup_data` - Opponent defensive rankings and matchup context.
   - `odds_data` - Spreads, totals, and implied team totals per game.
   - `projections` - Model-generated and consensus projections.
   - `draft_adp` - Average draft position data across platforms.

3. **Build data transformation pipeline:**
   - Normalize player names and IDs across sources.
   - Compute derived features (target share, snap percentage, rolling averages).
   - Handle missing data (injury absences, bye weeks).

4. **Add scheduling:**
   - Weekly cron job or APScheduler task to fetch new data every Tuesday.
   - Pre-game fetch on Sunday mornings for latest injury/weather updates.

### Deliverables
- Populated MongoDB collections with 3 seasons of historical data.
- Automated weekly refresh pipeline.
- Data validation tests confirming completeness and accuracy.

## Phase 2: Basic Analytics (Weeks 4-6)

### Objective
Deliver descriptive analytics and visualizations in the existing UI.

### Tasks

1. **Player trend analysis:**
   - Rolling average charts (3-week, 5-week) for fantasy points.
   - Usage trend charts (targets, snap counts, red zone opportunities).
   - Comparison tool to overlay two players' recent performance.

2. **Matchup analysis:**
   - Opponent defensive rankings by position.
   - Historical performance vs. upcoming opponent.
   - Strength of remaining schedule.

3. **League analytics:**
   - Team strength rankings based on roster composition.
   - Positional strength/weakness identification.
   - Trade value charts.

4. **New Flask routes and templates:**
   - `/analytics/player/<player_id>` - Player dashboard with charts.
   - `/analytics/matchups/<week>` - Weekly matchup analysis.
   - `/analytics/league/power` - Power rankings with methodology breakdown.

### Deliverables
- Player analytics dashboard with interactive charts.
- Matchup analysis page updated weekly.
- League power rankings.

## Phase 3: Predictive Models (Weeks 7-10)

### Objective
Train and deploy point projection models for each position.

### Tasks

1. **Feature engineering:**
   - Build feature matrix from MongoDB collections.
   - Position-specific feature sets (e.g., air yards for WR, goal-line carries
     for RB).
   - Matchup features from opponent defensive data.
   - Vegas implied totals as a feature.

2. **Model training pipeline:**
   - `services/analytics/model_trainer.py` - Trains position-specific models.
   - Walk-forward cross-validation splitting by NFL week.
   - Hyperparameter tuning with grid search or Optuna.
   - Model versioning with timestamp and performance metrics.

3. **Model progression:**
   - Start with ridge regression baseline for each position.
   - Train random forest models and compare MAE.
   - Train gradient boosting models (XGBoost) as the production model.
   - Ensemble the top 2-3 models for final projections.

4. **Projection generation:**
   - `services/analytics/projector.py` - Generates weekly projections.
   - Store projections in the `projections` collection with confidence intervals.
   - Back-test against historical weeks to validate accuracy.

### Deliverables
- Trained models for QB, RB, WR, TE positions.
- Weekly projection generation pipeline.
- Model performance dashboard showing MAE and accuracy metrics.

## Phase 4: Decision Support (Weeks 11-14)

### Objective
Turn projections into actionable start/sit and waiver recommendations.

### Tasks

1. **Start/sit recommendations:**
   - Compare projected points for players at each roster slot.
   - Incorporate floor/ceiling analysis based on projection variance.
   - Matchup-adjusted recommendations with confidence levels.

2. **Waiver wire recommendations:**
   - Identify free agents with rising usage trends.
   - Score available players by projected ROS (rest of season) value.
   - Suggest drop candidates from the user's roster.

3. **Trade analyzer:**
   - Compare ROS projected value of players in a proposed trade.
   - Account for positional need and roster construction.
   - Flag lopsided trades with a fairness score.

4. **Notification system:**
   - Alert when a player's projection changes significantly.
   - Injury impact alerts with replacement suggestions.
   - Waiver priority recommendations before the waiver deadline.

### Deliverables
- Start/sit recommendation page with explanations.
- Waiver wire rankings with trend indicators.
- Trade analysis tool.

## Phase 5: Draft Tools (Weeks 15-18)

### Objective
Provide a draft assistant for live drafts and pre-draft preparation.

### Tasks

1. **Value-based draft rankings:**
   - Compute VORP for all draftable players.
   - Dynamic re-ranking as players are drafted.
   - Best available player recommendations per pick.

2. **ADP comparison tool:**
   - Overlay our VORP rankings against platform ADP.
   - Highlight value picks (positive ADP differential) and fades (negative).

3. **Mock draft simulator:**
   - Simulate drafts using ADP-based bot drafters.
   - Test different draft strategies and measure expected team strength.

4. **Live draft assistant:**
   - Real-time best-pick recommendations during a live draft.
   - Track drafted players and adjust rankings dynamically.
   - Positional need tracking based on current roster.

5. **Auction draft support:**
   - Dollar value projections derived from VORP.
   - Budget tracking and value alerts during live auctions.

### Deliverables
- Pre-draft rankings and value board.
- Live draft assistant interface.
- Mock draft simulator with strategy analysis.

## MongoDB Collection Schemas

### player_stats

```json
{
  "player_id": "string",
  "name": "string",
  "position": "string",
  "team": "string",
  "season": 2025,
  "games_played": 16,
  "fantasy_points_total": 245.6,
  "fantasy_points_ppg": 15.35,
  "passing": { "attempts": 540, "completions": 360, "yards": 4200, "tds": 30 },
  "rushing": { "attempts": 40, "yards": 180, "tds": 2 },
  "receiving": { "targets": 0, "receptions": 0, "yards": 0, "tds": 0 },
  "snap_pct": 0.98,
  "updated_at": "2025-01-15T10:00:00Z"
}
```

### weekly_scores

```json
{
  "player_id": "string",
  "season": 2025,
  "week": 10,
  "opponent": "KC",
  "home_away": "home",
  "fantasy_points": 18.4,
  "snap_pct": 0.95,
  "target_share": 0.22,
  "red_zone_targets": 2,
  "stats": { "receptions": 6, "rec_yards": 84, "rec_tds": 1 },
  "updated_at": "2025-11-12T08:00:00Z"
}
```

### projections

```json
{
  "player_id": "string",
  "season": 2025,
  "week": 11,
  "model_version": "xgb_v3_2025-11-10",
  "projected_points": 14.2,
  "floor": 8.5,
  "ceiling": 22.0,
  "confidence": 0.72,
  "features_used": ["snap_pct", "target_share", "opp_rank", "implied_total"],
  "created_at": "2025-11-10T06:00:00Z"
}
```

## Success Metrics

| Metric                          | Target              |
|---------------------------------|---------------------|
| Projection MAE (all positions)  | Under 5.0 points    |
| QB projection MAE               | Under 4.5 points    |
| RB projection MAE               | Under 5.5 points    |
| WR projection MAE               | Under 5.0 points    |
| TE projection MAE               | Under 4.0 points    |
| Start/sit accuracy              | Above 60%           |
| Data pipeline uptime            | 99% during season   |
| Weekly refresh latency          | Under 5 minutes     |

## Risk Mitigation

- **API changes:** Pin package versions and add integration tests that detect
  breaking changes early.
- **Data quality:** Validate row counts and null percentages after each ingestion.
  Alert on anomalies.
- **Model drift:** Track weekly MAE and retrain when performance degrades beyond
  a threshold.
- **Storage growth:** Index MongoDB collections on player_id + season + week.
  Archive play-by-play data older than 5 seasons.
