"""T-013: Join the league-average defender-distance FG% prior onto each shot.

Reads shots_geo.parquet (T-010's output, which has shot_distance_bucket) and
the per-season defender-distance prior tables (T-007), then attaches a single
defender_distance_prior value per shot as a supplementary approximation — see
CLAUDE.md's "Known Data Limitations" note. Because we don't know the true
per-shot defender distance, the prior is blended (attempt-weighted) across all
closest-defender-distance buckets for that shot's (season, shot_distance_bucket)
cell, rather than picking one bucket arbitrarily.

Usage:
    python pipeline/06d_defender_prior.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import DATA_PROCESSED_DIR, DEFENDER_PRIORS_RAW_DIR

INPUT_PATH = DATA_PROCESSED_DIR / "shots_geo.parquet"
OUTPUT_PATH = DATA_PROCESSED_DIR / "shots_with_prior.parquet"


def load_blended_priors() -> pd.DataFrame:
    """T-013.1/.2: load per-season prior tables and collapse the closest-
    defender-distance dimension into a single attempt-weighted FG% per
    (season, shot_dist_range) cell.
    """
    frames = []
    for prior_file in sorted(DEFENDER_PRIORS_RAW_DIR.glob("*.parquet")):
        frames.append(pd.read_parquet(prior_file))

    if not frames:
        raise SystemExit(
            f"No defender-distance prior files found under {DEFENDER_PRIORS_RAW_DIR} — "
            "run 04_pull_defender_distance_priors.py first"
        )

    priors = pd.concat(frames, ignore_index=True)

    # Blended/weighted average across close_def_dist_range: summing makes and
    # attempts across buckets and dividing is equivalent to an attempt-weighted
    # average FG%, which is the documented approximation (see module docstring).
    blended = (
        priors.groupby(["season", "shot_dist_range"])
        .agg(fgm=("fgm", "sum"), fga=("fga", "sum"))
        .reset_index()
    )
    blended["defender_distance_prior"] = blended["fgm"] / blended["fga"]
    return blended[["season", "shot_dist_range", "defender_distance_prior"]]


def main() -> None:
    if not INPUT_PATH.exists():
        raise SystemExit(f"{INPUT_PATH} not found — run 06a_geo_features.py first")

    shots = pd.read_parquet(INPUT_PATH)
    blended_priors = load_blended_priors()

    merged = shots.merge(
        blended_priors,
        left_on=["SEASON", "shot_distance_bucket"],
        right_on=["season", "shot_dist_range"],
        how="left",
    ).drop(columns=["season", "shot_dist_range"])

    unmatched = int(merged["defender_distance_prior"].isna().sum())
    if unmatched:
        print(
            f"WARNING: {unmatched} shots ({unmatched / len(merged):.3%}) had no matching "
            "defender-distance prior (season/bucket combination not found in the pulled "
            "prior tables) — defender_distance_prior left as NaN for those rows"
        )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(OUTPUT_PATH, index=False)
    print(f"Saved {len(merged)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
