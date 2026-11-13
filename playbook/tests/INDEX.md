# Tests index

> **Load when:** you add a feature or fix a bug and need to know which test file to extend, or whether a new test file is needed.

Every script in `tests/` has a matching document in this folder with the same name in upper case (`tests/test_pinned_impact.py` → `TEST_PINNED_IMPACT.md`), and `conftest.py` has `CONFTEST.md`.
The third line of each document starts with "Add tests here when:", so all of them can be scanned at once:

```bash
grep -H "Add tests here when" playbook/tests/*.md
```

## Which test file for which change

| Change | Add the test to | Kind |
|---|---|---|
| A shared fixture, or how tests get a database or a running server | `conftest.py` ([CONFTEST.md](CONFTEST.md)) | fixtures |
| A JSON API endpoint under `/api/` (parameters, response shape, error codes) | `test_api_endpoints.py` ([doc](TEST_API_ENDPOINTS.md)) | API |
| How the app is assembled: mounts, `/health`, how `sw.js` and `index.html` are served | `test_app_startup.py` ([doc](TEST_APP_STARTUP.md)) | API |
| Season-threshold routing in `config/thresholds.py` | `test_config.py` ([doc](TEST_CONFIG.md)) | pure Python |
| Who is on the college Career page (Joined NFL, Prospects) and how the members are rebuilt | `test_career_members.py` ([doc](TEST_CAREER_MEMBERS.md)) | pure Python |
| The merged Career row (summed counts, weighted rates, Pass Cov Percent, last-season identity) and the `/api/ncaaf/career` routes | `test_career_merge.py` ([doc](TEST_CAREER_MERGE.md)) | pure Python and API |
| The page remembering the last axes (per category and position) and switches, per View | `test_remembered_choices.py` ([doc](TEST_REMEMBERED_CHOICES.md)) | browser |
| The NCAAF Career Teams checklist (a school that changed conference is one entry per conference; Latu, Broughton) | `test_ncaaf_career_teams.py` ([doc](TEST_NCAAF_CAREER_TEAMS.md)) | browser |
| The NCAAF Career page (Status Filter, two threshold bars, one pool) | `test_ncaaf_career_page.py` ([doc](TEST_NCAAF_CAREER_PAGE.md)) | browser |
| Ingestion: file path resolution, replacing a season/position slice | `test_db_ingestion.py` ([doc](TEST_DB_INGESTION.md)) | pure Python |
| The `nfl_*` table names, unique key, NOT NULL `player_id`, and which table has the pass-rush percent columns | `test_db_models.py` ([doc](TEST_DB_MODELS.md)) | pure Python |
| Neutral metrics: Pass Cov Percent order, grey chip on Player/Comparison/Linemate cards, chip contrast | `test_neutral_metric.py` ([doc](TEST_NEUTRAL_METRIC.md)) | browser |
| The league handling of the preprocessing scripts: `League`, per-league paths, the required-column check, the command line | `test_preprocessing_league.py` ([doc](TEST_PREPROCESSING_LEAGUE.md)) | pure Python |
| The NCAAF conference table: a school's stints per conference, `conference_of()`, the out-of-scope list | `test_teams_ncaaf.py` ([doc](TEST_TEAMS_NCAAF.md)) | pure Python |
| Updating a traded player's team mid-season (`midseason_trades.py`) | `test_midseason_trades.py` ([doc](TEST_MIDSEASON_TRADES.md)) | pure Python |
| The folder layout of `data/` and `frontend/` | `test_paths.py` ([doc](TEST_PATHS.md)) | pure Python |
| The Comparison (Merge) Card's table: Read and Sort layouts, and how it follows the sort order | `test_merge_table.py` ([doc](TEST_MERGE_TABLE.md)) | browser |
| How percentiles, ranks and percentile pools are computed | `test_percentiles.py` ([doc](TEST_PERCENTILES.md)) | browser |
| Which players the chart plots or highlights from Teams, Players and the threshold | `test_filters.py` ([doc](TEST_FILTERS.md)) | browser |
| What happens to Pinned Players and Comparisons when filters change, and who stays eligible in the Players filter | `test_pinned_impact.py` ([doc](TEST_PINNED_IMPACT.md)) | browser |
| Popup placement and closing on viewport change | `test_popup_position.py` ([doc](TEST_POPUP_POSITION.md)) | browser |
| Card buttons (Save, Fold, Close; the gold open-a-card buttons): size, colours, contrast | `test_card_buttons.py` ([doc](TEST_CARD_BUTTONS.md)) | CSS only |
| The Player Card's Volume column (the count beside each rate, the Volume and Rate header) | `test_volume_column.py` ([doc](TEST_VOLUME_COLUMN.md)) | browser |
| Linemate Card roster: the Card button column and opening a teammate's card | `test_linemate_card.py` ([doc](TEST_LINEMATE_CARD.md)) | browser |
| Pinned Players panel: first-visit default, remembered state, Hide / Manage label | `test_pinned_panel.py` ([doc](TEST_PINNED_PANEL.md)) | browser |
| How the controls are wired to the Apply gate, the Pinned Players invalidation and confirm, the Merge Card cap and quota, the commit points that re-check selected Players, the Linemate roster and RSWA, and axes, toggles, folding and dragging leaving cards alone (INVARIANTS 4, 9, 10, 11, 16, 17) | `test_browser_smoke.py` ([doc](TEST_BROWSER_SMOKE.md)) | browser |
| Card PNG exports: outer square frame, chart export unchanged | `test_card_export_frame.py` ([doc](TEST_CARD_EXPORT_FRAME.md)) | browser |
| How an exported PNG reaches the user: desktop download, share sheet, "Image ready" bar, Copy | `test_png_delivery.py` ([doc](TEST_PNG_DELIVERY.md)) | browser |
| The header Install button and its popup | `test_install_links.py` ([doc](TEST_INSTALL_LINKS.md)) | browser |
| That every test script has a document here, and every document has a script | `test_playbook_docs.py` ([doc](TEST_PLAYBOOK_DOCS.md)) | pure Python |
| What the shared info popover accepts and how each content form renders | `test_info_popover.py` ([doc](TEST_INFO_POPOVER.md)) | browser |
| The NCAAF Teams checklist: per-season schools and what stays checked across seasons | `test_ncaaf_teams_checklist.py` ([doc](TEST_NCAAF_TEAMS_CHECKLIST.md)) | browser |
| The NFL Teams checklist's conference and division buttons | `test_teams_group_buttons.py` ([doc](TEST_TEAMS_GROUP_BUTTONS.md)) | browser |
| The Teams (i) info popover | `test_teams_info_popover.py` ([doc](TEST_TEAMS_INFO_POPOVER.md)) | browser |
| Which requests the Service Worker intercepts | `test_sw_cache_bypass.py` ([doc](TEST_SW_CACHE_BYPASS.md)) | browser |
| The Claude Code hooks in `tools/claude_hooks/` and their installer | `test_hooks.py` ([doc](TEST_HOOKS.md)) | pure Python |
| Anything else | a new `tests/test_*.py` plus its own `TEST_*.md` here, in the same change | |

