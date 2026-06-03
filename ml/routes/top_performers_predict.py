"""
Route handler for Model 6: Top Performers Prediction.
POST /api/predict/top-performers

Given a match (two teams + venue), predicts which batters and bowlers
are most likely to shine — using the batting and bowling ML models
across each team's squad roster from the lookups.

Returns ranked lists of predicted top run-scorers and wicket-takers.
"""
import numpy as np
import pandas as pd
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from ml.utils import sanitize_model_input

router = APIRouter()


class TopPerformersRequest(BaseModel):
    team1_id: int
    team2_id: int
    venue_id: int
    toss_winner: str = Field("team1", pattern="^(team1|team2)$")
    toss_decision: str = Field("bat", pattern="^(bat|field)$")
    top_n: int = Field(5, ge=1, le=10, description="Number of players to return per category")


class PlayerPrediction(BaseModel):
    player_id: int
    player_name: str
    team: str
    predicted_runs: Optional[float] = None
    predicted_wickets: Optional[float] = None
    confidence_range: List[float]


class TopPerformersResponse(BaseModel):
    top_run_scorers: List[PlayerPrediction]
    top_wicket_takers: List[PlayerPrediction]
    match_context: dict


@router.post("/top-performers", response_model=TopPerformersResponse)
async def predict_top_performers(req: TopPerformersRequest, request: Request):
    batting_model = request.app.state.batting_model
    bowling_model = request.app.state.bowling_model
    if batting_model is None or bowling_model is None:
        raise HTTPException(status_code=503, detail="Player performance models not loaded")

    teams_df = request.app.state.teams_df
    venues_df = request.app.state.venues_df
    players_df = request.app.state.players_df
    lookups = request.app.state.feature_lookups
    batting_meta = request.app.state.batting_meta or {}
    bowling_meta = request.app.state.bowling_meta or {}

    # Resolve IDs
    t1_row = teams_df[teams_df["team_id"] == req.team1_id]
    t2_row = teams_df[teams_df["team_id"] == req.team2_id]
    venue_row = venues_df[venues_df["venue_id"] == req.venue_id]

    if t1_row.empty or t2_row.empty:
        raise HTTPException(status_code=400, detail="Invalid team ID")
    if venue_row.empty:
        raise HTTPException(status_code=400, detail="Invalid venue ID")

    team1_name = t1_row.iloc[0]["team_name"]
    team2_name = t2_row.iloc[0]["team_name"]
    boundary_distance = venue_row.iloc[0].get("boundary_distance_m")
    outfield_speed = venue_row.iloc[0].get("outfield_speed")

    # Get players for each team from the players_df
    # players_df should have player_id, player_name, team_id (if available)
    team1_players = _get_team_players(players_df, lookups, req.team1_id)
    team2_players = _get_team_players(players_df, lookups, req.team2_id)

    toss_elected_bat = 1 if req.toss_decision == "bat" else 0

    # Determine which team bats first
    toss_winner_id = req.team1_id if req.toss_winner == "team1" else req.team2_id
    if req.toss_decision == "bat":
        batting_first_id = toss_winner_id
    else:
        batting_first_id = req.team2_id if toss_winner_id == req.team1_id else req.team1_id

    # Build batting predictions for all players
    batting_results = []
    for team_id, team_name, players in [
        (req.team1_id, team1_name, team1_players),
        (req.team2_id, team2_name, team2_players),
    ]:
        opposition_id = req.team2_id if team_id == req.team1_id else req.team1_id
        for player_id, player_name in players:
            pred, low, high = _predict_batting(
                batting_model, batting_meta, lookups, players_df, venues_df,
                player_id, team_id, opposition_id, req.venue_id,
                toss_elected_bat
            )
            batting_results.append(PlayerPrediction(
                player_id=player_id,
                player_name=player_name,
                team=team_name,
                predicted_runs=round(pred, 1),
                confidence_range=[round(low, 1), round(high, 1)],
            ))

    # Build bowling predictions for all players
    bowling_results = []
    for team_id, team_name, players in [
        (req.team1_id, team1_name, team1_players),
        (req.team2_id, team2_name, team2_players),
    ]:
        opposition_id = req.team2_id if team_id == req.team1_id else req.team1_id
        for player_id, player_name in players:
            pred, low, high = _predict_bowling(
                bowling_model, bowling_meta, lookups, players_df, venues_df,
                player_id, team_id, opposition_id, req.venue_id
            )
            bowling_results.append(PlayerPrediction(
                player_id=player_id,
                player_name=player_name,
                team=team_name,
                predicted_wickets=round(pred, 2),
                confidence_range=[round(low, 2), round(high, 2)],
            ))

    # Sort and take top N
    top_batters = sorted(
        batting_results, key=lambda p: p.predicted_runs or 0, reverse=True
    )[:req.top_n]
    top_bowlers = sorted(
        bowling_results, key=lambda p: p.predicted_wickets or 0, reverse=True
    )[:req.top_n]

    match_context = {
        "team1": team1_name,
        "team2": team2_name,
        "batting_first": team1_name if batting_first_id == req.team1_id else team2_name,
        "venue": venue_row.iloc[0].get("venue_name", ""),
    }

    return TopPerformersResponse(
        top_run_scorers=top_batters,
        top_wicket_takers=top_bowlers,
        match_context=match_context,
    )


