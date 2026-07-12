"""Tests for database/db_ingestion.py's path resolution against the
category-then-season data/ layout (data/front_7_pass_rush/{season}.xlsx,
data/ol_pass_block/{season}.xlsx).
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import db_ingestion
from database.db_models import Base, PassBlockStat, PassRushStat


def _write_front_7_xlsx(path, team="BUF", player="T. Test") -> None:
    df = pd.DataFrame(
        {
            "Team": [team],
            "Player": [player],
            "Abbr Name": [player],
            "Games": [17],
            "PR Opp": [300],
            "TPS PR Opp": [120],
            "Win Rate": [15.0],
            "TPS Win Rate": [18.0],
            "Pressure Rate": [20.0],
            "TPS Pressure Rate": [25.0],
            "Havoc Rate": [8.0],
            "TPS Havoc Rate": [10.0],
        }
    )
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="ED", index=False)


def _write_ol_xlsx(path, team="MIA", player="O. Line") -> None:
    df = pd.DataFrame(
        {
            "Team": [team],
            "Player": [player],
            "Abbr Name": [player],
            "Games": [17],
            "Non Spike PB Snaps": [500],
            "TPS Non Spike PB Snaps": [200],
            "Allowed Pressure %": [5.0],
            "TPS Allowed Pressure %": [6.0],
            "Allowed Havoc %": [2.0],
            "TPS Allowed Havoc %": [3.0],
        }
    )
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="T", index=False)


def _fresh_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(engine)()


def test_ingest_pass_rush_reads_category_subdir(tmp_path):
    (tmp_path / "front_7_pass_rush").mkdir()
    _write_front_7_xlsx(tmp_path / "front_7_pass_rush" / "2025.xlsx")

    sess = _fresh_session()
    count = db_ingestion.ingest_pass_rush(sess, tmp_path, [2025])

    assert count == 1


def test_ingest_pass_block_reads_category_subdir(tmp_path):
    (tmp_path / "ol_pass_block").mkdir()
    _write_ol_xlsx(tmp_path / "ol_pass_block" / "2025.xlsx")

    sess = _fresh_session()
    count = db_ingestion.ingest_pass_block(sess, tmp_path, [2025])

    assert count == 1


def test_ingest_skips_missing_season_file(tmp_path, capsys):
    (tmp_path / "front_7_pass_rush").mkdir()

    sess = _fresh_session()
    count = db_ingestion.ingest_pass_rush(sess, tmp_path, [1999])

    assert count == 0
    assert "Skip pass rush 1999" in capsys.readouterr().out


def test_ingest_does_not_fall_back_to_legacy_flat_filename(tmp_path):
    """Old layout was `data/{season} NFL Front 7 Pass Rush.xlsx` directly
    under data_dir; make sure ingestion no longer looks there.
    """
    (tmp_path / f"2025 NFL Front 7 Pass Rush.xlsx").write_bytes(b"not-a-real-xlsx")

    sess = _fresh_session()
    count = db_ingestion.ingest_pass_rush(sess, tmp_path, [2025])

    assert count == 0


def test_repo_root_resolution_honors_data_dir_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LINESHINES_DATA_DIR", str(tmp_path))
    assert db_ingestion._repo_root() == tmp_path


def test_ingest_pass_rush_replaces_existing_season_position_rows(tmp_path):
    """Ingestion has no per-row UPSERT (see CLAUDE.md) — rerunning for the
    same (season, position) wipes the slice and reinserts. Rerun with a
    different fake player and confirm the old row is gone, not merged.
    """
    (tmp_path / "front_7_pass_rush").mkdir()
    xlsx_path = tmp_path / "front_7_pass_rush" / "2025.xlsx"

    _write_front_7_xlsx(xlsx_path, team="BUF", player="Old Guy")
    sess = _fresh_session()
    db_ingestion.ingest_pass_rush(sess, tmp_path, [2025])

    _write_front_7_xlsx(xlsx_path, team="KC", player="New Guy")
    db_ingestion.ingest_pass_rush(sess, tmp_path, [2025])

    rows = sess.query(PassRushStat).filter_by(season=2025, position="ED").all()
    assert [(r.team_code, r.player) for r in rows] == [("KC", "New Guy")]


def test_ingest_pass_block_replaces_existing_season_position_rows(tmp_path):
    (tmp_path / "ol_pass_block").mkdir()
    xlsx_path = tmp_path / "ol_pass_block" / "2025.xlsx"

    _write_ol_xlsx(xlsx_path, team="MIA", player="Old Lineman")
    sess = _fresh_session()
    db_ingestion.ingest_pass_block(sess, tmp_path, [2025])

    _write_ol_xlsx(xlsx_path, team="DAL", player="New Lineman")
    db_ingestion.ingest_pass_block(sess, tmp_path, [2025])

    rows = sess.query(PassBlockStat).filter_by(season=2025, position="T").all()
    assert [(r.team_code, r.player) for r in rows] == [("DAL", "New Lineman")]
