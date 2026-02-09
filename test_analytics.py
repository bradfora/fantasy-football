from unittest.mock import patch, MagicMock

import mongomock
import pandas as pd
import pytest

from analytics.data_pipeline import fetch_seasonal_data, fetch_weekly_data, ingest_seasonal_stats, ingest_weekly_stats
from analytics.basic_stats import (
    get_top_scorers, get_player_weekly_trend, get_positional_rankings,
    get_player_summary, get_position_averages, analyze_roster,
)


@pytest.fixture
def db():
    client = mongomock.MongoClient()
    database = client["analytics_test"]
    yield database
    client.close()


@pytest.fixture
def db_with_seasonal_data(db):
    """Seed seasonal stats."""
    db["seasonal_stats"].insert_many([
        {"player_id": "p1", "player_name": "Patrick Mahomes", "position": "QB",
         "recent_team": "KC", "season": 2024, "fantasy_points_ppr": 350.0, "games": 17},
        {"player_id": "p2", "player_name": "Josh Allen", "position": "QB",
         "recent_team": "BUF", "season": 2024, "fantasy_points_ppr": 330.0, "games": 17},
        {"player_id": "p3", "player_name": "Derrick Henry", "position": "RB",
         "recent_team": "BAL", "season": 2024, "fantasy_points_ppr": 280.0, "games": 16},
        {"player_id": "p4", "player_name": "Tyreek Hill", "position": "WR",
         "recent_team": "MIA", "season": 2024, "fantasy_points_ppr": 260.0, "games": 17},
        {"player_id": "p5", "player_name": "Travis Kelce", "position": "TE",
         "recent_team": "KC", "season": 2024, "fantasy_points_ppr": 200.0, "games": 17},
    ])
    return db


@pytest.fixture
def db_with_weekly_data(db):
    """Seed weekly stats."""
    records = []
    for week in range(1, 4):
        records.append({
            "player_id": "p1", "player_name": "Patrick Mahomes", "position": "QB",
            "season": 2024, "week": week, "opponent_team": f"OPP{week}",
            "fantasy_points_ppr": 20.0 + week,
        })
    db["weekly_stats"].insert_many(records)
    return db


# --- Data pipeline tests ---


class TestDataPipeline:
    def test_fetch_seasonal_data_returns_dataframe(self):
        with patch("analytics.data_pipeline.nfl.import_seasonal_data") as mock:
            mock.return_value = pd.DataFrame({"player_id": ["p1"], "season": [2024]})
            result = fetch_seasonal_data([2024])
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1

    def test_fetch_weekly_data_returns_dataframe(self):
        with patch("analytics.data_pipeline.nfl.import_weekly_data") as mock:
            mock.return_value = pd.DataFrame({"player_id": ["p1"], "season": [2024], "week": [1]})
            result = fetch_weekly_data([2024])
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1

    def test_ingest_seasonal_stats(self, db):
        mock_df = pd.DataFrame({
            "player_id": ["p1", "p2"],
            "player_name": ["Player 1", "Player 2"],
            "season": [2024, 2024],
            "fantasy_points_ppr": [300.0, 250.0],
        })
        with patch("analytics.data_pipeline.fetch_seasonal_data", return_value=mock_df):
            count = ingest_seasonal_stats(db, [2024])
        assert count == 2
        assert db["seasonal_stats"].count_documents({}) == 2

    def test_ingest_seasonal_stats_upsert(self, db):
        mock_df = pd.DataFrame({
            "player_id": ["p1"],
            "player_name": ["Player 1"],
            "season": [2024],
            "fantasy_points_ppr": [300.0],
        })
        with patch("analytics.data_pipeline.fetch_seasonal_data", return_value=mock_df):
            ingest_seasonal_stats(db, [2024])
            ingest_seasonal_stats(db, [2024])  # second call should upsert
        assert db["seasonal_stats"].count_documents({}) == 1

    def test_ingest_seasonal_stats_empty(self, db):
        with patch("analytics.data_pipeline.fetch_seasonal_data", return_value=pd.DataFrame()):
            count = ingest_seasonal_stats(db, [2024])
        assert count == 0

    def test_ingest_weekly_stats(self, db):
        mock_df = pd.DataFrame({
            "player_id": ["p1", "p1"],
            "player_name": ["Player 1", "Player 1"],
            "season": [2024, 2024],
            "week": [1, 2],
            "fantasy_points_ppr": [25.0, 30.0],
        })
        with patch("analytics.data_pipeline.fetch_weekly_data", return_value=mock_df):
            count = ingest_weekly_stats(db, [2024])
        assert count == 2
        assert db["weekly_stats"].count_documents({}) == 2

    def test_ingest_handles_nan(self, db):
        mock_df = pd.DataFrame({
            "player_id": ["p1"],
            "player_name": ["Player 1"],
            "season": [2024],
            "fantasy_points_ppr": [float("nan")],
        })
        with patch("analytics.data_pipeline.fetch_seasonal_data", return_value=mock_df):
            count = ingest_seasonal_stats(db, [2024])
        assert count == 1
        doc = db["seasonal_stats"].find_one({"player_id": "p1"})
        assert doc["fantasy_points_ppr"] is None


