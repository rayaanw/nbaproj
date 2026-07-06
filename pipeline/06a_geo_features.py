"""T-010: Compute derived geometric features.

Adds shot_angle (derived from court coordinates), a shot_distance_bucket
(aligned with the defender-distance prior buckets for the T-013 join), and an
is_heave flag for outlier full-court-heave shots that should be excluded from
training.

Note on pipeline numbering: T-009 (06_consolidate_shots.py) and T-015
(07_train_test_split.py) are explicitly named in todo.md. The feature
engineering steps in between (T-010-T-014) don't have prescribed filenames,
so they're numbered 06a-06e to sit clearly between the two fixed scripts
while still sorting in run order — see pipeline/README.md for the full run
order.

Usage:
    python pipeline/06a_geo_features.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import DATA_PROCESSED_DIR
from pipeline.features import bucket_shot_distance, compute_shot_angle_degrees, flag_heaves

INPUT_PATH = DATA_PROCESSED_DIR / "shots_consolidated.parquet"
OUTPUT_PATH = DATA_PROCESSED_DIR / "shots_geo.parquet"


def main() -> None:
    if not INPUT_PATH.exists():
        raise SystemExit(f"{INPUT_PATH} not found — run 06_consolidate_shots.py first")

    df = pd.read_parquet(INPUT_PATH)

    df["shot_angle"] = compute_shot_angle_degrees(df["LOC_X"], df["LOC_Y"])
    df["shot_distance_bucket"] = bucket_shot_distance(df["SHOT_DISTANCE"])
    df["is_heave"] = flag_heaves(df["SHOT_DISTANCE"])

    heave_count = int(df["is_heave"].sum())
    print(f"Flagged {heave_count} heave shots ({heave_count / len(df):.3%} of all shots)")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_PATH, index=False)
    print(f"Saved {len(df)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
