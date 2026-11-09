"""database/midseason_trades.py: a traded player's team is updated for the current season only.

Uses an in-memory database and synthetic rows; no xlsx and no real season data.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from database import midseason_trades
from database.db_models import Base, NFLPassBlockStat, NFLPassRushStat

SEASON = date.today().year


@pytest.fixture
def session_factory(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(midseason_trades, "SessionLocal", factory)
    return factory


def _add(factory, model, **columns):
    with factory() as sess:
        sess.add(model(**columns))
        sess.commit()


def _rusher(player="Jon Rush", team="BUF", player_id=1, season=SEASON):
    return {
        "season": season,
        "position": "ED",
        "team_code": team,
        "player_id": player_id,
        "player": player,
        "abbr_name": player,
    }


def test_a_traded_rusher_moves_to_the_new_team(session_factory, capsys):
    _add(session_factory, NFLPassRushStat, **_rusher(team="BUF"))

    midseason_trades.update_traded_player_team("Jon Rush", "MIN")

    with session_factory() as sess:
        row = sess.execute(select(NFLPassRushStat)).scalar_one()

    assert row.team_code == "MIN"
    assert "Moved" in capsys.readouterr().out


def test_a_traded_lineman_moves_to_the_new_team(session_factory):
    _add(
        session_factory,
        NFLPassBlockStat,
        season=SEASON,
        position="T",
        team_code="MIA",
        player_id=5,
        player="Big Blocker",
        abbr_name="Big Blocker",
    )

    midseason_trades.update_traded_player_team("Big Blocker", "MIN")

    with session_factory() as sess:
        row = sess.execute(select(NFLPassBlockStat)).scalar_one()
    assert row.team_code == "MIN"


def test_an_unknown_team_changes_nothing(session_factory, capsys):
    _add(session_factory, NFLPassRushStat, **_rusher(team="BUF"))

    midseason_trades.update_traded_player_team("Jon Rush", "ZZZ")

    with session_factory() as sess:
        row = sess.execute(select(NFLPassRushStat)).scalar_one()

    assert row.team_code == "BUF"
    assert "not a team code" in capsys.readouterr().out


def test_an_unknown_player_changes_nothing(session_factory, capsys):
    _add(session_factory, NFLPassRushStat, **_rusher(player="Jon Rush"))

    midseason_trades.update_traded_player_team("Nobody Here", "MIN")

    with session_factory() as sess:
        row = sess.execute(select(NFLPassRushStat)).scalar_one()

    assert row.team_code == "BUF"
    message = capsys.readouterr().out
    assert str(SEASON) in message and "nothing updated" in message


def test_a_prior_season_is_not_touched(session_factory, capsys):
    _add(session_factory, NFLPassRushStat, **_rusher(team="BUF", season=SEASON - 1))

    midseason_trades.update_traded_player_team("Jon Rush", "MIN")

    with session_factory() as sess:
        row = sess.execute(select(NFLPassRushStat)).scalar_one()

    assert row.team_code == "BUF"
    assert "nothing updated" in capsys.readouterr().out


def test_several_trades_apply_in_one_call(session_factory):
    _add(
        session_factory,
        NFLPassRushStat,
        **_rusher(player="Jon Rush", team="BUF", player_id=1),
    )

    _add(
        session_factory,
        NFLPassRushStat,
        **_rusher(player="Max Edge", team="MIA", player_id=2),
    )

    midseason_trades.update_traded_players(("Jon Rush", "MIN"), ("Max Edge", "PHI"))

    with session_factory() as sess:
        by_name = {
            row.player: row.team_code
            for row in sess.execute(select(NFLPassRushStat)).scalars()
        }

    assert by_name == {"Jon Rush": "MIN", "Max Edge": "PHI"}


def test_a_bad_entry_is_skipped_and_the_rest_still_run(session_factory, capsys):
    _add(
        session_factory,
        NFLPassRushStat,
        **_rusher(player="Jon Rush", team="BUF", player_id=1),
    )

    _add(
        session_factory,
        NFLPassRushStat,
        **_rusher(player="Max Edge", team="MIA", player_id=2),
    )

    midseason_trades.update_traded_players(("Ghost Player", "MIN"), ("Max Edge", "PHI"))

    with session_factory() as sess:
        by_name = {
            row.player: row.team_code
            for row in sess.execute(select(NFLPassRushStat)).scalars()
        }

    assert by_name == {"Jon Rush": "BUF", "Max Edge": "PHI"}
    assert "nothing updated" in capsys.readouterr().out
