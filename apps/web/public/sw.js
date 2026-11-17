/* IREP service worker: caches the app shell and the parent's last overview JSON for offline viewing. */
const SHELL_CACHE = "irep-shell-v1";
const DATA_CACHE = "irep-data-v1";

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(SHELL_CACHE).then((c) => c.addAll(["/parent", "/manifest.json"]).catch(() => undefined)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET") return;
  // Parent overview: network first, fall back to the last cached copy.
  if (url.pathname.includes("/api/v1/parent/overview") || url.pathname.includes("/api/v1/parent/children/")) {
    event.respondWith(
      fetch(event.request)
        .then((res) => {
          const copy = res.clone();
          caches.open(DATA_CACHE).then((c) => c.put(event.request, copy));
          return res;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }
  // App shell: cache first for navigations to /parent*
  if (event.request.mode === "navigate" && url.pathname.startsWith("/parent")) {
    event.respondWith(fetch(event.request).catch(() => caches.match("/parent")));
  }
});
