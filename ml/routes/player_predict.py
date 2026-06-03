"""
Route handler for Model 3: Player Performance Prediction.
POST /api/predict/player
"""
import numpy as np
import pandas as pd
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from ml.utils import sanitize_model_input

router = APIRouter()


class PlayerPredictRequest(BaseModel):
    player_name: str
    role: str = Field(..., pattern="^(batting|bowling)$")
    venue_id: int
    opposition_team_id: int
    match_stage: str = "league"


class RecentForm(BaseModel):
    last_5_avg: Optional[float] = None
    last_5_sr: Optional[float] = None
    last_5_economy: Optional[float] = None


class VenueHistory(BaseModel):
    innings_at_venue: int = 0
    avg_at_venue: Optional[float] = None


class VsOpposition(BaseModel):
    innings_vs: int = 0
    avg_vs: Optional[float] = None


class PlayerPredictResponse(BaseModel):
    player: str
    role: str
    predicted_runs: Optional[int] = None
    predicted_wickets: Optional[float] = None
    prediction_range: list
    recent_form: RecentForm
    venue_history: VenueHistory
    vs_opposition: VsOpposition


@router.post("/player", response_model=PlayerPredictResponse)
async def predict_player(req: PlayerPredictRequest, request: Request):
    players_df = request.app.state.players_df
    lookups = request.app.state.feature_lookups

    # Find player
    match = players_df[
        players_df["player_name"].str.lower() == req.player_name.strip().lower()
    ]
    if match.empty:
        # Try partial match
        match = players_df[
            players_df["player_name"].str.lower().str.contains(
                req.player_name.strip().lower(), regex=False
            )
        ]
    if match.empty:
        raise HTTPException(status_code=404, detail=f"Player '{req.player_name}' not found")

    player_id = int(match.iloc[0]["player_id"])
    player_name = match.iloc[0]["player_name"]

    if req.role == "batting":
        return _predict_batting(
            request, player_id, player_name, req.venue_id,
            req.opposition_team_id, lookups
        )
    else:
        return _predict_bowling(
            request, player_id, player_name, req.venue_id,
            req.opposition_team_id, lookups
        )


def _predict_batting(request, player_id, player_name, venue_id, opposition_id, lookups):
    model = request.app.state.batting_model
    if model is None:
        raise HTTPException(status_code=503, detail="Batting model not loaded")

    meta = request.app.state.batting_meta or {}
    venues_df = request.app.state.venues_df

    # Get player stats from lookups
    prefix = f"bat_{player_id}"
    rolling_avg_5 = lookups.get(f"{prefix}_avg5", 25.0)
    rolling_sr_5 = lookups.get(f"{prefix}_sr5", 125.0)
    rolling_avg_10 = lookups.get(f"{prefix}_avg10", 25.0)
    career_sr = lookups.get(f"{prefix}_career_sr", 125.0)
    career_avg_venue = lookups.get(f"{prefix}_venue_{venue_id}", 25.0)
    career_avg_vs = lookups.get(f"{prefix}_vs_{opposition_id}", 25.0)
    innings_count = lookups.get(f"{prefix}_innings", 10)
    bat_pos = lookups.get(f"{prefix}_pos", 5)
    days_since = lookups.get(f"{prefix}_days", 14)

    # Determine batting_team_id from player lookups
    batting_team_id = lookups.get(f"{prefix}_team", 1)
    player_row = request.app.state.players_df[request.app.state.players_df["player_id"] == player_id]
    batting_style_left = 1 if not player_row.empty and "left" in str(player_row.iloc[0].get("batting_style", "")).lower() else 0
    venue_row = venues_df[venues_df["venue_id"] == venue_id]
    boundary_distance = venue_row.iloc[0].get("boundary_distance_m") if not venue_row.empty else None
    outfield_speed = venue_row.iloc[0].get("outfield_speed") if not venue_row.empty else None

    features = {
        "venue_id": venue_id,
        "venue_boundary_distance_m": boundary_distance,
        "venue_outfield_speed": outfield_speed,
        "batting_team_id": batting_team_id,
        "bowling_team_id": opposition_id,
        "batting_style_left": batting_style_left,
        "batting_position": bat_pos,
        "rolling_avg_runs_5": rolling_avg_5,
        "rolling_sr_5": rolling_sr_5,
        "rolling_avg_runs_10": rolling_avg_10,
        "career_avg_at_venue": career_avg_venue,
        "career_avg_vs_opposition": career_avg_vs,
        "career_sr": career_sr,
        "innings_count": innings_count,
        "days_since_last_match": days_since,
        "is_home": 0,
        "toss_elected_bat": 0,
        "is_debut": int(innings_count == 0),
    }

    feature_cols = meta.get("features", list(features.keys()))
    X = pd.DataFrame([features])[feature_cols]
    X = sanitize_model_input(
        X,
        {
            "venue_boundary_distance_m": 75.0,
            "venue_outfield_speed": 1.0,
        },
    )

    predicted = float(model.predict(X)[0])
    predicted_runs = max(0, int(round(predicted)))

    residual_std = meta.get("residual_std", 20)
    margin = int(round(1.28 * residual_std))
    lower = max(0, predicted_runs - margin)
    upper = predicted_runs + margin

    # Context stats for response
    innings_at_venue = lookups.get(f"{prefix}_venue_{venue_id}_n", 0)
    innings_vs = lookups.get(f"{prefix}_vs_{opposition_id}_n", 0)

    return PlayerPredictResponse(
        player=player_name,
        role="batting",
        predicted_runs=predicted_runs,
        prediction_range=[lower, upper],
        recent_form=RecentForm(
            last_5_avg=round(rolling_avg_5, 1),
            last_5_sr=round(rolling_sr_5, 1),
        ),
        venue_history=VenueHistory(
            innings_at_venue=innings_at_venue,
            avg_at_venue=round(career_avg_venue, 1) if innings_at_venue > 0 else None,
        ),
        vs_opposition=VsOpposition(
            innings_vs=innings_vs,
            avg_vs=round(career_avg_vs, 1) if innings_vs > 0 else None,
        ),
    )


