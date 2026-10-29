"""SQLAlchemy models for the Game of Trenches database.

Portable across SQLite (local dev) and PostgreSQL (Railway prod) —
the only dialect-specific concern is autoincrement, which SQLAlchemy
handles transparently for `Integer` primary keys.

Every NFL table, constraint and index carries an `nfl` prefix (`nfl_teams`,
`uq_nfl_pr_...`, `idx_nfl_pb_...`) so the college tables can sit beside them
in the same database as `ncaaf_...`. The stat tables are keyed by PFF's
`player_id` (one row per player per season and position), which is also the
id the college files use.
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


class Base(DeclarativeBase):
    pass


class NFLTeam(Base):
    __tablename__ = "nfl_teams"

    code = Column(String(4), primary_key=True)
    full_name = Column(String, nullable=False)
    primary_color = Column(String(7))  # Hex like "#0085CA".

    pass_rush_stats = relationship("NFLPassRushStat", back_populates="team")
    pass_block_stats = relationship("NFLPassBlockStat", back_populates="team")


class NFLPassRushStat(Base):
    __tablename__ = "nfl_pass_rush_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    season = Column(Integer, nullable=False)

    position = Column(String(4), nullable=False)  # DI / ED.
    team_code = Column(String(4), ForeignKey("nfl_teams.code"), nullable=False)
    player_id = Column(Integer, nullable=False)  # PFF player id.
    player = Column(String, nullable=False)
    abbr_name = Column(String, nullable=False)

    games = Column(Integer)
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


class NFLPassBlockStat(Base):
    __tablename__ = "nfl_pass_block_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    season = Column(Integer, nullable=False)

    position = Column(String(4), nullable=False)  # T / G / C.
    team_code = Column(String(4), ForeignKey("nfl_teams.code"), nullable=False)
    player_id = Column(Integer, nullable=False)  # PFF player id.
    player = Column(String, nullable=False)
    abbr_name = Column(String, nullable=False)

    games = Column(Integer)
    non_spike_pb_snaps = Column(Integer)  # Non Spike PB Snaps.
    tps_non_spike_pb_snaps = Column(Integer)  # TPS Non Spike PB Snaps.

    allowed_pressure_pct = Column(Float)  # Allowed Pressure %.
    tps_allowed_pressure_pct = Column(Float)  # TPS Allowed Pressure %.

    allowed_havoc_pct = Column(Float)  # Allowed Havoc %.
    tps_allowed_havoc_pct = Column(Float)  # TPS Allowed Havoc %.

    pbe = Column(Float)  # PBE.
    tps_pbe = Column(Float)  # TPS PBE.

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
# preserved so no client-side renaming is needed).


def pass_rush_row_to_dict(row: NFLPassRushStat) -> dict:
    return {
        "id": row.id,
        "season": row.season,
        "position": row.position,
        "team": row.team_code,
        "player_id": row.player_id,
        "player": row.player,
        "abbr_name": row.abbr_name,
        "games": row.games,
        "PR Opp": row.pr_opp,
        "TPS PR Opp": row.tps_pr_opp,
        "Pass Cov Percent": row.pass_cov_percent,
        "TPS Pass Cov Percent": row.tps_pass_cov_percent,
        "Win Rate": row.win_rate,
        "TPS Win Rate": row.tps_win_rate,
        "Pressure Rate": row.pressure_rate,
        "TPS Pressure Rate": row.tps_pressure_rate,
        "Havoc Rate": row.havoc_rate,
        "TPS Havoc Rate": row.tps_havoc_rate,
        "PRP": row.prp,
        "TPS PRP": row.tps_prp,
    }


def pass_block_row_to_dict(row: NFLPassBlockStat) -> dict:
    return {
        "id": row.id,
        "season": row.season,
        "position": row.position,
        "team": row.team_code,
        "player_id": row.player_id,
        "player": row.player,
        "abbr_name": row.abbr_name,
        "games": row.games,
        "Non Spike PB Snaps": row.non_spike_pb_snaps,
        "TPS Non Spike PB Snaps": row.tps_non_spike_pb_snaps,
        "Allowed Pressure %": row.allowed_pressure_pct,
        "TPS Allowed Pressure %": row.tps_allowed_pressure_pct,
        "Allowed Havoc %": row.allowed_havoc_pct,
        "TPS Allowed Havoc %": row.tps_allowed_havoc_pct,
        "PBE": row.pbe,
        "TPS PBE": row.tps_pbe,
    }
