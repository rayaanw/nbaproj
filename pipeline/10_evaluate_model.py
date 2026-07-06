"""T-019: Evaluate the tuned model on the held-out test set.

Scores test.parquet with the trained model and computes the headline metrics
(log loss, AUC-ROC, Brier score), then compares against the baseline from
T-016 — this comparison is the headline result for the Methodology page.

Usage:
    python pipeline/10_evaluate_model.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import xgboost as xgb
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import DATA_PROCESSED_DIR, MODELS_DIR, XGBOOST_N_JOBS
from pipeline.features import TARGET_COLUMN

TEST_PATH = DATA_PROCESSED_DIR / "test.parquet"
MODEL_PATH = MODELS_DIR / "xgb_shot_quality.json"
FEATURE_LIST_PATH = MODELS_DIR / "feature_columns.json"
BASELINE_METRICS_PATH = MODELS_DIR / "baseline_metrics.json"
OUTPUT_PATH = MODELS_DIR / "model_metrics.json"


def main() -> None:
    for path, upstream in [
        (TEST_PATH, "07_train_test_split.py"),
        (MODEL_PATH, "09_train_model.py"),
        (FEATURE_LIST_PATH, "09_train_model.py"),
        (BASELINE_METRICS_PATH, "08_train_baseline.py"),
    ]:
        if not path.exists():
            raise SystemExit(f"{path} not found — run {upstream} first")

    test_df = pd.read_parquet(TEST_PATH)
    with open(FEATURE_LIST_PATH) as f:
        feature_columns = json.load(f)

    model = xgb.XGBClassifier(n_jobs=XGBOOST_N_JOBS)
    model.load_model(MODEL_PATH)

    # T-019.1: score the test set.
    X_test = test_df[feature_columns]
    y_test = test_df[TARGET_COLUMN]
    y_pred = model.predict_proba(X_test)[:, 1]

    # T-019.2: log loss (primary), AUC-ROC, Brier score.
    metrics = {
        "log_loss": float(log_loss(y_test, y_pred, labels=[0, 1])),
        "auc": float(roc_auc_score(y_test, y_pred)),
        "brier_score": float(brier_score_loss(y_test, y_pred)),
        "n_test_rows": len(test_df),
    }

    # T-019.3: compare against the baseline and compute relative improvement.
    with open(BASELINE_METRICS_PATH) as f:
        baseline_metrics = json.load(f)

    baseline_log_loss = baseline_metrics["log_loss"]
    metrics["baseline_log_loss"] = baseline_log_loss
    metrics["log_loss_improvement_pct"] = (
        100.0 * (baseline_log_loss - metrics["log_loss"]) / baseline_log_loss
    )

    # T-019.4: save.
    with open(OUTPUT_PATH, "w") as f:
        json.dump(metrics, f, indent=2)

    print(json.dumps(metrics, indent=2))
    print(f"Saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
