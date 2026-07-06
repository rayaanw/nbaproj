"""T-021: Generate the feature importance chart.

A second transparency artifact for the Methodology page, showing which
factors drive the model's predictions (shot distance/angle and action type
should dominate).

Usage:
    python pipeline/10b_feature_importance.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import xgboost as xgb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import MODELS_DIR, XGBOOST_N_JOBS

MODEL_PATH = MODELS_DIR / "xgb_shot_quality.json"
FEATURE_LIST_PATH = MODELS_DIR / "feature_columns.json"
PLOT_PATH = MODELS_DIR / "feature_importance.png"
DATA_PATH = MODELS_DIR / "feature_importance.json"

TOP_N = 20


def main() -> None:
    for path, upstream in [(MODEL_PATH, "09_train_model.py"), (FEATURE_LIST_PATH, "09_train_model.py")]:
        if not path.exists():
            raise SystemExit(f"{path} not found — run {upstream} first")

    with open(FEATURE_LIST_PATH) as f:
        feature_columns = json.load(f)

    model = xgb.XGBClassifier(n_jobs=XGBOOST_N_JOBS)
    model.load_model(MODEL_PATH)

    # T-021.1: extract feature importances (gain-based — reflects how much
    # each feature improves the model's splits, more informative than raw
    # split-count for this use case).
    booster = model.get_booster()
    raw_scores = booster.get_score(importance_type="gain")

    # Because the model was fit on a pandas DataFrame, the booster keys
    # importances by the real column names directly (not generic "f0", "f1",
    # ... indices, which is only what happens with a plain numpy/DMatrix
    # input) — verified by inspecting get_score()'s actual output. A feature
    # that was never used in any split simply doesn't appear in the dict, so
    # it correctly defaults to 0.
    importances = [
        {"feature": name, "importance": float(raw_scores.get(name, 0.0))}
        for name in feature_columns
    ]

    importances.sort(key=lambda row: row["importance"], reverse=True)

    with open(DATA_PATH, "w") as f:
        json.dump(importances, f, indent=2)

    # T-021.2: horizontal bar chart of top features.
    top = importances[:TOP_N]
    fig, ax = plt.subplots(figsize=(8, max(4, len(top) * 0.35)))
    ax.barh([row["feature"] for row in reversed(top)], [row["importance"] for row in reversed(top)], color="tab:blue")
    ax.set_xlabel("Importance (gain)")
    ax.set_title(f"Top {len(top)} feature importances")
    fig.tight_layout()

    # T-021.3: save.
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(PLOT_PATH, dpi=150)
    plt.close(fig)

    print(f"Saved plot to {PLOT_PATH}")
    print(f"Saved importance data ({len(importances)} features) to {DATA_PATH}")


if __name__ == "__main__":
    main()
