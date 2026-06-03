"""
Train Model 1: Match Outcome Prediction (XGBoost classifier).

Time-based split:
  Train: 2008–2022, Validate: 2023, Test: 2024–2025

Usage:
    python -m ml.train.train_match_outcome
"""
import json
import time
import numpy as np
import pandas as pd
import joblib
from pathlib import Path

from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit
from sklearn.metrics import log_loss, accuracy_score, roc_auc_score
from xgboost import XGBClassifier

from ml.config import (
    MODELS_DIR, EVALUATION_DIR, FEATURES_DIR,
    TRAIN_SEASONS_END, VALIDATION_SEASON,
    N_RANDOM_SEARCH_ITER, RANDOM_STATE,
)

FEATURE_COLS = [
    "venue_id",
    "venue_boundary_distance_m", "venue_outfield_speed",
    "toss_winner_is_team1", "toss_decision_bat",
    "team1_win_pct_overall", "team2_win_pct_overall",
    "team1_win_pct_at_venue", "team2_win_pct_at_venue",
    "h2h_team1_win_pct",
    "team1_recent_form", "team2_recent_form",
    "venue_chasing_win_pct",
    "team1_is_home", "team2_is_home",
    # Differential / interaction features (key improvement)
    "win_pct_diff", "form_diff", "venue_pct_diff",
    "h2h_advantage", "team1_form_3", "team2_form_3",
    "form_diff_3", "toss_bat_venue_advantage", "home_advantage",
]

TARGET = "target"


def load_data():
    path = FEATURES_DIR / "data" / "match_features.csv"
    df = pd.read_csv(path, parse_dates=["match_date"])
    df["season"] = df["match_date"].dt.year
    return df


def split_data(df):
    train = df[df["season"] <= TRAIN_SEASONS_END]
    val = df[df["season"] == VALIDATION_SEASON]
    test = df[df["season"] > VALIDATION_SEASON]
    return train, val, test


def train_baseline(X_train, y_train, X_val, y_val):
    """Logistic Regression baseline."""
    lr = LogisticRegression(max_iter=1000, random_state=RANDOM_STATE)
    lr.fit(X_train, y_train)
    val_probs = lr.predict_proba(X_val)[:, 1]
    val_preds = lr.predict(X_val)
    print(f"  [Baseline LR] Accuracy: {accuracy_score(y_val, val_preds):.4f}, "
          f"Log-loss: {log_loss(y_val, val_probs):.4f}, "
          f"AUC: {roc_auc_score(y_val, val_probs):.4f}")
    return lr


def train_xgboost(X_train, y_train, X_val, y_val):
    """XGBoost with RandomizedSearchCV using TimeSeriesSplit."""
    param_grid = {
        "n_estimators": [100, 300, 500],
        "max_depth": [3, 5, 7],
        "learning_rate": [0.01, 0.05, 0.1],
        "subsample": [0.7, 0.8, 0.9],
        "colsample_bytree": [0.7, 0.8, 0.9],
        "min_child_weight": [1, 3, 5],
    }

    xgb = XGBClassifier(
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=RANDOM_STATE,
        n_jobs=1,
    )

    tscv = TimeSeriesSplit(n_splits=5)
    search = RandomizedSearchCV(
        xgb, param_grid,
        n_iter=N_RANDOM_SEARCH_ITER,
        cv=tscv,
        scoring="neg_log_loss",
        random_state=RANDOM_STATE,
        n_jobs=1,
        verbose=1,
    )
    search.fit(X_train, y_train)

    best = search.best_estimator_
    print(f"  Best params: {search.best_params_}")

    val_probs = best.predict_proba(X_val)[:, 1]
    val_preds = best.predict(X_val)
    print(f"  [XGBoost] Accuracy: {accuracy_score(y_val, val_preds):.4f}, "
          f"Log-loss: {log_loss(y_val, val_probs):.4f}, "
          f"AUC: {roc_auc_score(y_val, val_probs):.4f}")

    return best, search.best_params_


def evaluate_on_test(model, X_test, y_test, name="Model"):
    probs = model.predict_proba(X_test)[:, 1]
    preds = model.predict(X_test)
    acc = accuracy_score(y_test, preds)
    ll = log_loss(y_test, probs)
    auc = roc_auc_score(y_test, probs)
    print(f"  [{name} TEST] Accuracy: {acc:.4f}, Log-loss: {ll:.4f}, AUC: {auc:.4f}")
    return {"accuracy": acc, "log_loss": ll, "auc": auc}


def main():
    print("=" * 60)
    print("Training Model 1: Match Outcome Prediction")
    print("=" * 60)

    df = load_data()
    train_df, val_df, test_df = split_data(df)
    print(f"Train: {len(train_df)}, Val: {len(val_df)}, Test: {len(test_df)}")

    X_train, y_train = train_df[FEATURE_COLS], train_df[TARGET]
    X_val, y_val = val_df[FEATURE_COLS], val_df[TARGET]
    X_test, y_test = test_df[FEATURE_COLS], test_df[TARGET]

    # Baseline
    print("\n--- Baseline (Logistic Regression) ---")
    lr_model = train_baseline(X_train, y_train, X_val, y_val)

    # XGBoost
    print("\n--- XGBoost ---")
    t0 = time.time()
    xgb_model, best_params = train_xgboost(X_train, y_train, X_val, y_val)
    print(f"  Training time: {time.time()-t0:.1f}s")

    # Retrain on train+val with best params
    print("\n--- Retrain XGBoost on train+val ---")
    X_train_val = pd.concat([X_train, X_val])
    y_train_val = pd.concat([y_train, y_val])
    final_model = XGBClassifier(
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=RANDOM_STATE,
        n_jobs=1,
        **best_params,
    )
    final_model.fit(X_train_val, y_train_val)

    # Test evaluation
    print("\n--- Test Set Evaluation ---")
    test_metrics = evaluate_on_test(final_model, X_test, y_test, "XGBoost (final)")
    lr_test_metrics = evaluate_on_test(lr_model, X_test, y_test, "Logistic Regression")

    # Save model
    model_path = MODELS_DIR / "match_outcome.joblib"
    joblib.dump(final_model, model_path)
    print(f"\nModel saved: {model_path}")

    # Save feature list
    feature_list_path = MODELS_DIR / "match_outcome_features.json"
    with open(feature_list_path, "w") as f:
        json.dump(FEATURE_COLS, f)
    print(f"Feature list saved: {feature_list_path}")

    # Save evaluation report
    report = {
        "model": "match_outcome",
        "algorithm": "XGBoost",
        "best_params": {k: (int(v) if isinstance(v, (np.integer,)) else float(v) if isinstance(v, (np.floating,)) else v) for k, v in best_params.items()},
        "train_size": len(train_df),
        "val_size": len(val_df),
        "test_size": len(test_df),
        "test_metrics": {k: round(v, 4) for k, v in test_metrics.items()},
        "baseline_test_metrics": {k: round(v, 4) for k, v in lr_test_metrics.items()},
        "features": FEATURE_COLS,
    }
    report_path = EVALUATION_DIR / "match_outcome_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"Evaluation report saved: {report_path}")

    print("\n" + "=" * 60)
    print("Match Outcome model training complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
