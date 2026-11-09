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
TEXAS_ID = 311  # Big 12 until 2023, SEC from 2024.
UCLA_ID = 324  # Pac-12 until 2023, B1G from 2024.
JOINED = CareerStatus.JOINED_NFL.value
PROSPECT = CareerStatus.PROSPECTS.value
FRONT_7 = ("ED", "DI")


@pytest.fixture()
def sess():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with sessionmaker(engine)() as session:
        yield session


def _rush_row(
    season, player_id, position="ED", team_code=AKRON_ID, conference=None, **values
):
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
        batted_pass_rate=1.0,
        tps_batted_pass_rate=1.0,
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
        conference=conference or ("MAC" if team_code == AKRON_ID else "SEC"),
        player_id=player_id,
        player=f"Player {player_id}",
        abbr_name=f"P. {player_id}",
        pass_cov_percent=10.0,
        tps_pass_cov_percent=10.0,
        **defaults,
    )


def _block_row(season, player_id, position="T", **values):
    defaults = dict(
        pressures=20,
        tps_pressures=6,
        havoc=8,
        tps_havoc=2,
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
    sess.add(NCAAFPassRushCareerMember(player_id=1, status=PROSPECT))
    sess.commit()

    (record,) = _merge_rush(sess)

    assert record["position"] == "ED"
    assert record["team"] == ALABAMA_ID
    assert record["conference"] == "SEC"
    assert record["status"] == PROSPECT


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

    assert last_season_conferences(sess, PASS_RUSH_CAREER) == {ALABAMA_ID: ["SEC"]}


def _add_member(sess, player_id, rows, name):
    """Add a member from `rows` of (season, team, conference), named `name`."""
    for season, team_code, conference in rows:
        row = _rush_row(season, player_id, team_code=team_code, conference=conference)
        row.player = name
        sess.add(row)

    sess.add(NCAAFPassRushCareerMember(player_id=player_id, status=JOINED))


def test_a_member_keeps_the_conference_of_his_last_season_after_his_school_moves(sess):
    # Laiatu Latu's last year at UCLA was 2023, the Pac-12's last season. UCLA joined
    # the B1G in 2024, but for Latu UCLA is still a Pac-12 school.
    _add_member(
        sess,
        1,
        [(2019, 340, "Pac-12"), (2022, UCLA_ID, "Pac-12"), (2023, UCLA_ID, "Pac-12")],
        "Laiatu Latu",
    )
    # A teammate of the B1G era shows that UCLA now holds members on both sides.
    _add_member(sess, 2, [(2025, UCLA_ID, "B1G")], "Later Bruin")
    sess.commit()

    (latu,) = _merge_rush(sess, player_id=1)
    (later,) = _merge_rush(sess, player_id=2)

    assert (latu["team"], latu["conference"]) == (UCLA_ID, "Pac-12")
    assert (later["team"], later["conference"]) == (UCLA_ID, "B1G")
    assert last_season_conferences(sess, PASS_RUSH_CAREER) == {
        UCLA_ID: ["B1G", "Pac-12"]
    }


def test_four_big_12_years_do_not_outweigh_a_last_season_in_the_sec(sess):
    # Vernon Broughton played at Texas from 2020; the school was in the Big 12 for the
    # first four years and in the SEC for 2024, his last. Only 2024 places him.
    _add_member(
        sess,
        1,
        [
            (2020, TEXAS_ID, "Big 12"),
            (2021, TEXAS_ID, "Big 12"),
            (2022, TEXAS_ID, "Big 12"),
            (2023, TEXAS_ID, "Big 12"),
            (2024, TEXAS_ID, "SEC"),
        ],
        "Vernon Broughton",
    )
    # A Texas member who left in 2023 is a Big 12 player.
    _add_member(sess, 2, [(2023, TEXAS_ID, "Big 12")], "Earlier Longhorn")
    sess.commit()

    (broughton,) = _merge_rush(sess, player_id=1)
    (earlier,) = _merge_rush(sess, player_id=2)

    assert broughton["seasons"] == 5
    assert (broughton["team"], broughton["conference"]) == (TEXAS_ID, "SEC")
    assert (earlier["team"], earlier["conference"]) == (TEXAS_ID, "Big 12")
    assert last_season_conferences(sess, PASS_RUSH_CAREER) == {
        TEXAS_ID: ["Big 12", "SEC"]
    }


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
                NCAAFPassRushCareerMember(player_id=2, status=PROSPECT),
                NCAAFPassBlockCareerMember(player_id=3, status=PROSPECT),
            ]
        )
        db.commit()

    yield


def test_career_metadata_lists_statuses_positions_and_two_thresholds(
    client, seeded_career_db
):
    body = client.get("/api/ncaaf/career/metadata").json()

    assert body["statuses"] == [JOINED, PROSPECT]
    assert list(body["pass_rush"]["positions"]) == ["ED", "DI"]
    assert list(body["pass_block"]["positions"]) == ["T", "G", "C"]
    assert (
        body["pass_rush"]["default_thresholds"]
        == NCAAF_CAREER_DEFAULT_THRESHOLDS["pass_rush"]
    )

    assert set(body["pass_block"]["default_thresholds"]) == {JOINED, PROSPECT}
    assert body["team_conferences"] == {
        str(ALABAMA_ID): ["SEC"],
        str(AKRON_ID): ["MAC"],
    }
    assert body["teams"][str(ALABAMA_ID)]["full_name"] == "Alabama"
    assert "tps_note" in body


