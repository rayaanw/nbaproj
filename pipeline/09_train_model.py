"""T-017 + T-018: Train the XGBoost shot-quality model.

Two stages in one script:
  1. (T-017) Train an initial default-hyperparameter model and sanity-check
     it on a held-out slice of the *training* data (never touching the test
     set at this stage).
  2. (T-018) Run a small hyperparameter grid via cross-validation on the
     training set only, retrain the final model on the full training set
     with the best combination, and save it.

Usage:
    python pipeline/09_train_model.py
"""

from __future__ import annotations

import sys
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import log_loss
from sklearn.model_selection import StratifiedKFold, train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import DATA_PROCESSED_DIR, MODELS_DIR, XGBOOST_N_JOBS
from pipeline.features import TARGET_COLUMN, get_feature_columns

TRAIN_PATH = DATA_PROCESSED_DIR / "train.parquet"
OUTPUT_MODEL_PATH = MODELS_DIR / "xgb_shot_quality.json"
OUTPUT_FEATURE_LIST_PATH = MODELS_DIR / "feature_columns.json"

# T-018.1: small, defensible hyperparameter grid for XGBoost binary classification.
PARAM_GRID = {
    "max_depth": [3, 4, 6],
    "learning_rate": [0.05, 0.1],
    "n_estimators": [200, 400],
    "subsample": [0.8, 1.0],
}

CV_FOLDS = 3
RANDOM_STATE = 42


def load_train_xy() -> tuple[pd.DataFrame, pd.Series, list[str]]:
    if not TRAIN_PATH.exists():
        raise SystemExit(f"{TRAIN_PATH} not found — run 07_train_test_split.py first")

    df = pd.read_parquet(TRAIN_PATH)
    feature_columns = get_feature_columns(df)
    X = df[feature_columns]
    y = df[TARGET_COLUMN]
    return X, y, feature_columns


def sanity_check_default_model(X: pd.DataFrame, y: pd.Series) -> None:
    """T-017.2/.3: fit a default-hyperparameter model and confirm it trains
    without error and produces sane (0-1, non-degenerate) probabilities on a
    held-out slice carved out of the *training* data only.
    """
    X_fit, X_holdout, y_fit, y_holdout = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
    )

    model = xgb.XGBClassifier(
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=RANDOM_STATE,
        n_jobs=XGBOOST_N_JOBS,
    )
    model.fit(X_fit, y_fit)

    preds = model.predict_proba(X_holdout)[:, 1]

    if not np.all((preds >= 0) & (preds <= 1)):
        raise RuntimeError("Default model produced predictions outside [0, 1]")
    if preds.std() < 1e-6:
        raise RuntimeError(
            "Default model produced a degenerate (near-constant) prediction — "
            "something is wrong with the feature set or training data"
        )

    print(
        f"Sanity check passed: predictions in [{preds.min():.3f}, {preds.max():.3f}], "
        f"std={preds.std():.4f}, holdout log loss={log_loss(y_holdout, preds):.4f}"
    )


def tune_hyperparameters(X: pd.DataFrame, y: pd.Series) -> dict:
    """T-018.2: small grid search via cross-validation on the training set
    only (test set is never touched here), optimizing for log loss.
    """
    keys = list(PARAM_GRID.keys())
    combinations = list(product(*PARAM_GRID.values()))
    print(f"Searching {len(combinations)} hyperparameter combinations x {CV_FOLDS} folds...")

    skf = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)

    best_params: dict | None = None
    best_score = np.inf

    for combo in combinations:
        params = dict(zip(keys, combo))
        fold_losses = []

        for train_idx, val_idx in skf.split(X, y):
            model = xgb.XGBClassifier(
                objective="binary:logistic",
                eval_metric="logloss",
                random_state=RANDOM_STATE,
                n_jobs=XGBOOST_N_JOBS,
                **params,
            )
            model.fit(X.iloc[train_idx], y.iloc[train_idx])
            preds = model.predict_proba(X.iloc[val_idx])[:, 1]
            fold_losses.append(log_loss(y.iloc[val_idx], preds, labels=[0, 1]))

        mean_loss = float(np.mean(fold_losses))
        print(f"  {params} -> mean CV log loss={mean_loss:.4f}")

        if mean_loss < best_score:
            best_score = mean_loss
            best_params = params

    assert best_params is not None
    print(f"Best params: {best_params} (mean CV log loss={best_score:.4f})")
    return best_params


def main() -> None:
    X, y, feature_columns = load_train_xy()
    print(f"Loaded {len(X)} training rows, {len(feature_columns)} feature columns")

    # T-017: initial default-hyperparameter model + sanity check.
    sanity_check_default_model(X, y)

    # T-018: hyperparameter search + final fit on the full training set.
    best_params = tune_hyperparameters(X, y)

    final_model = xgb.XGBClassifier(
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=RANDOM_STATE,
        n_jobs=XGBOOST_N_JOBS,
        **best_params,
    )
    final_model.fit(X, y)

    # T-018.4: save in XGBoost's native format.
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    final_model.save_model(OUTPUT_MODEL_PATH)

    # Save the exact feature column list/order alongside the model so
    # scoring (T-023) can reconstruct an identical input matrix.
    import json

    with open(OUTPUT_FEATURE_LIST_PATH, "w") as f:
        json.dump(feature_columns, f, indent=2)

    print(f"Saved model to {OUTPUT_MODEL_PATH}")
    print(f"Saved feature column list to {OUTPUT_FEATURE_LIST_PATH}")


if __name__ == "__main__":
    main()
