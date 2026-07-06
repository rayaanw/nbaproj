"""T-039: Player Page — search & backend route.

Implements player lookup (search-as-you-type or direct link from the
Leaderboard) and the data query for a single player's shot profile.
"""

from __future__ import annotations

from flask import Blueprint, abort, jsonify, render_template, request

from app.queries import get_player, get_player_latest_team, get_player_shots, get_seasons, search_players
from app.team_colors import get_team_color

bp = Blueprint("player", __name__, url_prefix="/players")


@bp.route("/")
def search_page():
    """Landing point for the nav's "Players" link — a search box with no
    player loaded yet.
    """
    return render_template("player_search.html", active_page="player")


@bp.route("/search")
def search():
    """T-039.3: search-as-you-type JSON endpoint."""
    query_text = request.args.get("q", "")
    if not query_text:
        return jsonify([])

    matches = search_players(query_text)
    return jsonify([{"player_id": row["player_id"], "name": row["name"]} for row in matches])


@bp.route("/<int:player_id>")
def detail(player_id: int):
    """T-039.1/.2/.4: player detail — shot chart data + actual vs. expected
    FG%, overall and by shot zone. Handles "player not found" / "no shots in
    this season" gracefully rather than raising.
    """
    season = request.args.get("season") or None

    player = get_player(player_id)
    if player is None:
        abort(404, description="Player not found")

    team_color = get_team_color(get_player_latest_team(player_id))

    shots = get_player_shots(player_id, season=season)

    if not shots:
        return render_template(
            "player.html",
            active_page="player",
            player=player,
            team_color=team_color,
            seasons=get_seasons(),
            selected_season=season,
            has_shots=False,
            overall=None,
            by_zone=[],
        )

    total_attempts = len(shots)
    made = sum(row["shot_made_flag"] for row in shots)
    actual_fg_pct = made / total_attempts
    expected_fg_pct = sum(row["xfg_pct"] for row in shots) / total_attempts

    overall = {
        "attempts": total_attempts,
        "actual_fg_pct": actual_fg_pct,
        "expected_fg_pct": expected_fg_pct,
        "differential": actual_fg_pct - expected_fg_pct,
    }

    by_zone_map: dict[str, dict] = {}
    for row in shots:
        zone = row["shot_zone_basic"] or "Unknown"
        z = by_zone_map.setdefault(zone, {"attempts": 0, "made": 0, "xfg_sum": 0.0})
        z["attempts"] += 1
        z["made"] += row["shot_made_flag"]
        z["xfg_sum"] += row["xfg_pct"]

    by_zone = [
        {
            "zone": zone,
            "attempts": z["attempts"],
            "actual_fg_pct": z["made"] / z["attempts"],
            "expected_fg_pct": z["xfg_sum"] / z["attempts"],
            "differential": (z["made"] / z["attempts"]) - (z["xfg_sum"] / z["attempts"]),
        }
        for zone, z in sorted(by_zone_map.items())
    ]

    return render_template(
        "player.html",
        active_page="player",
        player=player,
        team_color=team_color,
        seasons=get_seasons(),
        selected_season=season,
        has_shots=True,
        overall=overall,
        by_zone=by_zone,
    )
