"""Point a traded player at his new team mid-season, between weekly ingests.

The NFL trade deadline is always in early November, so the season is simply the
current calendar year and needs no argument. Like `database/db_ingestion.py`,
this updates whichever database `DATABASE_URL` points at (the local SQLite file
by default, or Railway Postgres when the env var is set), so export it first.

Usage:
    export DATABASE_URL=...   # omit to update the local SQLite file
    python -c "from database.midseason_trades import update_traded_player_team as move; move('Jonathan Allen', 'MIN')"

Several at once, each an independent (player, team) pair:
    python -c "from database.midseason_trades import update_traded_players as moves; moves(('Jonathan Allen', 'MIN'), ('Za Darius Smith', 'PHI'))"
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import update

from database.db_models import NFLPassBlockStat, NFLPassRushStat
from database.session import SessionLocal
from teams.nfl import TEAMS

# A player sits in exactly one category, so updating both touches only his rows.
_STAT_MODELS = (NFLPassRushStat, NFLPassBlockStat)


def update_traded_player_team(player_name: str, new_team: str) -> None:
    """Set a player's team for the current season; print and change nothing if off.

    The season is the current calendar year. A wrong team code, a wrong player
    name, or a season not ingested yet all end the same way: a message is printed
    and no row is changed.
    """
    season = date.today().year

    if new_team not in TEAMS:
        print(f"{new_team!r} is not a team code; nothing updated.")
        return

    with SessionLocal() as sess:
        updated_rows = 0
        for model in _STAT_MODELS:
            result = sess.execute(
                update(model)
                .where(model.season == season, model.player == player_name)
                .values(team_code=new_team)
            )
            updated_rows += result.rowcount

        if updated_rows == 0:
            print(f"No {season} player named {player_name!r}; nothing updated.")
            return

        sess.commit()

    full_name = TEAMS[new_team][0]
    print(
        f"Moved {player_name!r} to {new_team} ({full_name}) for {season}: "
        f"{updated_rows} row(s) updated."
    )


def update_traded_players(*trades: tuple[str, str]) -> None:
    """Apply several trades in one call, each an independent (player, team) pair.

    A bad entry (unknown team, or no such player this season) is reported and
    skipped while the rest still run, the same continue-on-error habit as the
    preprocessing command line.
    """
    for player_name, new_team in trades:
        update_traded_player_team(player_name, new_team)
