"""
Innings-level feature engineering for Model 2: Mid-Match Score Prediction.

Replays every 1st innings, capturing the game state at the end of each over
(1 through 20). Creates ~20 rows per match for training.
"""
import numpy as np
import pandas as pd


def build_innings_features(deliveries_df: pd.DataFrame, matches_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build feature matrix for score prediction.

    Parameters
    ----------
    deliveries_df : DataFrame from db_connect.load_deliveries()
    matches_df : DataFrame from db_connect.load_matches()

    Returns
    -------
    DataFrame with one row per (match, over) checkpoint with features + target.
    """
    # Filter to 1st innings only
    first = deliveries_df[deliveries_df["innings"] == 1].copy()

    # Compute the target: total 1st innings score per match
    match_totals = (
        first.groupby("match_id")
        .agg(total_runs=("runs_batter", "sum"), total_extras=("runs_extras", "sum"))
        .reset_index()
    )
    match_totals["target_total"] = match_totals["total_runs"] + match_totals["total_extras"]

    # Compute historical venue/team averages from matches_df
    venue_avg, bat_team_avg, bowl_team_avg = _compute_historical_averages(
        first, matches_df
    )

    # Build per-over snapshots
    rows = []
    for match_id, match_deliveries in first.groupby("match_id"):
        match_info = matches_df[matches_df["match_id"] == match_id]
        if match_info.empty:
            continue
        match_info = match_info.iloc[0]
        match_date = match_info["match_date"]
        venue_id = match_info["venue_id"]
        batting_team_id = match_deliveries["batting_team_id"].iloc[0]
        bowling_team_id = match_deliveries["bowling_team_id"].iloc[0]

        target = match_totals[match_totals["match_id"] == match_id]
        if target.empty:
            continue
        target_total = target.iloc[0]["target_total"]

        # Sort deliveries
        md = match_deliveries.sort_values(["over_num", "ball_num"])

        max_over = md["over_num"].max()

        for over_end in range(1, min(max_over + 1, 21)):
            balls_in_range = md[md["over_num"] <= over_end]
            runs_so_far = balls_in_range["runs_batter"].sum() + balls_in_range["runs_extras"].sum()
            wickets_so_far = balls_in_range["is_wicket"].sum()
            boundaries = ((balls_in_range["runs_batter"] == 4) | (balls_in_range["runs_batter"] == 6)).sum()
            dot_balls = ((balls_in_range["runs_batter"] == 0) & (balls_in_range["runs_extras"] == 0)).sum()
            total_balls = len(balls_in_range)
            extras_so_far = balls_in_range["runs_extras"].sum()

            current_rr = runs_so_far / over_end if over_end > 0 else 0

            # Last 3 overs run rate
            if over_end >= 3:
                last3 = md[(md["over_num"] > over_end - 3) & (md["over_num"] <= over_end)]
                last3_runs = last3["runs_batter"].sum() + last3["runs_extras"].sum()
                rr_last_3 = last3_runs / 3
            else:
                rr_last_3 = current_rr

            # Powerplay run rate (overs 1-6)
            if over_end >= 6:
                pp = md[md["over_num"] <= 6]
                pp_runs = pp["runs_batter"].sum() + pp["runs_extras"].sum()
                rr_powerplay = pp_runs / 6
            else:
                rr_powerplay = current_rr

            dot_pct = dot_balls / total_balls if total_balls > 0 else 0

            # Historical averages (pre-computed, looked up by date)
            v_avg = venue_avg.get((venue_id, match_date), np.nan)
            bt_avg = bat_team_avg.get((batting_team_id, match_date), np.nan)
            bw_avg = bowl_team_avg.get((bowling_team_id, match_date), np.nan)

            balls_remaining = max(0, 120 - (over_end * 6))
            wickets_in_hand = 10 - int(wickets_so_far)
            boundary_rate = boundaries / total_balls if total_balls > 0 else 0
            wicket_rate = int(wickets_so_far) / total_balls if total_balls > 0 else 0
            runs_per_ball = runs_so_far / total_balls if total_balls > 0 else 0

            rows.append({
                "match_id": match_id,
                "match_date": match_date,
                "venue_id": venue_id,
                "venue_boundary_distance_m": match_info.get("boundary_distance_m"),
                "venue_outfield_speed": match_info.get("outfield_speed"),
                "batting_team_id": batting_team_id,
                "bowling_team_id": bowling_team_id,
                "current_over": over_end,
                "runs_scored_so_far": runs_so_far,
                "wickets_fallen_so_far": wickets_so_far,
                "current_run_rate": round(current_rr, 4),
                "run_rate_last_3_overs": round(rr_last_3, 4),
                "run_rate_powerplay": round(rr_powerplay, 4),
                "boundaries_so_far": boundaries,
                "dot_ball_pct_so_far": round(dot_pct, 4),
                "extras_so_far": extras_so_far,
                "venue_avg_1st_innings": v_avg,
                "batting_team_avg_score": bt_avg,
                "bowling_team_avg_conceded": bw_avg,
                "is_powerplay": int(over_end <= 6),
                "is_middle": int(6 < over_end < 16),
                "is_death": int(over_end >= 16),
                # New high-signal features
                "balls_remaining": balls_remaining,
                "wickets_in_hand": wickets_in_hand,
                "boundary_rate": round(boundary_rate, 4),
                "wicket_rate": round(wicket_rate, 4),
                "runs_per_ball": round(runs_per_ball, 4),
                "target_total": target_total,
            })

    result = pd.DataFrame(rows)

    # Fill NaN historical averages with global mean
    for col in ["venue_avg_1st_innings", "batting_team_avg_score", "bowling_team_avg_conceded"]:
        global_mean = result["target_total"].mean()
        result[col] = result[col].fillna(global_mean)

    result["venue_boundary_distance_m"] = result["venue_boundary_distance_m"].fillna(75.0)
    result["venue_outfield_speed"] = result["venue_outfield_speed"].fillna(1.0)

    return result


def _compute_historical_averages(first_innings_df: pd.DataFrame, matches_df: pd.DataFrame):
    """
    Pre-compute historical averages for venues and teams.
    Returns dicts keyed by (id, match_date) → average using only prior data.
    """
    # Compute total per match
    match_scores = (
        first_innings_df.groupby("match_id")
        .apply(lambda g: g["runs_batter"].sum() + g["runs_extras"].sum())
        .reset_index(name="total_score")
    )
    match_scores = match_scores.merge(
        matches_df[["match_id", "match_date", "venue_id"]],
        on="match_id",
    )

    # Add batting/bowling team per match (from first innings)
    team_info = (
        first_innings_df.groupby("match_id")[["batting_team_id", "bowling_team_id"]]
        .first()
        .reset_index()
    )
    match_scores = match_scores.merge(team_info, on="match_id")
    match_scores = match_scores.sort_values("match_date").reset_index(drop=True)

    # Build lookups
    venue_avg = {}
    bat_avg = {}
    bowl_avg = {}

    for idx, row in match_scores.iterrows():
        md = row["match_date"]
        prior = match_scores[match_scores["match_date"] < md]

        # Venue average
        v_prior = prior[prior["venue_id"] == row["venue_id"]]
        venue_avg[(row["venue_id"], md)] = v_prior["total_score"].mean() if len(v_prior) > 0 else np.nan

        # Batting team average
        bt_prior = prior[prior["batting_team_id"] == row["batting_team_id"]]
        bat_avg[(row["batting_team_id"], md)] = bt_prior["total_score"].mean() if len(bt_prior) > 0 else np.nan

        # Bowling team conceded average
        bw_prior = prior[prior["bowling_team_id"] == row["bowling_team_id"]]
        bowl_avg[(row["bowling_team_id"], md)] = bw_prior["total_score"].mean() if len(bw_prior) > 0 else np.nan

    return venue_avg, bat_avg, bowl_avg
