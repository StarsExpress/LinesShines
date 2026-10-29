# Backend, data pipeline, deploy and tests

> **Load when:** changing ingestion, DB schema/models, API routes, team codes, deploy, or tests.
> Split from the former CLAUDE.md "Architecture" section on 2026-10-17. The original text is kept, apart from a few small later edits and
> appended sections marked "carried over from the retired `BLUEPRINT.md`".
> Cross-references like "see X above/below" point to another file in this folder — look them up in `INDEX.md`.

**Pipeline: raw PFF export → preprocessing → xlsx → ingestion → DB → API → frontend.**

1. `data/nfl/front_7_pass_rush/{season}.csv` and `data/nfl/ol_pass_block/{season}.csv` are raw PFF exports
   (one row per player-season).

2. `preprocessing/preprocess.py --league nfl --seasons {season ...}` (both required) calls
   `preprocessing/front_7.py` and `preprocessing/offensive_line.py`, which each read the season CSV,
   rename PFF's snake_case columns to display names via `utils/renamers.py`, compute derived rate
   metrics (Havoc Rate, Pressure Rate, and their TPS/"true pass set" variants), split by position
   into separate sheets, and write `data/nfl/{front_7_pass_rush,ol_pass_block}/{season}.xlsx` (`config.NFL_DATA_PATH`; the `League` enum in `config.py` picks the league's folder, `data/ncaaf/` for the college side, and `preprocessing/preprocess.py` also builds the paths and checks the required columns first).

3. `database/db_ingestion.py` reads those xlsx workbooks and upserts rows into `nfl_pass_rush_stats` /
   `nfl_pass_block_stats`. Every row carries PFF's `player_id` (NOT NULL; a null Player Id or a missing required column raises `ValueError`), and the unique key is `(season, position, player_id)`. It's idempotent by deleting all rows for a given `(season, position)` slice
   and bulk-reinserting — simpler and dialect-portable vs. per-row upsert. Must be run from the
   repo root; it locates the repo root by walking up for a `.gitignore` marker, and resolves the
   data directory via `--data-dir` / `LINESHINES_DATA_DIR` / `LINESHINES_REPO_ROOT` env vars, in
   that precedence order. `--seasons`' default (`DEFAULT_SEASONS`) is no longer a hardcoded list —
   `_discover_seasons()` scans both category subdirs for `{season}.xlsx` files (a clean 4-digit-year
   stem; `.csv` and any malformed filename are skipped, not erred on) and takes the **union** across
   `front_7_pass_rush`/`ol_pass_block`, since the two categories have no joint table and it's fine
   for one to get a season's file before the other. Computed once at import time from the *default*
   data dir resolution (no `--data-dir` awareness at that point — argparse defaults are built before
   flags are parsed) — an explicit `--seasons` still overrides it either way, and `--data-dir` alone
   with `--seasons` omitted will scan the default location's `DEFAULT_SEASONS`, not the directory
   actually pointed at.

4. `database/db_models.py` defines the SQLAlchemy schema (`NFLTeam`, `NFLPassRushStat`, `NFLPassBlockStat`; the `nfl_` prefix leaves room for NCAAF tables)
   plus `pass_rush_row_to_dict` / `pass_block_row_to_dict` serializers that intentionally reproduce
   PFF's original space-and-mixed-case column names (e.g. `"PR Opp"`, `"TPS Havoc Rate"`) in the API
   JSON payload — this keeps the frontend's key names stable across the CSV→xlsx→DB migration.

5. `main.py` is the FastAPI app: `/api/metadata` (seasons, positions, metric definitions, teams),
   `/api/pass_rush`, `/api/pass_block` (season-filtered, DB-backed; `position` is an *optional*
   query param — omitted, it returns every position in the category in one response, filtered,
   it keeps the old single-position behavior), `/health`. It also mounts `frontend/` as static
   files (mounted *last* so `/api/*` routes take precedence) and `frontend/images/team_logos/`
   under `/logos/` (NFL logos at `/logos/nfl/{team code}.png`, NCAAF logos at `/logos/ncaaf/{franchise_id}.png`). `index.html` is served through a small handler that replaces `{{VERSION}}`
   with the Railway commit SHA for cache-busting on deploy.

**Team codes** follow PFF's spellings (e.g. `ARZ`, `BLT`, `CLV`, `HST`, not the more common
`ARI`/`BAL`/`CLE`/`HOU`), defined once in `teams/nfl.py` and used by both ingestion (team
upsert) and `/api/metadata` (colors, full names) — the frontend never hardcodes team data.

**Deploy**: Railway, per `Procfile` (`uvicorn main:app`). `RAILWAY_GIT_COMMIT_SHA` env var drives
frontend cache-busting; `DATABASE_URL` (Postgres, `postgres://` scheme) is rewritten in
`main._resolve_database_url` to `postgresql+psycopg://` for the psycopg3 driver.

**Adding a nullable column to `db_models.py` requires a manual `ALTER TABLE` against the live
Railway Postgres** — `Base.metadata.create_all(engine)` (see "Tests" below) only creates tables
that don't exist yet; it never diffs or alters columns on a table already present, so a schema
change reaches local sqlite for free (delete `data/lines_shines.db`, `create_all` rebuilds it) but
not production. There's no Alembic yet, so this is a one-off DDL statement run by hand against
`DATABASE_URL` (e.g. via `psql`, or a throwaway `python -c` using this repo's own already-resolved
`main.engine` if `psql` isn't installed locally) — not something that lives in the repo, same spirit
as hand-editing `DYNAMIC_THRESHOLDS` each season. Precedent: `prp`/`tps_prp`
(`nfl_pass_rush_stats`)/`pbe`/`tps_pbe` (`nfl_pass_block_stats`) were added this way when those metrics
landed. After the `ALTER TABLE`, re-run `python -m database.db_ingestion` against that same
`DATABASE_URL` to backfill the new column's values into every existing row (safe — ingestion
deletes+reinserts per `(season, position)` slice regardless of what changed).

**Tests** (`tests/`) use an ephemeral sqlite DB per session (`conftest.py`), a `seeded_db` fixture
with a couple of hand-built rows for API-level assertions, and FastAPI's `TestClient`. Real schema
migrations aren't set up yet — `Base.metadata.create_all(engine)` runs at app startup; the code
comments call out Alembic as the intended path once the schema needs to evolve. `conftest.py` also
provides `live_server_url` (uvicorn on a free port in a daemon thread, over the seeded test DB) for
the Playwright browser tests (`test_teams_info_popover.py`, `test_install_links.py`,
`test_popup_position.py`); pure frontend functions with no JS test runner in the repo are
unit-tested by importing the served module inside Chromium (`import('/popup-position.js')`). Headless
Chromium can't emulate `display-mode: standalone` or pinch-zoom, so those are covered by checking the
served CSS rule and by firing synthetic `visualViewport` events respectively.
