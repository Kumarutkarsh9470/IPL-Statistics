"""
Master feature engineering pipeline.
Reads from MySQL, builds all feature matrices, saves as CSVs.

Usage:
    python -m ml.features.build_features
"""
import time
from pathlib import Path

from ml.db_connect import load_matches, load_deliveries, load_players
from ml.features.match_features import build_match_features
from ml.features.innings_features import build_innings_features
from ml.features.player_features import build_batting_features, build_bowling_features
from ml.config import FEATURES_DIR

OUTPUT_DIR = FEATURES_DIR / "data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    print("=" * 60)
    print("IPL ML Feature Engineering Pipeline")
    print("=" * 60)

    # Load base data
    print("\n[1/6] Loading matches from MySQL...")
    t0 = time.time()
    matches_df = load_matches()
    print(f"  Loaded {len(matches_df)} matches in {time.time()-t0:.1f}s")

    print("\n[2/6] Loading deliveries from MySQL...")
    t0 = time.time()
    deliveries_df = load_deliveries()
    print(f"  Loaded {len(deliveries_df)} deliveries in {time.time()-t0:.1f}s")

    # Build features
    print("\n[3/7] Loading player metadata from MySQL...")
    t0 = time.time()
    players_df = load_players()
    print(f"  Loaded {len(players_df)} players in {time.time()-t0:.1f}s")

    print("\n[4/7] Building match outcome features...")
    t0 = time.time()
    match_features = build_match_features(matches_df)
    match_path = OUTPUT_DIR / "match_features.csv"
    match_features.to_csv(match_path, index=False)
    print(f"  {len(match_features)} rows → {match_path} ({time.time()-t0:.1f}s)")

    print("\n[5/7] Building innings score features...")
    t0 = time.time()
    innings_features = build_innings_features(deliveries_df, matches_df)
    innings_path = OUTPUT_DIR / "innings_features.csv"
    innings_features.to_csv(innings_path, index=False)
    print(f"  {len(innings_features)} rows → {innings_path} ({time.time()-t0:.1f}s)")

    print("\n[6/7] Building batting features...")
    t0 = time.time()
    batting_features = build_batting_features(deliveries_df, matches_df, players_df)
    batting_path = OUTPUT_DIR / "batting_features.csv"
    batting_features.to_csv(batting_path, index=False)
    print(f"  {len(batting_features)} rows → {batting_path} ({time.time()-t0:.1f}s)")

    print("\n[7/7] Building bowling features...")
    t0 = time.time()
    bowling_features = build_bowling_features(deliveries_df, matches_df, players_df)
    bowling_path = OUTPUT_DIR / "bowling_features.csv"
    bowling_features.to_csv(bowling_path, index=False)
    print(f"  {len(bowling_features)} rows → {bowling_path} ({time.time()-t0:.1f}s)")

    print("\n" + "=" * 60)
    print("Feature engineering complete!")
    print(f"  Players metadata: {len(players_df)} rows")
    print(f"  Match features:   {len(match_features)} rows")
    print(f"  Innings features: {len(innings_features)} rows")
    print(f"  Batting features: {len(batting_features)} rows")
    print(f"  Bowling features: {len(bowling_features)} rows")
    print("=" * 60)


if __name__ == "__main__":
    main()
