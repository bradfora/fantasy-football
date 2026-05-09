"""Tests for ML models, projections, and matchup analysis."""

import os
import math

import mongomock
import numpy as np
import pytest

from analytics.models import PointProjector, PlayerClusterer, FEATURE_NAMES
from analytics.projections import (
    get_player_projection, get_remaining_season_projection,
    run_monte_carlo_simulation, batch_project_players,
)
from analytics.matchup_stats import (
    compute_defensive_rankings, get_upcoming_opponent, get_matchup_difficulty,
)


@pytest.fixture
def db():
    client = mongomock.MongoClient()
    database = client["models_test"]
    yield database
    client.close()


def _seed_training_data(db, seasons=None, n_players=6, weeks_per_season=10):
    """Seed multi-season data suitable for model training."""
    if seasons is None:
        seasons = [2023, 2024]
    positions = ["QB", "RB", "WR", "TE", "RB", "WR"]
    teams = ["KC", "BAL", "MIA", "KC", "BUF", "CIN"]

    for season in seasons:
        for i in range(n_players):
            pid = f"p{i+1}"
            name = f"Player {i+1}"
            pos = positions[i % len(positions)]
            team = teams[i % len(teams)]
            base_pts = 15 + i * 3

            # Seasonal stats
            total = base_pts * weeks_per_season
            db["seasonal_stats"].update_one(
                {"player_id": pid, "season": season},
                {"$set": {
                    "player_id": pid, "player_name": name, "position": pos,
                    "recent_team": team, "season": season,
                    "fantasy_points_ppr": total, "games": weeks_per_season,
                }},
                upsert=True,
            )

            # Weekly stats
            for week in range(1, weeks_per_season + 1):
                pts = base_pts + (week % 5) - 2
                db["weekly_stats"].update_one(
                    {"player_id": pid, "season": season, "week": week},
                    {"$set": {
                        "player_id": pid, "player_name": name, "position": pos,
                        "recent_team": team, "season": season, "week": week,
                        "opponent_team": f"OPP{week % 4}",
                        "fantasy_points_ppr": pts,
                    }},
                    upsert=True,
                )

            # Snap counts
            for week in range(1, weeks_per_season + 1):
                db["snap_counts"].update_one(
                    {"player": name, "season": season, "week": week},
                    {"$set": {
                        "player": name, "season": season, "week": week,
                        "offense_pct": 0.6 + (i * 0.05),
                    }},
                    upsert=True,
                )

    # Schedules
    for season in seasons:
        for week in range(1, weeks_per_season + 1):
            for j, (home, away) in enumerate([
                ("KC", "BAL"), ("MIA", "BUF"), ("CIN", "KC"),
                ("BAL", "MIA"),
            ]):
                db["schedules"].update_one(
                    {"game_id": f"{season}_{week}_{j}"},
                    {"$set": {
                        "game_id": f"{season}_{week}_{j}",
                        "season": season, "week": week,
                        "home_team": home, "away_team": away,
                    }},
                    upsert=True,
                )


@pytest.fixture
def db_with_training_data(db):
    _seed_training_data(db)
    return db


@pytest.fixture
def trained_projector(db_with_training_data):
    projector = PointProjector()
    projector.train(db_with_training_data, [2023, 2024])
    return projector


@pytest.fixture
def trained_clusterer(db_with_training_data):
    clusterer = PlayerClusterer(n_clusters=2)
    clusterer.train(db_with_training_data, 2024, "RB")
    return clusterer


# --- PointProjector tests ---


