# conftest.py

> **Add tests here when:** you need a fixture shared by several test files, or you change how tests get a database, a running server or a browser page.

- **Kind:** shared fixtures, not tests.
- **Order matters:** `DATABASE_URL` is pointed at an ephemeral sqlite file before anything imports `main`, because `main.py` resolves its engine at import time. Setting it inside a fixture would be too late.
- **Fixtures:**

| Fixture | What it gives you |
|---|---|
| `_create_tables` | Session-wide and automatic: creates the tables once. |
| `client` | A FastAPI `TestClient`. |
| `seeded_db` | Wipes the tables and loads a small deterministic set: 2 teams (BUF, MIA), pass-rush rows for ED and DI, pass-block rows for T and G, season 2025, written to the `nfl_*` tables with `player_id` (1001/1002 rush, 2001/2002 block) and Pass Cov Percent values (8/5 and 12/10, i.e. 100 minus the source Pass Rush Percent). |
| `live_server_url` | Starts the real app with uvicorn on a free port, on top of `seeded_db`, and yields its base URL. Shuts it down afterwards. |

- **Browser fixtures and helpers:**

| Name | What it gives you |
|---|---|
| `chromium_browser` | Headless Chromium for one test. A missing browser skips the test, or fails it when `REQUIRE_CHROMIUM` is set (the CI `browser` job). Every page and context it makes fails any request to a host other than the live server at once (`_keep_requests_local()`): `index.html` loads Google Fonts and Font Awesome from their CDNs, `page.goto()` waits for them, and a CDN that stalled on the CI runner failed two tests in their setup with `Page.goto: Timeout 30000ms exceeded`. Tests therefore run with the fallback fonts and no icons. |
| `open_page` | A function `open_page(url, viewport=None, ready_js=None, settle=False)` that opens a page, waits until `ready_js` is truthy and returns it. `settle=True` also waits for the network to go quiet and checks `ready_js` again, for a page that redraws once its logos load. |
| `APP_READY_JS`, `RECORDS_READY_JS` | The usual `ready_js`: the app holds its metadata and applied filters (and a slice of records). |
| `wait_until(page, expression, arg=None)` | Polls the expression in the page until it is truthy. Import it with `from conftest import wait_until`. |

- **Why `wait_until` and not `page.wait_for_function`:** Playwright treats the Promise an `async` function returns as truthy and returns at once, so a wait written that way never waits. It only passed when the page happened to be ready, and under load about one run in ten was not. A file's own `page` fixture is now a few lines: its URL, viewport and seed fixture.
- **`browser` marker:** `pytest_collection_modifyitems` adds it to every test whose fixtures include `page`, `live_server_url`, `chromium_browser` or `open_page` (directly or through another fixture); `pytest.ini` registers it.
- **Not here:** per-file seeds. A file that needs another seed (`seeded_ncaaf_db`, `seeded_career_page_db`) names it in its own `page` fixture.
- **Known gaps:** the seed has one player per position, so it cannot exercise ties, multi-team filters or percentile pools. A test for those needs its own data.
