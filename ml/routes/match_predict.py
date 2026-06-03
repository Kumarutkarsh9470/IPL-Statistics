"""
Route handler for Model 1: Match Outcome Prediction.
POST /api/predict/match
"""
import numpy as np
import pandas as pd
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from ml.utils import sanitize_model_input

router = APIRouter()


class MatchPredictRequest(BaseModel):
    team1_id: int
    team2_id: int
    venue_id: int
    toss_winner: str = Field(..., pattern="^(team1|team2)$")
    toss_decision: str = Field(..., pattern="^(bat|field)$")
    match_stage: str = "league"


class KeyFactor(BaseModel):
    factor: str
    impact: str


class MatchPredictResponse(BaseModel):
    team1: str
    team2: str
    team1_win_prob: float
    team2_win_prob: float
    confidence: str
    key_factors: List[KeyFactor]


@router.post("/match", response_model=MatchPredictResponse)
async def predict_match(req: MatchPredictRequest, request: Request):
    model = request.app.state.match_model
    if model is None:
        raise HTTPException(status_code=503, detail="Match outcome model not loaded")

    teams_df = request.app.state.teams_df
    venues_df = request.app.state.venues_df
    lookups = request.app.state.feature_lookups

    # Resolve names
    team1_row = teams_df[teams_df["team_id"] == req.team1_id]
    team2_row = teams_df[teams_df["team_id"] == req.team2_id]
    venue_row = venues_df[venues_df["venue_id"] == req.venue_id]

    if team1_row.empty or team2_row.empty:
        raise HTTPException(status_code=400, detail="Invalid team ID")
    if venue_row.empty:
        raise HTTPException(status_code=400, detail="Invalid venue ID")

    team1_name = team1_row.iloc[0]["team_name"]
    team2_name = team2_row.iloc[0]["team_name"]
    city = venue_row.iloc[0].get("city", "")
    boundary_distance = venue_row.iloc[0].get("boundary_distance_m")
    outfield_speed = venue_row.iloc[0].get("outfield_speed")

    toss_winner_is_team1 = 1 if req.toss_winner == "team1" else 0
    toss_decision_bat = 1 if req.toss_decision == "bat" else 0

    # Build feature vector using lookups or defaults
    t1_id = req.team1_id
    t2_id = req.team2_id
    v_id = req.venue_id

    team1_win_pct = lookups.get(f"team_win_pct_{t1_id}", 0.5)
    team2_win_pct = lookups.get(f"team_win_pct_{t2_id}", 0.5)
    team1_venue_pct = lookups.get(f"team_venue_{t1_id}_{v_id}", 0.5)
    team2_venue_pct = lookups.get(f"team_venue_{t2_id}_{v_id}", 0.5)
    h2h_pct = lookups.get(f"h2h_{t1_id}_{t2_id}", 0.5)
    team1_form = lookups.get(f"form_{t1_id}", 0.5)
    team2_form = lookups.get(f"form_{t2_id}", 0.5)
    venue_chase_pct = lookups.get(f"venue_chase_{v_id}", 0.5)

    from ml.utils import is_home_city
    team1_is_home = is_home_city(team1_name, city)
    team2_is_home = is_home_city(team2_name, city)

    features = {
        "venue_id": v_id,
        "venue_boundary_distance_m": boundary_distance,
        "venue_outfield_speed": outfield_speed,
        "toss_winner_is_team1": toss_winner_is_team1,
        "toss_decision_bat": toss_decision_bat,
        "team1_win_pct_overall": team1_win_pct,
        "team2_win_pct_overall": team2_win_pct,
        "team1_win_pct_at_venue": team1_venue_pct,
        "team2_win_pct_at_venue": team2_venue_pct,
        "h2h_team1_win_pct": h2h_pct,
        "team1_recent_form": team1_form,
        "team2_recent_form": team2_form,
        "venue_chasing_win_pct": venue_chase_pct,
        "team1_is_home": team1_is_home,
        "team2_is_home": team2_is_home,
        # Differential / interaction features
        "win_pct_diff": team1_win_pct - team2_win_pct,
        "form_diff": team1_form - team2_form,
        "venue_pct_diff": team1_venue_pct - team2_venue_pct,
        "h2h_advantage": h2h_pct - 0.5,
        "team1_form_3": lookups.get(f"form3_{t1_id}", team1_form),
        "team2_form_3": lookups.get(f"form3_{t2_id}", team2_form),
        "form_diff_3": lookups.get(f"form3_{t1_id}", team1_form) - lookups.get(f"form3_{t2_id}", team2_form),
        "toss_bat_venue_advantage": (
            toss_decision_bat * venue_chase_pct
            + (1 - toss_decision_bat) * (1 - venue_chase_pct)
        ),
        "home_advantage": int(team1_is_home) - int(team2_is_home),
    }

    feature_cols = request.app.state.match_features or list(features.keys())
    X = pd.DataFrame([features])[feature_cols]
    X = sanitize_model_input(
        X,
        {
            "venue_boundary_distance_m": 75.0,
            "venue_outfield_speed": 1.0,
        },
    )

    # Predict
    proba = model.predict_proba(X)[0]
    # proba[1] = P(target=1) = P(team1 wins)
    team1_prob = float(proba[1]) if len(proba) > 1 else float(proba[0])
    team2_prob = 1.0 - team1_prob

    # Confidence
    from ml.utils import confidence_label
    confidence = confidence_label(team1_prob)

    # Key factors (simple feature-based explanation)
    key_factors = _compute_key_factors(features, team1_name, team2_name, boundary_distance)

    return MatchPredictResponse(
        team1=team1_name,
        team2=team2_name,
        team1_win_prob=round(team1_prob, 2),
        team2_win_prob=round(team2_prob, 2),
        confidence=confidence,
        key_factors=key_factors,
    )


