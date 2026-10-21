# test_sw_cache_bypass.py

> **Add tests here when:** changing which requests the Service Worker intercepts (`shouldBypassCache()` in `sw.js`) or how static assets are fetched (network-first with a timeout, `networkFirst()` and `NETWORK_TIMEOUT_MS`).

- **Kind:** browser (Playwright). Loads the served `sw.js` text in the page with a stubbed `self` and `caches`, then fires synthetic fetch events with stubbed `fetch`, `caches` and `setTimeout`. No real service worker is registered.
- **Needs:** Chromium; the test skips without it.
- **Covers:** every `/api/` route and `/health` bypass the cache; static assets are intercepted; a fast network answer wins and refreshes the cache; after the 3000 ms timeout or when offline the cached copy is served; offline with nothing cached fails; non-GET requests are not intercepted; edge paths such as `/healthy.css` and `/apiary.js` are not bypassed.
- **Not here:** that `sw.js` is served and version-substituted, that static files carry `Cache-Control: no-cache`, and that `NETWORK_TIMEOUT_MS = 3000` is in the served text → `TEST_APP_STARTUP.md`.
- **Known gaps:** none recorded.
