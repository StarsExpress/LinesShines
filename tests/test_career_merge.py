"""Tests for database/career_merge.py and the /api/ncaaf/career routes.

A Career row merges every season of a member into one record: counts are summed,
rates are weighted by their own denominator, Pass Cov Percent comes from the snap
counts, and the identity is that of the last college season.
"""

from __future__ import annotations
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import NCAAF_CAREER_DEFAULT_THRESHOLDS, CareerStatus
from database.career_merge import (
    PASS_BLOCK_CAREER,
    PASS_RUSH_CAREER,
    last_season_conferences,
    merged_career_rows,
)
from database.db_models import (
    Base,
    NCAAFPassBlockCareerMember,
    NCAAFPassBlockStat,
    NCAAFPassRushCareerMember,
    NCAAFPassRushStat,
    NCAAFTeam,
)
from main import SessionLocal

AKRON_ID = 102  # MAC.
ALABAMA_ID = 103  # SEC.
JOINED = CareerStatus.JOINED_NFL.value
POTENTIAL = CareerStatus.POTENTIAL_DRAFTEES.value
FRONT_7 = ("ED", "DI")


@pytest.fixture()
def sess():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with sessionmaker(engine)() as session:
        yield session


def _rush_row(season, player_id, position="ED", team_code=AKRON_ID, **values):
    defaults = dict(
        games=10,
        pr_opp=100,
        tps_pr_opp=40,
        win_rate=10.0,
        tps_win_rate=10.0,
        pressure_rate=10.0,
        tps_pressure_rate=10.0,
        havoc_rate=10.0,
        tps_havoc_rate=10.0,
        prp=10.0,
        tps_prp=10.0,
        pass_rush_snaps=90,
        pass_play_snaps=100,
        tps_pass_rush_snaps=36,
        tps_pass_play_snaps=40,
    )
    defaults.update(values)

    return NCAAFPassRushStat(
        season=season,
        position=position,
        team_code=team_code,
        conference="MAC" if team_code == AKRON_ID else "SEC",
        player_id=player_id,
        player=f"Player {player_id}",
        abbr_name=f"P. {player_id}",
        pass_cov_percent=10.0,
        tps_pass_cov_percent=10.0,
        **defaults,
    )


def _block_row(season, player_id, position="T", **values):
    defaults = dict(
        games=10,
        non_spike_pb_snaps=400,
        tps_non_spike_pb_snaps=100,
        allowed_pressure_pct=4.0,
        tps_allowed_pressure_pct=4.0,
        allowed_havoc_pct=2.0,
        tps_allowed_havoc_pct=2.0,
        pbe=96.0,
        tps_pbe=96.0,
    )
    defaults.update(values)

    return NCAAFPassBlockStat(
        season=season,
        position=position,
        team_code=AKRON_ID,
        conference="MAC",
        player_id=player_id,
        player=f"Player {player_id}",
        abbr_name=f"P. {player_id}",
        **defaults,
    )


def _merge_rush(sess, player_id=1, positions=FRONT_7):
    records = merged_career_rows(sess, PASS_RUSH_CAREER, positions)

    return [record for record in records if record["player_id"] == player_id]


def test_counts_are_summed_and_rates_are_weighted_by_their_own_denominator(sess):
    sess.add(_rush_row(2023, 1, pr_opp=100, tps_pr_opp=10, win_rate=10.0))
    sess.add(_rush_row(2024, 1, pr_opp=300, tps_pr_opp=30, win_rate=20.0))
    sess.add(NCAAFPassRushCareerMember(player_id=1, status=JOINED))
    sess.commit()

    (record,) = _merge_rush(sess)

    assert record["PR Opp"] == 400
    assert record["games"] == 20
    assert record["TPS PR Opp"] == 40
    assert record["Win Rate"] == pytest.approx(17.5)
    assert record["seasons"] == 2
    assert (record["first_season"], record["last_season"]) == (2023, 2024)


def test_tps_rates_use_the_tps_denominator(sess):
    sess.add(_rush_row(2023, 1, pr_opp=100, tps_pr_opp=300, tps_win_rate=10.0))
    sess.add(_rush_row(2024, 1, pr_opp=300, tps_pr_opp=100, tps_win_rate=20.0))
    sess.add(NCAAFPassRushCareerMember(player_id=1, status=JOINED))
    sess.commit()

    (record,) = _merge_rush(sess)

    assert record["TPS Win Rate"] == pytest.approx(12.5)