## Test kinds

- **API**: the `client` fixture (FastAPI `TestClient`) with the `seeded_db` fixture, both from `conftest.py`. No browser.
- **Pure Python**: imports the module directly; builds whatever data it needs in `tmp_path` or an in-test sqlite engine.
- **Browser**: Playwright with Chromium. The `live_server_url` fixture starts the real app on a free port with the seeded database, and the test drives the real frontend.
  Frontend pure functions are tested by importing the ES module inside the page (`page.evaluate`, for example `import('/popup-position.js')`).
  These tests skip themselves when Playwright or Chromium is missing, so run `pytest -rs` and check that they were not skipped. With `REQUIRE_CHROMIUM=1` a missing browser fails instead (the CI `browser` job sets it).
  Every file gets its page from the `open_page` fixture of `conftest.py` and waits with `wait_until` (see [CONFTEST.md](CONFTEST.md)); do not copy the launch code or use `page.wait_for_function` with an `async` function, which never waits.
  `conftest.py` marks every test that uses the `page` or `live_server_url` fixture with `browser`, so `pytest -m "not browser"` runs everything else (the Claude Code CI gate does exactly that).

## Rules

- Synthetic data only. Fixtures are tiny hand-made rows, never PFF exports.
- Which invariants a file covers is the Coverage column of [`INVARIANTS.md`](../INVARIANTS.md); an invariant with coverage "none" has no test, and changing it means creating a new test file and its document. Each document lists what its file leaves out under "Known gaps".
- A new test file ships with its document in the same change. Copy the shape of an existing one. CI enforces it: `test_playbook_docs.py` fails when a script has no document, when a document has no script, when `INDEX.md` does not link a document or links a file that does not exist, or when a document's third line lacks "Add tests here when:".
- Keep documents short. Say where tests belong, what they need and what is not covered. Do not list test functions; `grep "^def test_" tests/<file>` does that.
