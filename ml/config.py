"""
Centralized configuration for IPL ML pipeline.

This module defines all configuration constants used across the ML subsystem:
- Database connection parameters
- Model and artifact paths
- Training hyperparameters and strategies
- Feature engineering constants
- Match stage and team metadata

All credentials should ideally be loaded from environment variables (.env file)
in production environments for security.

Usage:
    from ml.config import DB_CONFIG, MODELS_DIR, RANDOM_STATE
    
    # Use in your code
    engine_url = f"mysql+mysqlconnector://{DB_CONFIG['user']}:{DB_CONFIG['password']}"...

Configuration Details:
    - Time-based split: Train on past seasons, validate on most recent, test on future
    - Feature windows: Short (5) for recent form, Long (10) for seasonal trends
    - Match stages: League→Qualifier→Eliminator→Final (used for feature engineering)
    - Random state: 42 (for reproducibility across runs)
"""
from pathlib import Path
from typing import Dict, List
import os

# --- Paths ---
ML_DIR: Path = Path(__file__).resolve().parent
PROJECT_ROOT: Path = ML_DIR.parent
MODELS_DIR: Path = ML_DIR / "models"
FEATURES_DIR: Path = ML_DIR / "features"
EVALUATION_DIR: Path = ML_DIR / "evaluation"

# Ensure directories exist
MODELS_DIR.mkdir(parents=True, exist_ok=True)
EVALUATION_DIR.mkdir(parents=True, exist_ok=True)

# --- Database Configuration ---
# Can be overridden via environment variables (.env file)
DB_CONFIG: Dict[str, str] = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "ipl_user"),
    "password": os.getenv("DB_PASSWORD", "password123"),
    "database": os.getenv("DB_NAME", "ipl_db"),
}

# --- Training Data Split (Time-Based) ---
# No temporal data leakage: Train < Val < Test chronologically
TRAIN_SEASONS_END: int = 2022
"""Train on matches up to and including 2022 season."""

VALIDATION_SEASON: int = 2023
"""Validate on 2023 season matches to tune hyperparameters."""

# TEST_SEASON: 2024+ (all matches after VALIDATION_SEASON)
"""Test on 2024–2025 matches (computed dynamically in trainers)."""

# --- Model Hyperparameter Search ---
N_RANDOM_SEARCH_ITER: int = 50
"""Number of iterations for RandomizedSearchCV during hyperparameter tuning."""

RANDOM_STATE: int = 42
"""Random seed for reproducibility across all ML operations."""

# --- Feature Engineering Parameters ---
ROLLING_WINDOW_SHORT: int = 5
"""Short rolling window (matches) for recent form features.
   Provides responsiveness to short-term performance changes.
"""

ROLLING_WINDOW_LONG: int = 10
"""Long rolling window (matches) for seasonal trend features.
   Captures more stable performance patterns.
"""

MIN_INNINGS_FOR_RELIABLE: int = 5
"""Minimum innings required before considering a player's stats reliable.
   Avoids noise from limited sample sizes.
"""

# --- Match Stage Mapping ---
# Used to encode match stage as a numeric feature for tree-based models
MATCH_STAGE_MAP: Dict[str, int] = {
    "league": 0,
    "qualifier": 1,
    "eliminator": 2,
    "final": 3,
}
"""Encodes match stages for feature engineering. Higher values = higher importance."""

# --- Team Home Venues ---
# Approximate home cities for teams (multiple aliases for venue matching flexibility)
TEAM_HOME_CITIES: Dict[str, List[str]] = {
    "Mumbai Indians": ["Mumbai"],
    "Chennai Super Kings": ["Chennai"],
    "Royal Challengers Bengaluru": ["Bengaluru", "Bangalore"],
    "Kolkata Knight Riders": ["Kolkata"],
    "Sunrisers Hyderabad": ["Hyderabad"],
    "Rajasthan Royals": ["Jaipur"],
    "Delhi Capitals": ["Delhi"],
    "Punjab Kings": ["Mohali", "Chandigarh", "Dharamsala"],
    "Gujarat Titans": ["Ahmedabad"],
    "Lucknow Super Giants": ["Lucknow"],
}
