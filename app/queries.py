"""T-030: SQLite query layer.

Centralizes all DB access in one module so route handlers (app/routes/*)
stay thin and query/join logic isn't duplicated across pages. The app is
read-only at runtime (see CLAUDE.md) — every connection here is opened
read-only, so a bug elsewhere in the app can never accidentally write to
the database the offline pipeline built.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from flask import current_app


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """T-030.1: a read-only SQLite connection, scoped to a single `with` block.

    Uses SQLite's `mode=ro` URI flag rather than just opening the file
    normally, so a coding mistake elsewhere in the app can't accidentally
    write to the pipeline-built database.
    """
    db_path = current_app.config["DB_PATH"]
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def get_player_shots(player_id: int, season: str | None = None) -> list[sqlite3.Row]:
    """T-030.2: shots for a player, optionally filtered by season."""
    query = "SELECT * FROM shots WHERE player_id = ?"
    params: list = [player_id]
    if season:
        query += " AND season = ?"
        params.append(season)

    with get_connection() as conn:
        return conn.execute(query, params).fetchall()


def get_leaderboard(season_or_career: str, min_attempts: int | None = None) -> list[sqlite3.Row]:
    """T-030.3: qualified players for a season (or "career"), ranked by
    skill differential descending. `min_attempts` overrides the
    already-computed `qualified` flag if provided (e.g. for a future
    "show all" toggle); otherwise it just filters on `qualified = 1`.
    """
    if min_attempts is not None:
        query = (
            "SELECT l.*, p.name FROM leaderboard l JOIN players p ON p.player_id = l.player_id "
            "WHERE l.season_or_career = ? AND l.attempts >= ? ORDER BY l.skill_differential DESC"
        )
        params = [season_or_career, min_attempts]
    else:
        query = (
            "SELECT l.*, p.name FROM leaderboard l JOIN players p ON p.player_id = l.player_id "
            "WHERE l.season_or_career = ? AND l.qualified = 1 ORDER BY l.skill_differential DESC"
        )
        params = [season_or_career]

    with get_connection() as conn:
        return conn.execute(query, params).fetchall()


def get_explorer_shots(
    season: str | None = None,
    zone: str | None = None,
    player_id: int | None = None,
    team_id: int | None = None,
) -> list[sqlite3.Row]:
    """T-030.4: filtered shots for the Shot Explorer hexbin. Defaults to the
    full league-wide set when no filters are given.
    """
    query = "SELECT s.* FROM shots s"
    joins = []
    conditions = []
    params: list = []

    if team_id is not None:
        joins.append(
            "JOIN player_teams pt ON pt.player_id = s.player_id AND pt.season = s.season"
        )
        conditions.append("pt.team_id = ?")
        params.append(team_id)

    if season:
        conditions.append("s.season = ?")
        params.append(season)
    if zone:
        conditions.append("s.shot_zone_basic = ?")
        params.append(zone)
    if player_id is not None:
        conditions.append("s.player_id = ?")
        params.append(player_id)

    if joins:
        query += " " + " ".join(joins)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    with get_connection() as conn:
        return conn.execute(query, params).fetchall()


def get_model_metrics() -> list[sqlite3.Row]:
    """T-030.5: model + baseline metrics for the Methodology page."""
    with get_connection() as conn:
        return conn.execute("SELECT * FROM model_metrics ORDER BY context, metric_name").fetchall()


def get_calibration_bins() -> list[sqlite3.Row]:
    """T-030.5: calibration bucket data for the Methodology page."""
    with get_connection() as conn:
        return conn.execute("SELECT * FROM calibration_bins ORDER BY bin_low").fetchall()


def get_feature_importance(limit: int = 20) -> list[sqlite3.Row]:
    """T-030.5: top feature importances for the Methodology page."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM feature_importance ORDER BY importance DESC LIMIT ?", [limit]
        ).fetchall()


def search_players(query_text: str, limit: int = 10) -> list[sqlite3.Row]:
    """T-030.6: search-as-you-type matches for the Player Page search box."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT player_id, name FROM players WHERE name LIKE ? ORDER BY name LIMIT ?",
            [f"%{query_text}%", limit],
        ).fetchall()


def get_player(player_id: int) -> sqlite3.Row | None:
    """Helper used by the Player Page route to fetch basic player info."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM players WHERE player_id = ?", [player_id]
        ).fetchone()


def get_player_latest_team(player_id: int) -> str | None:
    """Most recent team abbreviation for a player (T-044.2's team-color accent)."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT team_abbreviation FROM player_teams WHERE player_id = ? "
            "ORDER BY season DESC LIMIT 1",
            [player_id],
        ).fetchone()
        return row["team_abbreviation"] if row else None


def get_seasons() -> list[str]:
    """Distinct seasons present in the DB, for populating filter dropdowns."""
    with get_connection() as conn:
        rows = conn.execute("SELECT DISTINCT season FROM shots ORDER BY season").fetchall()
        return [row["season"] for row in rows]


def get_shot_zones() -> list[str]:
    """Distinct shot zones present in the DB, for populating filter dropdowns."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT shot_zone_basic FROM shots WHERE shot_zone_basic IS NOT NULL ORDER BY shot_zone_basic"
        ).fetchall()
        return [row["shot_zone_basic"] for row in rows]


def list_players() -> list[sqlite3.Row]:
    """All players, for populating the Explorer's player-select dropdown."""
    with get_connection() as conn:
        return conn.execute("SELECT player_id, name FROM players ORDER BY name").fetchall()


def list_teams() -> list[sqlite3.Row]:
    """Distinct teams, for populating the Explorer's team-select dropdown."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT DISTINCT team_id, team_abbreviation FROM player_teams ORDER BY team_abbreviation"
        ).fetchall()
