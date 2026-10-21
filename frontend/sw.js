const CACHE_NAME = "lines-shines-{{VERSION}}";

const PRECACHE_URLS = [
  "/",
  "/style.css?v={{VERSION}}",
  "/main.js?v={{VERSION}}",
  "/vendor/plotly.min.js?v={{VERSION}}",
  "/vendor/html2canvas.min.js?v={{VERSION}}",
  "/manifest.json",
  "/images/favicon-192x192.png",
  "/images/favicon-512x512.png",
];

// Every API route and the health check always go to the network, so a route added later can never be served stale.
// "/health" is matched exactly (plus anything under "/health/"), so an unrelated file like "/healthy.css" is still cached.
const NEVER_CACHE_PREFIXES = ["/api/", "/health/"];
const NEVER_CACHE_PATHS = ["/health"];

function shouldBypassCache(pathname) {
  return NEVER_CACHE_PATHS.includes(pathname) || NEVER_CACHE_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

// Static files are network-first: the app should always run the latest deploy. If the network has not answered
// within this many milliseconds (or fails), the cached copy is used instead, so a slow connection never blocks the start.
const NETWORK_TIMEOUT_MS = 3000;

async function networkFirst(event) {
  const request = event.request;
  const cache = await caches.open(CACHE_NAME);

  const networkResponse = fetch(request).then((response) => {
    if (response.ok) {
      event.waitUntil(cache.put(request, response.clone()));
    }
    return response;
  });
  networkResponse.catch(() => {}); // A late failure after the timeout must not surface as an unhandled rejection.

  let timer;
  const timedOut = new Promise((resolve) => {
    timer = setTimeout(() => resolve(null), NETWORK_TIMEOUT_MS);
  });

  try {
    const winner = await Promise.race([networkResponse, timedOut]);
    if (winner) {
      clearTimeout(timer);
      return winner;
    }
  } catch {
    clearTimeout(timer); // Network failed outright: fall through to the cache.
  }

  const cached = await cache.match(request);
  return cached || networkResponse; // Nothing cached: keep waiting for the network (or fail).
}

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  if (shouldBypassCache(url.pathname)) {
    return; // No interception: always connect to network for latest data.
  }

  if (event.request.method !== "GET") {
    return; // Only GET responses can be cached.
  }

  event.respondWith(networkFirst(event));
});
