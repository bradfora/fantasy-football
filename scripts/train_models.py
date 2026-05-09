"""CLI script to train ML models for player performance projections."""

import argparse
import os
import sys
from urllib.parse import quote_plus

from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

load_dotenv()

from analytics.models import PointProjector, PlayerClusterer
from db import get_db


def _build_uri():
    """Build MongoDB URI from env vars, falling back to credentials if needed."""
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        username = os.environ.get("MONGO_USERNAME")
        password = os.environ.get("MONGO_PASSWORD")
        if username and password:
            uri = (
                f"mongodb://{quote_plus(username)}:{quote_plus(password)}"
                f"@localhost:27017/fantasy_football?authSource=admin"
            )
    return uri


def main():
    parser = argparse.ArgumentParser(description="Train ML models for player projections")
    parser.add_argument(
        "--seasons",
        type=int,
        nargs="+",
        required=True,
        help="NFL seasons to train on (e.g., --seasons 2022 2023)",
    )
    parser.add_argument(
        "--evaluate-on",
        type=int,
        default=None,
        help="Optional hold-out season for evaluation (e.g., --evaluate-on 2024)",
    )
    parser.add_argument(
        "--output-dir",
        default="models",
        help="Directory to save trained models (default: models/)",
    )
    args = parser.parse_args()

    db = get_db(uri=_build_uri())
    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    # Train PointProjector
    print(f"Training PointProjector on seasons: {args.seasons}")
    projector = PointProjector()
    metrics = projector.train(db, args.seasons)
    print(f"  Training metrics:")
    print(f"    MAE: {metrics['mae']}")
    print(f"    RMSE: {metrics['rmse']}")
    print(f"    R2: {metrics['r2']}")
    print(f"    Samples: {metrics['n_samples']}")
    print(f"    Ridge CV MAE: {metrics['ridge_cv_mae']}")
    print(f"    RF CV MAE: {metrics['rf_cv_mae']}")
    print(f"  Feature importances:")
    for feat, imp in sorted(metrics["feature_importances"].items(), key=lambda x: -x[1]):
        print(f"    {feat}: {imp}")

    projector_path = os.path.join(output_dir, "point_projector.pkl")
    projector.save(projector_path)
    print(f"  Saved to {projector_path}")

    # Evaluate on hold-out season if specified
    if args.evaluate_on:
        print(f"\nEvaluating on season {args.evaluate_on}...")
        eval_projector = PointProjector()
        eval_projector.load(projector_path)
        X_eval, y_eval, meta_eval = eval_projector.build_training_data(db, [args.evaluate_on])
        if len(X_eval) > 0:
            import numpy as np
            X_scaled = eval_projector._scaler.transform(X_eval)
            ridge_pred = eval_projector._ridge.predict(X_scaled)
            rf_pred = eval_projector._rf.predict(X_scaled)
            ensemble_pred = eval_projector._ridge_weight * ridge_pred + eval_projector._rf_weight * rf_pred
            errors = y_eval - ensemble_pred
            eval_mae = float(np.mean(np.abs(errors)))
            eval_rmse = float(np.sqrt(np.mean(errors ** 2)))
            ss_res = np.sum(errors ** 2)
            ss_tot = np.sum((y_eval - np.mean(y_eval)) ** 2)
            eval_r2 = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0
            print(f"  Evaluation metrics ({args.evaluate_on}):")
            print(f"    MAE: {eval_mae:.3f}")
            print(f"    RMSE: {eval_rmse:.3f}")
            print(f"    R2: {eval_r2:.4f}")
            print(f"    Samples: {len(X_eval)}")
        else:
            print(f"  No evaluation data found for season {args.evaluate_on}")

    # Store model metadata in MongoDB
    db["model_metadata"].update_one(
        {"model_name": "point_projector", "season": max(args.seasons)},
        {"$set": {
            "model_name": "point_projector",
            "season": max(args.seasons),
            "training_seasons": args.seasons,
            "metrics": metrics,
        }},
        upsert=True,
    )

    # Train PlayerClusterer for each position
    print("\nTraining PlayerClusterer for each position...")
    for position in ["QB", "RB", "WR", "TE"]:
        print(f"  Training clusterer for {position}...")
        clusterer = PlayerClusterer()
        try:
            cluster_info = clusterer.train(db, max(args.seasons), position)
            clusterer_path = os.path.join(output_dir, f"clusterer_{position.lower()}.pkl")
            clusterer.save(clusterer_path)
            print(f"    Saved to {clusterer_path}")
            for cid, info in cluster_info.items():
                print(f"    Cluster {cid}: {info['label']} ({info['n_players']} players)")

            db["model_metadata"].update_one(
                {"model_name": f"clusterer_{position.lower()}", "season": max(args.seasons)},
                {"$set": {
                    "model_name": f"clusterer_{position.lower()}",
                    "season": max(args.seasons),
                    "cluster_info": {str(k): v for k, v in cluster_info.items()},
                }},
                upsert=True,
            )
        except ValueError as e:
            print(f"    Skipped: {e}")

    print("\nDone.")


if __name__ == "__main__":
    main()