def test_the_joined_nfl_threshold_is_stricter_than_the_prospect_one():
    for thresholds in NCAAF_CAREER_DEFAULT_THRESHOLDS.values():
        assert thresholds[JOINED] > thresholds[PROSPECT]


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


def test_career_tps_proportion_is_the_ratio_of_the_summed_counts(sess):
    # Season ratios are 10% and 50%; their mean is 30%, but the counts say 110 / 500.
    sess.add(_block_row(2023, 1, non_spike_pb_snaps=100, tps_non_spike_pb_snaps=10))
    sess.add(_block_row(2024, 1, non_spike_pb_snaps=400, tps_non_spike_pb_snaps=200))
    sess.add(NCAAFPassBlockCareerMember(player_id=1, status=JOINED))
    sess.commit()

    (record,) = merged_career_rows(sess, PASS_BLOCK_CAREER, ("T", "G", "C"))

    assert record["TPS Non Spike PB Snaps"] == 210
    assert record["TPS Proportion %"] == 42.0


def test_career_tps_proportion_is_missing_without_snaps_and_absent_for_the_front_7(
    sess,
):
    sess.add(_block_row(2024, 1, non_spike_pb_snaps=0, tps_non_spike_pb_snaps=0))
    sess.add(NCAAFPassBlockCareerMember(player_id=1, status=JOINED))
    sess.add(_rush_row(2024, 2))
    sess.add(NCAAFPassRushCareerMember(player_id=2, status=JOINED))
    sess.commit()

    (block_record,) = merged_career_rows(sess, PASS_BLOCK_CAREER, ("T", "G", "C"))
    (rush_record,) = _merge_rush(sess, player_id=2)

    assert block_record["TPS Proportion %"] is None
    assert "TPS Proportion %" not in rush_record


def test_career_counts_behind_the_rates_are_summed_over_the_seasons(sess):
    sess.add(
        _rush_row(
            2023,
            1,
            wins=10,
            tps_wins=4,
            pressures=20,
            tps_pressures=8,
            havoc=6,
            tps_havoc=2,
        )
    )
    sess.add(
        _rush_row(
            2024,
            1,
            wins=15,
            tps_wins=5,
            pressures=30,
            tps_pressures=9,
            havoc=9,
            tps_havoc=3,
        )
    )
    sess.add(NCAAFPassRushCareerMember(player_id=1, status=JOINED))
    sess.commit()

    (record,) = _merge_rush(sess)

    assert (record["Wins"], record["TPS Wins"]) == (25, 9)
    assert (record["Pressures"], record["TPS Pressures"]) == (50, 17)
    assert (record["Havoc"], record["TPS Havoc"]) == (15, 5)


def test_career_counts_of_the_offensive_line_are_summed_too(sess):
    sess.add(_block_row(2023, 1, pressures=20, havoc=8, tps_pressures=5, tps_havoc=1))
    sess.add(_block_row(2024, 1, pressures=30, havoc=4, tps_pressures=7, tps_havoc=3))
    sess.add(NCAAFPassBlockCareerMember(player_id=1, status=JOINED))
    sess.commit()

    (record,) = merged_career_rows(sess, PASS_BLOCK_CAREER, ("T", "G", "C"))

    assert (record["Pressures"], record["TPS Pressures"]) == (50, 12)
    assert (record["Havoc"], record["TPS Havoc"]) == (12, 4)


def test_career_batted_passes_are_summed_and_their_rate_is_weighted_by_pr_opp(sess):
    sess.add(
        _rush_row(
            2023,
            1,
            pr_opp=100,
            batted_passes=2,
            batted_pass_rate=2.0,
            tps_batted_passes=1,
        )
    )
    sess.add(
        _rush_row(
            2024,
            1,
            pr_opp=300,
            batted_passes=3,
            batted_pass_rate=1.0,
            tps_batted_passes=2,
        )
    )
    sess.add(NCAAFPassRushCareerMember(player_id=1, status=JOINED))
    sess.commit()

    (record,) = _merge_rush(sess)

    assert (record["Batted Passes"], record["TPS Batted Passes"]) == (5, 3)
    # (2.0 x 100 + 1.0 x 300) / 400, which is also 5 / 400.
    assert record["Batted Pass Rate"] == 1.25


def test_career_metadata_lists_both_conferences_of_a_school_that_changed(client):
    with SessionLocal() as db:
        for model in (
            NCAAFPassRushStat,
            NCAAFPassBlockStat,
            NCAAFPassRushCareerMember,
            NCAAFPassBlockCareerMember,
            NCAAFTeam,
        ):
            db.query(model).delete()

        _add_member(db, 1, [(2023, UCLA_ID, "Pac-12")], "Laiatu Latu")
        _add_member(db, 2, [(2025, UCLA_ID, "B1G")], "Later Bruin")
        db.commit()

    body = client.get("/api/ncaaf/career/metadata").json()

    assert body["team_conferences"] == {str(UCLA_ID): ["B1G", "Pac-12"]}
