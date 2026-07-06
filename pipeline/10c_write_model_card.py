"""T-022: Confirm the full model artifact bundle and write MODEL_CARD.md.

Consolidates every training deliverable into one clearly versioned reference
so the scoring step (Phase 4) and the Methodology page (Phase 6) have a
single, stable source to read from.

Usage:
    python pipeline/10c_write_model_card.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import ALL_SEASONS, MODELS_DIR, TEST_SEASON, TRAIN_SEASONS

REQUIRED_ARTIFACTS = [
    "xgb_shot_quality.json",
    "feature_columns.json",
    "model_metrics.json",
    "baseline_metrics.json",
    "calibration_plot.png",
    "calibration_data.json",
    "feature_importance.png",
    "feature_importance.json",
]

MODEL_CARD_PATH = MODELS_DIR / "MODEL_CARD.md"


def main() -> None:
    # T-022.1: confirm every artifact exists.
    missing = [name for name in REQUIRED_ARTIFACTS if not (MODELS_DIR / name).exists()]
    if missing:
        raise SystemExit(
            f"Missing model artifacts: {missing} — run the earlier T-016-T-021 scripts first"
        )

    with open(MODELS_DIR / "feature_columns.json") as f:
        feature_columns = json.load(f)
    with open(MODELS_DIR / "model_metrics.json") as f:
        model_metrics = json.load(f)
    with open(MODELS_DIR / "baseline_metrics.json") as f:
        baseline_metrics = json.load(f)
    with open(MODELS_DIR / "feature_importance.json") as f:
        feature_importance = json.load(f)

    top_features = feature_importance[:8]

    # T-022.2: write the model card.
    lines = [
        "# Model Card — NBA Shot Quality Model",
        "",
        f"**Training date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        f"**Seasons used:** train={TRAIN_SEASONS}, test={TEST_SEASON} (chronological split, all seasons: {ALL_SEASONS})",
        f"**Algorithm:** XGBoost binary classifier (make/miss)",
        f"**Feature count:** {len(feature_columns)}",
        "",
        "## Headline metrics (test season)",
        "",
        "| Metric | Model | Baseline (constant prediction) | Improvement |",
        "|---|---|---|---|",
        f"| Log loss | {model_metrics['log_loss']:.4f} | {baseline_metrics['log_loss']:.4f} | {model_metrics['log_loss_improvement_pct']:.1f}% |",
        f"| AUC-ROC | {model_metrics['auc']:.4f} | {baseline_metrics.get('auc', 'n/a')} | — |",
        f"| Brier score | {model_metrics['brier_score']:.4f} | {baseline_metrics['brier_score']:.4f} | — |",
        "",
        "## Top feature importances (gain)",
        "",
        "| Feature | Importance |",
        "|---|---|",
        *[f"| {row['feature']} | {row['importance']:.2f} |" for row in top_features],
        "",
        "## Feature list",
        "",
        f"`{', '.join(feature_columns)}`",
        "",
        "## Data limitations",
        "",
        "See `PRD-NBAShotQualityModel.md` and `CLAUDE.md` for the full discussion. In short:",
        "`ACTION_TYPE` is the primary real per-shot contest proxy (true defender distance/shot",
        "clock/contested-shot flag are not exposed by nba_api's public endpoints);",
        "`defender_distance_prior` is a league-average approximation joined by",
        "(season, shot distance bucket), not true per-shot tracking data.",
        "",
    ]

    MODEL_CARD_PATH.write_text("\n".join(lines))
    print(f"Wrote {MODEL_CARD_PATH}")
    print("All required model artifacts present:")
    for name in REQUIRED_ARTIFACTS:
        print(f"  - {name}")


if __name__ == "__main__":
    main()
