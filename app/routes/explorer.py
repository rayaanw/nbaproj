"""T-035: Shot Explorer — backend route & query.

Wires the Explorer page's filter controls (season, shot zone, optional
player/team) to `get_explorer_shots()`.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request

from app.queries import get_explorer_shots, get_seasons, get_shot_zones, list_players, list_teams

bp = Blueprint("explorer", __name__, url_prefix="/explorer")


@bp.route("/")
def index():
    """T-035.3: page shell with filter dropdowns populated from the DB. The
    actual shot data is fetched by the page's own JS from /explorer/data.
    """
    return render_template(
        "explorer.html",
        active_page="explorer",
        seasons=get_seasons(),
        zones=get_shot_zones(),
        players=list_players(),
        teams=list_teams(),
    )


@bp.route("/data")
def data():
    """T-035.1/.2: JSON shot data for the frontend chart, filtered by the
    given query params. Defaults to the league-wide aggregate when no
    player/team is selected.
    """
    season = request.args.get("season") or None
    zone = request.args.get("zone") or None
    player_id = request.args.get("player_id", type=int)
    team_id = request.args.get("team_id", type=int)

    shots = get_explorer_shots(season=season, zone=zone, player_id=player_id, team_id=team_id)

    return jsonify(
        [
            {
                "loc_x": row["loc_x"],
                "loc_y": row["loc_y"],
                "shot_distance": row["shot_distance"],
                "action_type": row["action_type"],
                "xfg_pct": row["xfg_pct"],
                "shot_made_flag": row["shot_made_flag"],
            }
            for row in shots
        ]
    )
