"""T-005: Build the per-shot shot chart dataset.

The core dataset: per-shot location, distance, zone, and action type for every
qualifying (player, season) pair from `players_reference.parquet`, via
`shotchartdetail`. This is the slowest, most rate-limit-sensitive part of the
pipeline, so it is resumable and cache-friendly — already-pulled files are
skipped on rerun.

Usage:
    python pipeline/02_pull_shot_charts.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nba_api.stats.endpoints import shotchartdetail

from pipeline.config import PLAYERS_REFERENCE_PATH, SHOTS_RAW_DIR
from pipeline.utils import call_with_retry, log_failure

FAILURES_LOG = SHOTS_RAW_DIR / "_failures.log"


def pull_player_season_shots(player_id: int, team_id: int, season: str) -> pd.DataFrame:
    """Fetch every shot attempt for one player in one season."""

    def build():
        return shotchartdetail.ShotChartDetail(
            team_id=team_id,
            player_id=player_id,
            season_nullable=season,
            season_type_all_star="Regular Season",
            context_measure_simple="FGA",
        )

    endpoint = call_with_retry(
        build, description=f"shotchartdetail(player={player_id}, season={season})"
    )
    # "Shot_Chart_Detail" is the per-shot dataset (see expected_data in the
    # installed nba_api package); it is always the second dataset returned.
    return endpoint.get_data_frames()[0]


def output_path_for(season: str, player_id: int) -> Path:
    return SHOTS_RAW_DIR / season / f"{player_id}.parquet"


def main() -> None:
    if not PLAYERS_REFERENCE_PATH.exists():
        raise SystemExit(
            f"{PLAYERS_REFERENCE_PATH} not found — run 01_pull_player_reference.py first"
        )

    reference_df = pd.read_parquet(PLAYERS_REFERENCE_PATH)
    pairs = reference_df[["PLAYER_ID", "TEAM_ID", "SEASON"]].drop_duplicates()

    total = len(pairs)
    skipped = 0
    pulled = 0
    failed = 0

    print(f"Shot chart pull scope: {total} (player, season) pairs")

    for _, row in pairs.iterrows():
        player_id = int(row["PLAYER_ID"])
        team_id = int(row["TEAM_ID"])
        season = row["SEASON"]

        out_path = output_path_for(season, player_id)

        # T-005.4: skip pairs already pulled, so reruns are safe/resumable.
        if out_path.exists():
            skipped += 1
            continue

        try:
            shots_df = pull_player_season_shots(player_id, team_id, season)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            shots_df.to_parquet(out_path, index=False)
            pulled += 1
            print(f"  [{pulled + skipped + failed}/{total}] saved {out_path} ({len(shots_df)} shots)")
        except Exception as exc:  # noqa: BLE001 - log and continue rather than abort the whole run
            failed += 1
            log_failure(FAILURES_LOG, f"{season}:{player_id}", exc)
            print(f"  [failed] {season} player {player_id}: {exc!r}")

    print(
        f"\nDone. pulled={pulled} skipped(existing)={skipped} failed={failed} "
        f"(see {FAILURES_LOG} for failures)"
    )


if __name__ == "__main__":
    main()
