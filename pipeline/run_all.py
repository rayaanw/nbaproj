"""T-028: Run the full offline pipeline in order, one command.

Runs every numbered pipeline script in sequence (T-004 through T-027), then
a handful of sanity queries directly against the finished SQLite DB (T-028.2)
to confirm the whole chain — from raw pull through to a queryable
database — actually worked end-to-end.

This is slow (rate-limited nba_api calls across 3 seasons) and only needs to
be run once, or re-run manually to rebuild from scratch. See
pipeline/README.md for the full breakdown, prerequisites, and what to do if
a step fails partway through.

Usage:
    python pipeline/run_all.py
"""

from __future__ import annotations

import importlib
import importlib.util
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import DB_PATH

# Run order. Each entry is (module filename without .py, human label).
# Numbering matches the files on disk — see pipeline/README.md for why
# T-010-T-014 and T-020/T-021/T-022 use lettered sub-numbers (06a-06e,
# 10a-10c) instead of their own top-level numbers.
PIPELINE_STEPS = [
    ("01_pull_player_reference", "T-004: pull player/season reference"),
    ("02_pull_shot_charts", "T-005: pull shot charts"),
    ("03_pull_playbyplay", "T-006: pull play-by-play"),
    ("04_pull_defender_distance_priors", "T-007: pull defender-distance priors"),
    ("05_validate_raw_data", "T-008: validate raw data"),
    ("06_consolidate_shots", "T-009: consolidate shots"),
    ("06a_geo_features", "T-010: geometric features"),
    ("06b_score_margin", "T-011: score margin join"),
    ("06c_context_features", "T-012: game-situation context features"),
    ("06d_defender_prior", "T-013: defender-distance prior join"),
    ("06e_assemble_features", "T-014: assemble final feature table"),
    ("07_train_test_split", "T-015: chronological train/test split"),
    ("08_train_baseline", "T-016: train naive baseline"),
    ("09_train_model", "T-017/T-018: train + tune XGBoost model"),
    ("10_evaluate_model", "T-019: evaluate model on test set"),
    ("10a_calibration_plot", "T-020: calibration curve & plot"),
    ("10b_feature_importance", "T-021: feature importance chart"),
    ("10c_write_model_card", "T-022: model card + artifact bundle check"),
    ("11_score_all_shots", "T-023: score all shots"),
    ("12_load_db", "T-025: load scored shots into SQLite"),
    ("12a_load_model_artifacts", "T-026: load model metrics/artifacts into SQLite"),
    ("13_build_leaderboard_table", "T-027: build leaderboard table"),
]


def run_step(module_name: str, label: str) -> None:
    print(f"\n{'=' * 70}\n{label} ({module_name}.py)\n{'=' * 70}")
    # Modules are loaded by path since several start with a digit and can't
    # be imported with a normal `import pipeline.01_...` statement.
    module_path = Path(__file__).resolve().parent / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main()


def sanity_check_database() -> None:
    """T-028.2: basic sanity queries directly against the finished DB."""
    print(f"\n{'=' * 70}\nSanity-checking {DB_PATH}\n{'=' * 70}")

    if not DB_PATH.exists():
        raise SystemExit(f"{DB_PATH} does not exist — pipeline did not complete successfully")

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()

        total_shots = cur.execute("SELECT COUNT(*) FROM shots").fetchone()[0]
        print(f"Total shots: {total_shots}")
        if total_shots == 0:
            raise RuntimeError("`shots` table is empty")

        total_players = cur.execute("SELECT COUNT(*) FROM players").fetchone()[0]
        print(f"Total players: {total_players}")
        if total_players == 0:
            raise RuntimeError("`players` table is empty")

        metrics_count = cur.execute("SELECT COUNT(*) FROM model_metrics").fetchone()[0]
        print(f"model_metrics rows: {metrics_count}")
        if metrics_count == 0:
            raise RuntimeError("`model_metrics` table is empty")

        sample_leaderboard_row = cur.execute(
            "SELECT p.name, l.season_or_career, l.attempts, l.actual_fg_pct, l.expected_fg_pct, "
            "l.skill_differential FROM leaderboard l JOIN players p ON p.player_id = l.player_id "
            "WHERE l.qualified = 1 ORDER BY l.attempts DESC LIMIT 1"
        ).fetchone()
        if sample_leaderboard_row is None:
            print("WARNING: no qualified leaderboard rows found (dataset may be too small)")
        else:
            name, season, attempts, actual, expected, diff = sample_leaderboard_row
            print(
                f"Sample leaderboard row: {name} ({season}), {attempts} attempts, "
                f"actual={actual:.3f}, expected={expected:.3f}, differential={diff:+.3f}"
            )

        print("\nAll sanity checks passed.")
    finally:
        conn.close()


def main() -> None:
    for module_name, label in PIPELINE_STEPS:
        run_step(module_name, label)

    sanity_check_database()


if __name__ == "__main__":
    main()
