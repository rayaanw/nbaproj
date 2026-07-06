"""T-011: Join score margin from play-by-play data.

`shotchartdetail` doesn't include the live score. `playbyplayv2` (pulled in
T-006) does, via its SCOREMARGIN field on every event. Rather than a fuzzy
clock-time join, this uses an exact-ID join: shotchartdetail's GAME_EVENT_ID
and playbyplayv2's EVENTNUM refer to the same underlying event log for a
game, so they line up directly. We take the score margin as of the *last*
event strictly before the shot's own event (so a made shot's own scoring
isn't counted as "already happened" going into that shot).

Usage:
    python pipeline/06b_score_margin.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import DATA_PROCESSED_DIR, PLAYBYPLAY_RAW_DIR

INPUT_PATH = DATA_PROCESSED_DIR / "shots_consolidated.parquet"
OUTPUT_PATH = DATA_PROCESSED_DIR / "shots_with_score_margin.parquet"

FALLBACK_SCORE_MARGIN = 0  # T-011.4: documented fallback for unmatched shots


def parse_score_margin(raw: object) -> float:
    """Parse playbyplayv2's SCOREMARGIN field: "TIE" -> 0, "+5"/"-3" -> 5/-3,
    None/blank -> NaN (left for forward-fill to resolve).
    """
    if raw is None:
        return float("nan")
    text = str(raw).strip()
    if text == "" or text.lower() == "none":
        return float("nan")
    if text.upper() == "TIE":
        return 0.0
    try:
        return float(text)
    except ValueError:
        return float("nan")


def load_playbyplay() -> pd.DataFrame:
    """T-011.1: load and consolidate all pulled play-by-play files, with a
    running (forward-filled) score margin per game so every event has a
    known score state even if SCOREMARGIN itself is blank on that row.
    """
    frames = []
    for pbp_file in sorted(PLAYBYPLAY_RAW_DIR.glob("*.parquet")):
        df = pd.read_parquet(pbp_file, columns=["GAME_ID", "EVENTNUM", "SCOREMARGIN"])
        frames.append(df)

    if not frames:
        raise SystemExit(
            f"No play-by-play files found under {PLAYBYPLAY_RAW_DIR} — run "
            "03_pull_playbyplay.py first"
        )

    pbp = pd.concat(frames, ignore_index=True)
    pbp["GAME_ID"] = pbp["GAME_ID"].astype(str).str.zfill(10)
    pbp["EVENTNUM"] = pbp["EVENTNUM"].astype(int)
    pbp["score_margin_parsed"] = pbp["SCOREMARGIN"].map(parse_score_margin)

    pbp = pbp.sort_values(["GAME_ID", "EVENTNUM"])
    # Running score state as of each event, forward-filled within each game.
    pbp["score_margin_running"] = pbp.groupby("GAME_ID")["score_margin_parsed"].ffill()
    pbp["score_margin_running"] = pbp["score_margin_running"].fillna(0)

    return pbp[["GAME_ID", "EVENTNUM", "score_margin_running"]]


def join_score_margin(shots: pd.DataFrame, pbp: pd.DataFrame) -> pd.DataFrame:
    """T-011.2/.3: attach the score margin as of the last PBP event strictly
    before each shot's own GAME_EVENT_ID, via a per-game backward as-of merge.
    """
    shots = shots.sort_values(["GAME_ID", "GAME_EVENT_ID"]).reset_index(drop=True)
    pbp = pbp.sort_values(["GAME_ID", "EVENTNUM"]).reset_index(drop=True)

    merged = pd.merge_asof(
        shots,
        pbp,
        left_on="GAME_EVENT_ID",
        right_on="EVENTNUM",
        by="GAME_ID",
        direction="backward",
        allow_exact_matches=False,
    )
    merged = merged.rename(columns={"score_margin_running": "score_margin"})
    merged = merged.drop(columns=["EVENTNUM"], errors="ignore")
    return merged


def main() -> None:
    if not INPUT_PATH.exists():
        raise SystemExit(f"{INPUT_PATH} not found — run 06_consolidate_shots.py first")

    shots = pd.read_parquet(INPUT_PATH)
    pbp = load_playbyplay()

    merged = join_score_margin(shots, pbp)

    # T-011.4: handle unmatched shots gracefully.
    unmatched_mask = merged["score_margin"].isna()
    unmatched_count = int(unmatched_mask.sum())
    if unmatched_count:
        print(
            f"WARNING: {unmatched_count} shots ({unmatched_count / len(merged):.3%}) had no "
            f"matching play-by-play game data; imputing score_margin={FALLBACK_SCORE_MARGIN}"
        )
        merged.loc[unmatched_mask, "score_margin"] = FALLBACK_SCORE_MARGIN

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(OUTPUT_PATH, index=False)
    print(f"Saved {len(merged)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
