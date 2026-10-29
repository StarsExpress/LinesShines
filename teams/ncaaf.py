"""Which conference every NCAAF school belonged to in each season.

PFF's college exports carry no conference column, so the conversion step looks
it up here by `franchise_id` (stable, one-to-one with the team name) and season.
Only the six scoped conferences and Notre Dame are listed in `CONFERENCE_STINTS`;
the database keeps a row if and only if its school was in one of them that season.

Sources: ESPN "College football realignment: conference changes for 2026" and
Wikipedia "2010-2014 / 2021-2026 NCAA conference realignment". Design record:
`playbook/discussions/NCAAF-TEAM-LOGOS-AND-REALIGNMENT.md`.
"""

from __future__ import annotations
from typing import NamedTuple

SEC = "SEC"
B1G = "B1G"
ACC = "ACC"
BIG_12 = "Big 12"
PAC_12 = "Pac-12"
MAC = "MAC"
INDEPENDENT = "Independent"

SCOPED_CONFERENCES = (SEC, B1G, ACC, BIG_12, PAC_12, MAC, INDEPENDENT)

FIRST_SEASON_COVERED = 2014


class Stint(NamedTuple):
    """One stretch of consecutive seasons a school spent in one conference."""

    first_season: int
    last_season: int | None  # None: still there.
    conference: str


