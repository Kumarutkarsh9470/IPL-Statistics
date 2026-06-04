"""
Generate mock ML models for testing deployment.
These are placeholder models with correct structure.
Replace with real trained models after training on actual data.

Usage:
    python ml/generate_mock_models.py
"""
import json
import joblib
from pathlib import Path
from sklearn.linear_model import LogisticRegression
from sklearn.linear_model import LinearRegression
import numpy as np

MODELS_DIR = Path(__file__).parent / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

print("Generating mock ML models for testing...")

# ============ MATCH OUTCOME MODEL ============
# Mock match outcome predictor (binary: team1 wins or not)
match_features = [
    "venue_id", "venue_boundary_distance_m", "venue_outfield_speed",
    "toss_winner_is_team1", "toss_decision_bat",
    "team1_win_pct_overall", "team2_win_pct_overall",
    "team1_win_pct_at_venue", "team2_win_pct_at_venue",
    "h2h_team1_win_pct",
    "team1_recent_form", "team2_recent_form",
    "venue_chasing_win_pct",
    "team1_is_home", "team2_is_home",
    "win_pct_diff", "form_diff", "venue_pct_diff",
    "h2h_advantage", "team1_form_3", "team2_form_3",
    "form_diff_3", "toss_bat_venue_advantage", "home_advantage",
]

# Create mock model with correct number of features
X_dummy = np.random.randn(100, len(match_features))
y_dummy = np.random.randint(0, 2, 100)
match_model = LogisticRegression(random_state=42)
match_model.fit(X_dummy, y_dummy)
joblib.dump(match_model, MODELS_DIR / "match_outcome.joblib")
print(f"✓ match_outcome.joblib ({len(match_features)} features)")

match_meta = {
    "features": match_features,
    "feature_count": len(match_features),
    "residual_std": 0.15,  # Typical for binary classification
}
with open(MODELS_DIR / "match_outcome_features.json", "w") as f:
    json.dump(match_meta, f, indent=2)
print("✓ match_outcome_features.json")

# ============ SCORE PREDICTOR MODEL ============
# Mock score predictor (regression: predict total runs)
score_features = [
    "venue_id", "venue_boundary_distance_m", "venue_outfield_speed",
    "team_batting_id", "team_bowling_id",
    "team_avg_runs_at_venue", "team_avg_runs_overall",
    "opposition_avg_conceded_at_venue", "opposition_avg_conceded_overall",
    "team_form_runs", "opposition_form_runs_conceded",
    "venue_avg_runs", "toss_decision_bat",
]

X_dummy_score = np.random.randn(100, len(score_features))
y_dummy_score = np.random.uniform(120, 220, 100)  # Typical IPL scores
score_model = LinearRegression()
score_model.fit(X_dummy_score, y_dummy_score)
joblib.dump(score_model, MODELS_DIR / "score_predictor.joblib")
print(f"✓ score_predictor.joblib ({len(score_features)} features)")

score_meta = {
    "features": score_features,
    "feature_count": len(score_features),
    "residual_std": 18.5,  # Typical for score prediction
}
with open(MODELS_DIR / "score_predictor_meta.json", "w") as f:
    json.dump(score_meta, f, indent=2)
print("✓ score_predictor_meta.json")

# ============ PLAYER BATTING MODEL ============
# Mock player batting predictor (regression: runs scored)
batting_features = [
    "player_id", "team_id", "opposition_id", "venue_id",
    "player_avg_runs", "player_strike_rate",
    "opposition_avg_conceded_at_venue",
    "team_form_runs", "venue_avg_runs",
]

X_dummy_bat = np.random.randn(100, len(batting_features))
y_dummy_bat = np.random.uniform(0, 80, 100)
batting_model = LinearRegression()
batting_model.fit(X_dummy_bat, y_dummy_bat)
joblib.dump(batting_model, MODELS_DIR / "player_batting.joblib")
print(f"✓ player_batting.joblib ({len(batting_features)} features)")

batting_meta = {
    "features": batting_features,
    "feature_count": len(batting_features),
    "residual_std": 12.3,
}
with open(MODELS_DIR / "player_batting_meta.json", "w") as f:
    json.dump(batting_meta, f, indent=2)
print("✓ player_batting_meta.json")

# ============ PLAYER BOWLING MODEL ============
# Mock player bowling predictor (regression: wickets taken)
bowling_features = [
    "player_id", "team_id", "opposition_id", "venue_id",
    "player_avg_wickets", "player_economy",
    "opposition_avg_runs_scored",
    "team_form_wickets", "venue_avg_wickets",
]

X_dummy_bowl = np.random.randn(100, len(bowling_features))
y_dummy_bowl = np.random.uniform(0, 4, 100)
bowling_model = LinearRegression()
bowling_model.fit(X_dummy_bowl, y_dummy_bowl)
joblib.dump(bowling_model, MODELS_DIR / "player_bowling.joblib")
print(f"✓ player_bowling.joblib ({len(bowling_features)} features)")

bowling_meta = {
    "features": bowling_features,
    "feature_count": len(bowling_features),
    "residual_std": 0.95,
}
with open(MODELS_DIR / "player_bowling_meta.json", "w") as f:
    json.dump(bowling_meta, f, indent=2)
print("✓ player_bowling_meta.json")

print("\n✅ All mock models generated successfully!")
print(f"📂 Models directory: {MODELS_DIR}")
print("\n⚠️  IMPORTANT: These are placeholder models for testing only.")
print("Replace with real trained models after training on actual IPL data.")
