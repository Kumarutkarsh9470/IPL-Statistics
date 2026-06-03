"""
FastAPI application entry point.
Loads all ML models into memory at startup for fast inference.

Start with (from project root):
    uvicorn ml.serve:app --host 0.0.0.0 --port 8000
"""
import json
from pathlib import Path
from contextlib import asynccontextmanager

import joblib
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ml.config import MODELS_DIR, DB_CONFIG
from ml.db_connect import load_teams, load_venues, load_players


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load models and lookup data at startup."""
    print("Loading ML models into memory...")

    # Load models
    app.state.match_model = _safe_load(MODELS_DIR / "match_outcome.joblib")
    app.state.score_model = _safe_load(MODELS_DIR / "score_predictor.joblib")
    app.state.batting_model = _safe_load(MODELS_DIR / "player_batting.joblib")
    app.state.bowling_model = _safe_load(MODELS_DIR / "player_bowling.joblib")

    # Load metadata (feature lists, residual stds)
    app.state.match_features = _safe_load_json(MODELS_DIR / "match_outcome_features.json")
    app.state.score_meta = _safe_load_json(MODELS_DIR / "score_predictor_meta.json")
    app.state.batting_meta = _safe_load_json(MODELS_DIR / "player_batting_meta.json")
    app.state.bowling_meta = _safe_load_json(MODELS_DIR / "player_bowling_meta.json")

    # Load lookup tables from DB
    try:
        app.state.teams_df = load_teams()
        app.state.venues_df = load_venues()
        app.state.players_df = load_players()
        print(f"  Loaded {len(app.state.teams_df)} teams, "
              f"{len(app.state.venues_df)} venues, "
              f"{len(app.state.players_df)} players")
    except Exception as e:
        print(f"  WARNING: Could not load lookup tables from DB: {e}")
        app.state.teams_df = pd.DataFrame(columns=["team_id", "team_name"])
        app.state.venues_df = pd.DataFrame(columns=["venue_id", "venue_name", "city", "boundary_distance_m", "outfield_speed"])
        app.state.players_df = pd.DataFrame(columns=["player_id", "player_name", "batting_style", "bowling_arm", "bowling_type"])

    # Load pre-computed feature lookups if available
    lookup_path = MODELS_DIR / "feature_lookups.joblib"
    if lookup_path.exists():
        app.state.feature_lookups = joblib.load(lookup_path)
        print("  Loaded pre-computed feature lookups")
    else:
        app.state.feature_lookups = {}
        print("  No pre-computed feature lookups found (will use defaults)")

    print("All models loaded. Server ready.")
    yield
    print("Shutting down...")


def _safe_load(path: Path):
    if path.exists():
        model = joblib.load(path)
        print(f"  Loaded: {path.name}")
        return model
    print(f"  WARNING: {path.name} not found")
    return None


def _safe_load_json(path: Path):
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


app = FastAPI(
    title="IPL Predictions API",
    description="ML-powered predictions for IPL matches, scores, and player performance",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow browser calls from XAMPP (port 80) and common dev origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://127.0.0.1",
        "http://localhost:80",
        "http://127.0.0.1:80",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and include route modules
from ml.routes import match_predict, score_predict, player_predict, chase_predict, top_performers_predict

app.include_router(match_predict.router, prefix="/api/predict")
app.include_router(score_predict.router, prefix="/api/predict")
app.include_router(player_predict.router, prefix="/api/predict")
app.include_router(chase_predict.router, prefix="/api/predict")
app.include_router(top_performers_predict.router, prefix="/api/predict")


@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "models_loaded": {
            "match_outcome": app.state.match_model is not None,
            "score_predictor": app.state.score_model is not None,
            "player_batting": app.state.batting_model is not None,
            "player_bowling": app.state.bowling_model is not None,
        },
        "prediction_endpoints": [
            "POST /api/predict/match",
            "POST /api/predict/score",
            "POST /api/predict/player",
            "POST /api/predict/chase",
            "POST /api/predict/top-performers",
        ],
    }
