"""
Train Model 2: Mid-Match Score Prediction (20 * run rate + simple ML adjustment).

Time-based split:
  Train: 2008–2022, Validate: 2023, Test: 2024–2025

Usage:
    python -m ml.train.train_score_predictor
"""
import json
import numpy as np
import pandas as pd
import joblib
from pathlib import Path

from sklearn.linear_model import Ridge
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from ml.config import (
    MODELS_DIR, EVALUATION_DIR, FEATURES_DIR,
    TRAIN_SEASONS_END, VALIDATION_SEASON,
    RANDOM_STATE,
)

FEATURE_COLS = [
    "current_over",
    "boundaries_so_far",
    "extras_so_far",
    "wickets_fallen_so_far",
]

BASE_COEFFICIENT = 20.0

TARGET = "target_total"


def load_data():
    path = FEATURES_DIR / "data" / "innings_features.csv"
    df = pd.read_csv(path, parse_dates=["match_date"])
    df["season"] = df["match_date"].dt.year
    return df


def split_data(df):
    train = df[df["season"] <= TRAIN_SEASONS_END]
    val = df[df["season"] == VALIDATION_SEASON]
    test = df[df["season"] > VALIDATION_SEASON]
    return train, val, test


def _make_model():
    return Pipeline([
        ("scaler", StandardScaler()),
        ("ridge", Ridge(random_state=RANDOM_STATE)),
    ])


def train_baseline(X_train, y_train, X_val, y_val):
    """Simple Ridge baseline on the same adjustment target."""
    ridge = _make_model()
    ridge.fit(X_train, y_train)
    val_preds = ridge.predict(X_val)
    print(f"  [Baseline Ridge] MAE: {mean_absolute_error(y_val, val_preds):.2f}, "
          f"RMSE: {np.sqrt(mean_squared_error(y_val, val_preds)):.2f}, "
          f"R²: {r2_score(y_val, val_preds):.4f}")
    return ridge


def train_ridge(X_train, y_train, X_val, y_val):
    """Ridge regression with light alpha search."""
    param_grid = {
        "ridge__alpha": [1.0, 3.0, 10.0, 30.0, 100.0],
    }

    ridge = _make_model()
    tscv = TimeSeriesSplit(n_splits=5)
    search = GridSearchCV(
        ridge,
        param_grid,
        cv=tscv,
        scoring="neg_mean_absolute_error",
        n_jobs=1,
    )
    search.fit(X_train, y_train)

    best = search.best_estimator_
    print(f"  Best params: {search.best_params_}")

    val_preds = best.predict(X_val)
    print(f"  [Ridge] MAE: {mean_absolute_error(y_val, val_preds):.2f}, "
          f"RMSE: {np.sqrt(mean_squared_error(y_val, val_preds)):.2f}, "
          f"R²: {r2_score(y_val, val_preds):.4f}")

    return best, search.best_params_


def evaluate_on_test(model, X_test, y_test, test_df, name="Model"):
    preds = model.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    rmse = np.sqrt(mean_squared_error(y_test, preds))
    r2 = r2_score(y_test, preds)
    print(f"  [{name} TEST] MAE: {mae:.2f}, RMSE: {rmse:.2f}, R²: {r2:.4f}")

    # Per-over MAE
    per_over = {}
    for over in sorted(test_df["current_over"].unique()):
        mask = test_df["current_over"] == over
        if mask.sum() > 0:
            over_mae = mean_absolute_error(y_test[mask], preds[mask])
            per_over[int(over)] = round(over_mae, 2)
    print(f"  Per-over MAE: {per_over}")

    return {"mae": mae, "rmse": rmse, "r2": r2, "per_over_mae": per_over}


