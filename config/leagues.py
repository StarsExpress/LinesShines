"""The leagues, who is on the college Career page, and where the data lives."""

import os
from enum import Enum

# Repo root: this file sits one folder below it, in config/.
BASE_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FOLDER_PATH = os.path.join(BASE_PATH, "data")

# Each league keeps its files in its own subfolder:
# data/{nfl,ncaaf}/{front_7_pass_rush,ol_pass_block}/.
# DATA_FOLDER_PATH stays root of all data.
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
