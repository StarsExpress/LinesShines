# Invariants

Statements that must stay true after any change. Treat each as an acceptance check: if a change could
affect one, verify it before reporting done. "Coverage" says what actually enforces it today.
Where coverage is "none", adding a test is welcome, but only add tests with synthetic data.

## Working rules

These apply to every task. Read them before starting.

- **Git**: the owner reviews, pushes and opens PRs. Never run git commands.
- **Order of work**: explore (read-only) → design → implement → verify → report. If the task contradicts the code or `playbook/`, stop and report; do not redesign on your own.
- **What to work on**: only the file in `next_steps/` that the owner names. Never act on anything in `discussions/`.
- **Done means the whole CI set passes locally**: `pytest -v`, `black -S .`, `npm run lint:js`, `npm run format:js:check`. Not a single test file.
- **Tests**: when adding a feature or fixing a bug, add the test to the file `playbook/tests/INDEX.md` points to. If none fits, create a new `tests/test_*.py` and its `playbook/tests/TEST_*.md` in the same change. A test file without its document is incomplete.
- **Say what you could not verify** (touch, pinch-zoom, standalone mode, real phone). The owner tests those by hand over the LAN IP.
- **PFF data**: raw CSV/xlsx never enters the repo; test fixtures are synthetic only.
- **Frontend**: zero npm runtime dependencies, no build step, no framework. `html2canvas` is the one vendored exception.
- **Odd-looking code**: check `DECISIONS.md` before "fixing" it.
- **Record decisions** in `DECISIONS.md` (dated), not in `CLAUDE.md`.
- **Versioning**: `vSEASON.MINOR.PATCH`; features = MINOR, weekly data refresh = PATCH. MAJOR is reserved for a change of product identity; new-season data alone does not bump MAJOR.

## Invariants

| # | Invariant | Detail | Coverage |
|---|---|---|---|
| 1 | A percentile is computed only within the same season, same threshold and **exact** position. A Guard's percentile is identical whichever position is selected on the chart. | `architecture/PERCENTILES.md` | none |
| 2 | Tied players share one rank and one percentile (competition ranking). Every percentile in the app funnels through `rankAndPercentile()`. | `architecture/PERCENTILES.md` | none |
| 3 | Teams and Players combine by union (OR). Teams only highlights; it never changes the pool. The threshold is a hard gate. | `architecture/FILTERS-AND-SEARCH.md` | none |
| 4 | The chart changes only on Apply; the Players search pool stays live and never reads `currentRecords`. | `architecture/FILTERS-AND-SEARCH.md` | none |
| 5 | The threshold is display-only: preprocessing never drops rows by it and every row is ingested. | `architecture/THRESHOLDS.md` | `tests/test_config.py` covers routing only |
| 6 | `higher_is_better` is per metric. PBE and TPS PBE are higher-is-better. | `architecture/METRICS-AND-NOTES.md` | `test_metadata_shape` (shape only) |
| 7 | `/api/*` and `/health` are never cached by the Service Worker. The rule matches the whole `/api/` prefix, so a new route is covered automatically; `/health` matches exactly (plus anything under `/health/`), so `/healthy.css` is still cached. | `architecture/PWA.md` | `tests/test_app_startup.py::test_sw_js_never_caches_any_api_route`, `tests/test_sw_cache_bypass.py` |
| 8 | `/` is always the NFL page; the PWA `start_url` stays `/`. | `architecture/PWA.md` | none |
| 9 | Pinned Players: Category or Position change clears everything; any other change removes only players who no longer fit; a Comparison shrinks while 2+ members remain and dissolves below 2. | `architecture/PINNED-INVALIDATION.md` | `tests/test_pinned_impact.py` |
| 10 | Merge Cards show percentiles only (never raw values or `#rank/N`), cap at 5 players, and the 8-player Workspace quota is checked once, at Submit. | `architecture/CARDS.md` | none |
| 11 | Linemate roster excludes the anchor unless "include anchor" is on; RSWA uses uncapped raw snaps. | `architecture/CARDS.md` | none |
| 12 | Every PNG export carries the footer "Source: PFF Premium Stats" (`EXPORT_FOOTER_TEXT`). | `frontend/chart-export.js` | none |
| 13 | PFF raw CSV/xlsx never enters the repo. | `.gitignore` ignores `*.csv` and `*.xlsx` | `.gitignore` only; no test |
| 14 | Ingestion is idempotent: it deletes and reinserts a whole `(season, position)` slice. | `architecture/BACKEND-AND-DEPLOY.md` | `tests/test_db_ingestion.py` |
| 15 | Tests set `DATABASE_URL` to an ephemeral sqlite file before `main` is imported. | `architecture/BACKEND-AND-DEPLOY.md` | `tests/conftest.py` |
| 16 | X/Y axis selection, the Player Names / Team Logos / Include metric notes toggles, fold state and card dragging never invalidate, clear or reset any card. Axis controls must not be wired into the shared "filter changed → reset" handler. | `architecture/PINNED-INVALIDATION.md` | none for the handler wiring (`tests/test_pinned_impact.py` covers filter-driven impact only) |
