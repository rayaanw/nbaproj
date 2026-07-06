"""T-037: Leaderboard — backend route & query.

Serves the pre-aggregated leaderboard table (T-027), filtered to qualified
rows and sorted by skill differential.
"""

from __future__ import annotations

from flask import Blueprint, render_template, request

from app.queries import get_leaderboard, get_seasons

bp = Blueprint("leaderboard", __name__, url_prefix="/leaderboard")

CAREER_LABEL = "career"


@bp.route("/")
def index():
    season_or_career = request.args.get("season", CAREER_LABEL)

    rows = get_leaderboard(season_or_career)

    return render_template(
        "leaderboard.html",
        active_page="leaderboard",
        rows=rows,
        seasons=get_seasons(),
        selected_season=season_or_career,
        career_label=CAREER_LABEL,
    )
