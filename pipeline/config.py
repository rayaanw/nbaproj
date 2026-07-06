"""Central configuration for the offline data/ML pipeline.

Every pipeline script imports constants from here instead of hardcoding
season strings, thresholds, or file paths. Change values in exactly one
place when the project's scope needs to shift.
"""

from pathlib import Path

# --- Season scope -----------------------------------------------------------
# Train on the two older seasons, test on the most recent (chronological
# split — see CLAUDE.md "Key Architectural Decisions"). Update these three
# strings when rolling the window forward to a new season.
TRAIN_SEASONS = ["2022-23", "2023-24"]
TEST_SEASON = "2024-25"
ALL_SEASONS = [*TRAIN_SEASONS, TEST_SEASON]

# --- Inclusion / qualification thresholds -----------------------------------
# Minimum total field goal attempts (across the 3-season window) for a player
# to be included in the pulled/modeled dataset at all.
MIN_PLAYER_ATTEMPTS = 50

# Minimum attempts (per season, or in the 3-year combined view) for a player
# to be shown on the Leaderboard.
LEADERBOARD_MIN_ATTEMPTS = 250

# --- Filesystem paths ---------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
MODELS_DIR = PROJECT_ROOT / "models"
DB_DIR = PROJECT_ROOT / "db"

SHOTS_RAW_DIR = DATA_RAW_DIR / "shots"
PLAYBYPLAY_RAW_DIR = DATA_RAW_DIR / "playbyplay"
DEFENDER_PRIORS_RAW_DIR = DATA_RAW_DIR / "defender_priors"

PLAYERS_REFERENCE_PATH = DATA_RAW_DIR / "players_reference.parquet"
RAW_MANIFEST_PATH = DATA_RAW_DIR / "manifest.json"

DB_PATH = DB_DIR / "nba_shot_quality.sqlite3"
SCHEMA_PATH = DB_DIR / "schema.sql"

# --- nba_api request politeness ---------------------------------------------
# stats.nba.com rate-limits aggressively; these constants keep pulls slow and
# resumable rather than fast and blocked.
REQUEST_DELAY_SECONDS = 0.75
MAX_RETRIES = 5
