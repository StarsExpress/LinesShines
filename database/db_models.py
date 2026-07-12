"""SQLAlchemy models for the Game of Trenches database.

Portable across SQLite (local dev) and PostgreSQL (Railway prod) —
the only dialect-specific concern is autoincrement, which SQLAlchemy
handles transparently for `Integer` primary keys.
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


class Team(Base):
    __tablename__ = "teams"

    code = Column(String(4), primary_key=True)
    full_name = Column(String, nullable=False)
    primary_color = Column(String(7))  # Hex like "#0085CA".

    pass_rush_stats = relationship("PassRushStat", back_populates="team")
    pass_block_stats = relationship("PassBlockStat", back_populates="team")


class PassRushStat(Base):
    __tablename__ = "pass_rush_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    season = Column(Integer, nullable=False)
    position = Column(String(4), nullable=False)  # DI / ED.
    team_code = Column(String(4), ForeignKey("teams.code"), nullable=False)
    player = Column(String, nullable=False)
    abbr_name = Column(String, nullable=False)

    games = Column(Integer)
    pr_opp = Column(Integer)  # PR Opp.
    tps_pr_opp = Column(Integer)  # TPS PR Opp.
    win_rate = Column(Float)  # Win Rate.
    tps_win_rate = Column(Float)  # TPS Win Rate.
    pressure_rate = Column(Float)  # Pressure Rate.
    tps_pressure_rate = Column(Float)  # TPS Pressure Rate.
    havoc_rate = Column(Float)  # Havoc Rate.
    tps_havoc_rate = Column(Float)  # TPS Havoc Rate.

    team = relationship("Team", back_populates="pass_rush_stats")

    __table_args__ = (
        UniqueConstraint(
            "season",
            "position",
            "player",
            "team_code",
            name="uq_pr_season_position_player_team",
        ),
        Index("idx_pr_filter", "season", "position"),
    )


class PassBlockStat(Base):
    __tablename__ = "pass_block_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    season = Column(Integer, nullable=False)
    position = Column(String(4), nullable=False)  # T / G / C
    team_code = Column(String(4), ForeignKey("teams.code"), nullable=False)
    player = Column(String, nullable=False)
    abbr_name = Column(String, nullable=False)

    games = Column(Integer)
    non_spike_pb_snaps = Column(Integer)  # Non Spike PB Snaps.
    tps_non_spike_pb_snaps = Column(Integer)  # TPS Non Spike PB Snaps.
    allowed_pressure_pct = Column(Float)  # Allowed Pressure %.
    tps_allowed_pressure_pct = Column(Float)  # TPS Allowed Pressure %.
    allowed_havoc_pct = Column(Float)  # Allowed Havoc %.
    tps_allowed_havoc_pct = Column(Float)  # TPS Allowed Havoc %.

    team = relationship("Team", back_populates="pass_block_stats")

    __table_args__ = (
        UniqueConstraint(
            "season",
            "position",
            "player",
            "team_code",
            name="uq_pb_season_position_player_team",
        ),
        Index("idx_pb_filter", "season", "position"),
    )


# Serialization helpers used by main.py to keep API payload shape
# identical to what frontend already expects (space-and-mixed-case keys
# preserved so no client-side renaming is needed). ---


def pass_rush_row_to_dict(row: PassRushStat) -> dict:
    return {
        "season": row.season,
        "position": row.position,
        "team": row.team_code,
        "player": row.player,
        "abbr_name": row.abbr_name,
        "games": row.games,
        "PR Opp": row.pr_opp,
        "TPS PR Opp": row.tps_pr_opp,
        "Win Rate": row.win_rate,
        "TPS Win Rate": row.tps_win_rate,
        "Pressure Rate": row.pressure_rate,
        "TPS Pressure Rate": row.tps_pressure_rate,
        "Havoc Rate": row.havoc_rate,
        "TPS Havoc Rate": row.tps_havoc_rate,
    }


def pass_block_row_to_dict(row: PassBlockStat) -> dict:
    return {
        "season": row.season,
        "position": row.position,
        "team": row.team_code,
        "player": row.player,
        "abbr_name": row.abbr_name,
        "games": row.games,
        "Non Spike PB Snaps": row.non_spike_pb_snaps,
        "TPS Non Spike PB Snaps": row.tps_non_spike_pb_snaps,
        "Allowed Pressure %": row.allowed_pressure_pct,
        "TPS Allowed Pressure %": row.tps_allowed_pressure_pct,
        "Allowed Havoc %": row.allowed_havoc_pct,
        "TPS Allowed Havoc %": row.tps_allowed_havoc_pct,
    }