def test_pass_cov_percent_comes_from_the_snap_counts_not_from_pr_opp(sess):
    sess.add(_rush_row(2023, 1, pr_opp=500, pass_rush_snaps=100, pass_play_snaps=200))
    sess.add(_rush_row(2024, 1, pr_opp=100, pass_rush_snaps=300, pass_play_snaps=400))
    sess.add(NCAAFPassRushCareerMember(player_id=1, status=JOINED))
    sess.commit()

    (record,) = _merge_rush(sess)

    # 100 - (100 + 300) / (200 + 400) x 100.
    assert record["Pass Cov Percent"] == pytest.approx(33.333, abs=0.001)


def test_the_snap_columns_never_reach_the_record(sess):
    sess.add(_rush_row(2024, 1))
    sess.add(NCAAFPassRushCareerMember(player_id=1, status=JOINED))
    sess.commit()

    (record,) = _merge_rush(sess)

    assert not any("snaps" in key.lower() and "PB" not in key for key in record)


def test_identity_is_that_of_the_last_college_season(sess):
    sess.add(_rush_row(2023, 1, position="DI", team_code=AKRON_ID))
    sess.add(_rush_row(2024, 1, position="ED", team_code=ALABAMA_ID))
    sess.add(NCAAFPassRushCareerMember(player_id=1, status=POTENTIAL))
    sess.commit()

    (record,) = _merge_rush(sess)

    assert record["position"] == "ED"
    assert record["team"] == ALABAMA_ID
    assert record["conference"] == "SEC"
    assert record["status"] == POTENTIAL


def test_two_positions_in_the_last_season_pick_the_one_with_more_opportunities(sess):
    sess.add(_rush_row(2024, 1, position="DI", pr_opp=50))
    sess.add(_rush_row(2024, 1, position="ED", pr_opp=250))
    sess.add(NCAAFPassRushCareerMember(player_id=1, status=JOINED))
    sess.commit()

    (record,) = _merge_rush(sess)

    assert record["position"] == "ED"


def test_the_position_filter_uses_the_last_season_position(sess):
    sess.add(_rush_row(2023, 1, position="DI"))
    sess.add(_rush_row(2024, 1, position="ED"))
    sess.add(NCAAFPassRushCareerMember(player_id=1, status=JOINED))
    sess.commit()

    assert _merge_rush(sess, positions=("DI",)) == []
    assert len(_merge_rush(sess, positions=("ED",))) == 1


def test_a_player_who_is_not_a_member_is_not_listed(sess):
    sess.add(_rush_row(2024, 1))
    sess.add(_rush_row(2024, 2))
    sess.add(NCAAFPassRushCareerMember(player_id=2, status=JOINED))
    sess.commit()

    records = merged_career_rows(sess, PASS_RUSH_CAREER, FRONT_7)

    assert [record["player_id"] for record in records] == [2]


def test_a_zero_denominator_gives_none_instead_of_an_error(sess):
    sess.add(
        _rush_row(
            2024,
            1,
            pr_opp=0,
            pass_rush_snaps=0,
            pass_play_snaps=0,
        )
    )
    sess.add(NCAAFPassRushCareerMember(player_id=1, status=JOINED))
    sess.commit()

    (record,) = _merge_rush(sess)

    assert record["Win Rate"] is None
    assert record["Pass Cov Percent"] is None
    assert record["PR Opp"] == 0


def test_a_season_with_no_opportunities_and_an_infinite_rate_does_not_poison_the_career(
    sess,
):
    sess.add(
        _rush_row(
            2023,
            1,
            tps_pr_opp=0,
            tps_pressure_rate=float("inf"),
        )
    )
    sess.add(_rush_row(2024, 1, tps_pr_opp=40, tps_pressure_rate=25.0))
    sess.add(NCAAFPassRushCareerMember(player_id=1, status=JOINED))
    sess.commit()

    (record,) = _merge_rush(sess)

    assert record["TPS Pressure Rate"] == pytest.approx(25.0)


def test_records_come_ordered_by_opportunities_then_player_id(sess):
    sess.add(_rush_row(2024, 3, pr_opp=100))
    sess.add(_rush_row(2024, 1, pr_opp=300))
    sess.add(_rush_row(2024, 2, pr_opp=100))

    for player_id in (1, 2, 3):
        sess.add(NCAAFPassRushCareerMember(player_id=player_id, status=JOINED))

    sess.commit()

    records = merged_career_rows(sess, PASS_RUSH_CAREER, FRONT_7)

    assert [record["player_id"] for record in records] == [1, 2, 3]


