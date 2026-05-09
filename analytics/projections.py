"""Projection orchestrator: caching, risk adjustment, Monte Carlo simulation."""

import random

import numpy as np


def get_player_projection(db, player_id, season, week, risk_level="medium", model=None):
    """Get a player's projected points for a given week.

    Checks the projections cache first, runs model on cache miss.

    Args:
        db: MongoDB database instance
        player_id: nflverse player ID
        season: NFL season year
        week: week number
        risk_level: 'conservative', 'medium', or 'aggressive'
        model: trained PointProjector instance (or None)

    Returns:
        Dict with projected_points, confidence_low, confidence_high, display_points,
        or None if no model and no cache.
    """
    # Check cache
    cached = db["projections"].find_one({
        "player_id": player_id,
        "season": season,
        "week": week,
    })

    if cached:
        projection = {
            "projected_points": cached["projected_points"],
            "confidence_low": cached["confidence_low"],
            "confidence_high": cached["confidence_high"],
        }
    elif model is not None:
        projection = model.predict(db, player_id, season, week)
        if projection is None:
            return None
        # Cache the result
        db["projections"].update_one(
            {"player_id": player_id, "season": season, "week": week},
            {"$set": {
                "player_id": player_id,
                "season": season,
                "week": week,
                "projected_points": projection["projected_points"],
                "confidence_low": projection["confidence_low"],
                "confidence_high": projection["confidence_high"],
            }},
            upsert=True,
        )
    else:
        return None

    # Apply risk adjustment
    display_points = _apply_risk(projection, risk_level)

    return {
        "projected_points": projection["projected_points"],
        "confidence_low": projection["confidence_low"],
        "confidence_high": projection["confidence_high"],
        "display_points": display_points,
    }


def _apply_risk(projection, risk_level):
    """Adjust displayed projection based on risk preference."""
    if risk_level == "conservative":
        return projection["confidence_low"]
    elif risk_level == "aggressive":
        return projection["confidence_high"]
    return projection["projected_points"]


def get_remaining_season_projection(db, player_id, season, current_week,
                                     risk_level="medium", model=None, total_weeks=17):
    """Get week-by-week projections for remaining schedule.

    Returns dict with weekly list, remaining_total, season_total.
    """
    if model is None:
        return None

    result = model.predict_remaining_season(db, player_id, season, current_week, total_weeks)
    if result is None:
        return None

    # Add matchup context to each week
    from analytics.matchup_stats import get_upcoming_opponent, get_matchup_difficulty

    # Get player info
    player_doc = db["seasonal_stats"].find_one({"player_id": player_id, "season": season})
    team = player_doc.get("recent_team") if player_doc else None
    position = player_doc.get("position") if player_doc else None

    for week_proj in result["weekly"]:
        week_proj["opponent"] = None
        week_proj["matchup_label"] = None
        week_proj["home"] = None
        if team:
            opp_info = get_upcoming_opponent(db, team, season, week_proj["week"])
            if opp_info:
                week_proj["opponent"] = opp_info["opponent"]
                week_proj["home"] = opp_info["home"]
                if position:
                    diff = get_matchup_difficulty(db, opp_info["opponent"], position, season)
                    if diff:
                        week_proj["matchup_label"] = diff["label"]

    # Apply risk to totals
    if risk_level == "conservative":
        result["remaining_total"] = round(
            sum(w["confidence_low"] for w in result["weekly"]), 2
        )
    elif risk_level == "aggressive":
        result["remaining_total"] = round(
            sum(w["confidence_high"] for w in result["weekly"]), 2
        )

    # Recompute season total
    actual_docs = list(db["weekly_stats"].find(
        {"player_id": player_id, "season": season, "week": {"$lte": current_week}},
        {"fantasy_points_ppr": 1, "_id": 0},
    ))
    actual_total = sum(d.get("fantasy_points_ppr", 0) or 0 for d in actual_docs)
    result["season_total"] = round(actual_total + result["remaining_total"], 2)

    return result


