"""Basic analytics: player rankings and scoring trends."""

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
