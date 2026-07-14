"""T-007: Build the league-average (shot distance x closest defender distance) FG% prior.

`nba_api`'s public endpoints don't expose true per-shot defender distance (see
CLAUDE.md "Known Data Limitations"), so instead we pull the league's aggregated
tracking-dashboard breakdown of FG% by (shot distance bucket, closest defender
distance bucket) via `leaguedashplayerptshot`, one call per bucket combination,
summed across all players to get a league-wide total for that cell. This is a
supplementary, clearly-labeled approximation joined later by (season, shot
distance bucket) — see T-013 and the Methodology page's data-limitations copy
(T-042.3).

**Real-world finding (2026-07-14, running against live data):** some
(season, shot_dist_range, close_def_dist_range) combinations return a
response shape `nba_api` can't parse at all (`KeyError('resultSet')`, raised
during the request itself, before any row data is even reached) — even
after all retries, so it isn't transient network flakiness. It wasn't
possible to fully pin down whether this is because specific
SHOT_DIST_RANGES/CLOSE_DEF_DIST_RANGES string values are wrong for the live
API, or a broader issue with this endpoint (some research suggested
CLOSE_DEF_DIST_RANGES values are likely correct — real query strings from
nba.com matched exactly — but ShotDistRange couldn't be confirmed the same
way). Rather than keep guessing against an API this project's build/run
environment can't fully verify, this script now degrades gracefully: a
bucket combination that fails (even after retries) is logged and skipped
rather than crashing the whole pipeline, since T-007's output is an
explicitly supplementary/approximate feature (see CLAUDE.md "Known Data
Limitations") — not something worth blocking every other pipeline stage
over. Missing buckets are handled downstream in 06d_defender_prior.py /
06e_assemble_features.py by falling back to a neutral prior value rather
than dropping rows or crashing.

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

# Real-world finding (2026-07-14): every single bucket combination failed
# identically on a live run — strong evidence this is a deterministic/
# endpoint-wide failure, not a transient network issue that retries would
# fix. Using a much lower retry count than the pipeline default (5) so a
# fully-broken endpoint fails fast (~seconds per bucket) instead of burning
# ~15-20s per bucket on retries that were never going to succeed. If this
# endpoint starts working again later, bump this back up.
MAX_RETRIES_FOR_THIS_ENDPOINT = 1


def pull_bucket(season: str, shot_dist_range: str, close_def_dist_range: str) -> pd.DataFrame | None:
    """Returns None (rather than raising) if this bucket combination fails
    even after retries, or comes back empty — see the module docstring's
    "Real-world finding" note for why this degrades gracefully instead of
    crashing the whole pipeline.
    """
    description = (
        f"leaguedashplayerptshot(season={season}, shot={shot_dist_range}, "
        f"def={close_def_dist_range})"
    )

    def build():
        return leaguedashplayerptshot.LeagueDashPlayerPtShot(
            season=season,
            season_type_all_star="Regular Season",
            per_mode_simple="Totals",
            shot_dist_range_nullable=shot_dist_range,
            close_def_dist_range_nullable=close_def_dist_range,
        )

    try:
        endpoint = call_with_retry(build, description=description, max_retries=MAX_RETRIES_FOR_THIS_ENDPOINT)
    except Exception as exc:  # noqa: BLE001 - already retried; log and move on
        print(f"  [skip] {description}: {exc!r}")
        return None

    df = endpoint.get_data_frames()[0]
    if df.empty:
        print(f"  [skip] {description}: empty result")
        return None
    return df


def build_season_prior_table(season: str) -> pd.DataFrame:
    rows = []
    total = len(SHOT_DIST_RANGES) * len(CLOSE_DEF_DIST_RANGES)
    skipped = 0

    for shot_dist_range in SHOT_DIST_RANGES:
        for close_def_dist_range in CLOSE_DEF_DIST_RANGES:
            df = pull_bucket(season, shot_dist_range, close_def_dist_range)

            if df is None:
                skipped += 1
                continue

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

    if skipped:
        print(f"  WARNING: {skipped}/{total} bucket combinations skipped for {season} (see [skip] lines above)")

    return pd.DataFrame(rows)


def main() -> None:
    DEFENDER_PRIORS_RAW_DIR.mkdir(parents=True, exist_ok=True)

    any_data_pulled = False

    for season in ALL_SEASONS:
        out_path = DEFENDER_PRIORS_RAW_DIR / f"{season}.parquet"
        if out_path.exists():
            print(f"  skipping {season} (already exists at {out_path})")
            any_data_pulled = True
            continue

        print(f"Pulling defender-distance prior for {season} "
              f"({len(SHOT_DIST_RANGES) * len(CLOSE_DEF_DIST_RANGES)} bucket combinations)...")
        season_df = build_season_prior_table(season)

        if season_df.empty:
            print(
                f"  WARNING: zero usable bucket combinations for {season} — no file written. "
                "This season's defender_distance_prior will fall back to a neutral value "
                "downstream (see 06d_defender_prior.py)."
            )
            continue

        season_df.to_parquet(out_path, index=False)
        any_data_pulled = True
        print(f"  saved {out_path} ({len(season_df)} rows)")

    if not any_data_pulled:
        print(
            "\nWARNING: no defender-distance prior data was pulled for ANY season. "
            "This is a supplementary/approximate feature (see CLAUDE.md), so the pipeline "
            "will still proceed — defender_distance_prior will fall back to a neutral value "
            "for every shot rather than blocking the run."
        )

    print("Done.")


if __name__ == "__main__":
    main()