def _predict_bowling(request, player_id, player_name, venue_id, opposition_id, lookups):
    model = request.app.state.bowling_model
    if model is None:
        raise HTTPException(status_code=503, detail="Bowling model not loaded")

    meta = request.app.state.bowling_meta or {}
    venues_df = request.app.state.venues_df

    prefix = f"bowl_{player_id}"
    rolling_wk_5 = lookups.get(f"{prefix}_wk5", 0.8)
    rolling_eco_5 = lookups.get(f"{prefix}_eco5", 8.0)
    rolling_wk_10 = lookups.get(f"{prefix}_wk10", 0.8)
    career_eco = lookups.get(f"{prefix}_career_eco", 8.0)
    career_wk_venue = lookups.get(f"{prefix}_venue_{venue_id}", 0.8)
    overs_career = lookups.get(f"{prefix}_overs", 50)
    dot_pct = lookups.get(f"{prefix}_dot", 0.4)
    innings_count = lookups.get(f"{prefix}_innings", 10)
    days_since = lookups.get(f"{prefix}_days", 14)

    bowling_team_id = lookups.get(f"{prefix}_team", 1)
    player_row = request.app.state.players_df[request.app.state.players_df["player_id"] == player_id]
    bowling_arm_left = 1 if not player_row.empty and "left" in str(player_row.iloc[0].get("bowling_arm", "")).lower() else 0
    bowling_type_spin = 1 if not player_row.empty and "spin" in str(player_row.iloc[0].get("bowling_type", "")).lower() else 0
    venue_row = venues_df[venues_df["venue_id"] == venue_id]
    boundary_distance = venue_row.iloc[0].get("boundary_distance_m") if not venue_row.empty else None
    outfield_speed = venue_row.iloc[0].get("outfield_speed") if not venue_row.empty else None

    features = {
        "venue_id": venue_id,
        "venue_boundary_distance_m": boundary_distance,
        "venue_outfield_speed": outfield_speed,
        "batting_team_id": opposition_id,
        "bowling_team_id": bowling_team_id,
        "bowling_arm_left": bowling_arm_left,
        "bowling_type_spin": bowling_type_spin,
        "rolling_avg_wickets_5": rolling_wk_5,
        "rolling_economy_5": rolling_eco_5,
        "rolling_avg_wickets_10": rolling_wk_10,
        "career_avg_wickets_at_venue": career_wk_venue,
        "career_economy": career_eco,
        "overs_bowled_career": overs_career,
        "dot_ball_pct_rolling_5": dot_pct,
        "innings_count": innings_count,
        "days_since_last_match": days_since,
    }

    feature_cols = meta.get("features", list(features.keys()))
    X = pd.DataFrame([features])[feature_cols]
    X = sanitize_model_input(
        X,
        {
            "venue_boundary_distance_m": 75.0,
            "venue_outfield_speed": 1.0,
        },
    )

    predicted = float(model.predict(X)[0])
    predicted_wickets = max(0, round(predicted, 1))

    residual_std = meta.get("residual_std", 1.0)
    margin = round(1.28 * residual_std, 1)
    lower = max(0, round(predicted_wickets - margin, 1))
    upper = round(predicted_wickets + margin, 1)

    innings_at_venue = lookups.get(f"{prefix}_venue_{venue_id}_n", 0)
    innings_vs = lookups.get(f"{prefix}_vs_{opposition_id}_n", 0)

    return PlayerPredictResponse(
        player=player_name,
        role="bowling",
        predicted_wickets=predicted_wickets,
        prediction_range=[lower, upper],
        recent_form=RecentForm(
            last_5_economy=round(rolling_eco_5, 1),
        ),
        venue_history=VenueHistory(
            innings_at_venue=innings_at_venue,
            avg_at_venue=round(career_wk_venue, 2) if innings_at_venue > 0 else None,
        ),
        vs_opposition=VsOpposition(
            innings_vs=innings_vs,
        ),
    )
