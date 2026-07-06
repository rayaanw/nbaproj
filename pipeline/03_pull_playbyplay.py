"""T-006: Build the play-by-play dataset used for the score-margin feature.

`shotchartdetail` does not include the live score at the time of each shot, so
we separately pull play-by-play data per unique GAME_ID (which does include a
SCOREMARGIN field per event) and join it to shots later by GAME_ID + period +
clock time (T-011).

T-006.1: the distinct GAME_ID scope is derived from whatever shot chart files
have already been pulled under data/raw/shots/ (T-005) rather than a separate
lookup — this script can be run anytime after 02_pull_shot_charts.py has
produced at least some files, and rerun again once more shots have landed to
pick up newly-discovered games.

Usage:
    python pipeline/03_pull_playbyplay.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nba_api.stats.endpoints import playbyplayv2

from pipeline.config import PLAYBYPLAY_RAW_DIR, SHOTS_RAW_DIR
from pipeline.utils import call_with_retry, log_failure

FAILURES_LOG = PLAYBYPLAY_RAW_DIR / "_failures.log"


def collect_game_ids() -> list[str]:
    """T-006.1: derive the distinct set of GAME_IDs from pulled shot chart files."""
    game_ids: set[str] = set()
    for shot_file in SHOTS_RAW_DIR.glob("*/*.parquet"):
        df = pd.read_parquet(shot_file, columns=["GAME_ID"])
        game_ids.update(df["GAME_ID"].astype(str).unique())
    return sorted(game_ids)


def pull_game_playbyplay(game_id: str) -> pd.DataFrame:
    def build():
        return playbyplayv2.PlayByPlayV2(game_id=game_id)

    endpoint = call_with_retry(build, description=f"playbyplayv2(game={game_id})")
    return endpoint.get_data_frames()[0]


def output_path_for(game_id: str) -> Path:
    return PLAYBYPLAY_RAW_DIR / f"{game_id}.parquet"


def main() -> None:
    game_ids = collect_game_ids()
    if not game_ids:
        raise SystemExit(
            f"No shot files found under {SHOTS_RAW_DIR} — run 02_pull_shot_charts.py first "
            "(or run at least partially — this script only needs some games to be present)."
        )

    total = len(game_ids)
    skipped = 0
    pulled = 0
    failed = 0

    print(f"Play-by-play pull scope: {total} distinct games")

    for i, game_id in enumerate(game_ids, start=1):
        out_path = output_path_for(game_id)

        # T-006.3: skip already-pulled games on rerun.
        if out_path.exists():
            skipped += 1
            continue

        try:
            pbp_df = pull_game_playbyplay(game_id)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            pbp_df.to_parquet(out_path, index=False)
            pulled += 1
            print(f"  [{i}/{total}] saved {out_path} ({len(pbp_df)} events)")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            log_failure(FAILURES_LOG, game_id, exc)
            print(f"  [failed] game {game_id}: {exc!r}")

    print(
        f"\nDone. pulled={pulled} skipped(existing)={skipped} failed={failed} "
        f"(see {FAILURES_LOG} for failures)"
    )


if __name__ == "__main__":
    main()