def run_monte_carlo_simulation(db, player_id, season, current_week,
                                n_simulations=1000, model=None, total_weeks=17):
    """Simulate season outcomes using model predictions and historical variance.

    Returns dict with percentiles, histogram data, upside/bust probabilities.
    """
    if model is None:
        return None

    # Get actual points so far
    actual_docs = list(db["weekly_stats"].find(
        {"player_id": player_id, "season": season, "week": {"$lte": current_week}},
        {"fantasy_points_ppr": 1, "_id": 0},
    ))
    actual_total = sum(d.get("fantasy_points_ppr", 0) or 0 for d in actual_docs)

    # Get projections for remaining weeks
    remaining_weeks = []
    for week in range(current_week + 1, total_weeks + 1):
        pred = model.predict(db, player_id, season, week)
        if pred:
            remaining_weeks.append(pred)
        else:
            # Fallback
            pts = [d.get("fantasy_points_ppr", 0) or 0 for d in actual_docs] if actual_docs else [0]
            avg = sum(pts) / len(pts)
            remaining_weeks.append({
                "projected_points": avg,
                "confidence_low": max(0, avg * 0.6),
                "confidence_high": avg * 1.4,
            })

    if not remaining_weeks:
        return None

    # Run simulations
    rng = random.Random(42)
    season_totals = []

    for _ in range(n_simulations):
        sim_total = actual_total
        for week_pred in remaining_weeks:
            mid = week_pred["projected_points"]
            low = week_pred["confidence_low"]
            high = week_pred["confidence_high"]
            # Sample from a triangular distribution
            simulated = rng.triangular(low, high, mid)
            sim_total += max(0, simulated)
        season_totals.append(round(sim_total, 2))

    season_totals.sort()
    arr = np.array(season_totals)

    # Percentiles
    p10 = round(float(np.percentile(arr, 10)), 1)
    p25 = round(float(np.percentile(arr, 25)), 1)
    p50 = round(float(np.percentile(arr, 50)), 1)
    p75 = round(float(np.percentile(arr, 75)), 1)
    p90 = round(float(np.percentile(arr, 90)), 1)

    # Histogram bins
    n_bins = 20
    bin_min = float(arr.min())
    bin_max = float(arr.max())
    bin_width = (bin_max - bin_min) / n_bins if bin_max > bin_min else 1
    histogram = []
    for i in range(n_bins):
        bin_start = bin_min + i * bin_width
        bin_end = bin_start + bin_width
        if i == n_bins - 1:
            count = int(np.sum((arr >= bin_start) & (arr <= bin_end)))
        else:
            count = int(np.sum((arr >= bin_start) & (arr < bin_end)))
        histogram.append({
            "bin_start": round(bin_start, 1),
            "bin_end": round(bin_end, 1),
            "count": count,
        })

    # Upside/bust probabilities
    # "Upside" = exceeding p75 of preseason expectation (use p75 as threshold)
    # "Bust" = falling below p25
    upside_threshold = p75
    bust_threshold = p25
    upside_pct = round(float(np.sum(arr >= upside_threshold) / len(arr) * 100), 1)
    bust_pct = round(float(np.sum(arr <= bust_threshold) / len(arr) * 100), 1)

    return {
        "percentiles": {
            "p10": p10, "p25": p25, "p50": p50, "p75": p75, "p90": p90,
        },
        "histogram": histogram,
        "upside_pct": upside_pct,
        "bust_pct": bust_pct,
        "n_simulations": n_simulations,
        "actual_so_far": round(actual_total, 1),
    }


def batch_project_players(db, player_ids, season, week, model=None):
    """Batch project multiple players for a given week.

    Returns list of dicts with player_id and projection data.
    """
    results = []
    for player_id in player_ids:
        projection = get_player_projection(db, player_id, season, week, model=model)
        results.append({
            "player_id": player_id,
            "projection": projection,
        })
    return results
