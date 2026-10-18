"""Service Worker: every /api/ route and /health bypass the cache; static assets stay cache-first."""

from __future__ import annotations

import pytest

BYPASSED = [
    "/api/metadata",
    "/api/pass_rush",
    "/api/pass_block",
    "/health",
    "/health/ready",  # Anything under /health/ is covered too.
    "/api/ncaaf/anything",  # A route that does not exist yet must be covered too.
]
CACHED = [
    "/",
    "/style.css",
    "/main.js",
    "/manifest.json",
    "/vendor/plotly.min.js",
    "/images/favicon-192x192.png",
    "/healthy.css",  # Starts with "/health" but is not the health check, so it stays cache-first.
    "/apiary.js",  # Starts with "/api" but not "/api/", so it stays cache-first.
]

# Runs the served sw.js against a stubbed worker scope, then fires one synthetic fetch event per path.
# caches.match answers with a hit, so an intercepted request never reaches the real network.
RUN_FETCH_LISTENER = """
([swText, paths]) => {
  const listeners = {};
  const self = {
    addEventListener: (type, fn) => {
      listeners[type] = fn;
    },
    skipWaiting: () => {},
    clients: { claim: () => {} },
  };
  const caches = {
    open: async () => ({ addAll: async () => {}, put: async () => {} }),
    match: async () => ({ cached: true }),
    keys: async () => [],
    delete: async () => true,
  };
  new Function("self", "caches", swText)(self, caches);

  return paths.map((path) => {
    let intercepted = false;
    listeners.fetch({
      request: { url: location.origin + path },
      respondWith: () => {
        intercepted = true;
      },
    });
    return [path, intercepted];
  });
}
"""


@pytest.fixture()
def intercepted(live_server_url):
    sync_api = pytest.importorskip("playwright.sync_api")

    with sync_api.sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()

        except Exception as exc:  # Browser binary not installed.
            pytest.skip(f"chromium unavailable: {exc}")

        page = browser.new_page()
        page.goto(live_server_url)

        sw_text = page.evaluate("async () => (await fetch('/sw.js')).text()")
        results = page.evaluate(RUN_FETCH_LISTENER, [sw_text, BYPASSED + CACHED])
        browser.close()

    return dict(results)


def test_api_and_health_bypass_cache_but_static_assets_do_not(intercepted):
    assert {path: intercepted[path] for path in BYPASSED} == {
        path: False for path in BYPASSED
    }, "an API route or /health is being intercepted by the Service Worker"

    assert {path: intercepted[path] for path in CACHED} == {
        path: True for path in CACHED
    }, "a static asset is no longer served through the Service Worker cache"
