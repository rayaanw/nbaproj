"""T-014: Assemble the final feature table for model training.

Joins every feature stream built so far — geometric (T-010 + T-013's
defender prior, both already present in shots_with_prior.parquet), score
margin (T-011), and game-situation context (T-012) — into the single table
`pipeline/07_train_test_split.py` will consume, and finalizes categorical
encoding.

Usage:
    python pipeline/06e_assemble_features.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import DATA_PROCESSED_DIR

PRIOR_PATH = DATA_PROCESSED_DIR / "shots_with_prior.parquet"  # geo + defender prior
SCORE_MARGIN_PATH = DATA_PROCESSED_DIR / "shots_with_score_margin.parquet"
CONTEXT_PATH = DATA_PROCESSED_DIR / "shots_context.parquet"
OUTPUT_PATH = DATA_PROCESSED_DIR / "features_final.parquet"

# SEASON is included alongside the natural shot identifier defensively: a real
# NBA GAME_ID is season-unique on its own, but joining on the more specific
# key costs nothing and fully rules out fan-out if that assumption is ever
# violated (e.g. synthetic/test data reusing IDs across seasons).
KEY_COLUMNS = ["GAME_ID", "GAME_EVENT_ID", "SEASON"]

CATEGORICAL_COLUMNS = ["ACTION_TYPE", "SHOT_ZONE_BASIC", "SHOT_ZONE_AREA", "home_away"]

CRITICAL_COLUMNS = [
    "shot_angle",
    "shot_distance_bucket",
    "score_margin",
    # defender_distance_prior is included here for safety, but as of the
    # 2026-07-14 graceful-degradation fix (see 06d_defender_prior.py) it's
    # tiered-fallback-filled and should never actually be NaN by this point —
    # kept in the list in case that invariant is ever broken upstream.
    "defender_distance_prior",
    "home_away",
    "time_remaining_in_period",
]


def require(path: Path, upstream_script: str) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(f"{path} not found — run {upstream_script} first")
    return pd.read_parquet(path)


def main() -> None:
    base = require(PRIOR_PATH, "06d_defender_prior.py")  # has geo + prior columns already
    score_margin_df = require(SCORE_MARGIN_PATH, "06b_score_margin.py")
    context_df = require(CONTEXT_PATH, "06c_context_features.py")

    # T-014.1: join on the shared shot identifier (GAME_ID + GAME_EVENT_ID).
    # Only pull the *new* columns from each side table to avoid duplicating
    # every base column three times over.
    merged = base.merge(
        score_margin_df[[*KEY_COLUMNS, "score_margin"]], on=KEY_COLUMNS, how="left"
    )
    merged = merged.merge(
        context_df[[*KEY_COLUMNS, "time_remaining_in_period", "home_away", "period_clean", "is_overtime"]],
        on=KEY_COLUMNS,
        how="left",
    )

    rows_before_drop = len(merged)

    # T-010.3: exclude heaves from training (they were only *flagged*, not
    # dropped, in T-010, so intermediate files stay complete for inspection).
    merged = merged[~merged["is_heave"]]

    # T-014.3: drop rows with unresolved/missing critical features, logging
    # the drop rate so a silent data-quality regression doesn't go unnoticed.
    before_critical_drop = len(merged)
    merged = merged.dropna(subset=CRITICAL_COLUMNS)
    dropped_critical = before_critical_drop - len(merged)

    total_dropped = rows_before_drop - len(merged)
    print(
        f"Dropped {total_dropped}/{rows_before_drop} rows "
        f"({total_dropped / rows_before_drop:.3%}): heaves + {dropped_critical} rows missing "
        "critical features"
    )

    # T-014.2: one-hot encode categorical features.
    merged = pd.get_dummies(merged, columns=CATEGORICAL_COLUMNS, prefix=CATEGORICAL_COLUMNS)

    # T-014.4: season label column — already attached during consolidation
    # (T-009.1), carried through every join since; just confirm it's present.
    if "SEASON" not in merged.columns:
        raise RuntimeError("SEASON column missing from assembled feature table")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(OUTPUT_PATH, index=False)
    print(f"Saved {len(merged)} rows, {len(merged.columns)} columns to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
