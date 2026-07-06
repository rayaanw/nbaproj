"""T-026: Write model metrics & artifacts to SQLite.

Loads the training/evaluation outputs (T-016-T-021) into the DB so the
Methodology page can be built as a normal data-driven page instead of
reading static JSON files directly.

Numbering note: same convention as 06a-06e and 10a-10c — T-026 doesn't have
a prescribed filename, so this sits as 12a between T-025's 12_load_db.py and
T-027's 13_build_leaderboard_table.py.

Usage:
    python pipeline/12a_load_model_artifacts.py
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import DB_PATH, MODELS_DIR, PROJECT_ROOT

MODEL_METRICS_PATH = MODELS_DIR / "model_metrics.json"
BASELINE_METRICS_PATH = MODELS_DIR / "baseline_metrics.json"
CALIBRATION_DATA_PATH = MODELS_DIR / "calibration_data.json"
FEATURE_IMPORTANCE_PATH = MODELS_DIR / "feature_importance.json"

STATIC_IMAGES_DIR = PROJECT_ROOT / "app" / "static" / "images"


def load_model_metrics(conn: sqlite3.Connection) -> int:
    """T-026.1: insert log loss/AUC/Brier score (model + baseline) into `model_metrics`."""
    with open(MODEL_METRICS_PATH) as f:
        model_metrics = json.load(f)
    with open(BASELINE_METRICS_PATH) as f:
        baseline_metrics = json.load(f)

    rows = []
    for metric_name in ("log_loss", "auc", "brier_score"):
        if metric_name in model_metrics:
            rows.append(("model", metric_name, model_metrics[metric_name]))
        if metric_name in baseline_metrics:
            rows.append(("baseline", metric_name, baseline_metrics[metric_name]))

    conn.executemany(
        "INSERT INTO model_metrics (context, metric_name, value) VALUES (?, ?, ?)", rows
    )
    return len(rows)


def load_calibration_bins(conn: sqlite3.Connection) -> int:
    """T-026.2: insert calibration bucket data into `calibration_bins`."""
    with open(CALIBRATION_DATA_PATH) as f:
        bins = json.load(f)

    rows = [
        (b["bin_low"], b["bin_high"], b["predicted_midpoint"], b["actual_rate"], b["count"])
        for b in bins
    ]
    conn.executemany(
        "INSERT INTO calibration_bins (bin_low, bin_high, predicted_midpoint, actual_rate, sample_count) "
        "VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    return len(rows)


def load_feature_importance(conn: sqlite3.Connection) -> int:
    """T-026.3: insert feature importance values into `feature_importance`."""
    with open(FEATURE_IMPORTANCE_PATH) as f:
        importances = json.load(f)

    rows = [(row["feature"], row["importance"]) for row in importances]
    conn.executemany(
        "INSERT INTO feature_importance (feature_name, importance) VALUES (?, ?)", rows
    )
    return len(rows)


def copy_static_images() -> list[str]:
    """T-026.4: copy the plot images into app/static/images/ so Flask can
    serve them directly alongside the DB-driven numbers.
    """
    STATIC_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in ("calibration_plot.png", "feature_importance.png"):
        src = MODELS_DIR / name
        if not src.exists():
            raise SystemExit(f"{src} not found — run the T-020/T-021 scripts first")
        dst = STATIC_IMAGES_DIR / name
        shutil.copyfile(src, dst)
        copied.append(str(dst))
    return copied


def main() -> None:
    for path in (MODEL_METRICS_PATH, BASELINE_METRICS_PATH, CALIBRATION_DATA_PATH, FEATURE_IMPORTANCE_PATH):
        if not path.exists():
            raise SystemExit(f"{path} not found — run the Phase 3 (T-016-T-021) scripts first")
    if not DB_PATH.exists():
        raise SystemExit(f"{DB_PATH} not found — run 12_load_db.py first")

    conn = sqlite3.connect(DB_PATH)
    try:
        n_metrics = load_model_metrics(conn)
        print(f"Loaded {n_metrics} model_metrics rows")

        n_bins = load_calibration_bins(conn)
        print(f"Loaded {n_bins} calibration_bins rows")

        n_importances = load_feature_importance(conn)
        print(f"Loaded {n_importances} feature_importance rows")

        conn.commit()
    finally:
        conn.close()

    copied = copy_static_images()
    print(f"Copied {len(copied)} plot images to {STATIC_IMAGES_DIR}")


if __name__ == "__main__":
    main()
