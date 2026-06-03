"""
Player-level feature engineering for Model 3: Player Performance Prediction.

Sub-model 3A: Batting — predict runs scored by a batter.
Sub-model 3B: Bowling — predict wickets taken by a bowler.

Uses .shift(1) on all rolling features to prevent leakage.
"""
from typing import Optional

import numpy as np
import pandas as pd
from ml.config import ROLLING_WINDOW_SHORT, ROLLING_WINDOW_LONG, TEAM_HOME_CITIES


def build_batting_features(
    deliveries_df: pd.DataFrame,
    matches_df: pd.DataFrame,
    players_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Build one row per (player, match, innings) for batting prediction.

    Target: total runs scored by the batter in that innings.
    """
    # Aggregate deliveries to per-batter-per-innings
    batter_innings = (
        deliveries_df.groupby(["match_id", "innings", "batter_id", "batting_team_id", "bowling_team_id"])
        .agg(
            runs_scored=("runs_batter", "sum"),
            balls_faced=("batter_id", "count"),
            fours=("runs_batter", lambda x: (x == 4).sum()),
            sixes=("runs_batter", lambda x: (x == 6).sum()),
        )
        .reset_index()
    )

    # Compute strike rate
    batter_innings["strike_rate"] = np.where(
        batter_innings["balls_faced"] > 0,
        batter_innings["runs_scored"] / batter_innings["balls_faced"] * 100,
        0,
    )

    # Estimate batting position from order of appearance
    first_ball = (
        deliveries_df.groupby(["match_id", "innings", "batter_id"])
        .agg(first_over=("over_num", "min"), first_ball=("ball_num", "min"))
        .reset_index()
    )
    first_ball["order_key"] = first_ball["first_over"] * 10 + first_ball["first_ball"]
    first_ball["batting_position"] = (
        first_ball.groupby(["match_id", "innings"])["order_key"]
        .rank(method="dense")
        .astype(int)
    )
    batter_innings = batter_innings.merge(
        first_ball[["match_id", "innings", "batter_id", "batting_position"]],
        on=["match_id", "innings", "batter_id"],
        how="left",
    )

    # Merge match info
    batter_innings = batter_innings.merge(
        matches_df[[
            "match_id", "match_date", "venue_id", "toss_winner_id", "toss_decision",
            "boundary_distance_m", "outfield_speed",
        ]],
        on="match_id",
        how="left",
    )

    if players_df is not None and not players_df.empty:
        batter_profiles = players_df[["player_id", "batting_style"]].rename(columns={"player_id": "batter_id"})
        batter_innings = batter_innings.merge(batter_profiles, on="batter_id", how="left")
    else:
        batter_innings["batting_style"] = None

    batter_innings["batting_style_left"] = batter_innings["batting_style"].fillna("").astype(str).str.contains("left", case=False, na=False).astype(int)
    batter_innings["venue_boundary_distance_m"] = batter_innings["boundary_distance_m"]
    batter_innings["venue_outfield_speed"] = batter_innings["outfield_speed"]
    batter_innings = batter_innings.sort_values(["batter_id", "match_date"]).reset_index(drop=True)

    # --- Rolling features with shift(1) ---
    batter_innings["rolling_avg_runs_5"] = (
        batter_innings.groupby("batter_id")["runs_scored"]
        .transform(lambda x: x.rolling(ROLLING_WINDOW_SHORT, min_periods=1).mean().shift(1))
    )
    batter_innings["rolling_sr_5"] = (
        batter_innings.groupby("batter_id")["strike_rate"]
        .transform(lambda x: x.rolling(ROLLING_WINDOW_SHORT, min_periods=1).mean().shift(1))
    )
    batter_innings["rolling_avg_runs_10"] = (
        batter_innings.groupby("batter_id")["runs_scored"]
        .transform(lambda x: x.rolling(ROLLING_WINDOW_LONG, min_periods=1).mean().shift(1))
    )

    # Career averages (expanding + shift)
    batter_innings["career_sr"] = (
        batter_innings.groupby("batter_id")["strike_rate"]
        .transform(lambda x: x.expanding().mean().shift(1))
    )
    batter_innings["innings_count"] = (
        batter_innings.groupby("batter_id").cumcount()
    )

    # Career avg at venue
    batter_innings["career_avg_at_venue"] = (
        batter_innings.groupby(["batter_id", "venue_id"])["runs_scored"]
        .transform(lambda x: x.expanding().mean().shift(1))
    )

    # Career avg vs opposition
    batter_innings["career_avg_vs_opposition"] = (
        batter_innings.groupby(["batter_id", "bowling_team_id"])["runs_scored"]
        .transform(lambda x: x.expanding().mean().shift(1))
    )

    # Days since last match
    batter_innings["prev_date"] = batter_innings.groupby("batter_id")["match_date"].shift(1)
    batter_innings["days_since_last_match"] = (
        (batter_innings["match_date"] - batter_innings["prev_date"]).dt.days
    )

    # Home flag
    venue_city = matches_df[["venue_id", "city"]].drop_duplicates()
    team_names = matches_df[["team1_id", "team1_name"]].drop_duplicates().rename(
        columns={"team1_id": "team_id", "team1_name": "team_name"}
    )
    batter_innings = batter_innings.merge(venue_city, on="venue_id", how="left")
    batter_innings = batter_innings.merge(
        team_names, left_on="batting_team_id", right_on="team_id", how="left"
    )
    batter_innings["is_home"] = batter_innings.apply(
        lambda r: _is_home(r.get("team_name", ""), r.get("city", "")), axis=1
    )

    # Toss elected bat
    batter_innings["toss_elected_bat"] = (
        (batter_innings["toss_winner_id"] == batter_innings["batting_team_id"])
        & (batter_innings["toss_decision"] == "bat")
    ).astype(int)

    # Is debut flag
    batter_innings["is_debut"] = (batter_innings["innings_count"] == 0).astype(int)

    # Fill NaN rolling features with league average
    league_avg_runs = batter_innings["runs_scored"].mean()
    league_avg_sr = batter_innings["strike_rate"].mean()

    fill_map = {
        "rolling_avg_runs_5": league_avg_runs,
        "rolling_sr_5": league_avg_sr,
        "rolling_avg_runs_10": league_avg_runs,
        "career_sr": league_avg_sr,
        "career_avg_at_venue": league_avg_runs,
        "career_avg_vs_opposition": league_avg_runs,
        "days_since_last_match": 30,
        "batting_position": 5,
        "batting_style_left": 0,
        "venue_boundary_distance_m": 75.0,
        "venue_outfield_speed": 1.0,
    }
    for col, val in fill_map.items():
        batter_innings[col] = batter_innings[col].fillna(val)

    # --- Additional batting signal features ---
    # Boundary rate: (fours + sixes) / balls_faced, rolling 5
    batter_innings["boundary_count"] = batter_innings["fours"] + batter_innings["sixes"]
    batter_innings["boundary_rate"] = np.where(
        batter_innings["balls_faced"] > 0,
        batter_innings["boundary_count"] / batter_innings["balls_faced"],
        0,
    )
    batter_innings["rolling_boundary_rate_5"] = (
        batter_innings.groupby("batter_id")["boundary_rate"]
        .transform(lambda x: x.rolling(ROLLING_WINDOW_SHORT, min_periods=1).mean().shift(1))
    )

    # Consistency: rolling std / rolling mean (coefficient of variation)
    batter_innings["rolling_std_runs_5"] = (
        batter_innings.groupby("batter_id")["runs_scored"]
        .transform(lambda x: x.rolling(ROLLING_WINDOW_SHORT, min_periods=2).std().shift(1))
    )
    batter_innings["consistency_score"] = np.where(
        batter_innings["rolling_avg_runs_5"] > 0,
        1.0 - (batter_innings["rolling_std_runs_5"] / (batter_innings["rolling_avg_runs_5"] + 1)),
        0.5,
    ).clip(0, 1)

    # Opposition bowling quality: avg runs conceded per ball by opposition in last 5 innings
    opp_quality = (
        batter_innings.groupby(["bowling_team_id", "match_date"])["runs_scored"]
        .mean()
        .reset_index()
        .rename(columns={"runs_scored": "opp_runs_allowed"})
    )
    opp_quality = opp_quality.sort_values("match_date")
    opp_quality["opp_bowling_quality"] = (
        opp_quality.groupby("bowling_team_id")["opp_runs_allowed"]
        .transform(lambda x: x.rolling(ROLLING_WINDOW_SHORT, min_periods=1).mean().shift(1))
    )
    batter_innings = batter_innings.merge(
        opp_quality[["bowling_team_id", "match_date", "opp_bowling_quality"]].drop_duplicates(),
        on=["bowling_team_id", "match_date"],
        how="left",
    )

    league_avg_br = batter_innings["boundary_rate"].mean()
    batter_innings["rolling_boundary_rate_5"] = batter_innings["rolling_boundary_rate_5"].fillna(league_avg_br)
    batter_innings["consistency_score"] = batter_innings["consistency_score"].fillna(0.5)
    batter_innings["opp_bowling_quality"] = batter_innings["opp_bowling_quality"].fillna(
        batter_innings["runs_scored"].mean()
    )

    # Select feature columns
    feature_cols = [
        "match_id", "match_date", "batter_id", "venue_id",
        "batting_team_id", "bowling_team_id",
        "venue_boundary_distance_m", "venue_outfield_speed", "batting_style_left",
        "batting_position",
        "rolling_avg_runs_5", "rolling_sr_5", "rolling_avg_runs_10",
        "career_avg_at_venue", "career_avg_vs_opposition", "career_sr",
        "innings_count", "days_since_last_match",
        "is_home", "toss_elected_bat", "is_debut",
        # New features
        "rolling_boundary_rate_5", "consistency_score", "opp_bowling_quality",
        "runs_scored",  # target
    ]
    return batter_innings[feature_cols].copy()


def build_bowling_features(
    deliveries_df: pd.DataFrame,
    matches_df: pd.DataFrame,
    players_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Build one row per (bowler, match, innings) for bowling prediction.

    Target: wickets taken by the bowler in that innings.
    """
    # Aggregate per bowler per innings
    bowler_innings = (
        deliveries_df.groupby(["match_id", "innings", "bowler_id", "batting_team_id", "bowling_team_id"])
        .agg(
            wickets_taken=("is_wicket", "sum"),
            runs_conceded=("runs_batter", "sum"),
            extras_conceded=("runs_extras", "sum"),
            balls_bowled=("bowler_id", "count"),
            dot_balls=("runs_batter", lambda x: (x == 0).sum()),
        )
        .reset_index()
    )

    bowler_innings["overs_bowled"] = bowler_innings["balls_bowled"] / 6
    bowler_innings["economy"] = np.where(
        bowler_innings["overs_bowled"] > 0,
        (bowler_innings["runs_conceded"] + bowler_innings["extras_conceded"]) / bowler_innings["overs_bowled"],
        0,
    )
    bowler_innings["dot_ball_pct"] = np.where(
        bowler_innings["balls_bowled"] > 0,
        bowler_innings["dot_balls"] / bowler_innings["balls_bowled"],
        0,
    )

    # Merge match info
    bowler_innings = bowler_innings.merge(
        matches_df[["match_id", "match_date", "venue_id", "boundary_distance_m", "outfield_speed"]],
        on="match_id",
        how="left",
    )

    if players_df is not None and not players_df.empty:
        bowler_profiles = players_df[["player_id", "bowling_arm", "bowling_type"]].rename(columns={"player_id": "bowler_id"})
        bowler_innings = bowler_innings.merge(bowler_profiles, on="bowler_id", how="left")
    else:
        bowler_innings["bowling_arm"] = None
        bowler_innings["bowling_type"] = None

    bowler_innings["bowling_arm_left"] = bowler_innings["bowling_arm"].fillna("").astype(str).str.contains("left", case=False, na=False).astype(int)
    bowler_innings["bowling_type_spin"] = bowler_innings["bowling_type"].fillna("").astype(str).str.contains("spin", case=False, na=False).astype(int)
    bowler_innings["venue_boundary_distance_m"] = bowler_innings["boundary_distance_m"]
    bowler_innings["venue_outfield_speed"] = bowler_innings["outfield_speed"]
    bowler_innings = bowler_innings.sort_values(["bowler_id", "match_date"]).reset_index(drop=True)

    # --- Rolling features with shift(1) ---
    bowler_innings["rolling_avg_wickets_5"] = (
        bowler_innings.groupby("bowler_id")["wickets_taken"]
        .transform(lambda x: x.rolling(ROLLING_WINDOW_SHORT, min_periods=1).mean().shift(1))
    )
    bowler_innings["rolling_economy_5"] = (
        bowler_innings.groupby("bowler_id")["economy"]
        .transform(lambda x: x.rolling(ROLLING_WINDOW_SHORT, min_periods=1).mean().shift(1))
    )
    bowler_innings["rolling_avg_wickets_10"] = (
        bowler_innings.groupby("bowler_id")["wickets_taken"]
        .transform(lambda x: x.rolling(ROLLING_WINDOW_LONG, min_periods=1).mean().shift(1))
    )
    bowler_innings["career_economy"] = (
        bowler_innings.groupby("bowler_id")["economy"]
        .transform(lambda x: x.expanding().mean().shift(1))
    )
    bowler_innings["career_avg_wickets_at_venue"] = (
        bowler_innings.groupby(["bowler_id", "venue_id"])["wickets_taken"]
        .transform(lambda x: x.expanding().mean().shift(1))
    )
    bowler_innings["overs_bowled_career"] = (
        bowler_innings.groupby("bowler_id")["overs_bowled"]
        .transform(lambda x: x.expanding().sum().shift(1))
    )
    bowler_innings["dot_ball_pct_rolling_5"] = (
        bowler_innings.groupby("bowler_id")["dot_ball_pct"]
        .transform(lambda x: x.rolling(ROLLING_WINDOW_SHORT, min_periods=1).mean().shift(1))
    )
    bowler_innings["innings_count"] = bowler_innings.groupby("bowler_id").cumcount()

    # Days since last match
    bowler_innings["prev_date"] = bowler_innings.groupby("bowler_id")["match_date"].shift(1)
    bowler_innings["days_since_last_match"] = (
        (bowler_innings["match_date"] - bowler_innings["prev_date"]).dt.days
    )

    # Fill NaN
    league_avg_wk = bowler_innings["wickets_taken"].mean()
    league_avg_eco = bowler_innings["economy"].mean()
    league_avg_dot = bowler_innings["dot_ball_pct"].mean()

    fill_map = {
        "rolling_avg_wickets_5": league_avg_wk,
        "rolling_economy_5": league_avg_eco,
        "rolling_avg_wickets_10": league_avg_wk,
        "career_economy": league_avg_eco,
        "career_avg_wickets_at_venue": league_avg_wk,
        "overs_bowled_career": 0,
        "dot_ball_pct_rolling_5": league_avg_dot,
        "days_since_last_match": 30,
        "bowling_arm_left": 0,
        "bowling_type_spin": 0,
        "venue_boundary_distance_m": 75.0,
        "venue_outfield_speed": 1.0,
    }
    for col, val in fill_map.items():
        bowler_innings[col] = bowler_innings[col].fillna(val)

    # --- Additional bowling signal features ---
    # Career strike rate: balls per wicket (lower = better)
    bowler_innings["career_strike_rate"] = (
        bowler_innings.groupby("bowler_id")
        .apply(lambda g: (g["balls_bowled"].expanding().sum() / (g["wickets_taken"].expanding().sum() + 1e-9)).shift(1))
        .reset_index(level=0, drop=True)
    )

    # Rolling wicket rate: wickets per ball last 5 innings
    bowler_innings["wicket_rate"] = np.where(
        bowler_innings["balls_bowled"] > 0,
        bowler_innings["wickets_taken"] / bowler_innings["balls_bowled"],
        0,
    )
    bowler_innings["rolling_wicket_rate_5"] = (
        bowler_innings.groupby("bowler_id")["wicket_rate"]
        .transform(lambda x: x.rolling(ROLLING_WINDOW_SHORT, min_periods=1).mean().shift(1))
    )

    # Opposition batting quality: avg runs scored by opposition in last 5 innings
    opp_bat_quality = (
        bowler_innings.groupby(["batting_team_id", "match_date"])["runs_conceded"]
        .mean()
        .reset_index()
        .rename(columns={"runs_conceded": "opp_bat_avg"})
    )
    opp_bat_quality = opp_bat_quality.sort_values("match_date")
    opp_bat_quality["opp_batting_quality"] = (
        opp_bat_quality.groupby("batting_team_id")["opp_bat_avg"]
        .transform(lambda x: x.rolling(ROLLING_WINDOW_SHORT, min_periods=1).mean().shift(1))
    )
    bowler_innings = bowler_innings.merge(
        opp_bat_quality[["batting_team_id", "match_date", "opp_batting_quality"]].drop_duplicates(),
        on=["batting_team_id", "match_date"],
        how="left",
    )

    league_avg_sr_bowl = bowler_innings["balls_bowled"].sum() / (bowler_innings["wickets_taken"].sum() + 1e-9)
    league_wk_rate = bowler_innings["wicket_rate"].mean()
    bowler_innings["career_strike_rate"] = bowler_innings["career_strike_rate"].fillna(league_avg_sr_bowl)
    bowler_innings["rolling_wicket_rate_5"] = bowler_innings["rolling_wicket_rate_5"].fillna(league_wk_rate)
    bowler_innings["opp_batting_quality"] = bowler_innings["opp_batting_quality"].fillna(
        bowler_innings["runs_conceded"].mean()
    )

    feature_cols = [
        "match_id", "match_date", "bowler_id", "venue_id",
        "batting_team_id", "bowling_team_id",
        "venue_boundary_distance_m", "venue_outfield_speed", "bowling_arm_left", "bowling_type_spin",
        "rolling_avg_wickets_5", "rolling_economy_5", "rolling_avg_wickets_10",
        "career_avg_wickets_at_venue", "career_economy",
        "overs_bowled_career", "dot_ball_pct_rolling_5",
        "innings_count", "days_since_last_match",
        # New features
        "career_strike_rate", "rolling_wicket_rate_5", "opp_batting_quality",
        "wickets_taken",  # target
    ]
    return bowler_innings[feature_cols].copy()


def _is_home(team_name: str, city: str) -> int:
    if not city or not team_name:
        return 0
    home_cities = TEAM_HOME_CITIES.get(team_name, [])
    return int(any(hc.lower() in str(city).lower() for hc in home_cities))
