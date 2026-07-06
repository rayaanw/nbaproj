"""T-015: Chronological train/test split.

Implements the PRD's core validation decision — train on the two older
seasons, test on the most recent — to avoid leakage and mirror real
deployment (predicting unseen future shots). Do not change this to a random
split without updating PRD-NBAShotQualityModel.md (see CLAUDE.md's "Key
Architectural Decisions").

Usage:
    python pipeline/07_train_test_split.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import DATA_PROCESSED_DIR, TEST_SEASON, TRAIN_SEASONS

INPUT_PATH = DATA_PROCESSED_DIR / "features_final.parquet"
TRAIN_PATH = DATA_PROCESSED_DIR / "train.parquet"
TEST_PATH = DATA_PROCESSED_DIR / "test.parquet"


def main() -> None:
    if not INPUT_PATH.exists():
        raise SystemExit(f"{INPUT_PATH} not found — run 06e_assemble_features.py first")

    df = pd.read_parquet(INPUT_PATH)

    # T-015.1: split using the season scope from config.
    train_df = df[df["SEASON"].isin(TRAIN_SEASONS)].copy()
    test_df = df[df["SEASON"] == TEST_SEASON].copy()

    unassigned = df[~df["SEASON"].isin([*TRAIN_SEASONS, TEST_SEASON])]
    if len(unassigned):
        print(
            f"WARNING: {len(unassigned)} rows have a SEASON value outside "
            f"TRAIN_SEASONS/TEST_SEASON ({sorted(unassigned['SEASON'].unique())}) and were "
            "excluded from both splits"
        )

    # T-015.2: save.
    TRAIN_PATH.parent.mkdir(parents=True, exist_ok=True)
    train_df.to_parquet(TRAIN_PATH, index=False)
    test_df.to_parquet(TEST_PATH, index=False)

    # T-015.3: log basic stats to catch an obviously broken split.
    train_rate = train_df["SHOT_MADE_FLAG"].mean() if len(train_df) else float("nan")
    test_rate = test_df["SHOT_MADE_FLAG"].mean() if len(test_df) else float("nan")

    print(f"Train ({TRAIN_SEASONS}): {len(train_df)} rows, make-rate={train_rate:.3%}")
    print(f"Test  ({TEST_SEASON}): {len(test_df)} rows, make-rate={test_rate:.3%}")

    if len(train_df) == 0 or len(test_df) == 0:
        raise RuntimeError("Train or test split is empty — check SEASON values in the input data")

    rate_diff = abs(train_rate - test_rate)
    if rate_diff > 0.05:
        print(
            f"WARNING: train/test make-rate differ by {rate_diff:.3%}, which is unusually large "
            "— double check the split isn't broken (e.g. wrong season labels)"
        )

    print(f"Saved to {TRAIN_PATH} and {TEST_PATH}")


if __name__ == "__main__":
    main()
