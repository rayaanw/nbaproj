"""T-016: Train a naive baseline model.

Predicts the overall training-set make rate for every test-set shot. Without
this reference point, a "good-looking" log loss number from the real model
has nothing to prove it actually adds value.

Usage:
    python pipeline/08_train_baseline.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import DATA_PROCESSED_DIR, MODELS_DIR
from pipeline.features import TARGET_COLUMN

TRAIN_PATH = DATA_PROCESSED_DIR / "train.parquet"
TEST_PATH = DATA_PROCESSED_DIR / "test.parquet"
OUTPUT_PATH = MODELS_DIR / "baseline_metrics.json"


def main() -> None:
    if not TRAIN_PATH.exists() or not TEST_PATH.exists():
        raise SystemExit(f"{TRAIN_PATH}/{TEST_PATH} not found — run 07_train_test_split.py first")

    train_df = pd.read_parquet(TRAIN_PATH, columns=[TARGET_COLUMN])
    test_df = pd.read_parquet(TEST_PATH, columns=[TARGET_COLUMN])

    # T-016.1: constant prediction = overall training-set make rate.
    train_make_rate = float(train_df[TARGET_COLUMN].mean())
    y_true = test_df[TARGET_COLUMN].to_numpy()
    y_pred = np.full_like(y_true, fill_value=train_make_rate, dtype=float)

    # T-016.2: log loss, AUC, Brier score on the test set.
    metrics = {
        "constant_prediction": train_make_rate,
        "log_loss": float(log_loss(y_true, y_pred, labels=[0, 1])),
        "brier_score": float(brier_score_loss(y_true, y_pred)),
    }

    # AUC is undefined for a constant prediction (no ranking information) —
    # report it as null rather than raising, and note why.
    try:
        metrics["auc"] = float(roc_auc_score(y_true, y_pred))
    except ValueError:
        metrics["auc"] = None
        metrics["auc_note"] = "undefined for a constant-prediction baseline (no ranking signal)"

    # T-016.3: save.
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(metrics, f, indent=2)

    print(json.dumps(metrics, indent=2))
    print(f"Saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
