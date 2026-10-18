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

  event.respondWith(
    caches.match(event.request).then((cached) => {
      return (
        cached ||
        fetch(event.request).then((response) => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          return response;
        })
      );
    })
  );
});
