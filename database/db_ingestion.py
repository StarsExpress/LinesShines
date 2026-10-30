"""Ingest preprocessed PFF Excel workbooks into database.

Reads `nfl/front_7_pass_rush/{season}.xlsx` and
`nfl/ol_pass_block/{season}.xlsx` files (under the data root) that
`preprocessing/front_7.py` and `preprocessing/offensive_line.py` already
produce, and bulk-inserts them into the `nfl_pass_rush_stats` /
`nfl_pass_block_stats` tables.

Strict: a sheet that lacks any column the tables need, or a row without a
`Player Id`, stops the run with an error instead of loading NULLs.

Idempotent: rerunning for same season/position first deletes existing
rows for that slice, then bulk-inserts fresh ones — cleaner than
per-row upsert and dialect-agnostic (works on both SQLite and Postgres).

Usage:
1. Must always go from project root.
2. After running two preprocessing scripts.
3. python -m database.db_ingestion

For Railway, set DATABASE_URL to Postgres URL Railway assigns.
Point LINESHINES_REPO_ROOT at LinesShines project root so scripts can
locate xlsx files under $LINESHINES_REPO_ROOT/data/nfl/.
"""

from __future__ import annotations
import argparse
import os
from dataclasses import dataclass
import re
import sys
from datetime import date
from pathlib import Path
import pandas as pd
from sqlalchemy import delete
from sqlalchemy.orm import Session
from config import DYNAMIC_THRESHOLDS
from database.columns import (
    PASS_BLOCK_DATA_COLUMNS,
    PASS_RUSH_DATA_COLUMNS,
    required_excel_headers,
)
from database.db_models import Base, NFLPassBlockStat, NFLPassRushStat, NFLTeam
from database.session import engine, SessionLocal
from teams.nfl import TEAMS

FRONT_7_POSITIONS = ("DI", "ED", "LB")
OL_POSITIONS = ("T", "G", "C")

# The data root holds one folder per league; the NFL files are under data/nfl/.
NFL_SUBDIR = "nfl"

SEASON_CATEGORY_DIRS = ("front_7_pass_rush", "ol_pass_block")


def _find_project_root() -> Path:
    """Walk up from this file until we find a marker that identifies project root."""
    here = Path(__file__).resolve().parent
    for candidate in [here, *here.parents]:
        if (candidate / ".gitignore").exists():
            return candidate  # Root is found.

    raise RuntimeError("could not locate project root from " + str(here))


def _repo_root() -> Path:
    """The data root: the folder that holds `nfl/` (and later `ncaaf/`).

    Order of precedence:
      1. `--data-dir` CLI flag.
      2. `LINESHINES_DATA_DIR` env var.
      3. `LINESHINES_REPO_ROOT/data`.
      4. `../LinesShines/data` (sibling checkout convention).
    """
    env_data = os.environ.get("LINESHINES_DATA_DIR")
    if env_data:
        return Path(env_data)

    env_root = os.environ.get("LINESHINES_REPO_ROOT")
    if env_root:
        return Path(env_root) / "data"

    return _find_project_root() / "data"


def _discover_seasons(data_dir: Path) -> list[int]:
    """Union of seasons with a `{season}.xlsx` file under either category
    subdir (`front_7_pass_rush`, `ol_pass_block`) of `data_dir/nfl`.

    Union, not intersection — OL and DL are independent categories with no
    joint table, so it's fine for one to have a season's file before the other does.

    Only `.xlsx` files with a clean 4-digit-year stem count.
    `.csv` (raw/intermediate) and any malformed filename are skipped rather than error raising.

    A missing category subdir just yields no matches.
    """
    seasons = set()

    for category_dir in SEASON_CATEGORY_DIRS:
        for path in (data_dir / NFL_SUBDIR / category_dir).glob("*.xlsx"):
            if re.fullmatch(r"\d{4}", path.stem):
                seasons.add(int(path.stem))

    return list(seasons)


DEFAULT_SEASONS = _discover_seasons(_repo_root())


def _safe_int(val):
    return None if pd.isna(val) else int(val)


def _safe_float(val):
    return None if pd.isna(val) else float(val)


def _complement(val):
    """Pass Cov Percent = 100 - Pass Rush Percent (the source file holds the latter)."""
    return None if pd.isna(val) else round(100.0 - float(val), 10)


def _player_id(row, path, sheet) -> int:
    val = row.get("Player Id")
    if pd.isna(val):
        raise ValueError(
            f"{path} sheet {sheet}: row for {row.get('Player')!r} has no Player Id"
        )

    return int(val)


def _require_columns(df: pd.DataFrame, columns, path, sheet) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"{path} sheet {sheet} is missing columns: {missing}")


def upsert_teams(sess: Session) -> None:
    existing = {t.code for t in sess.query(NFLTeam).all()}

    for code, (full_name, color) in TEAMS.items():
        if code in existing:
            row = sess.get(NFLTeam, code)
            row.full_name = full_name
            row.primary_color = color

        else:
            sess.add(NFLTeam(code=code, full_name=full_name, primary_color=color))

    sess.commit()


