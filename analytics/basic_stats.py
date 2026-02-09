"""Basic analytics: player rankings and scoring trends."""

import math

import pandas as pd


def get_top_scorers(db, season, position=None, scoring="fantasy_points_ppr", limit=20):
    """Get top fantasy scorers for a season.

    Args:
        db: MongoDB database instance
        season: NFL season year
        position: optional position filter (QB, RB, WR, TE)
        scoring: scoring column name
        limit: number of results

    Returns:
        List of dicts with player stats
    """
    query = {"season": season}
    if position:
        query["position"] = position

    cursor = db["seasonal_stats"].find(
        query,
        {"player_id": 1, "player_name": 1, "position": 1, "recent_team": 1,
         scoring: 1, "games": 1, "_id": 0},
    ).sort(scoring, -1).limit(limit)

    return list(cursor)


def get_player_weekly_trend(db, player_id, season, scoring="fantasy_points_ppr"):
    """Get a player's weekly scoring trend for a season.

    Args:
        db: MongoDB database instance
        player_id: nflverse player ID
        season: NFL season year
        scoring: scoring column name

    Returns:
        List of dicts with week and points
    """
    cursor = db["weekly_stats"].find(
        {"player_id": player_id, "season": season},
        {"week": 1, scoring: 1, "opponent_team": 1, "_id": 0},
    ).sort("week", 1)

    return list(cursor)


def get_positional_rankings(db, season, scoring="fantasy_points_ppr"):
    """Get top players by position for a season.

    Args:
        db: MongoDB database instance
        season: NFL season year
        scoring: scoring column name

    Returns:
        Dict of position -> list of top players
    """
    rankings = {}
    for pos in ["QB", "RB", "WR", "TE"]:
        rankings[pos] = get_top_scorers(db, season, position=pos, scoring=scoring, limit=10)
    return rankings


def compute_weekly_averages(db, season, position=None, min_games=6, scoring="fantasy_points_ppr"):
    """Compute average weekly fantasy points for players in a season.

    Args:
        db: MongoDB database instance
        season: NFL season year
        position: optional position filter
        min_games: minimum games played to be included
        scoring: scoring column name

    Returns:
        List of dicts with player averages, sorted descending
    """
    query = {"season": season}
    if position:
        query["position"] = position

    pipeline = [
        {"$match": query},
        {"$group": {
            "_id": {"player_id": "$player_id", "player_name": "$player_name", "position": "$position"},
            "avg_points": {"$avg": f"${scoring}"},
            "total_points": {"$sum": f"${scoring}"},
            "games": {"$sum": 1},
            "max_points": {"$max": f"${scoring}"},
            "min_points": {"$min": f"${scoring}"},
        }},
        {"$match": {"games": {"$gte": min_games}}},
        {"$sort": {"avg_points": -1}},
        {"$project": {
            "player_id": "$_id.player_id",
            "player_name": "$_id.player_name",
            "position": "$_id.position",
            "avg_points": {"$round": ["$avg_points", 1]},
            "total_points": {"$round": ["$total_points", 1]},
            "games": 1,
            "max_points": {"$round": ["$max_points", 1]},
            "min_points": {"$round": ["$min_points", 1]},
            "_id": 0,
        }},
    ]

    return list(db["weekly_stats"].aggregate(pipeline))


def get_player_summary(db, player_id, season, scoring="fantasy_points_ppr"):
    """Get a comprehensive summary for a single player.

    Returns a dict with season totals, weekly trend, consistency stats,
    and positional rank. Returns None if the player is not found.
    """
    seasonal = db["seasonal_stats"].find_one(
        {"player_id": player_id, "season": season}
    )
    if not seasonal:
        return None

    weekly = get_player_weekly_trend(db, player_id, season, scoring)
    points = [w.get(scoring, 0) or 0 for w in weekly]

    games = len(points) if points else (seasonal.get("games") or 0)
    total = seasonal.get(scoring, 0) or 0
    avg = total / games if games else 0
    floor = min(points) if points else 0
    ceiling = max(points) if points else 0
    std_dev = 0
    if len(points) > 1:
        mean = sum(points) / len(points)
        std_dev = math.sqrt(sum((p - mean) ** 2 for p in points) / len(points))
    last_3_avg = sum(points[-3:]) / len(points[-3:]) if points else 0

    position = seasonal.get("position")
    higher_count = db["seasonal_stats"].count_documents({
        "season": season,
        "position": position,
        scoring: {"$gt": total},
    })
    pos_rank = higher_count + 1

    return {
        "player_id": player_id,
        "player_name": seasonal.get("player_name"),
        "position": position,
        "recent_team": seasonal.get("recent_team"),
        "total_points": round(total, 1),
        "avg_points": round(avg, 1),
        "games": games,
        "floor": round(floor, 1),
        "ceiling": round(ceiling, 1),
        "std_dev": round(std_dev, 1),
        "last_3_avg": round(last_3_avg, 1),
        "pos_rank": pos_rank,
        "weekly": weekly,
    }


