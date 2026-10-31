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
   metrics (Havoc Rate, Pressure Rate, and their TPS/"true pass set" variants) through the shared
   `percent_of()` helper in `preprocess.py`, split by position
   into separate sheets written by the shared `write_position_sheets()` helper, and write `data/nfl/{front_7_pass_rush,ol_pass_block}/{season}.xlsx` (`config.NFL_DATA_PATH`; the `League` enum in `config.py` picks the league's folder, `data/ncaaf/` for the college side, and `preprocessing/preprocess.py` also builds the paths and checks the required columns first).

3. `database/db_ingestion.py --league {nfl,ncaaf}` (the league is required) reads those xlsx workbooks and upserts rows into that league's tables: `nfl_pass_rush_stats` /
   `nfl_pass_block_stats`, or `ncaaf_pass_rush_stats` / `ncaaf_pass_block_stats`. One `ingest_category()` body loads every category, driven by a `_Category`
   descriptor (`LEAGUE_CATEGORIES` lists each league's two); the required-column check and the row building read the one column declaration in
   `database/columns.py` (`ingest_pass_rush` / `ingest_pass_block` and the `ingest_ncaaf_*` pair remain as thin wrappers). The NFL team key is the `Team` code; the college key is the workbook's `Franchise Id` (into `team_code`), and each college row also carries the `Conference` attached at conversion. The league's team table is filled first (`LEAGUE_TEAM_UPSERTS`: `nfl_teams` from `teams/nfl.py`, `ncaaf_teams` from `teams/ncaaf.py`, colours unset). Every row carries PFF's `player_id` (NOT NULL; a null Player Id or a missing required column raises `ValueError`), and the unique key is `(season, position, player_id)`. It's idempotent by deleting all rows for a given `(season, position)` slice
   and bulk-reinserting — simpler and dialect-portable vs. per-row upsert. Must be run from the
   repo root; it locates the repo root by walking up for a `.gitignore` marker, and resolves the
   data directory via `--data-dir` / `LINESHINES_DATA_DIR` / `LINESHINES_REPO_ROOT` env vars, in
   that precedence order. `--seasons`' default is no longer a hardcoded list —
   `_discover_seasons()` scans both category subdirs of the league's folder for `{season}.xlsx` files (a clean 4-digit-year
   stem; `.csv` and any malformed filename are skipped, not erred on) and takes the **union** across
   `front_7_pass_rush`/`ol_pass_block`, since the two categories have no joint table and it's fine
   for one to get a season's file before the other. It runs after the arguments are parsed, so
   `--data-dir` is honoured; an explicit `--seasons` still overrides it.
   **Career members (college only).** The college run ends by rebuilding `ncaaf_pass_rush_career_members` and
   `ncaaf_pass_block_career_members` (`database/career.py`: `player_id` and a `CareerStatus`), whole, never
   incrementally. `Joined NFL` = the `player_id` also in the NFL table of the same category; `Potential
   Draftees` = a row in `MAX(season)` of the college table (read from the table, never from `--seasons`) and
   not Joined NFL. The NFL run never rebuilds them, so run the NFL ingestion first when both run. The college
   pass-rush table also keeps four snap counts (`pass_rush_snaps`, `pass_play_snaps` and the TPS pair) that
   only the Career merge reads; they are not in `PASS_RUSH_DATA_COLUMNS` and never in the API payload.

4. `database/db_models.py` defines the SQLAlchemy schema (`NFLTeam`, `NFLPassRushStat`, `NFLPassBlockStat`; the `nfl_` prefix leaves room for NCAAF tables). The stat tables take their
   columns from mixins — `StatIdentityMixin` (id, season, position, player_id, player, abbr_name, games),
   `PassRushMetricsMixin` and `PassBlockMetricsMixin` — so the college tables can reuse them later; only the
   team foreign key and the table-level names stay per class. The metric attributes match the single column
   declaration in `database/columns.py` (a test asserts this), which also drives the
   `pass_rush_row_to_dict` / `pass_block_row_to_dict` serializers via `row_to_payload()`. The serializers
   intentionally reproduce PFF's original space-and-mixed-case column names (e.g. `"PR Opp"`, `"TPS Havoc Rate"`)
   in the API JSON payload — this keeps the frontend's key names stable across the CSV→xlsx→DB migration.

5. `main.py` is the FastAPI app. The three data endpoints are built by `build_api_router(league)`, a
   factory that takes a `_LeagueApi` (the league, its team model and key, its two `_CategoryApi` category
   configs) and returns an `APIRouter` with `/metadata`, `/pass_rush` and `/pass_block`. One router per
   league is mounted under its own prefix: `/api/nfl/...` and `/api/ncaaf/...` (the old unprefixed
   `/api/metadata` etc. no longer exist). Endpoints are season-filtered and DB-backed; `position` is an
   *optional* query param — omitted, it returns every position in the category in one response. The college
   metadata adds `conference_order` and `team_conferences` (`{season: {franchise_id: conference}}`, read from
   the loaded rows), and its `teams` are keyed by franchise id with no colour (the frontend falls back to a
   neutral grey). College thresholds are their own (`NCAAF_DEFAULT_THRESHOLDS` 230 / 360 and
   `NCAAF_DYNAMIC_THRESHOLDS` in `config.py`). Measured on the real data (2025/2026): the biggest college
   response (pass rush) is about 500 KB raw against about 150 KB for the NFL (the app does not compress
   responses). `/health` stays a plain route.
   The pages: `PAGES` lists each page (`/` NFL Season, `/ncaaf-season` NCAAF Season), its league, subtitle
   (eyebrow), tab title and navigation label; `render_page()` fills them into `index.html` together with the
   navigation and the `window.LEAGUE` object the frontend reads (see `FRONTEND-STRUCTURE.md`). It also mounts `frontend/` as static
   files (mounted *last* so `/api/*` routes take precedence) and `frontend/images/team_logos/`
   under `/logos/` (NFL logos at `/logos/nfl/{team code}.png`, NCAAF logos at `/logos/ncaaf/{franchise_id}.png`). `index.html` is served through `render_page()`, which replaces `{{VERSION}}`
   with the Railway commit SHA for cache-busting on deploy, plus the per-page placeholders above.

**Team codes** follow PFF's spellings (e.g. `ARZ`, `BLT`, `CLV`, `HST`, not the more common
`ARI`/`BAL`/`CLE`/`HOU`), defined once in `teams/nfl.py` and used by both ingestion (team
upsert) and `/api/nfl/metadata` (colors, full names) — the frontend never hardcodes team data.