def test_the_offensive_line_weights_by_non_spike_pass_block_snaps(sess):
    sess.add(_block_row(2023, 1, non_spike_pb_snaps=100, pbe=90.0))
    sess.add(_block_row(2024, 1, non_spike_pb_snaps=300, pbe=98.0))
    sess.add(NCAAFPassBlockCareerMember(player_id=1, status=JOINED))
    sess.commit()

    (record,) = merged_career_rows(sess, PASS_BLOCK_CAREER, ("T", "G", "C"))

    assert record["Non Spike PB Snaps"] == 400
    assert record["PBE"] == pytest.approx(96.0)


def test_conferences_come_from_each_members_last_school(sess):
    sess.add(_rush_row(2023, 1, team_code=AKRON_ID))
    sess.add(_rush_row(2024, 1, team_code=ALABAMA_ID))
    sess.add(NCAAFPassRushCareerMember(player_id=1, status=JOINED))
    sess.commit()

    assert last_season_conferences(sess, PASS_RUSH_CAREER) == {ALABAMA_ID: "SEC"}


@pytest.fixture()
def seeded_career_db():
    """Load two members per category into the shared test database."""
    with SessionLocal() as db:
        for model in (
            NCAAFPassRushStat,
            NCAAFPassBlockStat,
            NCAAFPassRushCareerMember,
            NCAAFPassBlockCareerMember,
            NCAAFTeam,
        ):
            db.query(model).delete()

        db.add(NCAAFTeam(franchise_id=AKRON_ID, full_name="Akron"))
        db.add(NCAAFTeam(franchise_id=ALABAMA_ID, full_name="Alabama"))
        db.add_all(
            [
                _rush_row(2024, 1, pr_opp=300),
                _rush_row(2025, 1, pr_opp=100, team_code=ALABAMA_ID),
                _rush_row(2025, 2, position="DI", pr_opp=200),
                _block_row(2025, 3, position="G"),
                NCAAFPassRushCareerMember(player_id=1, status=JOINED),
                NCAAFPassRushCareerMember(player_id=2, status=POTENTIAL),
                NCAAFPassBlockCareerMember(player_id=3, status=POTENTIAL),
            ]
        )
        db.commit()

    yield


def test_career_metadata_lists_statuses_positions_and_two_thresholds(
    client, seeded_career_db
):
    body = client.get("/api/ncaaf/career/metadata").json()

    assert body["statuses"] == [JOINED, POTENTIAL]
    assert list(body["pass_rush"]["positions"]) == ["ED", "DI"]
    assert list(body["pass_block"]["positions"]) == ["T", "G", "C"]
    assert (
        body["pass_rush"]["default_thresholds"]
        == NCAAF_CAREER_DEFAULT_THRESHOLDS["pass_rush"]
    )

    assert set(body["pass_block"]["default_thresholds"]) == {JOINED, POTENTIAL}
    assert body["team_conferences"] == {str(ALABAMA_ID): "SEC", str(AKRON_ID): "MAC"}
    assert body["teams"][str(ALABAMA_ID)]["full_name"] == "Alabama"
    assert "tps_note" in body


def test_the_joined_nfl_threshold_is_stricter_than_the_potential_draftee_one():
    for thresholds in NCAAF_CAREER_DEFAULT_THRESHOLDS.values():
        assert thresholds[JOINED] > thresholds[POTENTIAL]


def test_career_routes_send_every_member_with_no_server_side_threshold(
    client, seeded_career_db
):
    body = client.get("/api/ncaaf/career/pass_rush").json()

    assert body["category"] == "pass_rush"
    assert body["position"] is None
    assert {record["player_id"] for record in body["records"]} == {1, 2}

    first = body["records"][0]

    assert first["PR Opp"] == 400
    assert first["team"] == ALABAMA_ID
    assert first["status"] == JOINED


def test_career_routes_filter_by_the_last_position(client, seeded_career_db):
    body = client.get("/api/ncaaf/career/pass_rush", params={"position": "DI"}).json()

    assert [record["player_id"] for record in body["records"]] == [2]


def test_career_pass_block_route_returns_the_offensive_line(client, seeded_career_db):
    body = client.get("/api/ncaaf/career/pass_block").json()

    assert [record["player_id"] for record in body["records"]] == [3]


def test_career_routes_reject_an_unknown_position(client, seeded_career_db):
    response = client.get("/api/ncaaf/career/pass_rush", params={"position": "XX"})

    assert response.status_code == 400
    block = client.get("/api/ncaaf/career/pass_block", params={"position": "ED"})

    assert block.status_code == 400