def get_position_averages(db, season, scoring="fantasy_points_ppr"):
    """Get average fantasy points per position for a season.

    Returns dict of position -> {"avg_points": X, "count": N}.
    """
    pipeline = [
        {"$match": {"season": season, "position": {"$in": ["QB", "RB", "WR", "TE"]}}},
        {"$group": {
            "_id": "$position",
            "avg_points": {"$avg": f"${scoring}"},
            "count": {"$sum": 1},
        }},
    ]
    results = db["seasonal_stats"].aggregate(pipeline)
    return {
        r["_id"]: {"avg_points": round(r["avg_points"], 1), "count": r["count"]}
        for r in results
    }


def analyze_roster(db, espn_roster, season, scoring="fantasy_points_ppr"):
    """Analyze an ESPN roster against NFL stats data.

    Args:
        db: MongoDB database instance
        espn_roster: list of dicts with keys: name, position, lineupSlot,
                     proTeam, total_points, avg_points
        season: NFL season year

    Returns:
        dict with "players" (list of player analysis dicts) and
        "suggestions" (list of suggestion strings)
    """
    players = []
    for p in espn_roster:
        name = p["name"]
        position = p["position"]
        lineup_slot = p["lineupSlot"]

        # Try to match to nfl_data_py stats by name and season
        stat = db["seasonal_stats"].find_one(
            {"player_name": name, "season": season}
        )

        analysis = {
            "name": name,
            "position": position,
            "lineup_slot": lineup_slot,
            "espn_total": p.get("total_points", 0),
            "espn_avg": p.get("avg_points", 0),
            "matched": stat is not None,
            "player_id": None,
            "season_points": None,
            "last_3_avg": None,
            "season_avg": None,
            "trend": None,
            "pos_rank": None,
        }

        if stat:
            player_id = stat["player_id"]
            analysis["player_id"] = player_id
            total = stat.get(scoring, 0) or 0
            analysis["season_points"] = round(total, 1)

            weekly = get_player_weekly_trend(db, player_id, season, scoring)
            points = [w.get(scoring, 0) or 0 for w in weekly]
            games = len(points) if points else 1
            season_avg = total / games if games else 0
            analysis["season_avg"] = round(season_avg, 1)

            if len(points) >= 3:
                last_3 = sum(points[-3:]) / 3
                analysis["last_3_avg"] = round(last_3, 1)
                if last_3 > season_avg * 1.15:
                    analysis["trend"] = "trending_up"
                elif last_3 < season_avg * 0.7:
                    analysis["trend"] = "trending_down"
                else:
                    analysis["trend"] = "steady"
            elif points:
                analysis["last_3_avg"] = round(sum(points) / len(points), 1)
                analysis["trend"] = "steady"

            higher_count = db["seasonal_stats"].count_documents({
                "season": season,
                "position": position,
                scoring: {"$gt": total},
            })
            analysis["pos_rank"] = higher_count + 1

        players.append(analysis)

    # Generate suggestions
    suggestions = []
    is_starter_slot = lambda slot: slot not in ("BE", "IR")
    starters = [p for p in players if is_starter_slot(p["lineup_slot"])]
    bench = [p for p in players if p["lineup_slot"] == "BE"]

    for bench_p in bench:
        if not bench_p["matched"] or bench_p["last_3_avg"] is None:
            continue
        for starter in starters:
            if starter["position"] != bench_p["position"]:
                continue
            if not starter["matched"] or starter["last_3_avg"] is None:
                continue
            if bench_p["last_3_avg"] > starter["last_3_avg"]:
                suggestions.append(
                    f"Consider starting {bench_p['name']} over {starter['name']} "
                    f"— {bench_p['name']} averaged {bench_p['last_3_avg']} pts over "
                    f"last 3 weeks vs {starter['name']}'s {starter['last_3_avg']}"
                )

    for starter in starters:
        if not starter["matched"] or starter["trend"] is None:
            continue
        if starter["trend"] == "trending_down":
            suggestions.append(
                f"{starter['name']} is trending down — last 3 weeks avg "
                f"({starter['last_3_avg']}) is below 70% of season avg "
                f"({starter['season_avg']})"
            )

    return {"players": players, "suggestions": suggestions}