**Deploy**: Railway, per `Procfile` (`uvicorn main:app`). `RAILWAY_GIT_COMMIT_SHA` env var drives
frontend cache-busting; `DATABASE_URL` (Postgres, `postgres://` scheme) is rewritten in
`database/session.py` (`_resolve_database_url`, which also holds the engine and `SessionLocal`) to
`postgresql+psycopg://` for the psycopg3 driver.

**Adding a nullable column to `db_models.py` requires a manual `ALTER TABLE` against the live
Railway Postgres** — `Base.metadata.create_all(engine)` (see "Tests" below) only creates tables
that don't exist yet; it never diffs or alters columns on a table already present, so a schema
change reaches local sqlite for free (delete `data/lines_shines.db`, `create_all` rebuilds it) but
not production. There's no Alembic yet, so this is a one-off DDL statement run by hand against
`DATABASE_URL` (e.g. via `psql`, or a throwaway `python -c` using this repo's own already-resolved
`main.engine` if `psql` isn't installed locally) — not something that lives in the repo, same spirit
as hand-editing `DYNAMIC_THRESHOLDS` each season. Precedent: `prp`/`tps_prp`
(`nfl_pass_rush_stats`)/`pbe`/`tps_pbe` (`nfl_pass_block_stats`) were added this way when those metrics
landed. After the `ALTER TABLE`, re-run `python -m database.db_ingestion --league <league>` against that same
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
