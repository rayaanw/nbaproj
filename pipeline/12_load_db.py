"""T-025: Write the scored shots dataset to SQLite.

Creates the SQLite file at the configured path using db/schema.sql, then
loads shots_scored.parquet (T-023) and players_reference.parquet (T-004)
into it. This is the actual database file the Flask app reads from at
runtime.

Usage:
    python pipeline/12_load_db.py
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import DATA_PROCESSED_DIR, DB_PATH, PLAYERS_REFERENCE_PATH, SCHEMA_PATH

SHOTS_SCORED_PATH = DATA_PROCESSED_DIR / "shots_scored.parquet"

# Maps a shots_scored.parquet column to its shots table column. Only columns
# present here are persisted — the table intentionally doesn't store every
# intermediate/one-hot column from features_final.parquet, only what the app
# actually needs to query and display.
SHOT_COLUMN_MAP = {
    "GAME_ID": "game_id",
    "GAME_EVENT_ID": "game_event_id",
    "PLAYER_ID": "player_id",
    "SEASON": "season",
    "LOC_X": "loc_x",
    "LOC_Y": "loc_y",
    "SHOT_DISTANCE": "shot_distance",
    "SHOT_ZONE_BASIC": "shot_zone_basic",
    "SHOT_ZONE_AREA": "shot_zone_area",
    "ACTION_TYPE": "action_type",
    "period_clean": "period",
    "time_remaining_in_period": "time_remaining_in_period",
    "home_away": "home_away",
    "score_margin": "score_margin",
    "SHOT_MADE_FLAG": "shot_made_flag",
    "xfg_pct": "xfg_pct",
}


def create_schema(conn: sqlite3.Connection) -> None:
    """T-025.1: (re)create the database from schema.sql."""
    if not SCHEMA_PATH.exists():
        raise SystemExit(f"{SCHEMA_PATH} not found")
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())


def load_shots(conn: sqlite3.Connection) -> int:
    """T-025.2: insert every row from shots_scored.parquet into `shots`.

    Note: `shots_scored.parquet` doesn't carry ACTION_TYPE/SHOT_ZONE_BASIC/
    SHOT_ZONE_AREA/home_away directly — T-014's assembly one-hot-encoded
    them for the model. We reconstruct the original category from the
    one-hot columns here so the app can display/filter on the real category
    names rather than a pile of booleans.
    """
    if not SHOTS_SCORED_PATH.exists():
        raise SystemExit(f"{SHOTS_SCORED_PATH} not found — run 11_score_all_shots.py first")

    df = pd.read_parquet(SHOTS_SCORED_PATH)

    for prefix, target_col in [
        ("ACTION_TYPE_", "ACTION_TYPE"),
        ("SHOT_ZONE_BASIC_", "SHOT_ZONE_BASIC"),
        ("SHOT_ZONE_AREA_", "SHOT_ZONE_AREA"),
        ("home_away_", "home_away"),
    ]:
        df[target_col] = _undo_one_hot(df, prefix)

    missing = [c for c in SHOT_COLUMN_MAP if c not in df.columns]
    if missing:
        raise RuntimeError(f"shots_scored.parquet is missing expected columns: {missing}")

    shots_df = df[list(SHOT_COLUMN_MAP.keys())].rename(columns=SHOT_COLUMN_MAP)
    shots_df.to_sql("shots", conn, if_exists="append", index=False)
    return len(shots_df)


def _undo_one_hot(df: pd.DataFrame, prefix: str) -> pd.Series:
    """Reconstruct the original category name from a set of `{prefix}{value}`
    one-hot boolean columns (the inverse of T-014.2's pd.get_dummies call).
    """
    one_hot_cols = [c for c in df.columns if c.startswith(prefix)]
    if not one_hot_cols:
        return pd.Series([None] * len(df), index=df.index)

    def resolve_row(row: pd.Series) -> str | None:
        active = [c[len(prefix):] for c in one_hot_cols if row[c]]
        return active[0] if active else None

    return df[one_hot_cols].apply(resolve_row, axis=1)


def load_players(conn: sqlite3.Connection) -> tuple[int, int]:
    """T-025.3: insert player reference data into `players` and `player_teams`."""
    if not PLAYERS_REFERENCE_PATH.exists():
        raise SystemExit(f"{PLAYERS_REFERENCE_PATH} not found — run 01_pull_player_reference.py first")

    ref_df = pd.read_parquet(PLAYERS_REFERENCE_PATH)

    players_df = (
        ref_df[["PLAYER_ID", "PLAYER_NAME"]]
        .drop_duplicates(subset=["PLAYER_ID"])
        .rename(columns={"PLAYER_ID": "player_id", "PLAYER_NAME": "name"})
    )
    players_df.to_sql("players", conn, if_exists="append", index=False)

    player_teams_df = ref_df[["PLAYER_ID", "SEASON", "TEAM_ID", "TEAM_ABBREVIATION"]].rename(
        columns={
            "PLAYER_ID": "player_id",
            "SEASON": "season",
            "TEAM_ID": "team_id",
            "TEAM_ABBREVIATION": "team_abbreviation",
        }
    )
    player_teams_df.to_sql("player_teams", conn, if_exists="append", index=False)

    return len(players_df), len(player_teams_df)


def verify_row_counts(conn: sqlite3.Connection, expected_shots: int, expected_players: int) -> None:
    """T-025.4: verify row counts in the DB match the source parquet files."""
    cur = conn.cursor()
    actual_shots = cur.execute("SELECT COUNT(*) FROM shots").fetchone()[0]
    actual_players = cur.execute("SELECT COUNT(*) FROM players").fetchone()[0]

    if actual_shots != expected_shots:
        raise RuntimeError(f"shots row count mismatch: DB={actual_shots}, source={expected_shots}")
    if actual_players != expected_players:
        raise RuntimeError(f"players row count mismatch: DB={actual_players}, source={expected_players}")

    print(f"Verified: {actual_shots} shots, {actual_players} players match source files")


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        print(f"Removing existing database at {DB_PATH} to rebuild from scratch")
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    try:
        create_schema(conn)

        n_players, n_player_teams = load_players(conn)
        print(f"Loaded {n_players} players, {n_player_teams} player-team-season rows")

        n_shots = load_shots(conn)
        print(f"Loaded {n_shots} shots")

        conn.commit()

        verify_row_counts(conn, expected_shots=n_shots, expected_players=n_players)
    finally:
        conn.close()

    print(f"Database ready at {DB_PATH}")


if __name__ == "__main__":
    main()
