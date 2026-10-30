"""Tests for database/db_ingestion.py: path resolution against the league-category-season
data/ layout (data/nfl/front_7_pass_rush/{season}.xlsx, data/nfl/ol_pass_block/{season}.xlsx),
the Player Id column, Pass Cov Percent = 100 - Pass Rush Percent, and the strict column checks.
"""

from __future__ import annotations
import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import db_ingestion
from config import League
from database.db_models import (
    Base,
    NCAAFPassBlockStat,
    NCAAFPassRushStat,
    NCAAFTeam,
    NFLPassBlockStat,
    NFLPassRushStat,
)
from teams.ncaaf import SCHOOL_NAMES

AKRON_ID = 102  # MAC.


def _write_front_7_xlsx(
    path, team="BUF", player="T. Test", player_id=1001, drop=(), extra=None
) -> None:
    df = pd.DataFrame(
        {
            "Team": [team],
            "Player Id": [player_id],
            "Player": [player],
            "Abbr Name": [player],
            "Games": [17],
            "PR Opp": [300],
            "TPS PR Opp": [120],
            "Pass Rush Percent": [92.0],
            "TPS Pass Rush Percent": [95.0],
            "Win Rate": [15.0],
            "TPS Win Rate": [18.0],
            "Pressure Rate": [20.0],
            "TPS Pressure Rate": [25.0],
            "Havoc Rate": [8.0],
            "TPS Havoc Rate": [10.0],
            "PRP": [6.0],
            "TPS PRP": [7.5],
            **(extra or {}),
        }
    ).drop(columns=list(drop))

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="ED", index=False)


def _write_ol_xlsx(
    path, team="MIA", player="O. Line", player_id=2001, extra=None
) -> None:
    df = pd.DataFrame(
        {
            "Team": [team],
            "Player Id": [player_id],
            "Player": [player],
            "Abbr Name": [player],
            "Games": [17],
            "Non Spike PB Snaps": [500],
            "TPS Non Spike PB Snaps": [200],
            "Allowed Pressure %": [5.0],
            "TPS Allowed Pressure %": [6.0],
            "Allowed Havoc %": [2.0],
            "TPS Allowed Havoc %": [3.0],
            "PBE": [95.0],
            "TPS PBE": [92.0],
            **(extra or {}),
        }
    )

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="T", index=False)


def _fresh_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(engine)()


def test_ingest_pass_rush_reads_category_subdir(tmp_path):
    (tmp_path / "nfl" / "front_7_pass_rush").mkdir(parents=True)
    _write_front_7_xlsx(tmp_path / "nfl" / "front_7_pass_rush" / "2025.xlsx")

    sess = _fresh_session()
    count = db_ingestion.ingest_pass_rush(sess, tmp_path, [2025])
    assert count == 1


def test_ingest_pass_block_reads_category_subdir(tmp_path):
    (tmp_path / "nfl" / "ol_pass_block").mkdir(parents=True)
    _write_ol_xlsx(tmp_path / "nfl" / "ol_pass_block" / "2025.xlsx")

    sess = _fresh_session()
    count = db_ingestion.ingest_pass_block(sess, tmp_path, [2025])
    assert count == 1


def test_ingest_skips_missing_season_file(tmp_path, capsys):
    (tmp_path / "nfl" / "front_7_pass_rush").mkdir(parents=True)

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
    (tmp_path / "nfl" / "front_7_pass_rush").mkdir(parents=True)
    xlsx_path = tmp_path / "nfl" / "front_7_pass_rush" / "2025.xlsx"

    _write_front_7_xlsx(xlsx_path, team="BUF", player="Old Guy")
    sess = _fresh_session()
    db_ingestion.ingest_pass_rush(sess, tmp_path, [2025])

    _write_front_7_xlsx(xlsx_path, team="KC", player="New Guy", player_id=1002)
    db_ingestion.ingest_pass_rush(sess, tmp_path, [2025])

    rows = sess.query(NFLPassRushStat).filter_by(season=2025, position="ED").all()
    assert [(r.team_code, r.player) for r in rows] == [("KC", "New Guy")]


def test_ingest_pass_block_replaces_existing_season_position_rows(tmp_path):
    (tmp_path / "nfl" / "ol_pass_block").mkdir(parents=True)
    xlsx_path = tmp_path / "nfl" / "ol_pass_block" / "2025.xlsx"

    _write_ol_xlsx(xlsx_path, team="MIA", player="Old Lineman")
    sess = _fresh_session()
    db_ingestion.ingest_pass_block(sess, tmp_path, [2025])

    _write_ol_xlsx(xlsx_path, team="DAL", player="New Lineman", player_id=2002)
    db_ingestion.ingest_pass_block(sess, tmp_path, [2025])

    rows = sess.query(NFLPassBlockStat).filter_by(season=2025, position="T").all()
    assert [(r.team_code, r.player) for r in rows] == [("DAL", "New Lineman")]


