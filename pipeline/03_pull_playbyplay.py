"""T-006: Build the play-by-play dataset used for the score-margin feature.

`shotchartdetail` does not include the live score at the time of each shot, so
we separately pull play-by-play data per unique GAME_ID (which includes a
running score per event) and join it to shots later by GAME_ID + event number
(T-011).

Uses `playbyplayv3`, not `playbyplayv2`. **Real-world fix (found while running
this for real against live data):** `playbyplayv2` is effectively broken on
the current live stats.nba.com API — every single game failed with
`KeyError('resultSet')` after all retries, confirmed as a known, documented
nba_api/stats.nba.com issue (playbyplayv2 returns a response shape the
library can no longer parse; the fix upstream is to use playbyplayv3
instead, which has a different but analogous schema: `gameId`/`actionNumber`
in place of `GAME_ID`/`EVENTNUM`, and `scoreHome`/`scoreAway` in place of a
single `SCOREMARGIN` string). See pipeline/06b_score_margin.py for the
matching schema update. This is exactly the kind of gap flagged as
unverifiable from this project's build sandbox (no live stats.nba.com
access there) — only surfaced once run against the real API.

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

from nba_api.stats.endpoints import playbyplayv3

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
        return playbyplayv3.PlayByPlayV3(game_id=game_id)

    endpoint = call_with_retry(build, description=f"playbyplayv3(game={game_id})")
    # Real bug fixed here too: `get_data_frames()[0]` is "AvailableVideo" (a
    # single video-flag column), not the actual play-by-play data —
    # "PlayByPlay" is index 1. Use the named `.play_by_play` accessor instead
    # of a magic index so this can't silently regress again. (This was never
    # caught by the earlier mocked unit test, since the mock controlled
    # get_data_frames()'s return value directly and sidestepped the real
    # indexing question — a live-API-only bug.)
    return endpoint.play_by_play.get_data_frame()


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
