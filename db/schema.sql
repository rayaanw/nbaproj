-- T-024: SQLite schema for the NBA Shot Quality Model & Dashboard.
--
-- This is the canonical definition of every table the Flask app queries.
-- The app is read-only at runtime (see CLAUDE.md) — this file is only ever
-- run by pipeline/12_load_db.py to (re)create the database from scratch.

PRAGMA foreign_keys = ON;

-- One row per unique player. Team affiliation is per-season (a player can
-- change teams), so it lives in player_teams instead of a column here.
CREATE TABLE IF NOT EXISTS players (
    player_id       INTEGER PRIMARY KEY,
    name            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS player_teams (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id           INTEGER NOT NULL REFERENCES players(player_id),
    season              TEXT NOT NULL,
    team_id             INTEGER NOT NULL,
    team_abbreviation   TEXT NOT NULL,
    UNIQUE (player_id, season, team_id)
);

-- Per-shot features + outcome + predicted xfg_pct. This is the table every
-- other page (Explorer, Player, Leaderboard-by-drilldown) ultimately reads
-- shot-level detail from.
CREATE TABLE IF NOT EXISTS shots (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id                     TEXT NOT NULL,
    game_event_id               INTEGER NOT NULL,
    player_id                   INTEGER NOT NULL REFERENCES players(player_id),
    season                      TEXT NOT NULL,
    loc_x                       REAL NOT NULL,
    loc_y                       REAL NOT NULL,
    shot_distance               REAL NOT NULL,
    shot_zone_basic             TEXT,
    shot_zone_area              TEXT,
    action_type                 TEXT,
    period                      INTEGER NOT NULL,
    time_remaining_in_period    INTEGER,
    home_away                   TEXT,
    score_margin                REAL,
    shot_made_flag              INTEGER NOT NULL CHECK (shot_made_flag IN (0, 1)),
    xfg_pct                     REAL NOT NULL,
    UNIQUE (game_id, game_event_id, season)
);

CREATE INDEX IF NOT EXISTS idx_shots_player_id ON shots(player_id);
CREATE INDEX IF NOT EXISTS idx_shots_season ON shots(season);
CREATE INDEX IF NOT EXISTS idx_shots_player_season ON shots(player_id, season);

-- Model evaluation headline numbers (log loss, AUC, Brier score) for both
-- the tuned model and the naive baseline, so the Methodology page can show
-- them side by side.
CREATE TABLE IF NOT EXISTS model_metrics (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    context      TEXT NOT NULL,  -- 'model' or 'baseline'
    metric_name  TEXT NOT NULL,  -- 'log_loss', 'auc', 'brier_score', ...
    value        REAL,
    UNIQUE (context, metric_name)
);

CREATE TABLE IF NOT EXISTS feature_importance (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    feature_name TEXT NOT NULL UNIQUE,
    importance   REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS calibration_bins (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    bin_low             REAL NOT NULL,
    bin_high            REAL NOT NULL,
    predicted_midpoint  REAL NOT NULL,
    actual_rate         REAL NOT NULL,
    sample_count        INTEGER NOT NULL
);

-- Pre-aggregated per-player, per-season (or "career" = 3-year combined)
-- actual vs. expected FG%, so the Leaderboard page is a fast direct query
-- instead of aggregating thousands of shot rows on every page load.
CREATE TABLE IF NOT EXISTS leaderboard (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id           INTEGER NOT NULL REFERENCES players(player_id),
    season_or_career     TEXT NOT NULL,  -- a season string, or the literal 'career'
    attempts            INTEGER NOT NULL,
    actual_fg_pct        REAL NOT NULL,
    expected_fg_pct      REAL NOT NULL,
    skill_differential   REAL NOT NULL,  -- actual - expected
    qualified            INTEGER NOT NULL CHECK (qualified IN (0, 1)),
    UNIQUE (player_id, season_or_career)
);

CREATE INDEX IF NOT EXISTS idx_leaderboard_season ON leaderboard(season_or_career);
CREATE INDEX IF NOT EXISTS idx_leaderboard_qualified ON leaderboard(season_or_career, qualified);
