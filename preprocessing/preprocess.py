"""Preprocess CSV into Excel.

    python -m preprocessing.preprocess --league nfl --seasons 2026

Both arguments are required, so the wrong league is never processed by accident.
Several seasons go after one flag: --seasons 2022 2023 2024.
Also holds the helpers both category scripts share: file paths and the column check.
"""

import argparse
import os
import sys
import pandas as pd
from config import LEAGUE_DATA_PATHS, League


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
