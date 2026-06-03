"""
Match-level feature engineering for Model 1: Match Outcome Prediction.

Produces one row per match with historical features computed using only
data BEFORE each match date (anti-leakage protocol).
"""
import numpy as np
import pandas as pd
from ml.config import TEAM_HOME_CITIES, MATCH_STAGE_MAP
from ml.utils import is_home_city


def build_match_features(matches_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build the full match feature matrix.

    Parameters
    ----------
    matches_df : DataFrame from db_connect.load_matches() — must have columns:
        match_id, match_date, venue_id, team1_id, team2_id,
        toss_winner_id, toss_decision, match_won_by_id,
        venue_name, city, team1_name, team2_name, toss_winner_name, match_winner_name

    Returns
    -------
    DataFrame with one row per match and engineered features + target.
    """
    df = matches_df.copy()
    # Exclude matches with no result
    df = df.dropna(subset=["match_won_by_id"])
    df = df.sort_values("match_date").reset_index(drop=True)

    # --- Target: 1 if team1 wins, 0 if team2 wins ---
    df["target"] = (df["match_won_by_id"] == df["team1_id"]).astype(int)

    # --- Static features ---
    df["toss_winner_is_team1"] = (df["toss_winner_id"] == df["team1_id"]).astype(int)
    df["toss_decision_bat"] = (df["toss_decision"] == "bat").astype(int)
    df["venue_boundary_distance_m"] = df["boundary_distance_m"]
    df["venue_outfield_speed"] = df["outfield_speed"]

    # Home city
    df["team1_is_home"] = df.apply(
        lambda r: is_home_city(r["team1_name"], r["city"]), axis=1
    )
    df["team2_is_home"] = df.apply(
        lambda r: is_home_city(r["team2_name"], r["city"]), axis=1
    )

    # --- Historical features (expanding, prior-only) ---
    # We build helper columns then merge back

    # 1) Team overall win percentage
    df["team1_win_pct_overall"] = _expanding_team_win_pct(df, "team1_id")
    df["team2_win_pct_overall"] = _expanding_team_win_pct(df, "team2_id")

    # 2) Team win% at venue
    df["team1_win_pct_at_venue"] = _expanding_team_venue_win_pct(df, "team1_id")
    df["team2_win_pct_at_venue"] = _expanding_team_venue_win_pct(df, "team2_id")

    # 3) Head-to-head win%
    df["h2h_team1_win_pct"] = _expanding_h2h_win_pct(df)

    # 4) Recent form (last 5 matches)
    df["team1_recent_form"] = _rolling_team_form(df, "team1_id", window=5)
    df["team2_recent_form"] = _rolling_team_form(df, "team2_id", window=5)

    # 5) Venue chasing win%
    df["venue_chasing_win_pct"] = _expanding_venue_chasing_pct(df)

    # 6) Season stage (match_stage not in DB — infer from date position in season)
    df["season"] = df["match_date"].dt.year

    # --- Differential / interaction features ---
    # These give the model directional signal between the two teams
    df["win_pct_diff"] = df["team1_win_pct_overall"] - df["team2_win_pct_overall"]
    df["form_diff"] = df["team1_recent_form"] - df["team2_recent_form"]
    df["venue_pct_diff"] = df["team1_win_pct_at_venue"] - df["team2_win_pct_at_venue"]
    df["h2h_advantage"] = df["h2h_team1_win_pct"] - 0.5  # Positive = team1 historically dominant

    # 6) Recent form over last 3 matches (shorter window)
    df["team1_form_3"] = _rolling_team_form(df, "team1_id", window=3)
    df["team2_form_3"] = _rolling_team_form(df, "team2_id", window=3)
    df["form_diff_3"] = df["team1_form_3"] - df["team2_form_3"]

    # 7) Toss-specific win advantage: does batting/fielding first help at this venue?
    df["toss_bat_venue_advantage"] = (
        df["toss_decision_bat"] * df["venue_chasing_win_pct"]  # high chase% => batfirst advantage low
        + (1 - df["toss_decision_bat"]) * (1 - df["venue_chasing_win_pct"])
    )

    # 8) Home advantage differential
    df["home_advantage"] = df["team1_is_home"].astype(int) - df["team2_is_home"].astype(int)

    # --- Select final feature columns ---
    feature_cols = [
        "match_id", "match_date", "season",
        "venue_id", "team1_id", "team2_id",
        "venue_boundary_distance_m", "venue_outfield_speed",
        "toss_winner_is_team1", "toss_decision_bat",
        "team1_win_pct_overall", "team2_win_pct_overall",
        "team1_win_pct_at_venue", "team2_win_pct_at_venue",
        "h2h_team1_win_pct",
        "team1_recent_form", "team2_recent_form",
        "venue_chasing_win_pct",
        "team1_is_home", "team2_is_home",
        # Differential / interaction features
        "win_pct_diff", "form_diff", "venue_pct_diff",
        "h2h_advantage", "team1_form_3", "team2_form_3",
        "form_diff_3", "toss_bat_venue_advantage", "home_advantage",
        "target",
        # Keep names for lookup
        "team1_name", "team2_name", "venue_name",
    ]
    result = df[feature_cols].copy()

    # Fill NaN historical features with 0.5 (no prior info = coin flip)
    hist_cols = [
        "team1_win_pct_overall", "team2_win_pct_overall",
        "team1_win_pct_at_venue", "team2_win_pct_at_venue",
        "h2h_team1_win_pct",
        "team1_recent_form", "team2_recent_form",
        "venue_chasing_win_pct",
        "team1_form_3", "team2_form_3",
    ]
    result[hist_cols] = result[hist_cols].fillna(0.5)
    result["venue_boundary_distance_m"] = result["venue_boundary_distance_m"].fillna(75.0)
    result["venue_outfield_speed"] = result["venue_outfield_speed"].fillna(1.0)

    # Fill differential features derived from the above
    diff_cols = [
        "win_pct_diff", "form_diff", "venue_pct_diff",
        "h2h_advantage", "form_diff_3", "toss_bat_venue_advantage", "home_advantage",
    ]
    result[diff_cols] = result[diff_cols].fillna(0.0)

    return result


# ---- Internal helpers ----

def _expanding_team_win_pct(df: pd.DataFrame, team_col: str) -> pd.Series:
    """
    For each match, compute team's overall win% using only prior matches.
    This requires unpacking matches into a per-team timeline.
    """
    records = []
    for idx, row in df.iterrows():
        team_id = row[team_col]
        match_date = row["match_date"]
        won = row["match_won_by_id"]

        # All prior matches where this team played (as team1 or team2)
        prior = df[
            (df["match_date"] < match_date)
            & ((df["team1_id"] == team_id) | (df["team2_id"] == team_id))
        ]
        if len(prior) == 0:
            records.append(np.nan)
        else:
            wins = (prior["match_won_by_id"] == team_id).sum()
            records.append(wins / len(prior))

    return pd.Series(records, index=df.index)


def _expanding_team_venue_win_pct(df: pd.DataFrame, team_col: str) -> pd.Series:
    """Team's win% at the specific venue, using only prior matches."""
    records = []
    for idx, row in df.iterrows():
        team_id = row[team_col]
        venue_id = row["venue_id"]
        match_date = row["match_date"]

        prior = df[
            (df["match_date"] < match_date)
            & (df["venue_id"] == venue_id)
            & ((df["team1_id"] == team_id) | (df["team2_id"] == team_id))
        ]
        if len(prior) == 0:
            records.append(np.nan)
        else:
            wins = (prior["match_won_by_id"] == team_id).sum()
            records.append(wins / len(prior))

    return pd.Series(records, index=df.index)


def _expanding_h2h_win_pct(df: pd.DataFrame) -> pd.Series:
    """Team1's win% against team2 in prior H2H matches."""
    records = []
    for idx, row in df.iterrows():
        t1 = row["team1_id"]
        t2 = row["team2_id"]
        match_date = row["match_date"]

        prior = df[
            (df["match_date"] < match_date)
            & (
                ((df["team1_id"] == t1) & (df["team2_id"] == t2))
                | ((df["team1_id"] == t2) & (df["team2_id"] == t1))
            )
        ]
        if len(prior) == 0:
            records.append(np.nan)
        else:
            wins = (prior["match_won_by_id"] == t1).sum()
            records.append(wins / len(prior))

    return pd.Series(records, index=df.index)


def _rolling_team_form(df: pd.DataFrame, team_col: str, window: int = 5) -> pd.Series:
    """Team's win% in their last `window` matches (prior only)."""
    records = []
    for idx, row in df.iterrows():
        team_id = row[team_col]
        match_date = row["match_date"]

        prior = df[
            (df["match_date"] < match_date)
            & ((df["team1_id"] == team_id) | (df["team2_id"] == team_id))
        ].tail(window)

        if len(prior) == 0:
            records.append(np.nan)
        else:
            wins = (prior["match_won_by_id"] == team_id).sum()
            records.append(wins / len(prior))

    return pd.Series(records, index=df.index)


def _expanding_venue_chasing_pct(df: pd.DataFrame) -> pd.Series:
    """% of matches won by the chasing team at this venue (prior only)."""
    records = []
    for idx, row in df.iterrows():
        venue_id = row["venue_id"]
        match_date = row["match_date"]

        prior = df[
            (df["match_date"] < match_date)
            & (df["venue_id"] == venue_id)
        ]
        if len(prior) == 0:
            records.append(np.nan)
        else:
            # Chasing team = team2 when toss winner chose bat and is team1,
            # or the team that bowled first. Simplification: team that won
            # and wasn't batting first. We approximate: if toss decision is 'bat',
            # chasing team is the other team; if 'field', toss winner chases.
            chasing_wins = 0
            for _, pr in prior.iterrows():
                if pr["toss_decision"] == "bat":
                    # Toss winner batted first → chasing team is the other
                    if pr["toss_winner_id"] == pr["team1_id"]:
                        chasing_team = pr["team2_id"]
                    else:
                        chasing_team = pr["team1_id"]
                else:
                    # Toss winner fielded → toss winner chases
                    chasing_team = pr["toss_winner_id"]

                if pr["match_won_by_id"] == chasing_team:
                    chasing_wins += 1

            records.append(chasing_wins / len(prior))

    return pd.Series(records, index=df.index)