def _compute_key_factors(features: dict, team1: str, team2: str, boundary_distance=None) -> list:
    """Generate human-readable key factors from feature values."""
    factors = []

    # Venue advantage
    v1 = features["team1_win_pct_at_venue"]
    v2 = features["team2_win_pct_at_venue"]
    if abs(v1 - v2) > 0.05:
        better = team1 if v1 > v2 else team2
        diff = abs(v1 - v2) * 100
        factors.append(KeyFactor(
            factor="Venue advantage",
            impact=f"+{diff:.0f}% for {better}",
        ))

    # Recent form
    f1 = features["team1_recent_form"]
    f2 = features["team2_recent_form"]
    if abs(f1 - f2) > 0.05:
        better = team1 if f1 > f2 else team2
        diff = abs(f1 - f2) * 100
        factors.append(KeyFactor(
            factor="Recent form",
            impact=f"+{diff:.0f}% for {better}",
        ))

    # H2H
    h2h = features["h2h_team1_win_pct"]
    if abs(h2h - 0.5) > 0.05:
        better = team1 if h2h > 0.5 else team2
        diff = abs(h2h - 0.5) * 100
        factors.append(KeyFactor(
            factor="H2H record",
            impact=f"+{diff:.0f}% for {better}",
        ))

    # Toss
    if features["toss_winner_is_team1"]:
        factors.append(KeyFactor(
            factor="Toss advantage",
            impact=f"Won by {team1}",
        ))
    else:
        factors.append(KeyFactor(
            factor="Toss advantage",
            impact=f"Won by {team2}",
        ))

    # Home advantage
    if features["team1_is_home"]:
        factors.append(KeyFactor(factor="Home ground", impact=f"{team1} at home"))
    elif features["team2_is_home"]:
        factors.append(KeyFactor(factor="Home ground", impact=f"{team2} at home"))

    if boundary_distance is not None and not pd.isna(boundary_distance):
        factors.append(KeyFactor(factor="Boundary size", impact=f"{float(boundary_distance):.0f}m boundary"))

    return factors[:5]
