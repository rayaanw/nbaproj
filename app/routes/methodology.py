"""T-041: Methodology page — backend route.

Serves the model transparency data (metrics, calibration bins, feature
importance) from the DB tables populated in T-026.
"""

from __future__ import annotations

from flask import Blueprint, render_template

from app.queries import get_calibration_bins, get_feature_importance, get_model_metrics

bp = Blueprint("methodology", __name__, url_prefix="/methodology")


@bp.route("/")
def index():
    metrics_rows = get_model_metrics()

    # Reshape into {context: {metric_name: value}} for easy side-by-side
    # rendering in the template (T-042.1).
    metrics: dict[str, dict[str, float]] = {"model": {}, "baseline": {}}
    for row in metrics_rows:
        metrics.setdefault(row["context"], {})[row["metric_name"]] = row["value"]

    return render_template(
        "methodology.html",
        active_page="methodology",
        metrics=metrics,
        calibration_bins=get_calibration_bins(),
        feature_importance=get_feature_importance(),
        calibration_plot_url="images/calibration_plot.png",
        feature_importance_plot_url="images/feature_importance.png",
    )