# franchise_id -> stints, in season order. A school can have several stints:.
# UMass was a MAC football member in 2014 and 2015, independent until 2024.
CONFERENCE_STINTS: dict[int, list[Stint]] = {
    # SEC.
    103: [Stint(2014, None, SEC)],  # Alabama.
    111: [Stint(2014, None, SEC)],  # Arkansas.
    115: [Stint(2014, None, SEC)],  # Auburn.
    163: [Stint(2014, None, SEC)],  # Florida.
    173: [Stint(2014, None, SEC)],  # Georgia.
    202: [Stint(2014, None, SEC)],  # Kentucky.
    211: [Stint(2014, None, SEC)],  # LSU.
    226: [Stint(2014, None, SEC)],  # Ole Miss.
    227: [Stint(2014, None, SEC)],  # Mississippi State.
    229: [Stint(2014, None, SEC)],  # Missouri.
    289: [Stint(2014, None, SEC)],  # South Carolina.
    307: [Stint(2014, None, SEC)],  # Tennessee.
    312: [Stint(2014, None, SEC)],  # Texas A&M.
    333: [Stint(2014, None, SEC)],  # Vanderbilt.
    261: [Stint(2014, 2023, BIG_12), Stint(2024, None, SEC)],  # Oklahoma.
    311: [Stint(2014, 2023, BIG_12), Stint(2024, None, SEC)],  # Texas.
    # Big Ten.
    187: [Stint(2014, None, B1G)],  # Illinois.
    190: [Stint(2014, None, B1G)],  # Indiana.
    192: [Stint(2014, None, B1G)],  # Iowa.
    215: [Stint(2014, None, B1G)],  # Maryland.
    222: [Stint(2014, None, B1G)],  # Michigan.
    223: [Stint(2014, None, B1G)],  # Michigan State.
    225: [Stint(2014, None, B1G)],  # Minnesota.
    238: [Stint(2014, None, B1G)],  # Nebraska.
    256: [Stint(2014, None, B1G)],  # Northwestern.
    260: [Stint(2014, None, B1G)],  # Ohio State.
    266: [Stint(2014, None, B1G)],  # Penn State.
    273: [Stint(2014, None, B1G)],  # Purdue.
    278: [Stint(2014, None, B1G)],  # Rutgers.
    349: [Stint(2014, None, B1G)],  # Wisconsin.
    264: [Stint(2014, 2023, PAC_12), Stint(2024, None, B1G)],  # Oregon.
    324: [Stint(2014, 2023, PAC_12), Stint(2024, None, B1G)],  # UCLA.
    326: [Stint(2014, 2023, PAC_12), Stint(2024, None, B1G)],  # USC.
    340: [Stint(2014, 2023, PAC_12), Stint(2024, None, B1G)],  # Washington.
    # ACC.
    121: [Stint(2014, None, ACC)],  # Boston College.
    140: [Stint(2014, None, ACC)],  # Clemson.
    154: [Stint(2014, None, ACC)],  # Duke.
    167: [Stint(2014, None, ACC)],  # Florida State.
    176: [Stint(2014, None, ACC)],  # Georgia Tech.
    210: [Stint(2014, None, ACC)],  # Louisville.
    220: [Stint(2014, None, ACC)],  # Miami (FL).
    245: [Stint(2014, None, ACC)],  # North Carolina.
    248: [Stint(2014, None, ACC)],  # NC State.
    268: [Stint(2014, None, ACC)],  # Pittsburgh.
    304: [Stint(2014, None, ACC)],  # Syracuse.
    335: [Stint(2014, None, ACC)],  # Virginia.
    337: [Stint(2014, None, ACC)],  # Virginia Tech.
    339: [Stint(2014, None, ACC)],  # Wake Forest.
    287: [Stint(2024, None, ACC)],  # SMU.
    130: [Stint(2014, 2023, PAC_12), Stint(2024, None, ACC)],  # California.
    300: [Stint(2014, 2023, PAC_12), Stint(2024, None, ACC)],  # Stanford.
    # Big 12.
    118: [Stint(2014, None, BIG_12)],  # Baylor.
    193: [Stint(2014, None, BIG_12)],  # Iowa State.
    198: [Stint(2014, None, BIG_12)],  # Kansas.
    199: [Stint(2014, None, BIG_12)],  # Kansas State.
    262: [Stint(2014, None, BIG_12)],  # Oklahoma State.
    305: [Stint(2014, None, BIG_12)],  # TCU.
    315: [Stint(2014, None, BIG_12)],  # Texas Tech.
    343: [Stint(2014, None, BIG_12)],  # West Virginia.
    128: [Stint(2023, None, BIG_12)],  # BYU.
    138: [Stint(2023, None, BIG_12)],  # Cincinnati.
    182: [Stint(2023, None, BIG_12)],  # Houston.
    323: [Stint(2023, None, BIG_12)],  # UCF.
    109: [Stint(2014, 2023, PAC_12), Stint(2024, None, BIG_12)],  # Arizona.
    110: [Stint(2014, 2023, PAC_12), Stint(2024, None, BIG_12)],  # Arizona State.
    143: [Stint(2014, 2023, PAC_12), Stint(2024, None, BIG_12)],  # Colorado.
    328: [Stint(2014, 2023, PAC_12), Stint(2024, None, BIG_12)],  # Utah.
    # Pac-12 (Oregon State and Washington State stayed after 2024 restructure).
    265: [Stint(2014, None, PAC_12)],  # Oregon State.
    341: [Stint(2014, None, PAC_12)],  # Washington State.
    120: [Stint(2026, None, PAC_12)],  # Boise State.
    144: [Stint(2026, None, PAC_12)],  # Colorado State.
    169: [Stint(2026, None, PAC_12)],  # Fresno State.
    284: [Stint(2026, None, PAC_12)],  # San Diego State.
    329: [Stint(2026, None, PAC_12)],  # Utah State.
    314: [Stint(2026, None, PAC_12)],  # Texas State.
    # MAC.
    102: [Stint(2014, None, MAC)],  # Akron.
    117: [Stint(2014, None, MAC)],  # Ball State.
    122: [Stint(2014, None, MAC)],  # Bowling Green.
    126: [Stint(2014, None, MAC)],  # Buffalo.
    134: [Stint(2014, None, MAC)],  # Central Michigan.
    160: [Stint(2014, None, MAC)],  # Eastern Michigan.
    201: [Stint(2014, None, MAC)],  # Kent State.
    221: [Stint(2014, None, MAC)],  # Miami (OH).
    259: [Stint(2014, None, MAC)],  # Ohio.
    316: [Stint(2014, None, MAC)],  # Toledo.
    347: [Stint(2014, None, MAC)],  # Western Michigan.
    254: [Stint(2014, 2025, MAC)],  # Northern Illinois, Mountain West from 2026.
    216: [Stint(2014, 2015, MAC), Stint(2025, None, MAC)],  # UMass.
    279: [Stint(2026, None, MAC)],  # Sacramento State.
    # Independent.
    258: [Stint(2014, None, INDEPENDENT)],  # Notre Dame.
}


