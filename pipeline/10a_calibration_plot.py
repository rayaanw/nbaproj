"""T-020: Generate the calibration curve and plot.

Visual proof the predicted probabilities are trustworthy — critical since the
app displays "expected FG%" directly to users. Bucketed data is saved
alongside the plot so the Methodology page (T-042) can also render it
interactively from the database rather than only as a static image.

Numbering note: like T-010-T-014 (06a-06e), this and T-021's script don't
have a prescribed filename in the plan, so they're numbered 10a/10b to sit
between T-019's 10_evaluate_model.py and T-023's 11_score_all_shots.py.

Usage:
    python pipeline/10a_calibration_plot.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless-safe backend, no display needed
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xgboost as xgb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import DATA_PROCESSED_DIR, MODELS_DIR, XGBOOST_N_JOBS
from pipeline.features import TARGET_COLUMN

TEST_PATH = DATA_PROCESSED_DIR / "test.parquet"
MODEL_PATH = MODELS_DIR / "xgb_shot_quality.json"
FEATURE_LIST_PATH = MODELS_DIR / "feature_columns.json"
PLOT_PATH = MODELS_DIR / "calibration_plot.png"
DATA_PATH = MODELS_DIR / "calibration_data.json"

N_BINS = 10


def main() -> None:
    for path, upstream in [
        (TEST_PATH, "07_train_test_split.py"),
        (MODEL_PATH, "09_train_model.py"),
        (FEATURE_LIST_PATH, "09_train_model.py"),
    ]:
        if not path.exists():
            raise SystemExit(f"{path} not found — run {upstream} first")

    test_df = pd.read_parquet(TEST_PATH)
    with open(FEATURE_LIST_PATH) as f:
        feature_columns = json.load(f)

    model = xgb.XGBClassifier(n_jobs=XGBOOST_N_JOBS)
    model.load_model(MODEL_PATH)

    y_true = test_df[TARGET_COLUMN].to_numpy()
    y_pred = model.predict_proba(test_df[feature_columns])[:, 1]

    # T-020.1: bucket predictions into probability bins, compute actual make
    # rate per bin.
    bin_edges = np.linspace(0, 1, N_BINS + 1)
    bin_indices = np.clip(np.digitize(y_pred, bin_edges[1:-1], right=True), 0, N_BINS - 1)

    bins = []
    for i in range(N_BINS):
        mask = bin_indices == i
        count = int(mask.sum())
        if count == 0:
            continue
        bins.append(
            {
                "bin_low": float(bin_edges[i]),
                "bin_high": float(bin_edges[i + 1]),
                "predicted_midpoint": float(y_pred[mask].mean()),
                "actual_rate": float(y_true[mask].mean()),
                "count": count,
            }
        )

    with open(DATA_PATH, "w") as f:
        json.dump(bins, f, indent=2)

    # T-020.2: plot predicted probability vs. actual make rate against the diagonal.
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot([0, 1], [0, 1], linestyle="--", color="gray", label="Perfect calibration")
    ax.plot(
        [b["predicted_midpoint"] for b in bins],
        [b["actual_rate"] for b in bins],
        marker="o",
        color="tab:orange",
        label="Model",
    )
    ax.set_xlabel("Predicted probability (xFG%)")
    ax.set_ylabel("Actual make rate")
    ax.set_title("Calibration curve — test season")
    ax.legend()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    fig.tight_layout()

    # T-020.3: save.
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(PLOT_PATH, dpi=150)
    plt.close(fig)

    print(f"Saved plot to {PLOT_PATH}")
    print(f"Saved bin data ({len(bins)} bins) to {DATA_PATH}")


if __name__ == "__main__":
    main()
