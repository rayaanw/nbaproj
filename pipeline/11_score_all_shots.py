"""T-023: Score every shot (train + test seasons) with the trained model.

Produces the xfg_pct value the entire app displays. Unlike evaluation
(T-019), this scores the *full* 3-season table, not just the test split,
since the app needs predictions for every season.

Usage:
    python pipeline/11_score_all_shots.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import xgboost as xgb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import DATA_PROCESSED_DIR, MODELS_DIR, XGBOOST_N_JOBS
from pipeline.features import get_feature_columns

FEATURES_PATH = DATA_PROCESSED_DIR / "features_final.parquet"
MODEL_PATH = MODELS_DIR / "xgb_shot_quality.json"
FEATURE_LIST_PATH = MODELS_DIR / "feature_columns.json"
OUTPUT_PATH = DATA_PROCESSED_DIR / "shots_scored.parquet"


def main() -> None:
    for path, upstream in [
        (FEATURES_PATH, "06e_assemble_features.py"),
        (MODEL_PATH, "09_train_model.py"),
        (FEATURE_LIST_PATH, "09_train_model.py"),
    ]:
        if not path.exists():
            raise SystemExit(f"{path} not found — run {upstream} first")

    # T-023.1: load the full 3-season table and the trained model.
    df = pd.read_parquet(FEATURES_PATH)
    with open(FEATURE_LIST_PATH) as f:
        trained_feature_columns = json.load(f)

    # Defensive check: the feature set at score time must exactly match what
    # the model was trained on (see pipeline/features.py::get_feature_columns
    # docstring) — assembling features_final.parquet the same way T-014 did
    # should always produce the same columns, but this catches drift loudly
    # instead of silently mis-scoring.
    current_feature_columns = get_feature_columns(df)
    missing = set(trained_feature_columns) - set(current_feature_columns)
    if missing:
        raise RuntimeError(
            f"features_final.parquet is missing columns the model was trained on: {missing}"
        )

    model = xgb.XGBClassifier(n_jobs=XGBOOST_N_JOBS)
    model.load_model(MODEL_PATH)

    # T-023.2: generate the xfg_pct prediction for every shot.
    X = df[trained_feature_columns]
    df["xfg_pct"] = model.predict_proba(X)[:, 1]

    # T-023.3: save.
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_PATH, index=False)

    print(f"Scored {len(df)} shots. xfg_pct range: [{df['xfg_pct'].min():.3f}, {df['xfg_pct'].max():.3f}]")
    print(f"Saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
