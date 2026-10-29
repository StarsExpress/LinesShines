# conftest.py

> **Add tests here when:** you need a fixture shared by several test files, or you change how tests get a database or a running server.

- **Kind:** shared fixtures, not tests.
- **Order matters:** `DATABASE_URL` is pointed at an ephemeral sqlite file before anything imports `main`, because `main.py` resolves its engine at import time. Setting it inside a fixture would be too late.
- **Fixtures:**

| Fixture | What it gives you |
|---|---|
| `_create_tables` | Session-wide and automatic: creates the tables once. |
| `client` | A FastAPI `TestClient`. |
| `seeded_db` | Wipes the tables and loads a small deterministic set: 2 teams (BUF, MIA), pass-rush rows for ED and DI, pass-block rows for T and G, season 2025, written to the `nfl_*` tables with `player_id` (1001/1002 rush, 2001/2002 block) and Pass Cov Percent values (8/5 and 12/10, i.e. 100 minus the source Pass Rush Percent). |
| `live_server_url` | Starts the real app with uvicorn on a free port, on top of `seeded_db`, and yields its base URL. Shuts it down afterwards. |

- **Not here:** browser-session fixtures. Each browser test file defines its own `page` fixture today (whether to share one is under discussion).
- **Known gaps:** the seed has one player per position, so it cannot exercise ties, multi-team filters or percentile pools. A test for those needs its own data.
