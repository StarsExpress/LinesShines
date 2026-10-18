# test_app_startup.py

> **Add tests here when:** changing how the app is assembled: the `/logos` mount, the frontend at `/`, `/health`, or how `sw.js` and `index.html` are served.

- **Kind:** API (HTTP client).
- **Needs:** `client` from `conftest.py`. No browser.
- **Covers:** the app builds; `/health`; the logos mount and its folder; `/` serves the frontend; `/sw.js` is served with `{{VERSION}}` substituted and `no-cache`; the served `sw.js` carries the never-cache rule; `index.html` registers the service worker; `/` serves the NFL page and the PWA manifest keeps `start_url` and `scope` at `/`.
- **Not here:** how the Service Worker behaves at runtime → `TEST_SW_CACHE_BYPASS.md`; folder layout drift → `TEST_PATHS.md`.
- **Known gaps:** none recorded.
