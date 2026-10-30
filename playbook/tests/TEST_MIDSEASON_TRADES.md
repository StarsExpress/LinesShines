# test_midseason_trades.py

> **Add tests here when:** changing `database/midseason_trades.py` (`update_traded_player_team`, `update_traded_players`): how it finds the player, which season it targets, team validation, or the messages it prints.

- **Kind:** pure Python.
- **Needs:** nothing. An in-memory SQLite database and synthetic rows; `SessionLocal` is monkeypatched, so no real database is touched.
- **Covers:** a traded front-7 player and a traded offensive lineman both move to the new team for the current season; an unknown team code changes nothing and says so; an unknown player name changes nothing and names the season; a prior season's row is left alone (the season is the current calendar year, not a parameter); `update_traded_players` applies several pairs in one call and skips a bad entry while the rest still run.
- **Not here:** the live Postgres update path, which is the same code against `DATABASE_URL` (checked by hand).
- **Known gaps:** none recorded.
