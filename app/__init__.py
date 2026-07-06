"""T-029: Flask application factory.

`create_app()` is the single entry point used by both the dev server
(app/run.py) and any production WSGI server (gunicorn, T-047).
"""

from __future__ import annotations

from flask import Flask

from app.config import Config


def create_app(config_class: type = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    from app.routes import register_routes

    register_routes(app)

    return app
