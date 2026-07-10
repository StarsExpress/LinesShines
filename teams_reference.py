"""Shared reference data for the 32 NFL teams.

Kept in one place so `seed_sample_data.py` and `ingest_to_db.py` don't
drift from each other, and so `main.py`'s /api/metadata payload can serve
these values to the frontend (rather than the frontend hard-coding them,
which was the case in the earlier static-JSON version).
"""

# Team code → (full name, primary brand color hex).
# Codes match the abbreviations used by the LinesShines repo's PFF
# exports and /logos/ folder (e.g. ARZ, BLT, CLV, HST — PFF's spellings).
TEAMS: dict[str, tuple[str, str]] = {
    "ARZ": ("Arizona Cardinals", "#97233F"),
    "ATL": ("Atlanta Falcons", "#A71930"),
    "BLT": ("Baltimore Ravens", "#241773"),
    "BUF": ("Buffalo Bills", "#00338D"),
    "CAR": ("Carolina Panthers", "#0085CA"),
    "CHI": ("Chicago Bears", "#0B162A"),
    "CIN": ("Cincinnati Bengals", "#FB4F14"),
    "CLV": ("Cleveland Browns", "#FF3C00"),
    "DAL": ("Dallas Cowboys", "#041E42"),
    "DEN": ("Denver Broncos", "#FB4F14"),
    "DET": ("Detroit Lions", "#0076B6"),
    "GB":  ("Green Bay Packers", "#203731"),
    "HST": ("Houston Texans", "#03202F"),
    "IND": ("Indianapolis Colts", "#002C5F"),
    "JAX": ("Jacksonville Jaguars", "#006778"),
    "KC":  ("Kansas City Chiefs", "#E31837"),
    "LA":  ("Los Angeles Rams", "#003594"),
    "LAC": ("Los Angeles Chargers", "#0080C6"),
    "LV":  ("Las Vegas Raiders", "#A5ACAF"),
    "MIA": ("Miami Dolphins", "#008E97"),
    "MIN": ("Minnesota Vikings", "#4F2683"),
    "NE":  ("New England Patriots", "#002244"),
    "NO":  ("New Orleans Saints", "#D3BC8D"),
    "NYG": ("New York Giants", "#0B2265"),
    "NYJ": ("New York Jets", "#125740"),
    "PHI": ("Philadelphia Eagles", "#004C54"),
    "PIT": ("Pittsburgh Steelers", "#FFB612"),
    "SEA": ("Seattle Seahawks", "#69BE28"),
    "SF":  ("San Francisco 49ers", "#AA0000"),
    "TB":  ("Tampa Bay Buccaneers", "#D50A0A"),
    "TEN": ("Tennessee Titans", "#4B92DB"),
    "WAS": ("Washington Commanders", "#5A1414"),
}
