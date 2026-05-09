"""ML models for player performance projection."""

import math
import pickle

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import RidgeCV
from sklearn.cluster import KMeans
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler

from analytics.matchup_stats import compute_defensive_rankings


FEATURE_NAMES = [
    "season_avg_points",
    "last_3_avg",
    "last_5_avg",
    "std_dev",
    "games_played",
    "snap_pct",
    "matchup_rank",
    "matchup_avg_allowed",
    "home_away",
    "career_avg",
]


class PointProjector:
    """Ridge Regression + Random Forest ensemble for projecting fantasy points."""

    def __init__(self):
        self._ridge = None
        self._rf = None
        self._scaler = None
        self._ridge_weight = 0.3
        self._rf_weight = 0.7
        self._trained = False
        self._feature_importances = None

    def build_features(self, db, player_id, season, week):
        """Build feature vector for a player-week prediction.

        Returns a dict of features or None if insufficient data.
        """
        weekly_docs = list(db["weekly_stats"].find(
            {"player_id": player_id, "season": season, "week": {"$lt": week}},
        ).sort("week", 1))

        if not weekly_docs:
            return None

        points = [w.get("fantasy_points_ppr", 0) or 0 for w in weekly_docs]
        games_played = len(points)

        if games_played < 2:
            return None

        season_avg = sum(points) / games_played
        last_3 = points[-3:] if len(points) >= 3 else points
        last_5 = points[-5:] if len(points) >= 5 else points
        last_3_avg = sum(last_3) / len(last_3)
        last_5_avg = sum(last_5) / len(last_5)
        mean = sum(points) / len(points)
        std_dev = math.sqrt(sum((p - mean) ** 2 for p in points) / len(points))

        # Snap percentage (average recent snap %)
        player_name = weekly_docs[0].get("player_name")
        snap_pct = 0.5  # default
        if player_name:
            snap_docs = list(db["snap_counts"].find(
                {"player": player_name, "season": season, "week": {"$lt": week}},
            ).sort("week", -1).limit(3))
            if snap_docs:
                snap_vals = [s.get("offense_pct", 0.5) or 0.5 for s in snap_docs]
                snap_pct = sum(snap_vals) / len(snap_vals)

        # Matchup data
        position = weekly_docs[0].get("position")
        team = weekly_docs[0].get("recent_team")
        matchup_rank = 16  # neutral default
        matchup_avg_allowed = season_avg
        home_away = 0.5  # unknown default

        from analytics.matchup_stats import get_upcoming_opponent, get_matchup_difficulty
        opponent_info = get_upcoming_opponent(db, team, season, week) if team else None
        if opponent_info:
            home_away = 1 if opponent_info["home"] else 0
            difficulty = get_matchup_difficulty(db, opponent_info["opponent"], position, season)
            if difficulty:
                matchup_rank = difficulty["rank"]
                matchup_avg_allowed = difficulty["avg_allowed"]

        # Career average
        career_docs = list(db["seasonal_stats"].find(
            {"player_id": player_id},
            {"fantasy_points_ppr": 1, "games": 1, "_id": 0},
        ))
        career_pts = 0
        career_games = 0
        for doc in career_docs:
            pts = doc.get("fantasy_points_ppr", 0) or 0
            gms = doc.get("games", 0) or 0
            career_pts += pts
            career_games += gms
        career_avg = career_pts / career_games if career_games > 0 else season_avg

        return {
            "season_avg_points": round(season_avg, 2),
            "last_3_avg": round(last_3_avg, 2),
            "last_5_avg": round(last_5_avg, 2),
            "std_dev": round(std_dev, 2),
            "games_played": games_played,
            "snap_pct": round(snap_pct, 4),
            "matchup_rank": matchup_rank,
            "matchup_avg_allowed": round(matchup_avg_allowed, 2),
            "home_away": home_away,
            "career_avg": round(career_avg, 2),
        }

    def build_training_data(self, db, seasons):
        """Build training arrays from historical data.

        Returns (X, y, metadata) where metadata contains player/week info.
        """
        X_rows = []
        y_values = []
        metadata = []

        for season in seasons:
            players = db["weekly_stats"].distinct("player_id", {"season": season})
            for player_id in players:
                weeks = db["weekly_stats"].find(
                    {"player_id": player_id, "season": season},
                    {"week": 1, "fantasy_points_ppr": 1, "_id": 0},
                ).sort("week", 1)
                week_list = list(weeks)

                for week_doc in week_list:
                    week = week_doc["week"]
                    actual = week_doc.get("fantasy_points_ppr", 0) or 0

                    features = self.build_features(db, player_id, season, week)
                    if features is None:
                        continue

                    row = [features[name] for name in FEATURE_NAMES]
                    X_rows.append(row)
                    y_values.append(actual)
                    metadata.append({
                        "player_id": player_id,
                        "season": season,
                        "week": week,
                    })

        X = np.array(X_rows, dtype=np.float64) if X_rows else np.empty((0, len(FEATURE_NAMES)))
        y = np.array(y_values, dtype=np.float64) if y_values else np.empty(0)
        return X, y, metadata

    def train(self, db, seasons):
        """Train the ensemble model on historical data.

        Returns dict with training metrics.
        """
        X, y, metadata = self.build_training_data(db, seasons)

        if len(X) < 10:
            raise ValueError(f"Insufficient training data: {len(X)} samples (need >= 10)")

        self._scaler = StandardScaler()
        X_scaled = self._scaler.fit_transform(X)

        # Train Ridge
        self._ridge = RidgeCV(alphas=[0.1, 1.0, 10.0, 100.0])
        self._ridge.fit(X_scaled, y)
        ridge_cv = cross_val_score(self._ridge, X_scaled, y, cv=min(5, len(X)), scoring="neg_mean_absolute_error")

        # Train Random Forest
        self._rf = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            min_samples_leaf=5,
            random_state=42,
            n_jobs=-1,
        )
        self._rf.fit(X_scaled, y)
        rf_cv = cross_val_score(self._rf, X_scaled, y, cv=min(5, len(X)), scoring="neg_mean_absolute_error")

        # Feature importances from RF
        self._feature_importances = dict(zip(FEATURE_NAMES, self._rf.feature_importances_))

        # Compute metrics on full training set
        ridge_pred = self._ridge.predict(X_scaled)
        rf_pred = self._rf.predict(X_scaled)
        ensemble_pred = self._ridge_weight * ridge_pred + self._rf_weight * rf_pred

        errors = y - ensemble_pred
        mae = float(np.mean(np.abs(errors)))
        rmse = float(np.sqrt(np.mean(errors ** 2)))
        ss_res = np.sum(errors ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r2 = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0

        self._trained = True

        return {
            "mae": round(mae, 3),
            "rmse": round(rmse, 3),
            "r2": round(r2, 4),
            "n_samples": len(X),
            "ridge_cv_mae": round(-float(np.mean(ridge_cv)), 3),
            "rf_cv_mae": round(-float(np.mean(rf_cv)), 3),
            "feature_importances": {k: round(v, 4) for k, v in self._feature_importances.items()},
        }

    def predict(self, db, player_id, season, week):
        """Predict fantasy points for a player-week.

        Returns dict with projected_points, confidence_low, confidence_high.
        """
        if not self._trained:
            raise RuntimeError("Model not trained. Call train() first.")

        features = self.build_features(db, player_id, season, week)
        if features is None:
            return None

        row = np.array([[features[name] for name in FEATURE_NAMES]])
        row_scaled = self._scaler.transform(row)

        ridge_pred = self._ridge.predict(row_scaled)[0]
        rf_pred = self._rf.predict(row_scaled)[0]
        projected = self._ridge_weight * ridge_pred + self._rf_weight * rf_pred

        # Confidence interval from RF tree prediction spread
        tree_preds = np.array([tree.predict(row_scaled)[0] for tree in self._rf.estimators_])
        tree_std = float(np.std(tree_preds))
        confidence_low = max(0, projected - 1.5 * tree_std)
        confidence_high = projected + 1.5 * tree_std

        return {
            "projected_points": round(float(projected), 2),
            "confidence_low": round(float(confidence_low), 2),
            "confidence_high": round(float(confidence_high), 2),
        }

    def predict_remaining_season(self, db, player_id, season, current_week, total_weeks=17):
        """Project points for remaining weeks of the season.

        Returns dict with weekly projections list, remaining_total, season_total.
        """
        if not self._trained:
            raise RuntimeError("Model not trained. Call train() first.")

        # Get actual points so far
        actual_docs = list(db["weekly_stats"].find(
            {"player_id": player_id, "season": season, "week": {"$lte": current_week}},
            {"week": 1, "fantasy_points_ppr": 1, "_id": 0},
        ).sort("week", 1))
        actual_total = sum(d.get("fantasy_points_ppr", 0) or 0 for d in actual_docs)

        weekly_projections = []
        remaining_total = 0

        for week in range(current_week + 1, total_weeks + 1):
            prediction = self.predict(db, player_id, season, week)
            if prediction:
                weekly_projections.append({
                    "week": week,
                    "projected_points": prediction["projected_points"],
                    "confidence_low": prediction["confidence_low"],
                    "confidence_high": prediction["confidence_high"],
                })
                remaining_total += prediction["projected_points"]
            else:
                # Fallback to last known average
                if actual_docs:
                    pts = [d.get("fantasy_points_ppr", 0) or 0 for d in actual_docs]
                    avg = sum(pts) / len(pts)
                else:
                    avg = 0
                weekly_projections.append({
                    "week": week,
                    "projected_points": round(avg, 2),
                    "confidence_low": round(max(0, avg * 0.6), 2),
                    "confidence_high": round(avg * 1.4, 2),
                })
                remaining_total += avg

        return {
            "weekly": weekly_projections,
            "remaining_total": round(remaining_total, 2),
            "season_total": round(actual_total + remaining_total, 2),
        }

    def save(self, path):
        """Save the trained model to a pickle file."""
        with open(path, "wb") as f:
            pickle.dump({
                "ridge": self._ridge,
                "rf": self._rf,
                "scaler": self._scaler,
                "ridge_weight": self._ridge_weight,
                "rf_weight": self._rf_weight,
                "feature_importances": self._feature_importances,
                "trained": self._trained,
            }, f)

    def load(self, path):
        """Load a trained model from a pickle file."""
        with open(path, "rb") as f:
            data = pickle.load(f)
        self._ridge = data["ridge"]
        self._rf = data["rf"]
        self._scaler = data["scaler"]
        self._ridge_weight = data["ridge_weight"]
        self._rf_weight = data["rf_weight"]
        self._feature_importances = data["feature_importances"]
        self._trained = data["trained"]


CLUSTER_FEATURE_NAMES = [
    "avg_points", "std_dev", "floor", "ceiling", "snap_pct_avg", "consistency_score",
]

# Archetypes assigned based on cluster center characteristics
_ARCHETYPE_RULES = [
    ("High-Floor Consistent", lambda c: c["consistency_score"] < 0.35 and c["floor"] > 0.5),
    ("Boom-or-Bust", lambda c: c["std_dev"] > 0.6 and c["consistency_score"] > 0.5),
    ("Volume-Dependent", lambda c: c["snap_pct_avg"] > 0.6 and c["avg_points"] > 0.4),
    ("Matchup-Sensitive", lambda c: c["std_dev"] > 0.4),
]


class PlayerClusterer:
    """K-Means clustering for player archetypes by position."""

    def __init__(self, n_clusters=4):
        self.n_clusters = n_clusters
        self._kmeans = None
        self._scaler = None
        self._trained = False
        self._cluster_labels = {}
        self._cluster_centers_raw = None
        self._player_data = []
        self._position = None

    def _build_player_features(self, db, season, position):
        """Build feature matrix for clustering players of a given position."""
        pipeline = [
            {"$match": {"season": season, "position": position}},
            {"$group": {
                "_id": "$player_id",
                "player_name": {"$first": "$player_name"},
                "avg_points": {"$avg": "$fantasy_points_ppr"},
                "floor": {"$min": "$fantasy_points_ppr"},
                "ceiling": {"$max": "$fantasy_points_ppr"},
                "games": {"$sum": 1},
                "points_list": {"$push": "$fantasy_points_ppr"},
            }},
            {"$match": {"games": {"$gte": 6}}},
        ]
        results = list(db["weekly_stats"].aggregate(pipeline))

        player_data = []
        for r in results:
            player_id = r["_id"]
            avg = r["avg_points"] or 0
            points_list = [p or 0 for p in r.get("points_list", [])]

            # Compute std dev in Python (mongomock doesn't support $stdDevPop)
            if len(points_list) > 1:
                mean = sum(points_list) / len(points_list)
                std = math.sqrt(sum((p - mean) ** 2 for p in points_list) / len(points_list))
            else:
                std = 0

            consistency = std / avg if avg > 0 else 1.0

            # Get snap percentage
            player_name = r.get("player_name", "")
            snap_docs = list(db["snap_counts"].find(
                {"player": player_name, "season": season},
            ))
            player_snaps = [s.get("offense_pct", 0.5) or 0.5 for s in snap_docs]
            snap_pct_avg = sum(player_snaps) / len(player_snaps) if player_snaps else 0.5

            player_data.append({
                "player_id": player_id,
                "player_name": player_name,
                "avg_points": round(avg, 2),
                "std_dev": round(std, 2),
                "floor": round(r["floor"] or 0, 2),
                "ceiling": round(r["ceiling"] or 0, 2),
                "snap_pct_avg": round(snap_pct_avg, 4),
                "consistency_score": round(consistency, 4),
            })

        return player_data

    def _assign_cluster_labels(self, centers_normalized):
        """Assign interpretable labels to clusters based on center characteristics."""
        labels = {}
        used_labels = set()

        for cluster_id in range(self.n_clusters):
            center = dict(zip(CLUSTER_FEATURE_NAMES, centers_normalized[cluster_id]))
            assigned = False
            for label, rule in _ARCHETYPE_RULES:
                if label not in used_labels and rule(center):
                    labels[cluster_id] = label
                    used_labels.add(label)
                    assigned = True
                    break
            if not assigned:
                labels[cluster_id] = f"Archetype {cluster_id + 1}"

        return labels

    def train(self, db, season, position):
        """Train the clusterer for a specific position.

        Returns dict with cluster info.
        """
        self._position = position
        player_data = self._build_player_features(db, season, position)

        if len(player_data) < self.n_clusters:
            raise ValueError(
                f"Not enough players ({len(player_data)}) for {self.n_clusters} clusters"
            )

        X = np.array([
            [p[name] for name in CLUSTER_FEATURE_NAMES]
            for p in player_data
        ])

        self._scaler = StandardScaler()
        X_scaled = self._scaler.fit_transform(X)

        actual_clusters = min(self.n_clusters, len(player_data))
        self._kmeans = KMeans(n_clusters=actual_clusters, random_state=42, n_init=10)
        self._kmeans.fit(X_scaled)

        # Store raw centers (inverse-transformed)
        self._cluster_centers_raw = self._scaler.inverse_transform(self._kmeans.cluster_centers_)

        # Normalized centers for label assignment (0-1 range per feature)
        mins = X.min(axis=0)
        maxs = X.max(axis=0)
        ranges = maxs - mins
        ranges[ranges == 0] = 1
        centers_norm = (self._cluster_centers_raw - mins) / ranges
        self._cluster_labels = self._assign_cluster_labels(centers_norm)

        # Store player data with cluster assignments
        self._player_data = []
        for i, p in enumerate(player_data):
            p["cluster_id"] = int(self._kmeans.labels_[i])
            p["cluster_label"] = self._cluster_labels[p["cluster_id"]]
            self._player_data.append(p)

        self._trained = True

        cluster_info = {}
        for cid, label in self._cluster_labels.items():
            members = [p for p in self._player_data if p["cluster_id"] == cid]
            center = dict(zip(CLUSTER_FEATURE_NAMES, [round(v, 2) for v in self._cluster_centers_raw[cid]]))
            cluster_info[cid] = {
                "label": label,
                "center": center,
                "n_players": len(members),
            }

        return cluster_info

    def classify_player(self, db, player_id, season):
        """Classify a player into a cluster.

        Returns dict with cluster_id, cluster_label, characteristics.
        """
        if not self._trained:
            raise RuntimeError("Clusterer not trained. Call train() first.")

        # Check if player is in cached data
        for p in self._player_data:
            if p["player_id"] == player_id:
                center = dict(zip(
                    CLUSTER_FEATURE_NAMES,
                    [round(v, 2) for v in self._cluster_centers_raw[p["cluster_id"]]],
                ))
                return {
                    "cluster_id": p["cluster_id"],
                    "cluster_label": p["cluster_label"],
                    "characteristics": {k: p[k] for k in CLUSTER_FEATURE_NAMES},
                    "cluster_center": center,
                }

        return None

    def get_similar_players(self, db, player_id, season, limit=5):
        """Find similar players in the same cluster.

        Returns list of player dicts from the same cluster.
        """
        if not self._trained:
            raise RuntimeError("Clusterer not trained. Call train() first.")

        classification = self.classify_player(db, player_id, season)
        if classification is None:
            return []

        cluster_id = classification["cluster_id"]
        similar = [
            {"player_id": p["player_id"], "player_name": p["player_name"],
             "avg_points": p["avg_points"], "cluster_label": p["cluster_label"]}
            for p in self._player_data
            if p["cluster_id"] == cluster_id and p["player_id"] != player_id
        ]
        return similar[:limit]

    def save(self, path):
        """Save the trained clusterer to a pickle file."""
        with open(path, "wb") as f:
            pickle.dump({
                "kmeans": self._kmeans,
                "scaler": self._scaler,
                "trained": self._trained,
                "cluster_labels": self._cluster_labels,
                "cluster_centers_raw": self._cluster_centers_raw,
                "player_data": self._player_data,
                "position": self._position,
                "n_clusters": self.n_clusters,
            }, f)

    def load(self, path):
        """Load a trained clusterer from a pickle file."""
        with open(path, "rb") as f:
            data = pickle.load(f)
        self._kmeans = data["kmeans"]
        self._scaler = data["scaler"]
        self._trained = data["trained"]
        self._cluster_labels = data["cluster_labels"]
        self._cluster_centers_raw = data["cluster_centers_raw"]
        self._player_data = data["player_data"]
        self._position = data["position"]
        self.n_clusters = data["n_clusters"]
