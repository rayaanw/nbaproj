"""T-034: Landing page — brief project intro and links into the three core
features, per the PRD's app flow.
"""

from __future__ import annotations

from flask import Blueprint, render_template

bp = Blueprint("landing", __name__)


@bp.route("/")
def index():
    return render_template("landing.html", active_page="landing")