def _read_value(kind: str, value):
    """Read one Excel cell the way its column's kind says."""
    if kind == "int":
        return _safe_int(value)

    if kind == "float":
        return _safe_float(value)

    if kind == "complement":
        return _complement(value)

    raise ValueError(f"unknown column kind: {kind!r}")


@dataclass(frozen=True)
class _Category:
    """Everything the ingestion needs to load one category into its table."""

    model: type
    folder: str
    positions: tuple[str, ...]
    data_columns: tuple
    snap_header: str  # The column a row must have a value in (dropna subset).
    skip_label: str  # Wording of the "file not found" line.
    row_label: str  # Wording of the per-position "N rows" line.


_PASS_RUSH = _Category(
    model=NFLPassRushStat,
    folder="front_7_pass_rush",
    positions=FRONT_7_POSITIONS,
    data_columns=PASS_RUSH_DATA_COLUMNS,
    snap_header="PR Opp",
    skip_label="pass rush",
    row_label="pass_rush",
)

_PASS_BLOCK = _Category(
    model=NFLPassBlockStat,
    folder="ol_pass_block",
    positions=OL_POSITIONS,
    data_columns=PASS_BLOCK_DATA_COLUMNS,
    snap_header="Non Spike PB Snaps",
    skip_label="pass block",
    row_label="pass_block",
)


def ingest_category(
    sess: Session, data_dir: Path, seasons: list[int], category: _Category
) -> int:
    """Load one category's seasons into its table, replacing each slice first.

    The body is shared by the two categories (and later the two leagues); the
    column reads come from the declaration in `database/columns.py`.
    """
    required = required_excel_headers(category.data_columns)
    total = 0

    for season in seasons:
        path = data_dir / NFL_SUBDIR / category.folder / f"{season}.xlsx"

        if not path.exists():
            print(f"Skip {category.skip_label} {season}: {path} not found")
            continue

        sheets = pd.read_excel(path, sheet_name=None)
        for position in category.positions:
            position_df = sheets.get(position)
            if position_df is None or position_df.empty:
                continue

            _require_columns(position_df, required, path, position)
            position_df.dropna(subset=[category.snap_header], inplace=True)

            # Wipe slice before re-insertion.
            sess.execute(
                delete(category.model).where(
                    category.model.season == season,
                    category.model.position == position,
                )
            )

            rows = []
            for _, row in position_df.iterrows():
                values = {
                    "season": season,
                    "position": position,
                    "team_code": row["Team"],
                    "player_id": _player_id(row, path, position),
                    "player": row["Player"],
                    "abbr_name": row["Abbr Name"],
                }
                for column in category.data_columns:
                    values[column.attr] = _read_value(
                        column.kind, row.get(column.excel_header)
                    )

                rows.append(category.model(**values))

            sess.add_all(rows)
            total += len(rows)
            print(f"  {category.row_label} {season} {position}: {len(rows)} rows")

    sess.commit()
    return total


def ingest_pass_rush(sess: Session, data_dir: Path, seasons: list[int]) -> int:
    return ingest_category(sess, data_dir, seasons, _PASS_RUSH)


def ingest_pass_block(sess: Session, data_dir: Path, seasons: list[int]) -> int:
    return ingest_category(sess, data_dir, seasons, _PASS_BLOCK)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])

    parser.add_argument(
        "--seasons",
        type=int,
        nargs="+",
        default=DEFAULT_SEASONS,
        help=f"Seasons to ingest (default: {DEFAULT_SEASONS})",
    )

    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override where to look for the *.xlsx files.",
    )

    args = parser.parse_args()

    data_dir = args.data_dir or _repo_root()
    if not data_dir.exists():
        print(f"Data directory not found: {data_dir}", file=sys.stderr)
        print(
            "Set --data-dir or LINESHINES_DATA_DIR/LINESHINES_REPO_ROOT env var",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Reading xlsx from: {data_dir}")

    Base.metadata.create_all(engine)
    with SessionLocal() as sess:
        upsert_teams(sess)
        pass_rush_rows = ingest_pass_rush(sess, data_dir, args.seasons)
        pass_block_rows = ingest_pass_block(sess, data_dir, args.seasons)

    print(
        f"\nBulk-inserted {pass_rush_rows} pass-rush rows and {pass_block_rows} pass-block rows."
    )

    # In-progress season's threshold is hand-eyeballed weekly, not
    # auto-computed (see config.py's DYNAMIC_THRESHOLDS).
    # Nudge rather than silently falling back if this week's ingestion covers
    # the current season and nobody's touched it yet.
    current_year = date.today().year
    if current_year in args.seasons and current_year not in DYNAMIC_THRESHOLDS:
        print(
            f"Reminder: {current_year} has no entry in config.DYNAMIC_THRESHOLDS yet — "
            "falling back to the static default thresholds until you set one."
        )


if __name__ == "__main__":
    main()
