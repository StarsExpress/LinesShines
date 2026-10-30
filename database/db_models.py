"""SQLAlchemy models for the Game of Trenches database.

Portable across SQLite (local dev) and PostgreSQL (Railway prod) —
the only dialect-specific concern is autoincrement, which SQLAlchemy
handles transparently for `Integer` primary keys.

Every NFL table, constraint and index carries an `nfl` prefix (`nfl_teams`,
`uq_nfl_pr_...`, `idx_nfl_pb_...`) so the college tables can sit beside them
in the same database as `ncaaf_...`. The stat tables are keyed by PFF's
`player_id` (one row per player per season and position), which is also the
id the college files use.

The identity and metric columns live in mixins (`StatIdentityMixin`,
`PassRushMetricsMixin`, `PassBlockMetricsMixin`) so the college tables can reuse
them in a later PR; only the team foreign key and the table-level names differ
per league. The metric attributes match `database/columns.py` (checked by a test),
which also drives the API serializers below.
"""

from __future__ import annotations

from sqlalchemy import (
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship

from database.columns import (
    PASS_BLOCK_DATA_COLUMNS,
    PASS_RUSH_DATA_COLUMNS,
    row_to_payload,
)


class Base(DeclarativeBase):
    pass


class StatIdentityMixin:
    """Columns every stat row carries, whatever the league or category.

    The team foreign key is left to each table, because it points at that
    league's team table (`nfl_teams` here, `ncaaf_teams` later).
    """

    id = Column(Integer, primary_key=True, autoincrement=True)
    season = Column(Integer, nullable=False)

    position = Column(String(4), nullable=False)  # DI / ED, or T / G / C.
    player_id = Column(Integer, nullable=False)  # PFF player id.
    player = Column(String, nullable=False)
    abbr_name = Column(String, nullable=False)

    games = Column(Integer)


class PassRushMetricsMixin:
    """The front-7 pass-rush metric columns (see `PASS_RUSH_DATA_COLUMNS`)."""

    pr_opp = Column(Integer)  # PR Opp.
    tps_pr_opp = Column(Integer)  # TPS PR Opp.

    pass_cov_percent = Column(Float)  # Pass Cov Percent = 100 - Pass Rush Percent.
    tps_pass_cov_percent = Column(Float)  # TPS Pass Cov Percent.

    win_rate = Column(Float)  # Win Rate.
    tps_win_rate = Column(Float)  # TPS Win Rate.

    pressure_rate = Column(Float)  # Pressure Rate.
    tps_pressure_rate = Column(Float)  # TPS Pressure Rate.

    havoc_rate = Column(Float)  # Havoc Rate.
    tps_havoc_rate = Column(Float)  # TPS Havoc Rate.

    prp = Column(Float)  # PRP.
    tps_prp = Column(Float)  # TPS PRP.


class PassBlockMetricsMixin:
    """The offensive-line pass-block metric columns (see `PASS_BLOCK_DATA_COLUMNS`)."""

    non_spike_pb_snaps = Column(Integer)  # Non Spike PB Snaps.
    tps_non_spike_pb_snaps = Column(Integer)  # TPS Non Spike PB Snaps.

    allowed_pressure_pct = Column(Float)  # Allowed Pressure %.
    tps_allowed_pressure_pct = Column(Float)  # TPS Allowed Pressure %.

    allowed_havoc_pct = Column(Float)  # Allowed Havoc %.
    tps_allowed_havoc_pct = Column(Float)  # TPS Allowed Havoc %.

    pbe = Column(Float)  # PBE.
    tps_pbe = Column(Float)  # TPS PBE.


class NFLTeam(Base):
    __tablename__ = "nfl_teams"

    code = Column(String(4), primary_key=True)
    full_name = Column(String, nullable=False)
    primary_color = Column(String(7))  # Hex like "#0085CA".

    pass_rush_stats = relationship("NFLPassRushStat", back_populates="team")
    pass_block_stats = relationship("NFLPassBlockStat", back_populates="team")


class NFLPassRushStat(StatIdentityMixin, PassRushMetricsMixin, Base):
    __tablename__ = "nfl_pass_rush_stats"

    team_code = Column(String(4), ForeignKey("nfl_teams.code"), nullable=False)

    team = relationship("NFLTeam", back_populates="pass_rush_stats")

    __table_args__ = (
        UniqueConstraint(
            "season",
            "position",
            "player_id",
            name="uq_nfl_pr_season_position_player_id",
        ),
        Index("idx_nfl_pr_filter", "season", "position"),
        Index("idx_nfl_pr_player_id", "player_id"),
    )


class NFLPassBlockStat(StatIdentityMixin, PassBlockMetricsMixin, Base):
    __tablename__ = "nfl_pass_block_stats"

    team_code = Column(String(4), ForeignKey("nfl_teams.code"), nullable=False)

    team = relationship("NFLTeam", back_populates="pass_block_stats")

    __table_args__ = (
        UniqueConstraint(
            "season",
            "position",
            "player_id",
            name="uq_nfl_pb_season_position_player_id",
        ),
        Index("idx_nfl_pb_filter", "season", "position"),
        Index("idx_nfl_pb_player_id", "player_id"),
    )


# Serialization helpers used by main.py to keep API payload shape
# identical to what frontend already expects (space-and-mixed-case keys
# preserved so no client-side renaming is needed). Both read the one
# column declaration in database/columns.py.


def pass_rush_row_to_dict(row: NFLPassRushStat) -> dict:
    return row_to_payload(row, PASS_RUSH_DATA_COLUMNS)


def pass_block_row_to_dict(row: NFLPassBlockStat) -> dict:
    return row_to_payload(row, PASS_BLOCK_DATA_COLUMNS)
