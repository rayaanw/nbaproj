"""T-012: Engineer game-situation and context features.

Builds the per-shot context features that don't require any external join:
time remaining in the period, home/away (via a static team-ID-to-abbreviation
lookup — no network call needed), and a cleaned period encoding with an
overtime flag.

Usage:
    python pipeline/06c_context_features.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from nba_api.stats.static import teams as static_teams

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import DATA_PROCESSED_DIR
from pipeline.features import compute_time_remaining_seconds, encode_period

INPUT_PATH = DATA_PROCESSED_DIR / "shots_consolidated.parquet"
OUTPUT_PATH = DATA_PROCESSED_DIR / "shots_context.parquet"


def team_id_to_abbreviation() -> dict[int, str]:
    """Static team reference bundled with nba_api — no network call required."""
    return {team["id"]: team["abbreviation"] for team in static_teams.get_teams()}


def compute_home_away(df: pd.DataFrame, team_lookup: dict[int, str]) -> pd.Series:
    """T-012.2: derive home/away by comparing the shooting player's team
    abbreviation to the game's home-team abbreviation (HTM).
    """
    shooter_abbrev = df["TEAM_ID"].map(team_lookup)
    return (shooter_abbrev == df["HTM"]).map({True: "home", False: "away"})


def main() -> None:
    if not INPUT_PATH.exists():
        raise SystemExit(f"{INPUT_PATH} not found — run 06_consolidate_shots.py first")

    df = pd.read_parquet(INPUT_PATH)

    df["time_remaining_in_period"] = compute_time_remaining_seconds(
        df["MINUTES_REMAINING"], df["SECONDS_REMAINING"]
    )

    team_lookup = team_id_to_abbreviation()
    df["home_away"] = compute_home_away(df, team_lookup)
    unresolved = int(df["home_away"].isna().sum())
    if unresolved:
        print(f"WARNING: {unresolved} shots could not be resolved to home/away (unknown TEAM_ID)")

    period_encoded = encode_period(df["PERIOD"])
    df["period_clean"] = period_encoded["period_clean"]
    df["is_overtime"] = period_encoded["is_overtime"]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_PATH, index=False)
    print(f"Saved {len(df)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
