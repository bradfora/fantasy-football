"""Matchup analysis: defensive rankings and opponent difficulty."""


def compute_defensive_rankings(db, season):
    """Compute average fantasy points allowed per team per position.

    Aggregates weekly_stats to find how many PPR points each team allows
    to each opposing position.

    Args:
        db: MongoDB database instance
        season: NFL season year

    Returns:
        Dict of {team: {position: {avg_allowed, rank, games}}}
    """
    pipeline = [
        {"$match": {"season": season, "opponent_team": {"$ne": None},
                     "position": {"$in": ["QB", "RB", "WR", "TE"]}}},
        {"$group": {
            "_id": {"opponent": "$opponent_team", "position": "$position"},
            "avg_allowed": {"$avg": "$fantasy_points_ppr"},
            "total_allowed": {"$sum": "$fantasy_points_ppr"},
            "games": {"$sum": 1},
        }},
        {"$sort": {"avg_allowed": -1}},
    ]

    results = list(db["weekly_stats"].aggregate(pipeline))

    # Organize by team and position
    team_stats = {}
    for r in results:
        team = r["_id"]["opponent"]
        position = r["_id"]["position"]
        if team not in team_stats:
            team_stats[team] = {}
        team_stats[team][position] = {
            "avg_allowed": round(r["avg_allowed"], 2),
            "total_allowed": round(r["total_allowed"], 1),
            "games": r["games"],
        }

    # Compute ranks per position (1 = most points allowed = easiest matchup)
    for position in ["QB", "RB", "WR", "TE"]:
        teams_for_pos = [
            (team, stats[position]["avg_allowed"])
            for team, stats in team_stats.items()
            if position in stats
        ]
        teams_for_pos.sort(key=lambda x: x[1], reverse=True)
        for rank, (team, _) in enumerate(teams_for_pos, 1):
            team_stats[team][position]["rank"] = rank

    return team_stats


def get_upcoming_opponent(db, team, season, week):
    """Look up the opponent for a team in a given week from the schedules collection.

    Args:
        db: MongoDB database instance
        team: NFL team abbreviation (e.g. 'KC')
        season: NFL season year
        week: week number

    Returns:
        Dict with opponent info {opponent, home} or None if not found
    """
    game = db["schedules"].find_one({
        "season": season,
        "week": week,
        "home_team": team,
    })
    if game:
        return {"opponent": game.get("away_team"), "home": True}

    game = db["schedules"].find_one({
        "season": season,
        "week": week,
        "away_team": team,
    })
    if game:
        return {"opponent": game.get("home_team"), "home": False}

    return None


def get_matchup_difficulty(db, opponent_team, position, season):
    """Get matchup difficulty rating against a specific opponent and position.

    Args:
        db: MongoDB database instance
        opponent_team: NFL team abbreviation of the opponent
        position: offensive position (QB, RB, WR, TE)
        season: NFL season year

    Returns:
        Dict with {avg_allowed, rank, label} or None if data unavailable.
        Label is 'easy', 'medium', or 'hard' based on rank terciles.
    """
    rankings = compute_defensive_rankings(db, season)

    team_data = rankings.get(opponent_team)
    if not team_data or position not in team_data:
        return None

    pos_data = team_data[position]
    rank = pos_data.get("rank", 16)

    # Count total teams for this position to compute terciles
    total_teams = sum(
        1 for t in rankings.values() if position in t
    )
    tercile = total_teams / 3

    if rank <= tercile:
        label = "easy"
    elif rank <= 2 * tercile:
        label = "medium"
    else:
        label = "hard"

    return {
        "avg_allowed": pos_data["avg_allowed"],
        "rank": rank,
        "label": label,
    }
