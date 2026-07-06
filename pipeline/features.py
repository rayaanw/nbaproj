"""Pure feature-engineering functions shared across the T-010–T-014 scripts.

Kept separate from the numbered pipeline scripts so the transformation logic
itself is easy to unit test without needing any files on disk.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Shot-distance buckets, chosen to exactly match the SHOT_DIST_RANGES filter
# values used when pulling the defender-distance prior (see
# pipeline/04_pull_defender_distance_priors.py) so the T-013 join lines up
# without any relabeling.
SHOT_DISTANCE_BUCKETS = [
    "Less Than 5 ft.",
    "5-9 ft.",
    "10-14 ft.",
    "15-19 ft.",
    "20-24 ft.",
    "25-29 ft.",
    ">= 30 ft.",
]

# Upper bound (inclusive) of each bucket in the same order as
# SHOT_DISTANCE_BUCKETS, aligned to the >= 30 ft. tier
_BUCKET_UPPER_BOUNDS = [5, 10, 15, 20, 25, 30]

HEAVE_DISTANCE_THRESHOLD_FT = 40


def compute_shot_angle_degrees(loc_x: pd.Series, loc_y: pd.Series) -> pd.Series:
    """T-010.1: shot angle from the basket, in degrees, 0deg = straight-on.

    NBA shot-chart coordinates place the basket at approximately (0, 0), with
    LOC_X the left/right offset and LOC_Y the distance in front of the hoop
    (in tenths of a foot). atan2(LOC_X, LOC_Y) gives the angle off the
    straight-on axis (LOC_X = 0); we take the absolute value since the court
    is left/right symmetric for shot difficulty purposes.
    """
    angle_rad = np.arctan2(loc_x.astype(float), loc_y.astype(float))
    return np.degrees(angle_rad).abs()


def bucket_shot_distance(shot_distance_ft: pd.Series) -> pd.Series:
    """T-010.2: bucket SHOT_DISTANCE (feet) into the same ranges used by the
    defender-distance prior pull, so shots can be joined to a league-average
    FG% prior by bucket in T-013.
    """
    return pd.cut(
        shot_distance_ft.astype(float),
        bins=[-np.inf, *_BUCKET_UPPER_BOUNDS, np.inf],
        labels=SHOT_DISTANCE_BUCKETS,
        right=False,
    ).astype(str)


def flag_heaves(shot_distance_ft: pd.Series) -> pd.Series:
    """T-010.3: flag shots beyond a reasonable max distance as heaves, to be
    excluded from training (not from the raw dataset itself).
    """
    return shot_distance_ft.astype(float) > HEAVE_DISTANCE_THRESHOLD_FT


def compute_time_remaining_seconds(minutes_remaining: pd.Series, seconds_remaining: pd.Series) -> pd.Series:
    """T-012.1: time remaining in the period, in seconds."""
    return minutes_remaining.astype(int) * 60 + seconds_remaining.astype(int)


def encode_period(period: pd.Series) -> pd.DataFrame:
    """T-012.3: clean integer period plus an overtime flag (periods 5+)."""
    period_clean = period.astype(int)
    return pd.DataFrame({"period_clean": period_clean, "is_overtime": period_clean > 4})


TARGET_COLUMN = "SHOT_MADE_FLAG"

# Columns present in features_final.parquet that are NOT model inputs:
# identifiers/metadata (no predictive meaning, or would leak the shot's
# identity), raw text fields superseded by an engineered/one-hot version,
# and the prediction target itself.
#
# PLAYER_ID is deliberately excluded — the model predicts shot difficulty
# independent of who took the shot (see PRD "Core concept"); comparing a
# player's actual FG% to their aggregated xFG% is exactly what isolates
# shooting skill, which only works if the model itself never sees player
# identity.
NON_FEATURE_COLUMNS = {
    "GAME_ID",
    "GAME_EVENT_ID",
    "PLAYER_ID",
    "TEAM_ID",
    "TEAM_NAME",
    "GAME_DATE",
    "HTM",
    "VTM",
    "SEASON",
    "EVENT_TYPE",
    "SHOT_TYPE",
    "SHOT_ATTEMPTED_FLAG",
    "is_heave",  # already filtered out of features_final.parquet; not a model input
    "shot_distance_bucket",  # only needed to join the defender-distance prior; SHOT_DISTANCE (continuous) is the modeling feature
    TARGET_COLUMN,
}


def get_feature_columns(df: pd.DataFrame) -> list[str]:
    """The single shared definition of "which columns are model inputs",
    used by training (T-017), evaluation (T-019), and scoring (T-023) so
    train-time and predict-time feature sets can never silently drift apart.
    """
    return [c for c in df.columns if c not in NON_FEATURE_COLUMNS]
