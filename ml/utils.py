"""Shared utility functions for encoding, validation, and helpers."""
import numpy as np
import pandas as pd
from ml.config import MATCH_STAGE_MAP, TEAM_HOME_CITIES


def encode_match_stage(stage: str) -> int:
    """Convert match stage string to ordinal."""
    return MATCH_STAGE_MAP.get(stage.lower().strip(), 0)


def is_home_city(team_name: str, city: str) -> int:
    """Check if a team is playing in their home city."""
    if not city or not team_name:
        return 0
    home_cities = TEAM_HOME_CITIES.get(team_name, [])
    return int(any(hc.lower() in city.lower() for hc in home_cities))


def safe_divide(numerator, denominator, default=0.0):
    """Safe division that returns default on zero/NaN."""
    if denominator == 0 or pd.isna(denominator):
        return default
    return numerator / denominator


def compute_expanding_mean(df: pd.DataFrame, group_col: str, value_col: str) -> pd.Series:
    """
    For each row, compute the expanding mean of value_col within group_col,
    using only rows BEFORE the current one (shift(1)).
    DataFrame must already be sorted by date.
    """
    return (
        df.groupby(group_col)[value_col]
        .transform(lambda x: x.expanding().mean().shift(1))
    )


def compute_rolling_mean(df: pd.DataFrame, group_col: str, value_col: str, window: int) -> pd.Series:
    """
    Rolling mean within group, shifted by 1 to prevent leakage.
    """
    return (
        df.groupby(group_col)[value_col]
        .transform(lambda x: x.rolling(window, min_periods=1).mean().shift(1))
    )


def confidence_label(probability: float) -> str:
    """Map a win probability to a confidence label."""
    diff = abs(probability - 0.5)
    if diff < 0.05:
        return "low"
    elif diff < 0.15:
        return "medium"
    else:
        return "high"


def sanitize_model_input(X: pd.DataFrame, numeric_defaults: dict | None = None) -> pd.DataFrame:
    """
    Ensure model input has numeric dtypes where possible.
    This prevents runtime XGBoost errors when DB values arrive as object strings.
    """
    clean = X.copy()

    for col in clean.columns:
        if pd.api.types.is_object_dtype(clean[col]) or pd.api.types.is_string_dtype(clean[col]):
            clean[col] = pd.to_numeric(clean[col], errors="coerce")

    if numeric_defaults:
        for col, default in numeric_defaults.items():
            if col in clean.columns:
                clean[col] = clean[col].fillna(default)

    return clean
