"""Service Worker: /api/ and /health bypass the cache; static assets are network-first with a timeout."""

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
    "/apiary.js",  # Starts with "/api" but not "/api/", so it stays intercepted.
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
  const cacheHit = { cached: true };
  const caches = {
    open: async () => ({ addAll: async () => {}, put: async () => {}, match: async () => cacheHit }),
    match: async () => cacheHit,
    keys: async () => [],
    delete: async () => true,
  };
  // A fetch that never settles keeps the real network out of this test.
  const fetchStub = () => new Promise(() => {});
  new Function("self", "caches", "fetch", swText)(self, caches, fetchStub);

  return paths.map((path) => {
    let intercepted = false;
    listeners.fetch({
      request: { url: location.origin + path, method: "GET" },
      respondWith: () => {
        intercepted = true;
      },
      waitUntil: () => {},
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
    }, "a static asset is no longer handled by the Service Worker"


# Network-first behaviour: boots the served sw.js with a stubbed fetch, caches and setTimeout,
# fires one fetch event for /filters.js and reports which response won.
RUN_NETWORK_FIRST = """
async ([swText, scenario]) => {
  const listeners = {};
  const puts = [];
  const timers = [];
  const cached = scenario.cached ? { tag: "cache" } : undefined;
  const network = { ok: true, tag: "network", clone() { return this; } };

  const self = {
    addEventListener: (type, fn) => { listeners[type] = fn; },
    skipWaiting: () => {},
    clients: { claim: () => {} },
  };
  const caches = {
    open: async () => ({
      addAll: async () => {},
      put: async (request, response) => { puts.push(response.tag); },
      match: async () => cached,
    }),
    keys: async () => [],
    delete: async () => true,
  };
  const fetchStub = () => {
    if (scenario.network === "fast") return Promise.resolve(network);
    if (scenario.network === "fails") return Promise.reject(new Error("offline"));
    return new Promise(() => {}); // "hangs"
  };
  const setTimeoutStub = (fn, ms) => { timers.push({ fn, ms }); return timers.length; };
  new Function("self", "caches", "fetch", "setTimeout", "clearTimeout", swText)(
    self, caches, fetchStub, setTimeoutStub, () => {}
  );

  let promise = null;
  listeners.fetch({
    request: { url: location.origin + "/filters.js", method: scenario.method || "GET" },
    respondWith: (p) => { promise = p; },
    waitUntil: () => {},
  });
  if (!promise) return { intercepted: false };
  promise.catch(() => {}); // The browser handles this promise itself; the test awaits it below.

  const tick = () => new Promise((resolve) => window.setTimeout(resolve, 0));
  await tick();
  if (scenario.fireTimeout) timers[0].fn();

  try {
    const response = await promise;
    return { intercepted: true, tag: response.tag, puts, timeoutMs: timers.length ? timers[0].ms : null };
  } catch (error) {
    return { intercepted: true, failed: true, puts, timeoutMs: timers.length ? timers[0].ms : null };
  }
}
"""


@pytest.fixture()
def run_network_first(live_server_url):
    sync_api = pytest.importorskip("playwright.sync_api")

    with sync_api.sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()

        except Exception as exc:  # Browser binary not installed.
            pytest.skip(f"chromium unavailable: {exc}")

        page = browser.new_page()
        page.goto(live_server_url)
        sw_text = page.evaluate("async () => (await fetch('/sw.js')).text()")

        def run(**scenario):
            return page.evaluate(RUN_NETWORK_FIRST, [sw_text, scenario])

        yield run
        browser.close()


def test_network_answer_wins_and_refreshes_the_cache(run_network_first):
    result = run_network_first(network="fast", cached=True)
    assert result["tag"] == "network", "a fast network answer must beat the cached copy"
    assert result["puts"] == [
        "network"
    ], "the fresh response must be stored for next time"


def test_timeout_falls_back_to_cache_after_three_seconds(run_network_first):
    result = run_network_first(network="hangs", cached=True, fireTimeout=True)
    assert result["timeoutMs"] == 3000
    assert result["tag"] == "cache"


def test_offline_falls_back_to_cache(run_network_first):
    result = run_network_first(network="fails", cached=True)
    assert result["tag"] == "cache"


def test_offline_with_nothing_cached_fails(run_network_first):
    result = run_network_first(network="fails", cached=False)
    assert result["failed"] is True


def test_non_get_requests_are_not_intercepted(run_network_first):
    result = run_network_first(network="fast", cached=True, method="POST")
    assert result["intercepted"] is False
