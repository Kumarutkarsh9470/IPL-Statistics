"""
Train Model 3: Player Performance Prediction.
  3A: Batting — predict runs scored (XGBoost regressor)
  3B: Bowling — predict wickets taken (XGBoost regressor)

Time-based split:
  Train: 2008–2022, Validate: 2023, Test: 2024–2025

Usage:
    python -m ml.train.train_player_perf
"""
import json
import time
import numpy as np
import pandas as pd
import joblib

from sklearn.linear_model import Ridge
from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor

from ml.config import (
    MODELS_DIR, EVALUATION_DIR, FEATURES_DIR,
    TRAIN_SEASONS_END, VALIDATION_SEASON,
    N_RANDOM_SEARCH_ITER, RANDOM_STATE,
)

BATTING_FEATURES = [
    "venue_id", "batting_team_id", "bowling_team_id",
    "venue_boundary_distance_m", "venue_outfield_speed", "batting_style_left",
    "batting_position",
    "rolling_avg_runs_5", "rolling_sr_5", "rolling_avg_runs_10",
    "career_avg_at_venue", "career_avg_vs_opposition", "career_sr",
    "innings_count", "days_since_last_match",
    "is_home", "toss_elected_bat", "is_debut",
    # New features
    "rolling_boundary_rate_5", "consistency_score", "opp_bowling_quality",
]
BATTING_TARGET = "runs_scored"

BOWLING_FEATURES = [
    "venue_id", "batting_team_id", "bowling_team_id",
    "venue_boundary_distance_m", "venue_outfield_speed", "bowling_arm_left", "bowling_type_spin",
    "rolling_avg_wickets_5", "rolling_economy_5", "rolling_avg_wickets_10",
    "career_avg_wickets_at_venue", "career_economy",
    "overs_bowled_career", "dot_ball_pct_rolling_5",
    "innings_count", "days_since_last_match",
    # New features
    "career_strike_rate", "rolling_wicket_rate_5", "opp_batting_quality",
]
BOWLING_TARGET = "wickets_taken"


def load_data(kind: str):
    if kind == "batting":
        path = FEATURES_DIR / "data" / "batting_features.csv"
    else:
        path = FEATURES_DIR / "data" / "bowling_features.csv"
    df = pd.read_csv(path, parse_dates=["match_date"])
    df["season"] = df["match_date"].dt.year
    return df


def split_data(df):
    train = df[df["season"] <= TRAIN_SEASONS_END]
    val = df[df["season"] == VALIDATION_SEASON]
    test = df[df["season"] > VALIDATION_SEASON]
    return train, val, test


def train_model(X_train, y_train, X_val, y_val, model_name):
    """Train XGBoost with hyperparameter search + Ridge baseline."""
    # Baseline
    ridge = Ridge(alpha=1.0)
    ridge.fit(X_train, y_train)
    val_preds_ridge = ridge.predict(X_val)
    print(f"  [Baseline Ridge] MAE: {mean_absolute_error(y_val, val_preds_ridge):.2f}")

    # XGBoost
    param_grid = {
        "n_estimators": [100, 300, 500],
        "max_depth": [3, 5, 7],
        "learning_rate": [0.01, 0.05, 0.1],
        "subsample": [0.7, 0.8, 0.9],
        "colsample_bytree": [0.7, 0.8, 0.9],
        "min_child_weight": [1, 3, 5],
    }

    xgb = XGBRegressor(
        objective="reg:squarederror",
        random_state=RANDOM_STATE,
        n_jobs=1,
    )

    tscv = TimeSeriesSplit(n_splits=5)
    search = RandomizedSearchCV(
        xgb, param_grid,
        n_iter=min(N_RANDOM_SEARCH_ITER, 30),  # Fewer iters for player models
        cv=tscv,
        scoring="neg_mean_absolute_error",
        random_state=RANDOM_STATE,
        n_jobs=1,
        verbose=1,
    )
    search.fit(X_train, y_train)

    best = search.best_estimator_
    print(f"  Best params: {search.best_params_}")

    val_preds = best.predict(X_val)
    print(f"  [XGBoost] MAE: {mean_absolute_error(y_val, val_preds):.2f}, "
          f"RMSE: {np.sqrt(mean_squared_error(y_val, val_preds)):.2f}")

    return best, search.best_params_


def evaluate_on_test(model, X_test, y_test, name="Model"):
    preds = model.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    rmse = np.sqrt(mean_squared_error(y_test, preds))
    r2 = r2_score(y_test, preds)
    print(f"  [{name} TEST] MAE: {mae:.2f}, RMSE: {rmse:.2f}, R²: {r2:.4f}")
    return {"mae": round(mae, 4), "rmse": round(rmse, 4), "r2": round(r2, 4)}


def train_and_save(kind: str, features: list, target: str, model_filename: str):
    print(f"\n{'='*60}")
    print(f"Training Player {kind.title()} Model")
    print(f"{'='*60}")

    df = load_data(kind)
    train_df, val_df, test_df = split_data(df)
    print(f"Train: {len(train_df)}, Val: {len(val_df)}, Test: {len(test_df)}")

    X_train, y_train = train_df[features], train_df[target]
    X_val, y_val = val_df[features], val_df[target]
    X_test, y_test = test_df[features], test_df[target]

    t0 = time.time()
    xgb_model, best_params = train_model(X_train, y_train, X_val, y_val, kind)
    print(f"  Training time: {time.time()-t0:.1f}s")

    # Retrain on train+val
    X_tv = pd.concat([X_train, X_val])
    y_tv = pd.concat([y_train, y_val])
    final_model = XGBRegressor(
        objective="reg:squarederror",
        random_state=RANDOM_STATE,
        n_jobs=1,
        **best_params,
    )
    final_model.fit(X_tv, y_tv)

    # Test
    print("\n--- Test Set ---")
    test_metrics = evaluate_on_test(final_model, X_test, y_test, f"XGBoost {kind}")

    # Residual std for prediction intervals
    train_preds = final_model.predict(X_tv)
    residual_std = float(np.std(y_tv.values - train_preds))

    # Save
    model_path = MODELS_DIR / model_filename
    joblib.dump(final_model, model_path)
    print(f"Model saved: {model_path}")

    meta = {"features": features, "residual_std": round(residual_std, 2)}
    meta_path = MODELS_DIR / model_filename.replace(".joblib", "_meta.json")
    with open(meta_path, "w") as f:
        json.dump(meta, f)

    report = {
        "model": model_filename.replace(".joblib", ""),
        "algorithm": "XGBoost",
        "best_params": {k: (int(v) if isinstance(v, (np.integer,)) else float(v) if isinstance(v, (np.floating,)) else v) for k, v in best_params.items()},
        "train_size": len(train_df),
        "val_size": len(val_df),
        "test_size": len(test_df),
        "test_metrics": test_metrics,
        "residual_std": round(residual_std, 2),
        "features": features,
    }
    report_path = EVALUATION_DIR / f"{model_filename.replace('.joblib', '')}_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"Report saved: {report_path}")

    return final_model


def main():
    # 3A: Batting
    train_and_save(
        kind="batting",
        features=BATTING_FEATURES,
        target=BATTING_TARGET,
        model_filename="player_batting.joblib",
    )

    # 3B: Bowling
    train_and_save(
        kind="bowling",
        features=BOWLING_FEATURES,
        target=BOWLING_TARGET,
        model_filename="player_bowling.joblib",
    )

    print("\n" + "=" * 60)
    print("All player performance models trained!")
    print("=" * 60)


if __name__ == "__main__":
    main()
