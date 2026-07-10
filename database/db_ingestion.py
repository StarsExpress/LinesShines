"""Ingest the preprocessed PFF Excel workbooks into the database.

Reads the `{season} NFL Front 7 Pass Rush.xlsx` and
`{season} NFL OL Pass Block.xlsx` files that
`preprocessing/front_7.py` and `preprocessing/offensive_line.py` already
produce, and upserts them into the `pass_rush_stats` / `pass_block_stats`
tables.

Idempotent: rerunning for the same season/position first deletes existing
rows for that slice, then bulk-inserts fresh ones — cleaner than
per-row upsert and dialect-agnostic (works on both SQLite and Postgres).

Usage (from the repo root, after running the two preprocessing scripts):

    DATABASE_URL=sqlite:///./data/lines_shines.db python db_ingestion.py

For Railway, set DATABASE_URL to the Postgres URL Railway assigns.
Point LINESHINES_REPO_ROOT at the LinesShines repo root so the script can
locate the xlsx files under $LINESHINES_REPO_ROOT/data/.
"""

from __future__ import annotations
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
import pandas as pd
from sqlalchemy import delete
from sqlalchemy.orm import Session
from database.db_models import Base, DatasetInfo, PassBlockStat, PassRushStat, Team
from main import engine, SessionLocal
from teams_reference import TEAMS


DEFAULT_SEASONS = [2022, 2023, 2024, 2025]

FRONT_7_POSITIONS = ("DI", "ED", "LB")
OL_POSITIONS = ("T", "G", "C")


def _find_repo_root() -> Path:
    """Walk up from this file until we find a marker that identifies the repo root."""
    here = Path(__file__).resolve().parent
    for candidate in [here, *here.parents]:
        # Any of these markers means "you found the root"
        if (candidate / "main.py").exists() or (candidate / ".git").exists():
            return candidate

    raise RuntimeError("could not locate repo root from " + str(here))


def _repo_root() -> Path:
    """Where to find the preprocessed xlsx files.

    Order of precedence:
      1. --data-dir CLI flag
      2. LINESHINES_DATA_DIR env var
      3. $LINESHINES_REPO_ROOT/data
      4. ../LinesShines/data (sibling checkout convention)
    """
    env_data = os.environ.get("LINESHINES_DATA_DIR")
    if env_data:
        return Path(env_data)

    env_root = os.environ.get("LINESHINES_REPO_ROOT")
    if env_root:
        return Path(env_root) / "data"

    return _find_repo_root() / "data"


def _safe_int(val):
    return None if pd.isna(val) else int(val)


def _safe_float(val):
    return None if pd.isna(val) else float(val)


def upsert_teams(sess: Session) -> None:
    existing = {t.code for t in sess.query(Team).all()}

    for code, (full_name, color) in TEAMS.items():
        if code in existing:
            row = sess.get(Team, code)
            row.full_name = full_name
            row.primary_color = color

        else:
            sess.add(Team(code=code, full_name=full_name, primary_color=color))

    sess.commit()


def ingest_pass_rush(sess: Session, data_dir: Path, seasons: list[int]) -> int:
    total = 0
    for season in seasons:
        path = data_dir / f"{season} NFL Front 7 Pass Rush.xlsx"

        if not path.exists():
            print(f"  skip pass_rush {season}: {path} not found")
            continue

        sheets = pd.read_excel(path, sheet_name=None)
        for position in FRONT_7_POSITIONS:
            position_df = sheets.get(position)
            if position_df is None or position_df.empty:
                continue

            position_df.dropna(subset=["PR Opp"], inplace=True)

            # Wipe slice before reinserting: simplest cross-dialect upsert.
            sess.execute(
                delete(PassRushStat).where(
                    PassRushStat.season == season,
                    PassRushStat.position == position,
                )
            )

            rows = []
            for _, row in position_df.iterrows():
                rows.append(
                    PassRushStat(
                        season=season,
                        position=position,
                        team_code=row["Team"],
                        player=row["Player"],
                        abbr_name=row["Abbr Name"],
                        games=_safe_int(row.get("Games")),
                        pr_opp=_safe_int(row.get("PR Opp")),
                        tps_pr_opp=_safe_int(row.get("TPS PR Opp")),
                        win_rate=_safe_float(row.get("Win Rate")),
                        tps_win_rate=_safe_float(row.get("TPS Win Rate")),
                        pressure_rate=_safe_float(row.get("Pressure Rate")),
                        tps_pressure_rate=_safe_float(row.get("TPS Pressure Rate")),
                        havoc_rate=_safe_float(row.get("Havoc Rate")),
                        tps_havoc_rate=_safe_float(row.get("TPS Havoc Rate")),
                    )
                )

            sess.add_all(rows)
            total += len(rows)
            print(f"  pass_rush {season} {position}: {len(rows)} rows")

    sess.commit()
    return total


def ingest_pass_block(sess: Session, data_dir: Path, seasons: list[int]) -> int:
    total = 0
    for season in seasons:
        path = data_dir / f"{season} NFL OL Pass Block.xlsx"
        if not path.exists():
            print(f"  skip pass_block {season}: {path} not found")
            continue

        sheets = pd.read_excel(path, sheet_name=None)
        for position in OL_POSITIONS:
            position_df = sheets.get(position)
            if position_df is None or position_df.empty:
                continue

            position_df.dropna(subset=["Non Spike PB Snaps"], inplace=True)

            sess.execute(
                delete(PassBlockStat).where(
                    PassBlockStat.season == season,
                    PassBlockStat.position == position,
                )
            )

            rows = []
            for _, row in position_df.iterrows():
                rows.append(
                    PassBlockStat(
                        season=season,
                        position=position,
                        team_code=row["Team"],
                        player=row["Player"],
                        abbr_name=row["Abbr Name"],
                        games=_safe_int(row.get("Games")),
                        non_spike_pb_snaps=_safe_int(row.get("Non Spike PB Snaps")),
                        tps_non_spike_pb_snaps=_safe_int(
                            row.get("TPS Non Spike PB Snaps")
                        ),
                        allowed_pressure_pct=_safe_float(row.get("Allowed Pressure %")),
                        tps_allowed_pressure_pct=_safe_float(
                            row.get("TPS Allowed Pressure %")
                        ),
                        allowed_havoc_pct=_safe_float(row.get("Allowed Havoc %")),
                        tps_allowed_havoc_pct=_safe_float(row.get("TPS Allowed Havoc %")),
                    )
                )

            sess.add_all(rows)
            total += len(rows)
            print(f"  pass_block {season} {position}: {len(rows)} rows")

    sess.commit()
    return total


def _set_dataset_info(sess: Session) -> None:
    """Flag this DB as production (not sample), stamp the ingest time."""
    updates = {
        "is_sample_data": "false",
        "last_ingested_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }

    for key, value in updates.items():
        existing = sess.get(DatasetInfo, key)
        if existing:
            existing.value = value

        else:
            sess.add(DatasetInfo(key=key, value=value))

    sess.commit()


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
        print(f"data directory not found: {data_dir}", file=sys.stderr)
        print(
            "set --data-dir or LINESHINES_DATA_DIR/LINESHINES_REPO_ROOT env var",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"reading xlsx from: {data_dir}")

    Base.metadata.create_all(engine)
    with SessionLocal() as sess:
        upsert_teams(sess)
        pr = ingest_pass_rush(sess, data_dir, args.seasons)
        pb = ingest_pass_block(sess, data_dir, args.seasons)
        _set_dataset_info(sess)

    print(f"\ningested {pr} pass-rush rows and {pb} pass-block rows.")


if __name__ == "__main__":
    main()
