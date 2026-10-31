"""Tests for database/career.py: who is on the college Career page.

A member is Joined NFL (the player_id also sits in the NFL table of the same category)
or a Potential Draftee (a row in the latest college season, and not Joined NFL).
"""

from __future__ import annotations
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import CareerStatus
from database import career
from database.db_models import (
    Base,
    NCAAFPassBlockCareerMember,
    NCAAFPassBlockStat,
    NCAAFPassRushCareerMember,
    NCAAFPassRushStat,
    NFLPassBlockStat,
    NFLPassRushStat,
)

AKRON_ID = 102  # MAC.
JOINED = CareerStatus.JOINED_NFL.value
POTENTIAL = CareerStatus.POTENTIAL_DRAFTEES.value

PASS_RUSH_TABLES = career.CAREER_TABLES[0]
PASS_BLOCK_TABLES = career.CAREER_TABLES[1]


@pytest.fixture()
def sess():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with sessionmaker(engine)() as session:
        yield session


def _college_row(model, season, player_id, position="ED"):
    return model(
        season=season,
        position=position,
        team_code=AKRON_ID,
        conference="MAC",
        player_id=player_id,
        player=f"Player {player_id}",
        abbr_name=f"P. {player_id}",
    )


def _nfl_row(model, season, player_id, position="ED"):
    return model(
        season=season,
        position=position,
        team_code="BUF",
        player_id=player_id,
        player=f"Player {player_id}",
        abbr_name=f"P. {player_id}",
    )


def _members(sess, member_model) -> dict[int, str]:
    return {member.player_id: member.status for member in sess.query(member_model)}


def test_a_player_also_in_the_nfl_table_is_joined_nfl(sess):
    sess.add(_college_row(NCAAFPassRushStat, 2024, 1))
    sess.add(_nfl_row(NFLPassRushStat, 2025, 1))
    sess.commit()

    career.rebuild_career_members(sess, PASS_RUSH_TABLES)

    assert _members(sess, NCAAFPassRushCareerMember) == {1: JOINED}


def test_a_player_in_the_latest_season_and_not_in_the_nfl_is_a_potential_draftee(sess):
    sess.add(_college_row(NCAAFPassRushStat, 2025, 2))
    sess.commit()

    career.rebuild_career_members(sess, PASS_RUSH_TABLES)

    assert _members(sess, NCAAFPassRushCareerMember) == {2: POTENTIAL}


def test_a_player_in_neither_group_is_not_a_member(sess):
    # Played in 2024 only, never reached the NFL tables: a graduate who did not go pro.
    sess.add(_college_row(NCAAFPassRushStat, 2024, 3))
    sess.add(_college_row(NCAAFPassRushStat, 2025, 4))
    sess.commit()

    career.rebuild_career_members(sess, PASS_RUSH_TABLES)

    assert _members(sess, NCAAFPassRushCareerMember) == {4: POTENTIAL}


def test_a_joined_nfl_player_in_the_latest_season_is_not_also_a_potential_draftee(sess):
    sess.add(_college_row(NCAAFPassRushStat, 2025, 5))
    sess.add(_nfl_row(NFLPassRushStat, 2026, 5))
    sess.commit()

    counts = career.rebuild_career_members(sess, PASS_RUSH_TABLES)

    assert _members(sess, NCAAFPassRushCareerMember) == {5: JOINED}
    assert counts == {JOINED: 1, POTENTIAL: 0}


def test_the_latest_season_is_read_from_the_table_not_from_the_seasons_just_loaded(
    sess,
):
    # Back-filling an old season adds a row but never moves the latest season.
    sess.add(_college_row(NCAAFPassRushStat, 2025, 6))
    sess.commit()
    career.rebuild_career_members(sess, PASS_RUSH_TABLES)

    sess.add(_college_row(NCAAFPassRushStat, 2023, 7))
    sess.commit()
    career.rebuild_career_members(sess, PASS_RUSH_TABLES)

    assert _members(sess, NCAAFPassRushCareerMember) == {6: POTENTIAL}


def test_rebuilding_follows_the_nfl_table_and_replaces_the_old_members(sess):
    sess.add(_college_row(NCAAFPassRushStat, 2025, 8))
    sess.commit()
    career.rebuild_career_members(sess, PASS_RUSH_TABLES)
    assert _members(sess, NCAAFPassRushCareerMember) == {8: POTENTIAL}

    # He is drafted and shows up in the NFL table: the next rebuild flips him.
    sess.add(_nfl_row(NFLPassRushStat, 2026, 8))
    sess.commit()
    career.rebuild_career_members(sess, PASS_RUSH_TABLES)

    assert _members(sess, NCAAFPassRushCareerMember) == {8: JOINED}


def test_rebuilding_twice_gives_the_same_members(sess):
    sess.add(_college_row(NCAAFPassRushStat, 2025, 9))
    sess.add(_college_row(NCAAFPassRushStat, 2024, 10))
    sess.add(_nfl_row(NFLPassRushStat, 2025, 10))
    sess.commit()

    career.rebuild_career_members(sess, PASS_RUSH_TABLES)
    first = _members(sess, NCAAFPassRushCareerMember)
    career.rebuild_career_members(sess, PASS_RUSH_TABLES)

    assert first == {9: POTENTIAL, 10: JOINED}
    assert _members(sess, NCAAFPassRushCareerMember) == first


def test_each_category_matches_against_its_own_nfl_table(sess):
    # He is in the NFL pass-rush table only, so he is Joined NFL for the front 7
    # and a Potential Draftee for the OL (a college tackle who plays on the edge in the
    # pros is not flagged; accepted, rare).
    sess.add(_college_row(NCAAFPassRushStat, 2025, 11))
    sess.add(_college_row(NCAAFPassBlockStat, 2025, 11, position="T"))
    sess.add(_nfl_row(NFLPassRushStat, 2025, 11))
    sess.commit()

    career.rebuild_career_members(sess, PASS_RUSH_TABLES)
    career.rebuild_career_members(sess, PASS_BLOCK_TABLES)

    assert _members(sess, NCAAFPassRushCareerMember) == {11: JOINED}
    assert _members(sess, NCAAFPassBlockCareerMember) == {11: POTENTIAL}


def test_the_pass_block_members_use_the_nfl_pass_block_table(sess):
    sess.add(_college_row(NCAAFPassBlockStat, 2025, 12, position="T"))
    sess.add(_nfl_row(NFLPassBlockStat, 2025, 12, position="T"))
    sess.commit()

    career.rebuild_career_members(sess, PASS_BLOCK_TABLES)

    assert _members(sess, NCAAFPassBlockCareerMember) == {12: JOINED}


def test_an_empty_college_table_gives_no_members(sess):
    counts = career.rebuild_career_members(sess, PASS_RUSH_TABLES)

    assert counts == {JOINED: 0, POTENTIAL: 0}
    assert _members(sess, NCAAFPassRushCareerMember) == {}


def test_an_empty_nfl_table_prints_a_warning_to_run_the_nfl_ingestion_first(
    sess, capsys
):
    sess.add(_college_row(NCAAFPassRushStat, 2025, 13))
    sess.commit()

    career.rebuild_all_career_members(sess)

    output = capsys.readouterr().out
    assert "NFL pass rush table is empty" in output
    assert "Run the NFL ingestion first" in output
