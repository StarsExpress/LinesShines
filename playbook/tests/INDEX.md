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
| Season-threshold routing in `config.py` | `test_config.py` ([doc](TEST_CONFIG.md)) | pure Python |
| Ingestion: file path resolution, replacing a season/position slice | `test_db_ingestion.py` ([doc](TEST_DB_INGESTION.md)) | pure Python |
| The folder layout of `data/` and `frontend/` | `test_paths.py` ([doc](TEST_PATHS.md)) | pure Python |
| How percentiles, ranks and percentile pools are computed | `test_percentiles.py` ([doc](TEST_PERCENTILES.md)) | browser |
| Which players the chart plots or highlights from Teams, Players and the threshold | `test_filters.py` ([doc](TEST_FILTERS.md)) | browser |
| What happens to Pinned Players and Comparisons when filters change, and who stays eligible in the Players filter | `test_pinned_impact.py` ([doc](TEST_PINNED_IMPACT.md)) | browser |
| Popup placement and closing on viewport change | `test_popup_position.py` ([doc](TEST_POPUP_POSITION.md)) | browser |
| The header Install button and its popup | `test_install_links.py` ([doc](TEST_INSTALL_LINKS.md)) | browser |
| The Teams (i) info popover | `test_teams_info_popover.py` ([doc](TEST_TEAMS_INFO_POPOVER.md)) | browser |
| Which requests the Service Worker intercepts | `test_sw_cache_bypass.py` ([doc](TEST_SW_CACHE_BYPASS.md)) | browser |
| Anything else | a new `tests/test_*.py` plus its own `TEST_*.md` here, in the same change | |

## Test kinds

- **API**: the `client` fixture (FastAPI `TestClient`) with the `seeded_db` fixture, both from `conftest.py`. No browser.
- **Pure Python**: imports the module directly; builds whatever data it needs in `tmp_path` or an in-test sqlite engine.
- **Browser**: Playwright with Chromium. The `live_server_url` fixture starts the real app on a free port with the seeded database, and the test drives the real frontend.
  Frontend pure functions are tested by importing the ES module inside the page (`page.evaluate`, for example `import('/popup-position.js')`).
  These tests skip themselves when Playwright or Chromium is missing, so run `pytest -rs` and check that they were not skipped.

## Rules

- Synthetic data only. Fixtures are tiny hand-made rows, never PFF exports.
- A new test file ships with its document in the same change. Copy the shape of an existing one.
- Keep documents short. Say where tests belong, what they need and what is not covered. Do not list test functions; `grep "^def test_" tests/<file>` does that.

## Behavior with no test file yet

These invariants (see `INVARIANTS.md`) have no test today. If you change one of them, create a new test file and its document. For client-side logic, a browser test in the style of `test_percentiles.py` or `test_pinned_impact.py` fits.

- Invariant 4: the chart changes only on Apply, while the Players search pool stays live.
- Invariant 10: Merge Card display rules, the 5-player cap and the 8-player quota.
- Invariant 11: the Linemate roster excludes the anchor by default; RSWA uses uncapped raw snaps.
- Invariant 16: axis controls, display toggles, fold state and dragging never reset cards (the handler wiring).
- Invariant 17 (wiring only): the Players filter re-checks selections on commit, not while dragging or typing, and shows the toast. The shared function and the toast text are tested; the event wiring is not.

## Deliberately untested

- **Invariant 12 (every PNG export carries the PFF source footer):** the footer is one constant drawn onto a canvas, so a test would only restate the constant, and every export shows it.
- **Invariant 13 (PFF raw CSV/xlsx never enters the repo):** git state is outside what the app's tests can see, and `.gitignore` already ignores `*.csv` and `*.xlsx`.
