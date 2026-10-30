# test_app_startup.py

> **Add tests here when:** changing how the app is assembled: the `/logos` mount, the frontend at `/` and `/ncaaf-season`, `/health`, or how `sw.js` and `index.html` are served.

- **Kind:** API (HTTP client).
- **Needs:** `client` from `conftest.py`. No browser.
- **Covers:** the app builds; `/health`; the logos mount and its folder (an NFL logo is served at `/logos/nfl/ARZ.png`); `/` serves the frontend; `/sw.js` is served with `{{VERSION}}` substituted and `no-cache`; the served `sw.js` carries the never-cache rule and `NETWORK_TIMEOUT_MS = 3000`; every root-mount file, `/` and `/sw.js` carry `Cache-Control: no-cache` while `/logos` does not; `index.html` registers the service worker; `/` serves the NFL page and the PWA manifest keeps `start_url` and `scope` at `/`.
- **Also covers:** each season page filled with its own league (`window.LEAGUE`, subtitle, tab title, the college scope line), no `{{` placeholder left, the navigation present with the current page marked once, and the pages served `no-cache` and kept out of the API schema.
- **Not here:** how the Service Worker behaves at runtime → `TEST_SW_CACHE_BYPASS.md`; folder layout drift → `TEST_PATHS.md`.
- **Known gaps:** none recorded.
