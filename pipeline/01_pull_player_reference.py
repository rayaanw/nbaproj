"""T-004: Build the player/season reference table.

Determines which players qualify for the rest of the pipeline (>= MIN_PLAYER_ATTEMPTS
total field goal attempts across the 3-season window) and which team(s) they played
for in each season, so later pulls (T-005, T-006) are scoped and don't waste calls on
players with negligible sample size.

Usage:
    python pipeline/01_pull_player_reference.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nba_api.stats.endpoints import leaguedashplayerstats

from pipeline.config import ALL_SEASONS, MIN_PLAYER_ATTEMPTS, PLAYERS_REFERENCE_PATH
from pipeline.utils import call_with_retry


def pull_season_player_stats(season: str) -> pd.DataFrame:
    """Fetch per-player totals (incl. FGA) for one season via leaguedashplayerstats."""

    def build():
        return leaguedashplayerstats.LeagueDashPlayerStats(
            season=season,
            season_type_all_star="Regular Season",
            per_mode_detailed="Totals",
        )

    endpoint = call_with_retry(build, description=f"leaguedashplayerstats({season})")
    df = endpoint.get_data_frames()[0]
    df["SEASON"] = season
    return df[["PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "TEAM_ABBREVIATION", "FGA", "SEASON"]]


def main() -> None:
    print(f"Pulling player reference for seasons: {ALL_SEASONS}")

    season_frames = []
    for season in ALL_SEASONS:
        print(f"  fetching {season} ...")
        season_frames.append(pull_season_player_stats(season))

    all_seasons_df = pd.concat(season_frames, ignore_index=True)
    total_players_seen = all_seasons_df["PLAYER_ID"].nunique()

    # T-004.2: aggregate total FGA per player across the 3-season window.
    attempts_by_player = (
        all_seasons_df.groupby(["PLAYER_ID", "PLAYER_NAME"])["FGA"].sum().reset_index()
    )

    # T-004.3: filter to players meeting MIN_PLAYER_ATTEMPTS.
    qualifying_ids = set(
        attempts_by_player.loc[attempts_by_player["FGA"] >= MIN_PLAYER_ATTEMPTS, "PLAYER_ID"]
    )
    qualified_df = all_seasons_df[all_seasons_df["PLAYER_ID"].isin(qualifying_ids)].copy()

    # Keep player id, name, and team id per season (players can change teams).
    reference_df = qualified_df[
        ["PLAYER_ID", "PLAYER_NAME", "SEASON", "TEAM_ID", "TEAM_ABBREVIATION"]
    ].drop_duplicates()

    # T-004.4: save the result.
    PLAYERS_REFERENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    reference_df.to_parquet(PLAYERS_REFERENCE_PATH, index=False)

    # T-004.5: log summary counts.
    print(f"Players seen across {len(ALL_SEASONS)} seasons: {total_players_seen}")
    print(f"Players meeting MIN_PLAYER_ATTEMPTS ({MIN_PLAYER_ATTEMPTS}): {len(qualifying_ids)}")
    print(f"Player/season rows saved: {len(reference_df)}")
    print(f"Saved to {PLAYERS_REFERENCE_PATH}")


if __name__ == "__main__":
    main()
