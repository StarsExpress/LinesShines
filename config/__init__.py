"""All configurations, split by what they describe.

- `leagues`: the leagues, who is on the college Career page, and the data paths.
- `metrics`: position names, rounding, and the notes that explain each metric.
- `thresholds`: the default thresholds per league and the rule that picks one.

Every name is re-exported here, so code writes `from config import League` and does
not care which file defines it.
"""

from config.leagues import (
    BASE_PATH,
    DATA_FOLDER_PATH,
    LEAGUE_DATA_PATHS,
    NCAAF_DATA_PATH,
    NFL_DATA_PATH,
    CareerStatus,
    League,
)
from config.metrics import (
    ALLOWED_HAVOC_RATE_NOTE,
    DISPLAY_DECIMALS,
    FRONT_7_NAMES,
    HAVOC_RATE_NOTE,
    OL_NAMES,
    PASS_COV_PERCENT_NOTE,
    PBE_NOTE,
    PRP_NOTE,
    ROUNDING_DECIMALS,
    TPS_NOTE,
)
from config.thresholds import (
    DEFAULT_THRESHOLDS,
    DYNAMIC_THRESHOLDS,
    LEAGUE_DEFAULT_THRESHOLDS,
    LEAGUE_DYNAMIC_THRESHOLDS,
    NCAAF_DEFAULT_THRESHOLDS,
    NCAAF_DYNAMIC_THRESHOLDS,
    resolve_default_threshold,
)

__all__ = [
    "ALLOWED_HAVOC_RATE_NOTE",
    "BASE_PATH",
    "DATA_FOLDER_PATH",
    "DEFAULT_THRESHOLDS",
    "DISPLAY_DECIMALS",
    "DYNAMIC_THRESHOLDS",
    "FRONT_7_NAMES",
    "HAVOC_RATE_NOTE",
    "LEAGUE_DATA_PATHS",
    "LEAGUE_DEFAULT_THRESHOLDS",
    "LEAGUE_DYNAMIC_THRESHOLDS",
    "NCAAF_DATA_PATH",
    "NCAAF_DEFAULT_THRESHOLDS",
    "NCAAF_DYNAMIC_THRESHOLDS",
    "NFL_DATA_PATH",
    "OL_NAMES",
    "PASS_COV_PERCENT_NOTE",
    "PBE_NOTE",
    "PRP_NOTE",
    "ROUNDING_DECIMALS",
    "TPS_NOTE",
    "CareerStatus",
    "League",
    "resolve_default_threshold",
]
