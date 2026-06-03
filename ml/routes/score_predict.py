"""
Route handler for Model 2: Mid-Match Score Prediction.
POST /api/predict/score
"""
import numpy as np
import pandas as pd
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from ml.utils import sanitize_model_input

router = APIRouter()


class ScorePredictRequest(BaseModel):
    batting_team_id: int
    bowling_team_id: int
    venue_id: int
    current_over: int = Field(..., ge=1, le=20)
    runs_scored: int = Field(..., ge=0)
    wickets_fallen: int = Field(..., ge=0, le=10)
    boundaries: int = Field(0, ge=0)
    dot_balls: int = Field(0, ge=0)
    extras: int = Field(0, ge=0)
    last_3_overs_runs: Optional[int] = None


class ScorePredictResponse(BaseModel):
    predicted_total: int
    prediction_range: List[int]
    current_run_rate: float
    required_acceleration: Optional[float]
    phase_breakdown: Optional[dict]
    confidence: Optional[int] = None


def _validate_score_request(req: ScorePredictRequest):
    total_balls = req.current_over * 6
    max_runs = req.current_over * 36

    if req.runs_scored > max_runs:
        raise HTTPException(
            status_code=400,
            detail=f"Runs scored cannot be more than {max_runs} for {req.current_over} overs.",
        )

    if req.wickets_fallen > 10:
        raise HTTPException(
            status_code=400,
            detail="Wickets cannot be more than 10.",
        )

    if req.boundaries + req.dot_balls >= total_balls:
        raise HTTPException(
            status_code=400,
            detail=f"Boundaries + dot balls must be less than {total_balls} for {req.current_over} overs.",
        )

    if req.runs_scored <= (6 * req.boundaries) + req.extras:
        raise HTTPException(
            status_code=400,
            detail="Runs scored must be greater than 6 * boundaries + extras.",
        )


def _build_phase_breakdown(req: ScorePredictRequest, remaining_runs: int, current_rr: float):
    if remaining_runs <= 0:
        return None

    if req.current_over < 11:
        # Use a conservative middle-overs run rate so the display does not explode early.
        mid_overs = 5
        mid_rate = min(max(current_rr + 1.5, current_rr * 1.1), 16.0)
        mid_expected = min(remaining_runs, int(round(mid_overs * mid_rate)))
        death_expected = max(0, remaining_runs - mid_expected)
        return {
            "overs_11_15_expected": mid_expected,
            "overs_16_20_expected": death_expected,
        }

    if req.current_over < 16:
        return {
            "overs_16_20_expected": remaining_runs,
        }

    return {
        "overs_16_20_expected": remaining_runs,
    }


