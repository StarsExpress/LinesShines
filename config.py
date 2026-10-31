"""All configurations."""

import os
from datetime import date
from enum import Enum

NFL_BASE_PATH = os.path.dirname(os.path.abspath(__file__))
DATA_FOLDER_PATH = os.path.join(NFL_BASE_PATH, "data")
# Each league keeps its files in its own subfolder:
# data/{nfl,ncaaf}/{front_7_pass_rush,ol_pass_block}/.
# DATA_FOLDER_PATH stays the root of all data.
NFL_DATA_PATH = os.path.join(DATA_FOLDER_PATH, "nfl")
NCAAF_DATA_PATH = os.path.join(DATA_FOLDER_PATH, "ncaaf")


class League(str, Enum):
    """The leagues the data pipeline knows. The value is the data folder name."""

    NFL = "nfl"
    NCAAF = "ncaaf"


class CareerStatus(str, Enum):
    """Who is on the college Career page. The value is what the table stores and the page shows."""

    JOINED_NFL = "Joined NFL"
    POTENTIAL_DRAFTEES = "Potential Draftees"


LEAGUE_DATA_PATHS: dict[League, str] = {
    League.NFL: NFL_DATA_PATH,
    League.NCAAF: NCAAF_DATA_PATH,
}


ROUNDING_DECIMALS = 3  # Better precision alleviates overlaps in plots.
DISPLAY_DECIMALS = 1  # For UI displays only.


FRONT_7_NAMES = {"DI": "Defensive Interior", "ED": "Edge", "LB": "Linebacker"}
OL_NAMES = {"T": "Offensive Tackles", "G": "Guards", "C": "Centers"}


HAVOC_RATE_NOTE = "Havoc Rate = (Sacks + QB Hits) / Pass Rush Opportunities."
ALLOWED_HAVOC_RATE_NOTE = (
    "Allowed Havoc Rate = (Sacks + QB Hits) / Non Spike Pass Block Snaps."
)

PRP_NOTE = "PRP = (Sacks + 0.5 x (QB Hits + Hurries)) / Pass Rush Opportunities x 100."
PASS_COV_PERCENT_NOTE = "Pass Cov Percent = 100 - Pass Rush Percent, where Pass Rush Percent = Pass Rush Snaps / Pass Play Snaps x 100."
PBE_NOTE = "PBE = 100 - (Sacks + 0.5 x (QB Hits + Hurries)) / Non Spike Pass Block Snaps x 100."

# Shared across every "TPS "-prefixed metric — not a per-metric formula, so
# it lives once here rather than duplicated into a TPS_*_NOTE per metric.
# The frontend appends this to whatever a TPS metric's own note/formula
# already says, keyed off the "TPS " prefix rather than a per-metric flag
# (see main.py's /api/metadata: exposed once at the top level, not per metric).
TPS_NOTE = (
    "True Pass Set: excludes plays with less than 4 rushers, play action, "
    "screens, short dropbacks and time-to-throws under 2 seconds."
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
        "pass_rush": 95,  # Min PR Opp for pass rush filter.
        "pass_block": 105,  # Min Non Spike PB Snaps for pass block filter.
    },
}


# NCAAF thresholds. The NFL values do not fit: the NFL's 230 pass rush opportunities
# lets only 12 to 17% of the college ED and DI players through (about 36% in the NFL),
# so the college value is about 140; the NFL's 300 pass block snaps already fits the OL.
# Starting values, confirmed by trying the real page; change them if they feel wrong.
NCAAF_DEFAULT_THRESHOLDS: dict[str, int] = {
    "pass_rush": 230,  # Min PR Opp for pass rush filter.
    "pass_block": 360,  # Min Non Spike PB Snaps for pass block filter.
}

# Set BY HAND each week, like the NFL ones above. The 2026 entry is a placeholder
# of about 2/3 of the static values (a college season has about 12 games).
NCAAF_DYNAMIC_THRESHOLDS: dict[int, dict[str, int]] = {
    2026: {
        "pass_rush": 120,  # Min PR Opp for pass rush filter.
        "pass_block": 205,  # Min Non Spike PB Snaps for pass block filter.
    },
}

LEAGUE_DEFAULT_THRESHOLDS: dict[League, dict[str, int]] = {
    League.NFL: DEFAULT_THRESHOLDS,
    League.NCAAF: NCAAF_DEFAULT_THRESHOLDS,
}

LEAGUE_DYNAMIC_THRESHOLDS: dict[League, dict[int, dict[str, int]]] = {
    League.NFL: DYNAMIC_THRESHOLDS,
    League.NCAAF: NCAAF_DYNAMIC_THRESHOLDS,
}


def resolve_default_threshold(
    category: str,
    season: int,
    league: League = League.NFL,
    *,
    today: date | None = None
) -> int:
    """Static preset for a finalized season, dynamic preset for the season
    currently in progress. Routing is a Calendar Year comparison
    (season_year vs. today's year), not schedule-aware.
    Regular season is ~90% complete before New Year's Day, so this is an accepted
    near-100%-accurate approximation. No need to be perfectly precise.
    """
    current_year = (today or date.today()).year

    if season == current_year:
        dynamic = LEAGUE_DYNAMIC_THRESHOLDS[league].get(season, {})
        if category in dynamic:
            return dynamic[category]

    return LEAGUE_DEFAULT_THRESHOLDS[league][category]
