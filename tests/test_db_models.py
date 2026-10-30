"""The NFL tables: nfl prefix on every table, constraint and index name, and the player_id key."""

from __future__ import annotations
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from database.db_models import Base, NFLPassBlockStat, NFLPassRushStat, NFLTeam

STAT_TABLES = {
    "nfl_pass_rush_stats": ("pr", NFLPassRushStat),
    "nfl_pass_block_stats": ("pb", NFLPassBlockStat),
}


def _engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def test_every_table_name_starts_with_nfl():
    assert set(Base.metadata.tables) == {"nfl_teams", *STAT_TABLES}


def test_every_constraint_and_index_name_carries_the_nfl_prefix():
    for name, (short, _model) in STAT_TABLES.items():
        table = Base.metadata.tables[name]
        names = {c.name for c in table.constraints if c.name} | {
            i.name for i in table.indexes
        }

        assert names == {
            f"uq_nfl_{short}_season_position_player_id",
            f"idx_nfl_{short}_filter",
            f"idx_nfl_{short}_player_id",
        }


def test_the_unique_key_is_season_position_player_id():
    inspector = inspect(_engine())
    for name in STAT_TABLES:
        (unique,) = inspector.get_unique_constraints(name)
        assert unique["column_names"] == ["season", "position", "player_id"]


def test_player_id_cannot_be_null():
    inspector = inspect(_engine())
    for name in STAT_TABLES:
        column = next(
            c for c in inspector.get_columns(name) if c["name"] == "player_id"
        )
        assert column["nullable"] is False


def test_pass_rush_table_has_the_pass_cov_percent_columns_and_the_block_table_does_not():
    inspector = inspect(_engine())
    rush = {c["name"] for c in inspector.get_columns("nfl_pass_rush_stats")}
    block = {c["name"] for c in inspector.get_columns("nfl_pass_block_stats")}

    assert {"pass_cov_percent", "tps_pass_cov_percent"} <= rush
    assert not {c for c in block if "pass_cov_percent" in c or "pass_rush_percent" in c}


@pytest.mark.parametrize(
    "same_player_other_team", [False, True], ids=["same-team", "other-team"]
)
def test_a_second_row_for_the_same_season_position_and_player_id_is_rejected(
    same_player_other_team,
):
    sessionmaker_ = sessionmaker(_engine())

    with sessionmaker_() as sess:
        sess.add_all(
            [
                NFLTeam(code="BUF", full_name="Buffalo Bills"),
                NFLTeam(code="MIA", full_name="Miami Dolphins"),
            ]
        )

        def row(team):
            return NFLPassRushStat(
                season=2025,
                position="ED",
                team_code=team,
                player_id=7,
                player="A. Player",
                abbr_name="A. Player",
            )

        sess.add(row("BUF"))
        sess.add(row("MIA" if same_player_other_team else "BUF"))

        with pytest.raises(IntegrityError):
            sess.commit()


def test_the_same_player_id_may_appear_in_another_season_or_position():
    sessionmaker_ = sessionmaker(_engine())

    with sessionmaker_() as sess:
        sess.add(NFLTeam(code="BUF", full_name="Buffalo Bills"))

        for season, position in ((2024, "ED"), (2025, "ED"), (2025, "DI")):
            sess.add(
                NFLPassRushStat(
                    season=season,
                    position=position,
                    team_code="BUF",
                    player_id=7,
                    player="A. Player",
                    abbr_name="A. Player",
                )
            )

        sess.commit()
        assert sess.query(NFLPassRushStat).count() == 3


def test_model_columns_match_the_column_spec():
    """The mixins' columns are exactly the identity columns plus the spec's attributes.

    This keeps the single source in `database/columns.py`: a metric added there
    (and so to the ingestion and the API) must be given a model column too.
    """
    from database.columns import PASS_BLOCK_DATA_COLUMNS, PASS_RUSH_DATA_COLUMNS

    identity = {
        "id",
        "season",
        "position",
        "team_code",
        "player_id",
        "player",
        "abbr_name",
    }

    for model, data_columns in (
        (NFLPassRushStat, PASS_RUSH_DATA_COLUMNS),
        (NFLPassBlockStat, PASS_BLOCK_DATA_COLUMNS),
    ):
        table_columns = {column.name for column in model.__table__.columns}
        expected = identity | {column.attr for column in data_columns}
        assert table_columns == expected, model.__name__