# franchise_id -> the school's name as used on screen and to match ESPN's team list.
SCHOOL_NAMES: dict[int, str] = {
    103: "Alabama",
    111: "Arkansas",
    115: "Auburn",
    163: "Florida",
    173: "Georgia",
    202: "Kentucky",
    211: "LSU",
    226: "Ole Miss",
    227: "Mississippi State",
    229: "Missouri",
    289: "South Carolina",
    307: "Tennessee",
    312: "Texas A&M",
    333: "Vanderbilt",
    261: "Oklahoma",
    311: "Texas",
    187: "Illinois",
    190: "Indiana",
    192: "Iowa",
    215: "Maryland",
    222: "Michigan",
    223: "Michigan State",
    225: "Minnesota",
    238: "Nebraska",
    256: "Northwestern",
    260: "Ohio State",
    266: "Penn State",
    273: "Purdue",
    278: "Rutgers",
    349: "Wisconsin",
    264: "Oregon",
    324: "UCLA",
    326: "USC",
    340: "Washington",
    121: "Boston College",
    140: "Clemson",
    154: "Duke",
    167: "Florida State",
    176: "Georgia Tech",
    210: "Louisville",
    220: "Miami (FL)",
    245: "North Carolina",
    248: "NC State",
    268: "Pittsburgh",
    304: "Syracuse",
    335: "Virginia",
    337: "Virginia Tech",
    339: "Wake Forest",
    287: "SMU",
    130: "California",
    300: "Stanford",
    118: "Baylor",
    193: "Iowa State",
    198: "Kansas",
    199: "Kansas State",
    262: "Oklahoma State",
    305: "TCU",
    315: "Texas Tech",
    343: "West Virginia",
    128: "BYU",
    138: "Cincinnati",
    182: "Houston",
    323: "UCF",
    109: "Arizona",
    110: "Arizona State",
    143: "Colorado",
    328: "Utah",
    265: "Oregon State",
    341: "Washington State",
    120: "Boise State",
    144: "Colorado State",
    169: "Fresno State",
    284: "San Diego State",
    329: "Utah State",
    314: "Texas State",
    102: "Akron",
    117: "Ball State",
    122: "Bowling Green",
    126: "Buffalo",
    134: "Central Michigan",
    160: "Eastern Michigan",
    201: "Kent State",
    221: "Miami (OH)",
    259: "Ohio",
    316: "Toledo",
    347: "Western Michigan",
    254: "Northern Illinois",
    216: "UMass",
    279: "Sacramento State",
    258: "Notre Dame",
}

# Every other franchise_id found in the PFF exports of 2022 to 2026: deliberately.
# out of scope, dropped without a message. An id in neither dict is an error.
OUT_OF_SCOPE_FRANCHISE_IDS = frozenset(
    {
        101, 108, 113, 114, 136, 141, 146, 151, 156, 165, 166, 174, 175, 180, 196,
        197, 200, 206, 207, 208, 209, 214, 218, 224, 230, 237, 239, 241, 242, 250,
        251, 263, 275, 281, 285, 288, 296, 306, 318, 319, 320, 321, 325, 327, 330,
        331, 346, 351, 1177,
    }
)  # fmt: skip


def conference_of(franchise_id: int, season: int) -> str | None:
    """The conference a school played in that season, or None when out of scope.

    None covers a school that is never in scope and a scoped school in a season
    outside its stints (BYU in 2022). Raises KeyError for an unknown franchise_id,
    so a new team in a PFF export is noticed instead of silently dropped.
    """
    if franchise_id in OUT_OF_SCOPE_FRANCHISE_IDS:
        return None

    for stint in CONFERENCE_STINTS[franchise_id]:
        ends_after_season = stint.last_season is None or season <= stint.last_season
        if stint.first_season <= season and ends_after_season:
            return stint.conference

    return None


def scoped_franchise_ids(first_season: int, last_season: int) -> list[int]:
    """Franchise ids in scope in at least one season of the range, sorted."""
    return sorted(
        franchise_id
        for franchise_id in CONFERENCE_STINTS
        if any(
            conference_of(franchise_id, season) is not None
            for season in range(first_season, last_season + 1)
        )
    )