class TestPointProjector:
    def test_build_features_returns_complete_dict(self, db_with_training_data):
        projector = PointProjector()
        features = projector.build_features(db_with_training_data, "p1", 2024, 5)
        assert features is not None
        for name in FEATURE_NAMES:
            assert name in features, f"Missing feature: {name}"

    def test_build_features_insufficient_data_returns_none(self, db_with_training_data):
        projector = PointProjector()
        result = projector.build_features(db_with_training_data, "nonexistent", 2024, 5)
        assert result is None

    def test_build_features_too_few_weeks(self, db):
        """Player with only 1 week of data should return None."""
        db["weekly_stats"].insert_one({
            "player_id": "px", "player_name": "One Week", "position": "QB",
            "season": 2024, "week": 1, "fantasy_points_ppr": 20.0,
        })
        projector = PointProjector()
        result = projector.build_features(db, "px", 2024, 2)
        assert result is None

    def test_build_training_data_shape(self, db_with_training_data):
        projector = PointProjector()
        X, y, meta = projector.build_training_data(db_with_training_data, [2024])
        assert X.shape[0] == y.shape[0]
        assert X.shape[1] == len(FEATURE_NAMES)
        assert len(meta) == X.shape[0]
        assert X.shape[0] > 0

    def test_train_produces_metrics(self, db_with_training_data):
        projector = PointProjector()
        metrics = projector.train(db_with_training_data, [2023, 2024])
        assert "mae" in metrics
        assert "r2" in metrics
        assert "n_samples" in metrics
        assert metrics["n_samples"] > 0
        assert metrics["mae"] >= 0

    def test_predict_returns_projection_with_confidence(self, db_with_training_data, trained_projector):
        result = trained_projector.predict(db_with_training_data, "p1", 2024, 8)
        assert result is not None
        assert result["confidence_low"] <= result["projected_points"]
        assert result["projected_points"] <= result["confidence_high"]

    def test_predict_untrained_raises(self, db_with_training_data):
        projector = PointProjector()
        with pytest.raises(RuntimeError, match="not trained"):
            projector.predict(db_with_training_data, "p1", 2024, 5)

    def test_predict_remaining_season(self, db_with_training_data, trained_projector):
        result = trained_projector.predict_remaining_season(
            db_with_training_data, "p1", 2024, 5, total_weeks=10
        )
        assert "weekly" in result
        assert "remaining_total" in result
        assert "season_total" in result
        assert len(result["weekly"]) == 5  # weeks 6-10
        assert result["season_total"] >= result["remaining_total"]

    def test_save_and_load_roundtrip(self, db_with_training_data, trained_projector, tmp_path):
        path = str(tmp_path / "model.pkl")
        trained_projector.save(path)

        loaded = PointProjector()
        loaded.load(path)

        orig = trained_projector.predict(db_with_training_data, "p1", 2024, 8)
        reloaded = loaded.predict(db_with_training_data, "p1", 2024, 8)
        assert orig is not None and reloaded is not None
        assert abs(orig["projected_points"] - reloaded["projected_points"]) < 0.01

    def test_feature_importances_populated(self, db_with_training_data):
        projector = PointProjector()
        metrics = projector.train(db_with_training_data, [2023, 2024])
        importances = metrics["feature_importances"]
        for name in FEATURE_NAMES:
            assert name in importances
            assert importances[name] >= 0


# --- PlayerClusterer tests ---


class TestPlayerClusterer:
    def test_train_assigns_clusters(self, db_with_training_data):
        clusterer = PlayerClusterer(n_clusters=2)
        info = clusterer.train(db_with_training_data, 2024, "RB")
        assert len(info) == 2
        for cid, cluster in info.items():
            assert "label" in cluster
            assert "n_players" in cluster
            assert cluster["n_players"] > 0

    def test_classify_player(self, db_with_training_data, trained_clusterer):
        result = trained_clusterer.classify_player(db_with_training_data, "p2", 2024)
        assert result is not None
        assert "cluster_id" in result
        assert "cluster_label" in result
        assert "characteristics" in result

    def test_classify_unknown_player(self, db_with_training_data, trained_clusterer):
        result = trained_clusterer.classify_player(db_with_training_data, "nonexistent", 2024)
        assert result is None

    def test_get_similar_players(self, db_with_training_data, trained_clusterer):
        result = trained_clusterer.get_similar_players(db_with_training_data, "p2", 2024)
        assert isinstance(result, list)
        # All returned players should not include the query player
        for p in result:
            assert p["player_id"] != "p2"

    def test_save_and_load_roundtrip(self, db_with_training_data, trained_clusterer, tmp_path):
        path = str(tmp_path / "clusterer.pkl")
        trained_clusterer.save(path)

        loaded = PlayerClusterer()
        loaded.load(path)

        orig = trained_clusterer.classify_player(db_with_training_data, "p2", 2024)
        reloaded = loaded.classify_player(db_with_training_data, "p2", 2024)
        assert orig is not None and reloaded is not None
        assert orig["cluster_id"] == reloaded["cluster_id"]


# --- Projections tests ---


