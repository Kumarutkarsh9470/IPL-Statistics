"""
Route handler for Model 5: Live Chase Win Probability.
POST /api/predict/chase

Given the current state of a 2nd innings chase, predicts:
  - Probability of the chasing team winning
  - Required run rate vs current run rate
  - Pressure index and situational context

Uses a statistical DL-inspired approach combining historical chase data
from the pre-computed feature lookups with real-time match state.
"""
import math
import numpy as np
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

router = APIRouter()


class ChaseRequest(BaseModel):
    batting_team_id: int
    bowling_team_id: int
    venue_id: int
    target: int = Field(..., ge=1, description="Target runs to win")
    current_score: int = Field(..., ge=0)
    wickets_fallen: int = Field(..., ge=0, le=10)
    current_over: int = Field(..., ge=0, le=20)
    balls_in_current_over: int = Field(0, ge=0, le=5)
    boundaries: int = Field(0, ge=0)
    dot_balls: int = Field(0, ge=0)


class ChaseResponse(BaseModel):
    chasing_team_win_prob: float
    defending_team_win_prob: float
    runs_needed: int
    balls_remaining: int
    wickets_in_hand: int
    required_run_rate: float
    current_run_rate: float
    run_rate_gap: float
    pressure_index: float
    situation: str
    confidence: str
    key_stats: dict


@router.post("/chase", response_model=ChaseResponse)
async def predict_chase(req: ChaseRequest, request: Request):
    lookups = request.app.state.feature_lookups

    # Basic state calculations
    total_balls_bowled = req.current_over * 6 + req.balls_in_current_over
    balls_remaining = max(0, 120 - total_balls_bowled)
    wickets_in_hand = max(0, 10 - req.wickets_fallen)
    runs_needed = max(0, req.target - req.current_score)

    if balls_remaining == 0:
        # Match over
        win_prob = 1.0 if runs_needed <= 0 else 0.0
        return _build_response(win_prob, runs_needed, balls_remaining,
                                wickets_in_hand, req, 0.0)

    required_rr = (runs_needed / balls_remaining) * 6
    current_rr = (req.current_score / total_balls_bowled * 6) if total_balls_bowled > 0 else 0.0

    # Historical lookup factors
    venue_chase_pct = lookups.get(f"venue_chase_{req.venue_id}", 0.5)
    bat_team_avg = lookups.get(f"bat_team_avg_{req.batting_team_id}", 160.0)
    bowl_team_avg = lookups.get(f"bowl_team_avg_{req.bowling_team_id}", 160.0)

    # Compute win probability using a logistic function
    # Key predictors: run_rate_gap, wickets_in_hand, balls_remaining (proportion)
    run_rate_gap = current_rr - required_rr  # Positive = chasing team ahead

    # Normalised resources remaining (wickets × balls, inspired by DL)
    # Resources: full wickets+full overs = 10 * 120 = 1200 units
    resources_remaining = (wickets_in_hand * balls_remaining) / (10.0 * 120.0)

    # Pressure index: required_rr / historical avg scoring rate at venue
    expected_rr = bat_team_avg / 20.0  # Expected run rate per over for the team
    pressure_index = required_rr / expected_rr if expected_rr > 0 else 1.0

    # Logistic model for win probability
    # Features: run_rate_gap, wickets_in_hand_pct, resources_remaining, pressure_index, venue_chase_pct
    wickets_in_hand_pct = wickets_in_hand / 10.0

    # Weights derived from domain knowledge and typical DL approaches
    logit = (
        1.8 * run_rate_gap / max(required_rr, 1.0)  # How far ahead/behind RR-wise (normalized)
        + 1.5 * wickets_in_hand_pct                   # Wickets in hand advantage
        + 0.8 * resources_remaining                   # Overall resources remaining
        - 1.2 * math.log1p(max(0, pressure_index - 1))  # Pressure penalty when RRR > avg
        + 0.4 * (venue_chase_pct - 0.5)               # Venue chase history
        + 0.2 * (bat_team_avg - bowl_team_avg) / max(bat_team_avg, 1.0)  # Team strength
    )

    win_prob = 1.0 / (1.0 + math.exp(-logit))
    win_prob = float(np.clip(win_prob, 0.02, 0.98))

    return _build_response(win_prob, runs_needed, balls_remaining,
                            wickets_in_hand, req, pressure_index,
                            required_rr, current_rr)


def _build_response(
    win_prob: float,
    runs_needed: int,
    balls_remaining: int,
    wickets_in_hand: int,
    req: ChaseRequest,
    pressure_index: float,
    required_rr: float = 0.0,
    current_rr: float = 0.0,
) -> ChaseResponse:
    run_rate_gap = current_rr - required_rr

    # Determine situation label
    if runs_needed <= 0:
        situation = "Chasing team has won"
    elif balls_remaining == 0:
        situation = "Match over — target not reached"
    elif win_prob >= 0.75:
        situation = "Chasing team in strong control"
    elif win_prob >= 0.60:
        situation = "Chasing team has the edge"
    elif win_prob >= 0.45:
        situation = "Evenly poised"
    elif win_prob >= 0.30:
        situation = "Defending team has the edge"
    else:
        situation = "Defending team in strong control"

    # Confidence based on resources remaining (more balls left = less certain)
    overs_gone = (120 - balls_remaining) / 6
    if overs_gone >= 15:
        confidence = "High"
    elif overs_gone >= 10:
        confidence = "Medium"
    else:
        confidence = "Low"

    key_stats = {
        "runs_per_ball_needed": round(runs_needed / max(balls_remaining, 1), 3),
        "balls_per_run_available": round(balls_remaining / max(runs_needed, 1), 2),
        "pressure_index": round(pressure_index, 2),
        "wickets_utilised": req.wickets_fallen,
        "overs_remaining": round(balls_remaining / 6, 1),
    }

    return ChaseResponse(
        chasing_team_win_prob=round(win_prob, 3),
        defending_team_win_prob=round(1.0 - win_prob, 3),
        runs_needed=runs_needed,
        balls_remaining=balls_remaining,
        wickets_in_hand=wickets_in_hand,
        required_run_rate=round(required_rr, 2),
        current_run_rate=round(current_rr, 2),
        run_rate_gap=round(run_rate_gap, 2),
        pressure_index=round(pressure_index, 2),
        situation=situation,
        confidence=confidence,
        key_stats=key_stats,
    )
