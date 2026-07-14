"""T-013: Join the league-average defender-distance FG% prior onto each shot.

Reads shots_geo.parquet (T-010's output, which has shot_distance_bucket) and
the per-season defender-distance prior tables (T-007), then attaches a single
defender_distance_prior value per shot as a supplementary approximation — see
CLAUDE.md's "Known Data Limitations" note. Because we don't know the true
per-shot defender distance, the prior is blended (attempt-weighted) across all
closest-defender-distance buckets for that shot's (season, shot_distance_bucket)
cell, rather than picking one bucket arbitrarily.

**Graceful degradation (added 2026-07-14):** T-007's pull is now resilient
to individual bucket combinations failing against the live API (see that
script's docstring), which means prior data may be partial or, in the worst
case, entirely absent for some or all seasons. Rather than crash the whole
pipeline over a supplementary/approximate feature, missing values here fall
back in tiers: (1) exact season+bucket match, (2) bucket-only average across
whatever seasons *do* have data for that bucket, (3) a flat neutral constant
if literally no prior data exists anywhere. Each tier is logged so it's
obvious how much of this feature is "real" vs. fallback for any given run.

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

# Tier-3 fallback: used only if there's zero prior data anywhere (no pulled
# files at all, or every bucket failed). A flat, roughly-league-average FG%
# is a defensible neutral value — this is explicitly a last resort.
FLAT_FALLBACK_FG_PCT = 0.46


def load_blended_priors() -> pd.DataFrame:
    """T-013.1/.2: load per-season prior tables and collapse the closest-
    defender-distance dimension into a single attempt-weighted FG% per
    (season, shot_dist_range) cell.

    Returns an empty (but correctly-shaped) DataFrame rather than raising if
    no prior files exist at all — see module docstring on graceful
    degradation.
    """
    frames = []
    for prior_file in sorted(DEFENDER_PRIORS_RAW_DIR.glob("*.parquet")):
        frames.append(pd.read_parquet(prior_file))

    if not frames:
        print(
            f"WARNING: no defender-distance prior files found under {DEFENDER_PRIORS_RAW_DIR} "
            "— every shot will fall back to a neutral defender_distance_prior value. "
            "Run 04_pull_defender_distance_priors.py to get real data for this feature."
        )
        return pd.DataFrame(columns=["season", "shot_dist_range", "defender_distance_prior"])

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


def bucket_only_fallback(blended_priors: pd.DataFrame) -> pd.DataFrame:
    """Tier 2 fallback: average across whatever seasons *do* have data for a
    given shot_dist_range bucket, ignoring season. Used for (season, bucket)
    combinations with no exact match.
    """
    if blended_priors.empty:
        return pd.DataFrame(columns=["shot_dist_range", "defender_distance_prior_bucket_only"])

    return (
        blended_priors.groupby("shot_dist_range")["defender_distance_prior"]
        .mean()
        .reset_index()
        .rename(columns={"defender_distance_prior": "defender_distance_prior_bucket_only"})
    )


def main() -> None:
    if not INPUT_PATH.exists():
        raise SystemExit(f"{INPUT_PATH} not found — run 06a_geo_features.py first")

    shots = pd.read_parquet(INPUT_PATH)
    blended_priors = load_blended_priors()
    bucket_fallback = bucket_only_fallback(blended_priors)

    # Tier 1: exact (season, shot_dist_range) match.
    merged = shots.merge(
        blended_priors,
        left_on=["SEASON", "shot_distance_bucket"],
        right_on=["season", "shot_dist_range"],
        how="left",
    ).drop(columns=["season", "shot_dist_range"], errors="ignore")

    tier1_missing = int(merged["defender_distance_prior"].isna().sum())

    # Tier 2: bucket-only average, for rows tier 1 missed.
    merged = merged.merge(
        bucket_fallback, left_on="shot_distance_bucket", right_on="shot_dist_range", how="left"
    ).drop(columns=["shot_dist_range"], errors="ignore")
    merged["defender_distance_prior"] = merged["defender_distance_prior"].fillna(
        merged["defender_distance_prior_bucket_only"]
    )
    merged = merged.drop(columns=["defender_distance_prior_bucket_only"])

    tier2_missing = int(merged["defender_distance_prior"].isna().sum())

    # Tier 3: flat neutral constant, for anything still missing.
    if tier2_missing:
        merged["defender_distance_prior"] = merged["defender_distance_prior"].fillna(FLAT_FALLBACK_FG_PCT)

    if tier1_missing:
        tier2_resolved = tier1_missing - tier2_missing
        print(
            f"defender_distance_prior fallback usage: {tier2_resolved} shots used the bucket-only "
            f"average (tier 2), {tier2_missing} shots used the flat {FLAT_FALLBACK_FG_PCT} fallback "
            f"(tier 3) — {len(merged) - tier1_missing} shots had an exact season+bucket match (tier 1)."
        )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(OUTPUT_PATH, index=False)
    print(f"Saved {len(merged)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