def main():
    print("=" * 60)
    print("Training Model 2: Mid-Match Score Prediction")
    print("=" * 60)

    df = load_data()
    train_df, val_df, test_df = split_data(df)
    print(f"Train: {len(train_df)}, Val: {len(val_df)}, Test: {len(test_df)}")

    X_train, y_train = train_df[FEATURE_COLS], train_df[TARGET]
    X_val, y_val = val_df[FEATURE_COLS], val_df[TARGET]
    X_test, y_test = test_df[FEATURE_COLS], test_df[TARGET]

    train_base = BASE_COEFFICIENT * train_df["current_run_rate"]
    val_base = BASE_COEFFICIENT * val_df["current_run_rate"]
    test_base = BASE_COEFFICIENT * test_df["current_run_rate"]

    y_train_adjustment = train_df[TARGET] - train_base
    y_val_adjustment = val_df[TARGET] - val_base
    y_test_adjustment = test_df[TARGET] - test_base

    # Baseline
    print("\n--- Baseline (Ridge Regression) ---")
    ridge_model = train_baseline(X_train, y_train_adjustment, X_val, y_val_adjustment)

    # Ridge
    print("\n--- Ridge Regression ---")
    final_model, best_params = train_ridge(X_train, y_train_adjustment, X_val, y_val_adjustment)

    # Retrain on train+val
    print("\n--- Retrain Ridge on train+val ---")
    X_train_val = pd.concat([X_train, X_val])
    y_train_val = pd.concat([y_train_adjustment, y_val_adjustment])
    final_model = _make_model()
    final_model.set_params(**best_params)
    final_model.fit(X_train_val, y_train_val)

    # Test evaluation
    print("\n--- Test Set Evaluation ---")
    test_preds = final_model.predict(X_test) + test_base
    mae = mean_absolute_error(y_test, test_preds)
    rmse = np.sqrt(mean_squared_error(y_test, test_preds))
    r2 = r2_score(y_test, test_preds)
    print(f"  [Hybrid (final) TEST] MAE: {mae:.2f}, RMSE: {rmse:.2f}, R²: {r2:.4f}")

    # Per-over MAE
    per_over = {}
    for over in sorted(test_df["current_over"].unique()):
        mask = test_df["current_over"] == over
        if mask.sum() > 0:
            over_mae = mean_absolute_error(y_test[mask], test_preds[mask])
            per_over[int(over)] = round(over_mae, 2)
    print(f"  Per-over MAE: {per_over}")

    test_metrics = {"mae": mae, "rmse": rmse, "r2": r2, "per_over_mae": per_over}

    # Compute residual distribution for prediction intervals
    train_preds = final_model.predict(X_train_val) + (BASE_COEFFICIENT * pd.concat([train_df, val_df])["current_run_rate"])
    residuals = pd.concat([train_df, val_df])[TARGET].values - train_preds
    residual_std = float(np.std(residuals))

    # Save model
    model_path = MODELS_DIR / "score_predictor.joblib"
    joblib.dump(final_model, model_path)
    print(f"\nModel saved: {model_path}")

    # Save feature list + residual stats
    meta = {
        "features": FEATURE_COLS,
        "residual_std": round(residual_std, 2),
        "base_coefficient": BASE_COEFFICIENT,
    }
    meta_path = MODELS_DIR / "score_predictor_meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f)
    print(f"Metadata saved: {meta_path}")

    # Save evaluation report
    report = {
        "model": "score_predictor",
        "algorithm": "HybridLinear",
        "formula": "predicted_total = 20 * current_run_rate + ridge_adjustment",
        "best_params": {k: (int(v) if isinstance(v, (np.integer,)) else float(v) if isinstance(v, (np.floating,)) else v) for k, v in best_params.items()},
        "train_size": len(train_df),
        "val_size": len(val_df),
        "test_size": len(test_df),
        "test_metrics": {k: round(v, 4) if isinstance(v, float) else v for k, v in test_metrics.items()},
        "residual_std": round(residual_std, 2),
        "features": FEATURE_COLS,
    }
    report_path = EVALUATION_DIR / "score_predictor_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"Evaluation report saved: {report_path}")

    print("\n" + "=" * 60)
    print("Score Predictor model training complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