def test_ingest_stores_player_id_and_pass_cov_percent(tmp_path):
    (tmp_path / "nfl" / "front_7_pass_rush").mkdir(parents=True)
    _write_front_7_xlsx(
        tmp_path / "nfl" / "front_7_pass_rush" / "2025.xlsx", player_id=4321
    )

    sess = _fresh_session()
    db_ingestion.ingest_pass_rush(sess, tmp_path, [2025])

    row = sess.query(NFLPassRushStat).one()

    # Source file holds Pass Rush Percent (92 / 95); the table stores 100 minus it.
    assert (row.player_id, row.pass_cov_percent, row.tps_pass_cov_percent) == (
        4321,
        8.0,
        5.0,
    )


def test_ingest_stores_player_id_for_pass_block(tmp_path):
    (tmp_path / "nfl" / "ol_pass_block").mkdir(parents=True)
    _write_ol_xlsx(tmp_path / "nfl" / "ol_pass_block" / "2025.xlsx", player_id=8765)

    sess = _fresh_session()
    db_ingestion.ingest_pass_block(sess, tmp_path, [2025])

    assert sess.query(NFLPassBlockStat).one().player_id == 8765


@pytest.mark.parametrize(
    "column", ["Player Id", "Pass Rush Percent", "TPS Pass Rush Percent"]
)
def test_ingest_fails_loudly_when_a_required_column_is_missing(tmp_path, column):
    (tmp_path / "nfl" / "front_7_pass_rush").mkdir(parents=True)
    _write_front_7_xlsx(
        tmp_path / "nfl" / "front_7_pass_rush" / "2025.xlsx", drop=[column]
    )

    sess = _fresh_session()
    with pytest.raises(ValueError, match=column):
        db_ingestion.ingest_pass_rush(sess, tmp_path, [2025])

    assert sess.query(NFLPassRushStat).count() == 0


def test_ingest_fails_loudly_when_a_row_has_no_player_id(tmp_path):
    (tmp_path / "nfl" / "front_7_pass_rush").mkdir(parents=True)
    _write_front_7_xlsx(
        tmp_path / "nfl" / "front_7_pass_rush" / "2025.xlsx", player_id=None
    )

    sess = _fresh_session()
    with pytest.raises(ValueError, match="Player Id"):
        db_ingestion.ingest_pass_rush(sess, tmp_path, [2025])


def test_season_discovery_reads_only_the_nfl_subfolder(tmp_path):
    # A category folder directly under the data root is the old layout and is ignored.
    (tmp_path / "front_7_pass_rush").mkdir()
    _write_front_7_xlsx(tmp_path / "front_7_pass_rush" / "2023.xlsx")

    (tmp_path / "nfl" / "ol_pass_block").mkdir(parents=True)
    _write_ol_xlsx(tmp_path / "nfl" / "ol_pass_block" / "2024.xlsx")

    (tmp_path / "ncaaf" / "ol_pass_block").mkdir(parents=True)
    _write_ol_xlsx(tmp_path / "ncaaf" / "ol_pass_block" / "2022.xlsx")

    assert db_ingestion._discover_seasons(tmp_path) == [2024]


def _college_columns(franchise_id=AKRON_ID, conference="MAC") -> dict:
    """The two columns the college conversion adds to a workbook."""
    return {"Franchise Id": [franchise_id], "Conference": [conference]}


def test_ncaaf_pass_rush_is_read_from_the_ncaaf_folder_into_the_college_table(
    tmp_path,
):
    (tmp_path / "ncaaf" / "front_7_pass_rush").mkdir(parents=True)
    _write_front_7_xlsx(
        tmp_path / "ncaaf" / "front_7_pass_rush" / "2025.xlsx",
        team="AKRON",
        extra=_college_columns(),
    )
    sess = _fresh_session()
    db_ingestion.upsert_ncaaf_teams(sess)

    count = db_ingestion.ingest_ncaaf_pass_rush(sess, tmp_path, [2025])

    row = sess.query(NCAAFPassRushStat).one()
    assert count == 1
    assert (row.team_code, row.conference, row.player_id) == (AKRON_ID, "MAC", 1001)
    assert sess.query(NFLPassRushStat).count() == 0


def test_ncaaf_pass_block_is_read_from_the_ncaaf_folder_into_the_college_table(
    tmp_path,
):
    (tmp_path / "ncaaf" / "ol_pass_block").mkdir(parents=True)
    _write_ol_xlsx(
        tmp_path / "ncaaf" / "ol_pass_block" / "2025.xlsx",
        team="AKRON",
        extra=_college_columns(),
    )
    sess = _fresh_session()
    db_ingestion.upsert_ncaaf_teams(sess)

    count = db_ingestion.ingest_ncaaf_pass_block(sess, tmp_path, [2025])

    row = sess.query(NCAAFPassBlockStat).one()
    assert count == 1
    assert (row.team_code, row.conference) == (AKRON_ID, "MAC")
    assert sess.query(NFLPassBlockStat).count() == 0


