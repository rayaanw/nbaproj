"""T-031: Flask app configuration.

Keeps environment-specific config (DB path, debug flag) out of hardcoded
values, loaded via python-dotenv so local development and the eventual
Render deployment (T-047) both work from the same config class.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.config import DB_PATH as PIPELINE_DB_PATH  # single source of truth for the DB path

# Load app/.env if present (never required — see .env.example; there are no
# secrets in this project, just DB_PATH/DEBUG overrides for local dev).
load_dotenv(PROJECT_ROOT / "app" / ".env")


class Config:
    DB_PATH = os.environ.get("DB_PATH", str(PIPELINE_DB_PATH))
    DEBUG = os.environ.get("DEBUG", "false").lower() in ("1", "true", "yes")
