const CACHE_NAME = "lines-shines-{{VERSION}}";

const PRECACHE_URLS = [
  "/",
  "/style.css?v={{VERSION}}",
  "/main.js?v={{VERSION}}",
  "/vendor/plotly.min.js?v={{VERSION}}",
  "/vendor/html2canvas.min.js?v={{VERSION}}",
  "/manifest.json",
  "/images/favicon-192x192.png",
  "/images/favicon-512x512.png"
];

const NEVER_CACHE_PREFIXES = ["/api/metadata", "/api/pass_rush", "/api/pass_block", "/health"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  if (NEVER_CACHE_PREFIXES.some((prefix) => url.pathname.startsWith(prefix))) {
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
