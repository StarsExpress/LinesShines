# test_sw_cache_bypass.py

> **Add tests here when:** changing which requests the Service Worker intercepts (`shouldBypassCache()` in `sw.js`) or how static assets are cached.

- **Kind:** browser (Playwright). Loads the served `sw.js` text in the page with a stubbed `self` and `caches`, then fires synthetic fetch events. No real service worker is registered.
- **Needs:** Chromium; the test skips without it.
- **Covers:** every `/api/` route and `/health` bypass the cache; static assets stay cache-first; edge paths such as `/healthy.css` and `/apiary.js` are not bypassed.
- **Not here:** that `sw.js` is served and version-substituted → `TEST_APP_STARTUP.md`.
- **Known gaps:** none recorded.