# --- Basic stats tests ---


class TestBasicStats:
    def test_get_top_scorers(self, db_with_seasonal_data):
        result = get_top_scorers(db_with_seasonal_data, 2024, limit=3)
        assert len(result) == 3
        assert result[0]["player_name"] == "Patrick Mahomes"

    def test_get_top_scorers_by_position(self, db_with_seasonal_data):
        result = get_top_scorers(db_with_seasonal_data, 2024, position="QB")
        assert len(result) == 2
        assert all(r["position"] == "QB" for r in result)

    def test_get_top_scorers_empty_season(self, db_with_seasonal_data):
        result = get_top_scorers(db_with_seasonal_data, 2020)
        assert len(result) == 0

    def test_get_player_weekly_trend(self, db_with_weekly_data):
        result = get_player_weekly_trend(db_with_weekly_data, "p1", 2024)
        assert len(result) == 3
        assert result[0]["week"] == 1
        assert result[2]["week"] == 3

    def test_get_positional_rankings(self, db_with_seasonal_data):
        result = get_positional_rankings(db_with_seasonal_data, 2024)
        assert "QB" in result
        assert "RB" in result
        assert "WR" in result
        assert "TE" in result
        assert len(result["QB"]) == 2
        assert len(result["RB"]) == 1


@pytest.fixture
def db_with_full_data(db):
    """Seed both seasonal and weekly stats for comprehensive tests."""
    db["seasonal_stats"].insert_many([
        {"player_id": "p1", "player_name": "Patrick Mahomes", "position": "QB",
         "recent_team": "KC", "season": 2024, "fantasy_points_ppr": 350.0, "games": 17},
        {"player_id": "p2", "player_name": "Josh Allen", "position": "QB",
         "recent_team": "BUF", "season": 2024, "fantasy_points_ppr": 330.0, "games": 17},
        {"player_id": "p3", "player_name": "Derrick Henry", "position": "RB",
         "recent_team": "BAL", "season": 2024, "fantasy_points_ppr": 280.0, "games": 16},
        {"player_id": "p4", "player_name": "Tyreek Hill", "position": "WR",
         "recent_team": "MIA", "season": 2024, "fantasy_points_ppr": 260.0, "games": 17},
        {"player_id": "p5", "player_name": "Travis Kelce", "position": "TE",
         "recent_team": "KC", "season": 2024, "fantasy_points_ppr": 200.0, "games": 17},
    ])
    # Weekly data for p1 (6 weeks)
    for week in range(1, 7):
        db["weekly_stats"].insert_one({
            "player_id": "p1", "player_name": "Patrick Mahomes", "position": "QB",
            "season": 2024, "week": week, "opponent_team": f"OPP{week}",
            "fantasy_points_ppr": 20.0 + week,
        })
    # Weekly data for p3 (6 weeks, trending down)
    for week in range(1, 7):
        pts = 25.0 - week * 3 if week >= 4 else 25.0
        db["weekly_stats"].insert_one({
            "player_id": "p3", "player_name": "Derrick Henry", "position": "RB",
            "season": 2024, "week": week, "opponent_team": f"OPP{week}",
            "fantasy_points_ppr": pts,
        })
    return db


