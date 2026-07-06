"""T-044.2: NBA team primary colors, keyed by team abbreviation.

Used to tint the Player Page header with the player's (most recent) team
color, per the PRD's "team-colored accents" design requirement. Values are
each team's primary brand color.
"""

TEAM_COLORS = {
    "ATL": "#E03A3E",
    "BOS": "#007A33",
    "BKN": "#000000",
    "CHA": "#1D1160",
    "CHI": "#CE1141",
    "CLE": "#860038",
    "DAL": "#00538C",
    "DEN": "#0E2240",
    "DET": "#C8102E",
    "GSW": "#1D428A",
    "HOU": "#CE1141",
    "IND": "#002D62",
    "LAC": "#C8102E",
    "LAL": "#552583",
    "MEM": "#5D76A9",
    "MIA": "#98002E",
    "MIL": "#00471B",
    "MIN": "#0C2340",
    "NOP": "#0C2340",
    "NYK": "#006BB6",
    "OKC": "#007AC1",
    "ORL": "#0077C0",
    "PHI": "#006BB6",
    "PHX": "#1D1160",
    "POR": "#E03A3E",
    "SAC": "#5A2D81",
    "SAS": "#C4CED4",
    "TOR": "#CE1141",
    "UTA": "#002B5C",
    "WAS": "#002B5C",
}

DEFAULT_ACCENT = "#ff6b35"  # the app's default accent, for players with no resolvable team


def get_team_color(team_abbreviation: str | None) -> str:
    if not team_abbreviation:
        return DEFAULT_ACCENT
    return TEAM_COLORS.get(team_abbreviation, DEFAULT_ACCENT)
