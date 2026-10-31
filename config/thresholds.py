"""The default thresholds per league, and the rule that picks one for a season."""

from datetime import date
from config.leagues import League

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


# NCAAF thresholds, their own because the NFL values left too many or too few players on
# the college chart: the front 7 uses the same 230 as the NFL, the OL a stricter 360.
# Set by the owner after trying the real page; change them if they feel wrong.
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
