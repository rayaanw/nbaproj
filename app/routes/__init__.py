"""Route registration.

Kept as a single `register_routes(app)` entry point so `app/__init__.py`
doesn't need to know about every individual page module.
"""

from __future__ import annotations

from flask import Flask, jsonify


def register_routes(app: Flask) -> None:
    @app.route("/health")
    def health():
        """Trivial route confirming the app boots correctly (T-029.4)."""
        return jsonify({"status": "ok", "message": "NBA Shot Quality Model app is running"})

    # Phase 6 (T-034-T-042): one blueprint per core page.
    from app.routes.explorer import bp as explorer_bp
    from app.routes.landing import bp as landing_bp
    from app.routes.leaderboard import bp as leaderboard_bp
    from app.routes.methodology import bp as methodology_bp
    from app.routes.player import bp as player_bp

    app.register_blueprint(landing_bp)
    app.register_blueprint(explorer_bp)
    app.register_blueprint(leaderboard_bp)
    app.register_blueprint(player_bp)
    app.register_blueprint(methodology_bp)
