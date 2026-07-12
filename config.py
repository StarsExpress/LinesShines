"""All configurations."""

import os

NFL_BASE_PATH = os.path.dirname(os.path.abspath(__file__))
DATA_FOLDER_PATH = os.path.join(NFL_BASE_PATH, "data")

ROUNDING_DIGITS = 1

HAVOC_RATE_NOTE = "Havoc Rate = (Sacks + QB Hits) / Pass Rush Opportunities."
ALLOWED_HAVOC_RATE_NOTE = (
    "Allowed Havoc Rate = (Sacks + QB Hits) / Non Spike Pass Block Snaps."
)

# Default thresholds applied on page load.
DEFAULT_THRESHOLDS = {
    "pass_rush": 230,  # Min PR Opp for pass rush filter.
    "pass_block": 300,  # Min Non Spike PB Snaps for pass block filter.
}
