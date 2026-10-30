"""Preprocess CSV into Excel.

    python -m preprocessing.preprocess --league nfl --seasons 2026

Both arguments are required, so the wrong league is never processed by accident.
Several seasons go after one flag: --seasons 2022 2023 2024.
Also holds the helpers both category scripts share: file paths, the column check
and the league scope (the NCAAF conference column and its out-of-scope filter).
"""

import argparse
import os
import sys
import pandas as pd
from config import LEAGUE_DATA_PATHS, ROUNDING_DECIMALS, League
from teams.ncaaf import conference_of


def season_file_path(league: League, category: str, season: int, extension: str) -> str:
    """data/{league}/{category}/{season}.{extension}."""
    return os.path.join(LEAGUE_DATA_PATHS[league], category, f"{season}.{extension}")


def require_columns(
    df: pd.DataFrame, required: list[str], league: League, season: int
) -> None:
    """Fail with one clear error before any calculation if a column is missing."""
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(
            f"{league.value} {season}: the CSV lacks the columns {missing}; "
            "export it again with all columns."
        )


def apply_league_scope(df: pd.DataFrame, league: League, season: int) -> pd.DataFrame:
    """NCAAF: add the Conference column and drop the schools outside the scope.

    The NFL has no conference, so its rows come back untouched. A school the
    lookup does not know raises, naming the school and the season, so a new team
    in a PFF export is noticed instead of silently dropped.
    """
    if league is not League.NCAAF:
        return df

    require_columns(df, ["Team", "Franchise Id"], league, season)

    conference_by_franchise_id = dict()
    schools_df = df[["Franchise Id", "Team"]].drop_duplicates()
    for franchise_id, team in schools_df.itertuples(index=False):
        try:
            conference_by_franchise_id[franchise_id] = conference_of(
                int(franchise_id), season
            )

        except KeyError:
            raise ValueError(
                f"{league.value} {season}: unknown school {team} "
                f"(franchise_id {franchise_id}); add it to teams/ncaaf.py."
            ) from None

    scoped_df = df.copy()
    scoped_df["Conference"] = scoped_df["Franchise Id"].map(conference_by_franchise_id)

    return scoped_df[scoped_df["Conference"].notna()].copy()


def percent_of(numerator, denominator):
    """A rate as a rounded percentage: numerator / denominator, zero-filled, x100."""
    rate = numerator / denominator
    rate = rate.fillna(0)
    rate *= 100

    return rate.round(ROUNDING_DECIMALS)


def write_position_sheets(league, category, season, positional_sheets) -> None:
    """Write one sheet per position to the season's xlsx, in insertion order."""
    destination_path = season_file_path(league, category, season, "xlsx")

    with pd.ExcelWriter(destination_path, engine="openpyxl") as writer:
        for position, sheet in positional_sheets.items():
            sheet.to_excel(writer, sheet_name=position, index=False)


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0], allow_abbrev=False
    )
    parser.add_argument(
        "--league", required=True, choices=[league.value for league in League]
    )
    parser.add_argument("--seasons", required=True, type=int, nargs="+")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> list[str]:
    """Preprocess every requested CSV; an error in one is printed and the rest go on.

    Returns what failed, one "league season category: error" line each.
    """
    # Imported here: category scripts import helpers above from this module.
    from preprocessing.front_7 import preprocess_front_7
    from preprocessing.offensive_line import preprocess_offensive_line

    arguments = parse_arguments(argv)
    league = League(arguments.league)
    categories = {
        "front_7_pass_rush": preprocess_front_7,
        "ol_pass_block": preprocess_offensive_line,
    }

    failures = []
    for season in arguments.seasons:
        for category, preprocess in categories.items():
            try:
                preprocess(league, season)

            except Exception as error:
                failure = f"{league.value} {season} {category}: {type(error).__name__}: {error}"
                print(f"FAILED {failure}", file=sys.stderr)
                failures.append(failure)

    if failures:
        print(f"{len(failures)} CSV(s) failed:", file=sys.stderr)
        for failure in failures:
            print(f"{failure}", file=sys.stderr)

    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
