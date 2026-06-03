"""
Build pre-computed feature lookup tables for fast inference.
Uses the latest data from MySQL to compute historical stats for every
team/venue/player combination.

Run after training models, before starting the server.

Usage:
    python -m ml.build_lookups
"""
import joblib
import numpy as np
import pandas as pd

from ml.config import MODELS_DIR, ROLLING_WINDOW_SHORT
from ml.db_connect import load_matches, load_deliveries


def main():
    print("Building pre-computed feature lookups for inference...")
    lookups = {}

    matches = load_matches()
    deliveries = load_deliveries()

    matches = matches.dropna(subset=["match_won_by_id"])
    matches = matches.sort_values("match_date")

    # --- Team overall win percentage (latest) ---
    print("  Computing team win percentages...")
    all_team_ids = set(matches["team1_id"].unique()) | set(matches["team2_id"].unique())
    for tid in all_team_ids:
        team_matches = matches[
            (matches["team1_id"] == tid) | (matches["team2_id"] == tid)
        ]
        if len(team_matches) > 0:
            wins = (team_matches["match_won_by_id"] == tid).sum()
            lookups[f"team_win_pct_{tid}"] = round(wins / len(team_matches), 4)

    # --- Team win% at each venue ---
    print("  Computing team-venue win percentages...")
    for tid in all_team_ids:
        for vid in matches["venue_id"].unique():
            tv = matches[
                ((matches["team1_id"] == tid) | (matches["team2_id"] == tid))
                & (matches["venue_id"] == vid)
            ]
            if len(tv) > 0:
                wins = (tv["match_won_by_id"] == tid).sum()
                lookups[f"team_venue_{tid}_{vid}"] = round(wins / len(tv), 4)

    # --- H2H ---
    print("  Computing H2H records...")
    team_list = sorted(all_team_ids)
    for i, t1 in enumerate(team_list):
        for t2 in team_list[i+1:]:
            h2h = matches[
                ((matches["team1_id"] == t1) & (matches["team2_id"] == t2))
                | ((matches["team1_id"] == t2) & (matches["team2_id"] == t1))
            ]
            if len(h2h) > 0:
                t1_wins = (h2h["match_won_by_id"] == t1).sum()
                lookups[f"h2h_{t1}_{t2}"] = round(t1_wins / len(h2h), 4)
                lookups[f"h2h_{t2}_{t1}"] = round(1 - t1_wins / len(h2h), 4)

    # --- Recent form (last 5 and last 3) ---
    print("  Computing recent form...")
    for tid in all_team_ids:
        recent5 = matches[
            (matches["team1_id"] == tid) | (matches["team2_id"] == tid)
        ].tail(ROLLING_WINDOW_SHORT)
        if len(recent5) > 0:
            wins = (recent5["match_won_by_id"] == tid).sum()
            lookups[f"form_{tid}"] = round(wins / len(recent5), 4)

        recent3 = matches[
            (matches["team1_id"] == tid) | (matches["team2_id"] == tid)
        ].tail(3)
        if len(recent3) > 0:
            wins = (recent3["match_won_by_id"] == tid).sum()
            lookups[f"form3_{tid}"] = round(wins / len(recent3), 4)

    # --- Venue chasing win% ---
    print("  Computing venue chasing stats...")
    for vid in matches["venue_id"].unique():
        vm = matches[matches["venue_id"] == vid]
        if len(vm) > 0:
            chasing_wins = 0
            for _, row in vm.iterrows():
                if row["toss_decision"] == "bat":
                    chasing = row["team2_id"] if row["toss_winner_id"] == row["team1_id"] else row["team1_id"]
                else:
                    chasing = row["toss_winner_id"]
                if row["match_won_by_id"] == chasing:
                    chasing_wins += 1
            lookups[f"venue_chase_{vid}"] = round(chasing_wins / len(vm), 4)

    # --- Venue/team averages for score prediction ---
    print("  Computing score prediction lookups...")
    first_innings = deliveries[deliveries["innings"] == 1]
    match_totals = (
        first_innings.groupby("match_id")
        .agg(total=("runs_batter", "sum"), extras=("runs_extras", "sum"))
        .reset_index()
    )
    match_totals["score"] = match_totals["total"] + match_totals["extras"]
    match_totals = match_totals.merge(
        matches[["match_id", "venue_id"]], on="match_id"
    )
    team_per_match = first_innings.groupby("match_id")[["batting_team_id", "bowling_team_id"]].first().reset_index()
    match_totals = match_totals.merge(team_per_match, on="match_id")

    for vid in match_totals["venue_id"].unique():
        vs = match_totals[match_totals["venue_id"] == vid]["score"]
        lookups[f"venue_avg_{vid}"] = round(vs.mean(), 1)

    for tid in match_totals["batting_team_id"].unique():
        ts = match_totals[match_totals["batting_team_id"] == tid]["score"]
        lookups[f"bat_team_avg_{tid}"] = round(ts.mean(), 1)

    for tid in match_totals["bowling_team_id"].unique():
        ts = match_totals[match_totals["bowling_team_id"] == tid]["score"]
        lookups[f"bowl_team_avg_{tid}"] = round(ts.mean(), 1)

    # --- Player batting lookups ---
    print("  Computing player batting lookups...")
    bat = (
        deliveries.groupby(["match_id", "innings", "batter_id", "batting_team_id", "bowling_team_id"])
        .agg(
            runs=("runs_batter", "sum"),
            balls=("batter_id", "count"),
        )
        .reset_index()
    )
    bat["sr"] = np.where(bat["balls"] > 0, bat["runs"] / bat["balls"] * 100, 0)
    bat = bat.merge(matches[["match_id", "match_date", "venue_id"]], on="match_id")
    bat = bat.sort_values(["batter_id", "match_date"])

    for pid, grp in bat.groupby("batter_id"):
        prefix = f"bat_{pid}"
        last5 = grp.tail(ROLLING_WINDOW_SHORT)
        lookups[f"{prefix}_avg5"] = round(last5["runs"].mean(), 1)
        lookups[f"{prefix}_sr5"] = round(last5["sr"].mean(), 1)
        last10 = grp.tail(10)
        lookups[f"{prefix}_avg10"] = round(last10["runs"].mean(), 1)
        lookups[f"{prefix}_career_sr"] = round(grp["sr"].mean(), 1)
        lookups[f"{prefix}_innings"] = len(grp)
        lookups[f"{prefix}_pos"] = 5  # Default, could refine
        lookups[f"{prefix}_team"] = int(grp.iloc[-1]["batting_team_id"])

        if len(grp) >= 2:
            last_date = grp.iloc[-1]["match_date"]
            prev_date = grp.iloc[-2]["match_date"]
            lookups[f"{prefix}_days"] = (last_date - prev_date).days
        else:
            lookups[f"{prefix}_days"] = 30

        # Boundary rate (fours + sixes) / balls, rolling last 5
        if "fours" in grp.columns and "sixes" in grp.columns:
            last5_br = last5["fours"].sum() + last5["sixes"].sum()
            last5_balls = last5["balls"].sum()
            lookups[f"{prefix}_br5"] = round(last5_br / last5_balls, 4) if last5_balls > 0 else 0.15
        else:
            lookups[f"{prefix}_br5"] = 0.15

        # Consistency: 1 - (std / (mean + 1)) clipped to [0,1]
        if len(grp) >= 3:
            std5 = last5["runs"].std()
            mean5 = last5["runs"].mean()
            lookups[f"{prefix}_consistency"] = round(float(np.clip(1 - std5 / (mean5 + 1), 0, 1)), 4)
        else:
            lookups[f"{prefix}_consistency"] = 0.5

        # Per venue
        for vid, vgrp in grp.groupby("venue_id"):
            lookups[f"{prefix}_venue_{vid}"] = round(vgrp["runs"].mean(), 1)
            lookups[f"{prefix}_venue_{vid}_n"] = len(vgrp)

        # Per opposition
        for oid, ogrp in grp.groupby("bowling_team_id"):
            lookups[f"{prefix}_vs_{oid}"] = round(ogrp["runs"].mean(), 1)
            lookups[f"{prefix}_vs_{oid}_n"] = len(ogrp)

    # Opposition bowling quality: avg runs allowed per innings by each team (last 5)
    print("  Computing opposition quality lookups...")
    for tid in bat["bowling_team_id"].unique():
        opp_rows = bat[bat["bowling_team_id"] == tid].tail(ROLLING_WINDOW_SHORT)
        if len(opp_rows) > 0:
            lookups[f"opp_bowl_q_{tid}"] = round(opp_rows["runs"].mean(), 1)

    # --- Player bowling lookups ---
    print("  Computing player bowling lookups...")
    bowl = (
        deliveries.groupby(["match_id", "innings", "bowler_id", "batting_team_id", "bowling_team_id"])
        .agg(
            wickets=("is_wicket", "sum"),
            runs_conceded=("runs_batter", "sum"),
            extras=("runs_extras", "sum"),
            balls=("bowler_id", "count"),
            dots=("runs_batter", lambda x: (x == 0).sum()),
        )
        .reset_index()
    )
    bowl["overs"] = bowl["balls"] / 6
    bowl["economy"] = np.where(
        bowl["overs"] > 0,
        (bowl["runs_conceded"] + bowl["extras"]) / bowl["overs"],
        0,
    )
    bowl["dot_pct"] = np.where(bowl["balls"] > 0, bowl["dots"] / bowl["balls"], 0)
    bowl = bowl.merge(matches[["match_id", "match_date", "venue_id"]], on="match_id")
    bowl = bowl.sort_values(["bowler_id", "match_date"])

    for pid, grp in bowl.groupby("bowler_id"):
        prefix = f"bowl_{pid}"
        last5 = grp.tail(ROLLING_WINDOW_SHORT)
        lookups[f"{prefix}_wk5"] = round(last5["wickets"].mean(), 2)
        lookups[f"{prefix}_eco5"] = round(last5["economy"].mean(), 2)
        last10 = grp.tail(10)
        lookups[f"{prefix}_wk10"] = round(last10["wickets"].mean(), 2)
        lookups[f"{prefix}_career_eco"] = round(grp["economy"].mean(), 2)
        lookups[f"{prefix}_overs"] = round(grp["overs"].sum(), 1)
        lookups[f"{prefix}_dot5"] = round(last5["dot_pct"].mean(), 3)
        lookups[f"{prefix}_innings"] = len(grp)
        lookups[f"{prefix}_team"] = int(grp.iloc[-1]["bowling_team_id"])

        if len(grp) >= 2:
            lookups[f"{prefix}_days"] = (grp.iloc[-1]["match_date"] - grp.iloc[-2]["match_date"]).days
        else:
            lookups[f"{prefix}_days"] = 30

        # Career strike rate: total balls / total wickets
        total_balls_bowl = grp["balls"].sum()
        total_wk = grp["wickets"].sum()
        lookups[f"{prefix}_career_sr"] = round(total_balls_bowl / (total_wk + 1e-9), 2)

        # Rolling wicket rate (wickets/ball) last 5
        last5_wk = last5["wickets"].sum()
        last5_balls = last5["balls"].sum()
        lookups[f"{prefix}_wkr5"] = round(last5_wk / last5_balls, 4) if last5_balls > 0 else 0.03

        for vid, vgrp in grp.groupby("venue_id"):
            lookups[f"{prefix}_venue_{vid}"] = round(vgrp["wickets"].mean(), 2)
            lookups[f"{prefix}_venue_{vid}_n"] = len(vgrp)

        for oid, ogrp in grp.groupby("batting_team_id"):
            lookups[f"{prefix}_vs_{oid}_n"] = len(ogrp)

    # Opposition batting quality: avg runs scored per innings by each team (last 5)
    for tid in bowl["batting_team_id"].unique():
        opp_rows = bowl[bowl["batting_team_id"] == tid].tail(ROLLING_WINDOW_SHORT)
        if len(opp_rows) > 0:
            lookups[f"opp_bat_q_{tid}"] = round(opp_rows["runs_conceded"].mean(), 2)

    # Save
    out_path = MODELS_DIR / "feature_lookups.joblib"
    joblib.dump(lookups, out_path)
    print(f"\nSaved {len(lookups)} lookup entries to {out_path}")


if __name__ == "__main__":
    main()