def test_ncaaf_ingestion_does_not_read_the_nfl_folder(tmp_path):
    (tmp_path / "nfl" / "front_7_pass_rush").mkdir(parents=True)
    _write_front_7_xlsx(
        tmp_path / "nfl" / "front_7_pass_rush" / "2025.xlsx",
        extra=_college_columns(),
    )
    sess = _fresh_session()

    assert db_ingestion.ingest_ncaaf_pass_rush(sess, tmp_path, [2025]) == 0


def test_a_college_workbook_without_a_conference_stops_the_run(tmp_path):
    (tmp_path / "ncaaf" / "front_7_pass_rush").mkdir(parents=True)
    _write_front_7_xlsx(
        tmp_path / "ncaaf" / "front_7_pass_rush" / "2025.xlsx",
        extra=_college_columns(),
        drop=["Conference"],
    )
    sess = _fresh_session()

    with pytest.raises(ValueError, match="Conference"):
        db_ingestion.ingest_ncaaf_pass_rush(sess, tmp_path, [2025])

    assert sess.query(NCAAFPassRushStat).count() == 0


def test_a_college_workbook_without_a_franchise_id_stops_the_run(tmp_path):
    (tmp_path / "ncaaf" / "ol_pass_block").mkdir(parents=True)
    _write_ol_xlsx(
        tmp_path / "ncaaf" / "ol_pass_block" / "2025.xlsx", extra=_college_columns()
    )
    path = tmp_path / "ncaaf" / "ol_pass_block" / "2025.xlsx"
    broken_df = pd.read_excel(path).drop(columns=["Franchise Id"])
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        broken_df.to_excel(writer, sheet_name="T", index=False)
    sess = _fresh_session()

    with pytest.raises(ValueError, match="Franchise Id"):
        db_ingestion.ingest_ncaaf_pass_block(sess, tmp_path, [2025])


def test_college_reingestion_replaces_the_season_position_slice(tmp_path):
    (tmp_path / "ncaaf" / "front_7_pass_rush").mkdir(parents=True)
    path = tmp_path / "ncaaf" / "front_7_pass_rush" / "2025.xlsx"
    sess = _fresh_session()
    db_ingestion.upsert_ncaaf_teams(sess)

    _write_front_7_xlsx(path, player="Old Guy", extra=_college_columns())
    db_ingestion.ingest_ncaaf_pass_rush(sess, tmp_path, [2025])
    _write_front_7_xlsx(
        path, player="New Guy", player_id=1002, extra=_college_columns()
    )
    db_ingestion.ingest_ncaaf_pass_rush(sess, tmp_path, [2025])

    assert [row.player for row in sess.query(NCAAFPassRushStat)] == ["New Guy"]


def test_season_discovery_looks_only_in_the_requested_leagues_folder(tmp_path):
    (tmp_path / "nfl" / "front_7_pass_rush").mkdir(parents=True)
    (tmp_path / "ncaaf" / "front_7_pass_rush").mkdir(parents=True)
    _write_front_7_xlsx(tmp_path / "nfl" / "front_7_pass_rush" / "2024.xlsx")
    _write_front_7_xlsx(tmp_path / "ncaaf" / "front_7_pass_rush" / "2026.xlsx")

    assert db_ingestion._discover_seasons(tmp_path, League.NFL) == [2024]
    assert db_ingestion._discover_seasons(tmp_path, League.NCAAF) == [2026]


def test_the_college_team_table_holds_every_scoped_school_and_is_rerunnable():
    sess = _fresh_session()

    db_ingestion.upsert_ncaaf_teams(sess)
    db_ingestion.upsert_ncaaf_teams(sess)

    teams = {team.franchise_id: team.full_name for team in sess.query(NCAAFTeam)}
    assert teams == SCHOOL_NAMES
    assert all(team.primary_color is None for team in sess.query(NCAAFTeam))


def test_the_command_line_needs_a_league(monkeypatch):
    monkeypatch.setattr("sys.argv", ["db_ingestion", "--seasons", "2026"])

    with pytest.raises(SystemExit):
        db_ingestion.main()


def test_every_league_has_two_categories_and_a_team_upsert():
    assert set(db_ingestion.LEAGUE_CATEGORIES) == set(League)
    assert set(db_ingestion.LEAGUE_TEAM_UPSERTS) == set(League)
    assert all(len(cats) == 2 for cats in db_ingestion.LEAGUE_CATEGORIES.values())
