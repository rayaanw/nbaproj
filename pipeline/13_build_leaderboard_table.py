"""T-027: Build the leaderboard aggregation table.

Pre-computes per-player, per-season (and 3-year-combined "career") actual
FG% vs. expected FG% (xFG%) so the Leaderboard page is a fast, simple query
instead of aggregating thousands of shot rows on every page load.

Usage:
    python pipeline/13_build_leaderboard_table.py
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import DB_PATH, LEADERBOARD_MIN_ATTEMPTS

CAREER_LABEL = "career"


def load_shots(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql(
        "SELECT player_id, season, shot_made_flag, xfg_pct FROM shots", conn
    )


def aggregate(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    agg = (
        df.groupby(group_cols)
        .agg(attempts=("shot_made_flag", "size"), actual_fg_pct=("shot_made_flag", "mean"), expected_fg_pct=("xfg_pct", "mean"))
        .reset_index()
    )
    agg["skill_differential"] = agg["actual_fg_pct"] - agg["expected_fg_pct"]
    agg["qualified"] = (agg["attempts"] >= LEADERBOARD_MIN_ATTEMPTS).astype(int)
    return agg


def build_leaderboard(shots_df: pd.DataFrame) -> pd.DataFrame:
    # T-027.1: per-player, per-season aggregation.
    per_season = aggregate(shots_df, ["player_id", "season"])
    per_season = per_season.rename(columns={"season": "season_or_career"})

    # T-027.2: 3-year combined ("career") aggregation.
    career_df = shots_df.copy()
    career_df["season_or_career"] = CAREER_LABEL
    per_career = aggregate(career_df, ["player_id", "season_or_career"])

    combined = pd.concat([per_season, per_career], ignore_index=True)
    return combined[
        ["player_id", "season_or_career", "attempts", "actual_fg_pct", "expected_fg_pct", "skill_differential", "qualified"]
    ]


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"{DB_PATH} not found — run 12_load_db.py first")

    conn = sqlite3.connect(DB_PATH)
    try:
        shots_df = load_shots(conn)
        if shots_df.empty:
            raise SystemExit("`shots` table is empty — run 12_load_db.py first")

        leaderboard_df = build_leaderboard(shots_df)

        conn.execute("DELETE FROM leaderboard")
        leaderboard_df.to_sql("leaderboard", conn, if_exists="append", index=False)
        conn.commit()

        n_qualified = int(leaderboard_df["qualified"].sum())
        print(
            f"Loaded {len(leaderboard_df)} leaderboard rows "
            f"({n_qualified} meeting LEADERBOARD_MIN_ATTEMPTS={LEADERBOARD_MIN_ATTEMPTS})"
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