class TestPlayerSummary:
    def test_get_player_summary(self, db_with_full_data):
        result = get_player_summary(db_with_full_data, "p1", 2024)
        assert result is not None
        assert result["player_name"] == "Patrick Mahomes"
        assert result["position"] == "QB"
        assert result["games"] == 6
        assert result["pos_rank"] == 1
        assert len(result["weekly"]) == 6
        assert result["floor"] > 0
        assert result["ceiling"] > result["floor"]
        assert result["std_dev"] >= 0
        assert result["last_3_avg"] > 0

    def test_get_player_summary_not_found(self, db_with_full_data):
        result = get_player_summary(db_with_full_data, "nonexistent", 2024)
        assert result is None

    def test_get_position_averages(self, db_with_full_data):
        result = get_position_averages(db_with_full_data, 2024)
        assert "QB" in result
        assert "RB" in result
        assert "WR" in result
        assert "TE" in result
        assert result["QB"]["count"] == 2
        assert result["QB"]["avg_points"] > 0

    def test_analyze_roster(self, db_with_full_data):
        roster = [
            {"name": "Patrick Mahomes", "position": "QB", "lineupSlot": "QB",
             "proTeam": "KC", "total_points": 350.0, "avg_points": 20.6},
            {"name": "Unknown Player", "position": "WR", "lineupSlot": "WR",
             "proTeam": "NYG", "total_points": 50.0, "avg_points": 5.0},
        ]
        result = analyze_roster(db_with_full_data, roster, 2024)
        assert "players" in result
        assert "suggestions" in result
        assert len(result["players"]) == 2
        # First player should be matched
        assert result["players"][0]["matched"] is True
        assert result["players"][0]["player_id"] == "p1"
        # Second player should not be matched
        assert result["players"][1]["matched"] is False

    def test_analyze_roster_bench_over_starter(self, db_with_full_data):
        """Bench player with better recent form generates a swap suggestion."""
        # Add weekly data for p4 (bench player trending up)
        for week in range(1, 7):
            pts = 10.0 if week < 4 else 30.0
            db_with_full_data["weekly_stats"].insert_one({
                "player_id": "p4", "player_name": "Tyreek Hill", "position": "WR",
                "season": 2024, "week": week, "opponent_team": f"OPP{week}",
                "fantasy_points_ppr": pts,
            })
        # Add a weak starter WR with weekly data
        db_with_full_data["seasonal_stats"].insert_one({
            "player_id": "p6", "player_name": "Weak WR", "position": "WR",
            "recent_team": "NYG", "season": 2024, "fantasy_points_ppr": 100.0, "games": 17,
        })
        for week in range(1, 7):
            db_with_full_data["weekly_stats"].insert_one({
                "player_id": "p6", "player_name": "Weak WR", "position": "WR",
                "season": 2024, "week": week, "opponent_team": f"OPP{week}",
                "fantasy_points_ppr": 5.0,
            })

        roster = [
            {"name": "Weak WR", "position": "WR", "lineupSlot": "WR",
             "proTeam": "NYG", "total_points": 100.0, "avg_points": 5.9},
            {"name": "Tyreek Hill", "position": "WR", "lineupSlot": "BE",
             "proTeam": "MIA", "total_points": 260.0, "avg_points": 15.3},
        ]
        result = analyze_roster(db_with_full_data, roster, 2024)
        assert len(result["suggestions"]) > 0
        assert any("Consider starting Tyreek Hill over Weak WR" in s for s in result["suggestions"])