class TestProjections:
    def test_get_player_projection_computes_and_caches(self, db_with_training_data, trained_projector):
        result = get_player_projection(
            db_with_training_data, "p1", 2024, 8, model=trained_projector
        )
        assert result is not None
        assert "projected_points" in result
        assert "display_points" in result

        # Verify it was cached
        cached = db_with_training_data["projections"].find_one(
            {"player_id": "p1", "season": 2024, "week": 8}
        )
        assert cached is not None
        assert cached["projected_points"] == result["projected_points"]

    def test_get_player_projection_cache_hit(self, db):
        """Pre-seeded cache should be returned without needing a model."""
        db["projections"].insert_one({
            "player_id": "px", "season": 2024, "week": 5,
            "projected_points": 18.5,
            "confidence_low": 12.0,
            "confidence_high": 25.0,
        })
        result = get_player_projection(db, "px", 2024, 5, model=None)
        assert result is not None
        assert result["projected_points"] == 18.5

    def test_risk_level_ordering(self, db_with_training_data, trained_projector):
        conservative = get_player_projection(
            db_with_training_data, "p1", 2024, 8,
            risk_level="conservative", model=trained_projector,
        )
        medium = get_player_projection(
            db_with_training_data, "p1", 2024, 8,
            risk_level="medium", model=trained_projector,
        )
        aggressive = get_player_projection(
            db_with_training_data, "p1", 2024, 8,
            risk_level="aggressive", model=trained_projector,
        )
        assert conservative["display_points"] <= medium["display_points"]
        assert medium["display_points"] <= aggressive["display_points"]

    def test_remaining_season_projection_structure(self, db_with_training_data, trained_projector):
        result = get_remaining_season_projection(
            db_with_training_data, "p1", 2024, 5, model=trained_projector, total_weeks=10
        )
        assert result is not None
        assert "weekly" in result
        assert "remaining_total" in result
        assert "season_total" in result
        assert len(result["weekly"]) == 5

    def test_monte_carlo_percentile_ordering(self, db_with_training_data, trained_projector):
        result = run_monte_carlo_simulation(
            db_with_training_data, "p1", 2024, 5,
            n_simulations=500, model=trained_projector, total_weeks=10,
        )
        assert result is not None
        p = result["percentiles"]
        assert p["p10"] <= p["p25"] <= p["p50"] <= p["p75"] <= p["p90"]

    def test_monte_carlo_probabilities_valid(self, db_with_training_data, trained_projector):
        result = run_monte_carlo_simulation(
            db_with_training_data, "p1", 2024, 5,
            n_simulations=500, model=trained_projector, total_weeks=10,
        )
        assert 0 <= result["upside_pct"] <= 100
        assert 0 <= result["bust_pct"] <= 100

    def test_batch_project_players(self, db_with_training_data, trained_projector):
        result = batch_project_players(
            db_with_training_data, ["p1", "p2", "p3"], 2024, 8, model=trained_projector
        )
        assert len(result) == 3
        for r in result:
            assert "player_id" in r
            assert "projection" in r

    def test_projection_with_no_model_returns_none(self, db):
        result = get_player_projection(db, "p1", 2024, 5, model=None)
        assert result is None


# --- Matchup Stats tests ---


class TestMatchupStats:
    def test_compute_defensive_rankings_structure(self, db_with_training_data):
        rankings = compute_defensive_rankings(db_with_training_data, 2024)
        assert isinstance(rankings, dict)
        # Should have at least some teams
        assert len(rankings) > 0
        for team, positions in rankings.items():
            for pos, data in positions.items():
                assert "avg_allowed" in data
                assert "rank" in data
                assert "games" in data

    def test_get_upcoming_opponent(self, db_with_training_data):
        result = get_upcoming_opponent(db_with_training_data, "KC", 2024, 1)
        assert result is not None
        assert "opponent" in result
        assert "home" in result

    def test_get_upcoming_opponent_not_found(self, db):
        result = get_upcoming_opponent(db, "FAKE", 2024, 1)
        assert result is None

    def test_get_matchup_difficulty_labels(self, db_with_training_data):
        result = get_matchup_difficulty(
            db_with_training_data, "OPP0", "QB", 2024
        )
        if result is not None:
            assert result["label"] in ("easy", "medium", "hard")
            assert result["rank"] >= 1
            assert result["avg_allowed"] >= 0

    def test_matchup_with_missing_schedule(self, db):
        result = get_upcoming_opponent(db, "KC", 2024, 99)
        assert result is None
