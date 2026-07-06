"""T-008: Validate raw pulls before spending time on feature engineering.

Checks:
  - expected file counts (per players_reference.parquet scope) are present
  - no shot-chart file has zero rows unexpectedly
  - column schemas are consistent across all shot-chart files
  - null rates on key columns are below a small threshold
Writes a manifest.json summarizing row counts, used as a sanity checkpoint
for future pipeline reruns.

Usage:
    python pipeline/05_validate_raw_data.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import (
    ALL_SEASONS,
    DEFENDER_PRIORS_RAW_DIR,
    PLAYBYPLAY_RAW_DIR,
    PLAYERS_REFERENCE_PATH,
    RAW_MANIFEST_PATH,
    SHOTS_RAW_DIR,
)

NULL_RATE_THRESHOLD = 0.01  # T-008.2: fail loudly if any key column exceeds 1% nulls
KEY_COLUMNS = ["LOC_X", "LOC_Y", "SHOT_DISTANCE", "ACTION_TYPE", "SHOT_MADE_FLAG"]


class ValidationError(Exception):
    pass


def validate_expected_file_counts() -> dict:
    if not PLAYERS_REFERENCE_PATH.exists():
        raise ValidationError(f"{PLAYERS_REFERENCE_PATH} does not exist")

    reference_df = pd.read_parquet(PLAYERS_REFERENCE_PATH)
    expected_pairs = reference_df[["PLAYER_ID", "SEASON"]].drop_duplicates()
    expected_count = len(expected_pairs)

    actual_files = list(SHOTS_RAW_DIR.glob("*/*.parquet"))
    actual_count = len(actual_files)

    missing = []
    for _, row in expected_pairs.iterrows():
        expected_path = SHOTS_RAW_DIR / row["SEASON"] / f"{int(row['PLAYER_ID'])}.parquet"
        if not expected_path.exists():
            missing.append(str(expected_path))

    if missing:
        print(
            f"  WARNING: {len(missing)}/{expected_count} expected shot-chart files are missing "
            "(pipeline run may still be in progress, or some pulls failed — see "
            "data/raw/shots/_failures.log)"
        )

    return {
        "expected_player_season_pairs": expected_count,
        "actual_shot_files": actual_count,
        "missing_files": len(missing),
    }


def validate_shot_chart_files() -> dict:
    files = sorted(SHOTS_RAW_DIR.glob("*/*.parquet"))
    if not files:
        raise ValidationError(f"No shot-chart files found under {SHOTS_RAW_DIR}")

    reference_columns: set[str] | None = None
    total_rows = 0
    zero_row_files = []
    null_counts = {col: 0 for col in KEY_COLUMNS}

    for f in files:
        df = pd.read_parquet(f)

        if len(df) == 0:
            zero_row_files.append(str(f))
            continue

        columns = set(df.columns)
        if reference_columns is None:
            reference_columns = columns
        elif columns != reference_columns:
            raise ValidationError(
                f"Schema mismatch in {f}: columns differ from the first file seen "
                f"(missing={reference_columns - columns}, extra={columns - reference_columns})"
            )

        total_rows += len(df)
        for col in KEY_COLUMNS:
            if col in df.columns:
                null_counts[col] += int(df[col].isna().sum())

    if zero_row_files:
        print(f"  WARNING: {len(zero_row_files)} shot-chart files have zero rows")

    # T-008.2: null-rate check.
    for col, n_null in null_counts.items():
        rate = n_null / total_rows if total_rows else 0
        if rate > NULL_RATE_THRESHOLD:
            raise ValidationError(
                f"Null rate for {col} is {rate:.2%}, exceeding the {NULL_RATE_THRESHOLD:.0%} threshold"
            )

    return {
        "shot_chart_files": len(files),
        "shot_chart_total_rows": total_rows,
        "zero_row_files": len(zero_row_files),
        "null_counts": null_counts,
    }


def summarize_playbyplay() -> dict:
    files = list(PLAYBYPLAY_RAW_DIR.glob("*.parquet"))
    total_rows = sum(len(pd.read_parquet(f)) for f in files)
    return {"playbyplay_files": len(files), "playbyplay_total_rows": total_rows}


def summarize_defender_priors() -> dict:
    files = list(DEFENDER_PRIORS_RAW_DIR.glob("*.parquet"))
    seasons_present = sorted(f.stem for f in files)
    missing_seasons = sorted(set(ALL_SEASONS) - set(seasons_present))
    if missing_seasons:
        print(f"  WARNING: missing defender-distance prior for seasons: {missing_seasons}")
    return {"defender_prior_files": len(files), "seasons_present": seasons_present}


def main() -> None:
    print("Validating raw data...")

    manifest = {}

    print("Checking expected file counts...")
    manifest["player_season_coverage"] = validate_expected_file_counts()

    print("Checking shot-chart schema/null rates...")
    manifest["shot_charts"] = validate_shot_chart_files()

    print("Summarizing play-by-play coverage...")
    manifest["playbyplay"] = summarize_playbyplay()

    print("Summarizing defender-distance prior coverage...")
    manifest["defender_priors"] = summarize_defender_priors()

    RAW_MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RAW_MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nManifest written to {RAW_MANIFEST_PATH}")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