@router.post("/score", response_model=ScorePredictResponse)
async def predict_score(req: ScorePredictRequest, request: Request):
    model = request.app.state.score_model
    if model is None:
        raise HTTPException(status_code=503, detail="Score prediction model not loaded")

    _validate_score_request(req)

    overs_remaining = max(0, 20 - req.current_over)
    max_possible_total = req.runs_scored + (overs_remaining * 36)

    if overs_remaining == 0:
        predicted_total = req.runs_scored
        current_rr = req.runs_scored / req.current_over if req.current_over > 0 else 0
        return ScorePredictResponse(
            predicted_total=predicted_total,
            prediction_range=[predicted_total, predicted_total],
            current_run_rate=round(current_rr, 1),
            required_acceleration=0.0,
            phase_breakdown=None,
            confidence=100,
        )

    meta = request.app.state.score_meta or {}
    lookups = request.app.state.feature_lookups
    base_coefficient = float(meta.get("base_coefficient", 20.0))

    # Current run rate
    current_rr = req.runs_scored / req.current_over if req.current_over > 0 else 0

    # Last 3 overs run rate
    if req.last_3_overs_runs is not None and req.current_over >= 3:
        rr_last_3 = req.last_3_overs_runs / 3
    else:
        rr_last_3 = current_rr

    # Powerplay run rate
    if req.current_over >= 6:
        # Approximate: if we don't have exact PP data, use current RR
        rr_pp = current_rr  # Best approximation without full ball-by-ball
    else:
        rr_pp = current_rr

    # Total balls so far (approximate: 6 * overs)
    total_balls = req.current_over * 6
    dot_pct = req.dot_balls / total_balls if total_balls > 0 else 0
    boundary_rate = req.boundaries / total_balls if total_balls > 0 else 0
    wicket_rate = req.wickets_fallen / total_balls if total_balls > 0 else 0
    runs_per_ball = req.runs_scored / total_balls if total_balls > 0 else 0
    balls_remaining = max(0, 120 - total_balls)
    wickets_in_hand = max(0, 10 - req.wickets_fallen)

    # Historical averages from lookups
    v_avg = lookups.get(f"venue_avg_{req.venue_id}", 160.0)
    bt_avg = lookups.get(f"bat_team_avg_{req.batting_team_id}", 160.0)
    bw_avg = lookups.get(f"bowl_team_avg_{req.bowling_team_id}", 160.0)
    venue_row = request.app.state.venues_df[request.app.state.venues_df["venue_id"] == req.venue_id]
    boundary_distance = venue_row.iloc[0].get("boundary_distance_m") if not venue_row.empty else None
    outfield_speed = venue_row.iloc[0].get("outfield_speed") if not venue_row.empty else None

    features = {
        "current_over": req.current_over,
        "runs_scored_so_far": req.runs_scored,
        "wickets_fallen_so_far": req.wickets_fallen,
        "current_run_rate": round(current_rr, 4),
        "run_rate_last_3_overs": round(rr_last_3, 4),
        "run_rate_powerplay": round(rr_pp, 4),
        "current_over": req.current_over,
        "boundaries_so_far": req.boundaries,
        "dot_ball_pct_so_far": round(dot_pct, 4),
        "extras_so_far": req.extras,
        "venue_avg_1st_innings": v_avg,
        "venue_boundary_distance_m": boundary_distance,
        "venue_outfield_speed": outfield_speed,
        "batting_team_avg_score": bt_avg,
        "bowling_team_avg_conceded": bw_avg,
        "venue_id": req.venue_id,
        "batting_team_id": req.batting_team_id,
        "bowling_team_id": req.bowling_team_id,
        "is_powerplay": int(req.current_over <= 6),
        "is_middle": int(6 < req.current_over < 16),
        "is_death": int(req.current_over >= 16),
        # New high-signal features
        "balls_remaining": balls_remaining,
        "wickets_in_hand": wickets_in_hand,
        "boundary_rate": round(boundary_rate, 4),
        "wicket_rate": round(wicket_rate, 4),
        "runs_per_ball": round(runs_per_ball, 4),
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

    # Predict using the fixed base formula plus a small ML-tuned adjustment.
    base_prediction = base_coefficient * current_rr
    adjustment = float(model.predict(X)[0])
    adjustment = max(-30.0, min(30.0, adjustment))

    # Apply a more aggressive penalty for wickets fallen. This makes the
    # forecast drop faster as wickets increase (configurable via meta).
    wicket_penalty_coeff = float(meta.get("wicket_penalty_coeff", 4.0))
    wicket_penalty_exp = float(meta.get("wicket_penalty_exponent", 1.6))
    wicket_penalty = wicket_penalty_coeff * (req.wickets_fallen ** wicket_penalty_exp)
    # Cap the penalty to avoid completely implausible reductions
    wicket_penalty = min(wicket_penalty, float(meta.get("wicket_penalty_cap", 60.0)))

    predicted_total = int(round(base_prediction + adjustment - wicket_penalty))
    predicted_total = max(predicted_total, req.runs_scored)
    predicted_total = min(predicted_total, max_possible_total)

    # Prediction interval using residual std
    residual_std = meta.get("residual_std", 20)
    # Scale interval by how many overs remain (more uncertainty early)
    scale = max(0.3, overs_remaining / 20)
    margin = int(round(1.28 * residual_std * scale))  # ~80% interval
    lower = max(req.runs_scored, predicted_total - margin)
    upper = predicted_total + margin

    # Required acceleration
    if overs_remaining > 0:
        projected_rr_needed = (predicted_total - req.runs_scored) / overs_remaining
        req_accel = round(projected_rr_needed - current_rr, 1)
    else:
        req_accel = None

    confidence = max(10, min(99, int(round(100 - (margin / max(1, max_possible_total - req.runs_scored)) * 100))))

    # Phase breakdown (rough estimate)
    phase_breakdown = _build_phase_breakdown(req, predicted_total - req.runs_scored, current_rr)

    return ScorePredictResponse(
        predicted_total=predicted_total,
        prediction_range=[lower, upper],
        current_run_rate=round(current_rr, 1),
        required_acceleration=req_accel,
        phase_breakdown=phase_breakdown,
        confidence=confidence,
    )
