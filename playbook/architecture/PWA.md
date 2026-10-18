# PWA and Service Worker

> **Load when:** touching sw.js, manifest.json, caching rules, install flow, or adding any new route or API prefix.
> Split from the former CLAUDE.md "Architecture" section on 2026-10-17. The original text is kept, apart from a few small later edits and
> appended sections marked "carried over from the retired `BLUEPRINT.md`".
> Cross-references like "see X above/below" point to another file in this folder — look them up in `INDEX.md`.

**The app is an installable PWA** (the header's Install button links to per-platform instructions
in `PWA.md`, see "Info-popover triggers and the header Install button" below; `frontend/manifest.json`, `frontend/sw.js`,
wired up in `frontend/index.html`'s `<head>` and its final inline `<script>`): a `<link rel="manifest">` plus
`apple-touch-icon`/`apple-mobile-web-app-*` tags make the app addable to a phone's home screen
(`display: "standalone"`, `background_color`/`theme_color` both `#0d1f17` matching the app's own
turf-dark chrome), and a classic install/activate/fetch service worker precaches the static shell
(`index.html`, `style.css`, `main.js`, the vendored Plotly/html2canvas bundles, the manifest, and
the two PNG icon sizes manifest.json references) for offline/flaky-connection resilience and
faster repeat loads. Registration (`navigator.serviceWorker.register("/sw.js")`) is wrapped in an
`"serviceWorker" in navigator` feature check and a `.catch()` that only `console.warn`s — a
registration failure (e.g. an unsupported browser, or `/sw.js` 404ing) degrades silently to the
ordinary non-PWA experience rather than breaking the page. **`/api/*` and `/health` are
deliberately never cached** (`sw.js`'s `shouldBypassCache()` matches the whole `/api/` prefix plus exactly `/health` and anything under `/health/`, so a route added later is covered automatically; it is checked first in the `fetch`
listener and allowed to fall through to a normal network request with no interception at all) —
this app's whole value is current PFF data, so a service worker that cached a stat endpoint would
risk silently showing stale numbers, which is a worse failure mode than a wasted network request.
Everything else uses cache-first-with-network-fallback (`caches.match()` → cached hit, or fetch +
populate the cache for next time) — fine for static assets that only change on deploy.
`sw.js` carries the same `{{VERSION}}` placeholder convention `index.html` already used for
cache-busting (both its `CACHE_NAME` and its precached URLs' `?v=` query strings) — `main.py`'s
`serve_sw()` route exists *only* to do that one substitution (`Response(...).replace("{{VERSION}}",
COMMIT_SHA)`, mirroring `serve_index()`) before `/sw.js` would otherwise fall through to the
wholesale `StaticFiles` mount below it, which serves files byte-for-byte with no templating and
would leave the literal string `"{{VERSION}}"` baked into every installed worker forever. That
route also sets `Cache-Control: no-cache` so an intermediate/CDN cache can't extend a stale
service-worker script's lifetime beyond the browser's own ~24h re-check interval. Because
`CACHE_NAME` itself is keyed by `COMMIT_SHA`, a new deploy mints a new cache name automatically —
the worker's `activate` handler deletes every cache key that doesn't match the current one, so
there's no manual cache-versioning step to remember on top of the existing commit-SHA
cache-busting `main.py` already does for `index.html`'s asset URLs.