def _get_team_players(players_df: pd.DataFrame, lookups: dict, team_id: int):
    """Return list of (player_id, player_name) for a team using lookup data."""
    # If players_df has a team_id column, use it; otherwise use lookup
    if "team_id" in players_df.columns:
        team_players = players_df[players_df["team_id"] == team_id]
        if not team_players.empty:
            return list(zip(team_players["player_id"].tolist(),
                            team_players["player_name"].tolist()))

    # Fallback: find players whose team lookup matches this team
    player_team_lookups = {
        k: v for k, v in lookups.items()
        if k.startswith("bat_") and k.endswith("_team") and v == team_id
    }
    player_ids = []
    for k in player_team_lookups:
        try:
            pid = int(k.split("_")[1])
            player_ids.append(pid)
        except (IndexError, ValueError):
            continue

    if not player_ids:
        # Last resort: use top-20 players by innings count
        player_ids = [
            int(k.split("_")[1])
            for k in lookups
            if k.startswith("bat_") and k.endswith("_innings")
        ][:20]

    result = []
    for pid in player_ids[:15]:  # Cap per team
        row = players_df[players_df["player_id"] == pid]
        if not row.empty:
            result.append((pid, row.iloc[0]["player_name"]))
    return result


def _predict_batting(model, meta, lookups, players_df, venues_df, player_id, team_id, opposition_id,
                     venue_id, toss_elected_bat):
    """Build feature vector and run batting model inference for one player."""
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
    rolling_br5 = lookups.get(f"{prefix}_br5", 0.15)
    consistency = lookups.get(f"{prefix}_consistency", 0.5)
    opp_bowling_q = lookups.get(f"opp_bowl_q_{opposition_id}", 25.0)
    player_row = players_df[players_df["player_id"] == player_id]
    batting_style_left = 1 if not player_row.empty and "left" in str(player_row.iloc[0].get("batting_style", "")).lower() else 0
    venue_row = venues_df[venues_df["venue_id"] == venue_id]
    boundary_distance = venue_row.iloc[0].get("boundary_distance_m") if not venue_row.empty else None
    outfield_speed = venue_row.iloc[0].get("outfield_speed") if not venue_row.empty else None

    features = {
        "venue_id": venue_id,
        "venue_boundary_distance_m": boundary_distance,
        "venue_outfield_speed": outfield_speed,
        "batting_team_id": team_id,
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
        "toss_elected_bat": toss_elected_bat,
        "is_debut": int(innings_count == 0),
        "rolling_boundary_rate_5": rolling_br5,
        "consistency_score": consistency,
        "opp_bowling_quality": opp_bowling_q,
    }
    feature_cols = meta.get("features", list(features.keys()))
    X = pd.DataFrame([features]).reindex(columns=feature_cols, fill_value=0)
    X = sanitize_model_input(
        X,
        {
            "venue_boundary_distance_m": 75.0,
            "venue_outfield_speed": 1.0,
        },
    )

    pred = float(model.predict(X)[0])
    pred = max(0.0, pred)
    residual_std = meta.get("residual_std", 19.0)
    return pred, max(0.0, pred - residual_std), pred + residual_std


def _predict_bowling(model, meta, lookups, players_df, venues_df, player_id, team_id, opposition_id, venue_id):
    """Build feature vector and run bowling model inference for one player."""
    prefix = f"bowl_{player_id}"
    rolling_wk_5 = lookups.get(f"{prefix}_wk5", 1.0)
    rolling_eco_5 = lookups.get(f"{prefix}_eco5", 8.0)
    rolling_wk_10 = lookups.get(f"{prefix}_wk10", 1.0)
    career_wk_venue = lookups.get(f"{prefix}_venue_{venue_id}", 1.0)
    career_eco = lookups.get(f"{prefix}_career_eco", 8.0)
    overs_bowled = lookups.get(f"{prefix}_overs", 50.0)
    dot_pct = lookups.get(f"{prefix}_dot5", 0.3)
    innings_count = lookups.get(f"{prefix}_innings", 10)
    days_since = lookups.get(f"{prefix}_days", 14)
    career_sr = lookups.get(f"{prefix}_career_sr", 30.0)
    rolling_wkr_5 = lookups.get(f"{prefix}_wkr5", 0.03)
    opp_bat_q = lookups.get(f"opp_bat_q_{opposition_id}", 8.0)
    player_row = players_df[players_df["player_id"] == player_id]
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
        "bowling_team_id": team_id,
        "bowling_arm_left": bowling_arm_left,
        "bowling_type_spin": bowling_type_spin,
        "rolling_avg_wickets_5": rolling_wk_5,
        "rolling_economy_5": rolling_eco_5,
        "rolling_avg_wickets_10": rolling_wk_10,
        "career_avg_wickets_at_venue": career_wk_venue,
        "career_economy": career_eco,
        "overs_bowled_career": overs_bowled,
        "dot_ball_pct_rolling_5": dot_pct,
        "innings_count": innings_count,
        "days_since_last_match": days_since,
        "career_strike_rate": career_sr,
        "rolling_wicket_rate_5": rolling_wkr_5,
        "opp_batting_quality": opp_bat_q,
    }
    feature_cols = meta.get("features", list(features.keys()))
    X = pd.DataFrame([features]).reindex(columns=feature_cols, fill_value=0)
    X = sanitize_model_input(
        X,
        {
            "venue_boundary_distance_m": 75.0,
            "venue_outfield_speed": 1.0,
        },
    )

    pred = float(model.predict(X)[0])
    pred = max(0.0, pred)
    residual_std = meta.get("residual_std", 1.04)
    return pred, max(0.0, pred - residual_std), pred + residual_std
