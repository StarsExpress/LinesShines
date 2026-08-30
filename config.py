"""All configurations."""

import os
from datetime import date

NFL_BASE_PATH = os.path.dirname(os.path.abspath(__file__))
DATA_FOLDER_PATH = os.path.join(NFL_BASE_PATH, "data")

ROUNDING_DECIMALS = 3  # Better precision alleviates overlaps in plots.
DISPLAY_DECIMALS = 1  # For UI displays only.

FRONT_7_NAMES = {"DI": "Defensive Interior", "ED": "Edge", "LB": "Linebacker"}
OL_NAMES = {"T": "Offensive Tackles", "G": "Guards", "C": "Centers"}

HAVOC_RATE_NOTE = "Havoc Rate = (Sacks + QB Hits) / Pass Rush Opportunities."
ALLOWED_HAVOC_RATE_NOTE = (
    "Allowed Havoc Rate = (Sacks + QB Hits) / Non Spike Pass Block Snaps."
)

# Default "historical seasons'" thresholds applied on page load.
DEFAULT_THRESHOLDS: dict[str, int] = {
    "pass_rush": 230,  # Min PR Opp for pass rush filter.
    "pass_block": 300,  # Min Non Spike PB Snaps for pass block filter.
}

# Dynamic threshold for the current season in progress.
# Set thresholds BY HAND each week during data ingestion.
# Eyeballed against how far the season has actually progressed.

# Deliberately NOT derived from a fraction-of-season-elapsed formula.
# Because season pacing is not uniform. But — the final end is quite stable throughout years.
# Hereby, we use static thresholds for already ended seasons.

# Add/edit current year's entry weekly; once a season ends, leave it in place.
# With a season's end, resolve_default_threshold() falls back to static
# DEFAULT_THRESHOLDS automatically after entering next following calendar year.
# Key, which means current season, must be "renamed" when a new season comes.
DYNAMIC_THRESHOLDS: dict[int, dict[str, int]] = {
    2026: {
        "pass_rush": 20,  # Min PR Opp for pass rush filter.
        "pass_block": 30,  # Min Non Spike PB Snaps for pass block filter.
    },
}


def resolve_default_threshold(
    category: str, season: int, *, today: date | None = None
) -> int:
    """Static preset for a finalized season, dynamic preset for the season
    currently in progress. Routing is a Calendar Year comparison
    (season_year vs. today's year), not schedule-aware.
    Regular season is ~90% complete before New Year's Day, so this is an accepted
    near-100%-accurate approximation. No need to be perfectly precise.
    """
    current_year = (today or date.today()).year

    if season == current_year:
        dynamic = DYNAMIC_THRESHOLDS.get(season, {})
        if category in dynamic:
            return dynamic[category]

    return DEFAULT_THRESHOLDS[category]
