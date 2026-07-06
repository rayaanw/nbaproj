"""T-009: Merge and consolidate raw shot data.

Combines the per-player/per-season shot files pulled in T-005 into one
working table, standardizing types so every downstream feature step (T-010-
T-014) operates on a single clean parquet file instead of hundreds of small
per-player-per-season files.

Usage:
    python pipeline/06_consolidate_shots.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import DATA_PROCESSED_DIR, SHOTS_RAW_DIR

OUTPUT_PATH = DATA_PROCESSED_DIR / "shots_consolidated.parquet"


def load_all_shot_files() -> pd.DataFrame:
    """T-009.1: load and concatenate every file under data/raw/shots/{season}/{player_id}.parquet.

    The season isn't a column in the raw shotchartdetail response itself (it's
    implicit in which season we requested), so it's attached here from the
    folder name — this is also where T-014.4's "season label column" first
    enters the pipeline, since this is the one place the season is naturally
    known without an extra lookup.
    """
    frames = []
    for season_dir in sorted(SHOTS_RAW_DIR.iterdir()):
        if not season_dir.is_dir():
            continue
        season = season_dir.name
        for shot_file in sorted(season_dir.glob("*.parquet")):
            df = pd.read_parquet(shot_file)
            df["SEASON"] = season
            frames.append(df)

    if not frames:
        raise SystemExit(
            f"No shot files found under {SHOTS_RAW_DIR} — run 02_pull_shot_charts.py first"
        )

    return pd.concat(frames, ignore_index=True)


def standardize(df: pd.DataFrame) -> pd.DataFrame:
    """T-009.2: standardize column names/types for reliable downstream joins."""
    df = df.copy()

    # SHOT_MADE_FLAG as int 0/1 (nba_api already returns 0/1 but coerce defensively).
    df["SHOT_MADE_FLAG"] = df["SHOT_MADE_FLAG"].fillna(0).astype(int)

    # GAME_ID as a consistent zero-padded string (nba_api game IDs are 10-digit
    # strings like "0022200001" already, but coerce in case of numeric read-back).
    df["GAME_ID"] = df["GAME_ID"].astype(str).str.zfill(10)

    df["GAME_EVENT_ID"] = df["GAME_EVENT_ID"].astype(int)
    df["PLAYER_ID"] = df["PLAYER_ID"].astype(int)
    df["PERIOD"] = df["PERIOD"].astype(int)
    df["SHOT_DISTANCE"] = df["SHOT_DISTANCE"].astype(float)
    df["LOC_X"] = df["LOC_X"].astype(float)
    df["LOC_Y"] = df["LOC_Y"].astype(float)

    return df


def main() -> None:
    print("Loading raw shot files...")
    df = load_all_shot_files()
    rows_before = len(df)
    print(f"  loaded {rows_before} rows from {SHOTS_RAW_DIR}")

    df = standardize(df)

    # T-009.3: drop exact duplicate rows (can occur if a script reran partially).
    df = df.drop_duplicates()
    rows_after = len(df)
    if rows_after < rows_before:
        print(f"  dropped {rows_before - rows_after} exact duplicate rows")

    # T-009.4: save.
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_PATH, index=False)
    print(f"Saved {rows_after} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
