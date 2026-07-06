"""T-007: Build the league-average (shot distance x closest defender distance) FG% prior.

`nba_api`'s public endpoints don't expose true per-shot defender distance (see
CLAUDE.md "Known Data Limitations"), so instead we pull the league's aggregated
tracking-dashboard breakdown of FG% by (shot distance bucket, closest defender
distance bucket) via `leaguedashplayerptshot`, one call per bucket combination,
summed across all players to get a league-wide total for that cell. This is a
supplementary, clearly-labeled approximation joined later by (season, shot
distance bucket) — see T-013 and the Methodology page's data-limitations copy
(T-042.3).

IMPORTANT — verify before a real run: the SHOT_DIST_RANGES / CLOSE_DEF_DIST_RANGES
string values below match stats.nba.com's public shooting-dashboard filter
values as documented in nba_api usage, but could not be confirmed against a
live call while building this in a sandboxed environment with no network
access to stats.nba.com. Before running the full pipeline, run this script
for a single season first and confirm each combination returns nonzero rows
(the script raises loudly if a combination comes back empty) rather than
silently proceeding with a garbage prior.

Usage:
    python pipeline/04_pull_defender_distance_priors.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nba_api.stats.endpoints import leaguedashplayerptshot

from pipeline.config import ALL_SEASONS, DEFENDER_PRIORS_RAW_DIR
from pipeline.utils import call_with_retry

# See the module docstring's "IMPORTANT" note — confirm these against a live
# call before trusting a full run.
SHOT_DIST_RANGES = [
    "Less Than 5 ft.",
    "5-9 ft.",
    "10-14 ft.",
    "15-19 ft.",
    "20-24 ft.",
    "25-29 ft.",
    ">= 30 ft.",
]

CLOSE_DEF_DIST_RANGES = [
    "0-2 Feet - Very Tight",
    "2-4 Feet - Tight",
    "4-6 Feet - Open",
    "6+ Feet - Wide Open",
]


def pull_bucket(season: str, shot_dist_range: str, close_def_dist_range: str) -> pd.DataFrame:
    def build():
        return leaguedashplayerptshot.LeagueDashPlayerPtShot(
            season=season,
            season_type_all_star="Regular Season",
            per_mode_simple="Totals",
            shot_dist_range_nullable=shot_dist_range,
            close_def_dist_range_nullable=close_def_dist_range,
        )

    endpoint = call_with_retry(
        build,
        description=(
            f"leaguedashplayerptshot(season={season}, shot={shot_dist_range}, "
            f"def={close_def_dist_range})"
        ),
    )
    return endpoint.get_data_frames()[0]


def build_season_prior_table(season: str) -> pd.DataFrame:
    rows = []
    for shot_dist_range in SHOT_DIST_RANGES:
        for close_def_dist_range in CLOSE_DEF_DIST_RANGES:
            df = pull_bucket(season, shot_dist_range, close_def_dist_range)

            if df.empty:
                raise RuntimeError(
                    f"Empty result for season={season}, shot_dist_range={shot_dist_range!r}, "
                    f"close_def_dist_range={close_def_dist_range!r}. This most likely means one "
                    "of the filter string values is wrong for the live API — check the "
                    "SHOT_DIST_RANGES/CLOSE_DEF_DIST_RANGES constants against stats.nba.com "
                    "before continuing."
                )

            # T-007.2: aggregate across all players to a single league-wide cell.
            fgm = int(df["FGM"].sum())
            fga = int(df["FGA"].sum())
            fg_pct = fgm / fga if fga > 0 else None

            rows.append(
                {
                    "season": season,
                    "shot_dist_range": shot_dist_range,
                    "close_def_dist_range": close_def_dist_range,
                    "fgm": fgm,
                    "fga": fga,
                    "fg_pct": fg_pct,
                }
            )

    return pd.DataFrame(rows)


def main() -> None:
    DEFENDER_PRIORS_RAW_DIR.mkdir(parents=True, exist_ok=True)

    for season in ALL_SEASONS:
        out_path = DEFENDER_PRIORS_RAW_DIR / f"{season}.parquet"
        if out_path.exists():
            print(f"  skipping {season} (already exists at {out_path})")
            continue

        print(f"Pulling defender-distance prior for {season} "
              f"({len(SHOT_DIST_RANGES) * len(CLOSE_DEF_DIST_RANGES)} bucket combinations)...")
        season_df = build_season_prior_table(season)
        season_df.to_parquet(out_path, index=False)
        print(f"  saved {out_path} ({len(season_df)} rows)")

    print("Done.")


if __name__ == "__main__":
    main()
