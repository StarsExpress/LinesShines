"""All configurations."""

import os

NFL_BASE_PATH = os.path.dirname(os.path.abspath(__file__))

DATA_FOLDER_PATH = os.path.join(NFL_BASE_PATH, "data")

LOGOS_FOLDER_PATH = os.path.join(NFL_BASE_PATH, "logos")
LOGOS_PICKLE_PATH = os.path.join(NFL_BASE_PATH, "teams_logos.pkl")

OUTPUTS_FOLDER_PATH = os.path.join(NFL_BASE_PATH, "outputs")


TEAMS = [
    "ARZ",
    "ATL",
    "BLT",
    "BUF",
    "CAR",
    "CHI",
    "CIN",
    "CLV",
    "DAL",
    "DEN",
    "DET",
    "GB",
    "HST",
    "IND",
    "JAX",
    "KC",
    "LA",
    "LAC",
    "LV",
    "MIA",
    "MIN",
    "NE",
    "NO",
    "NYG",
    "NYJ",
    "PHI",
    "PIT",
    "SEA",
    "SF",
    "TB",
    "TEN",
    "WAS",
]


FRONT_7_NAMES = {"DI": "Defensive Interior", "ED": "Edge", "LB": "Linebacker"}
OL_NAMES = {"T": "Offensive Tackles", "G": "Guards", "C": "Centers"}

ROUNDING_DIGITS = 1

HAVOC_NOTE = "Havoc = Sacks + QB Hits."
HAVOC_RATE_NOTE = "Havoc Rate = (Sacks + QB Hits) / Pass Rush Opportunities."
ALLOWED_HAVOC_RATE_NOTE = "Allowed Havoc Rate = (Sacks + QB Hits) / Non Spike Pass Block Snaps."
