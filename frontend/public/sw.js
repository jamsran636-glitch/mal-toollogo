const CACHE = "mal-toollogo-shell-v2";
const CORE = ["/", "/manifest.webmanifest", "/icon-192.png", "/icon-512.png"];

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    for (const url of CORE) {
      const coreResponse = await fetch(url, { cache: "reload" });
      if (!coreResponse.ok) throw new Error(`Unable to precache ${url}`);
      await cache.put(url, coreResponse);
    }
    const response = await fetch("/", { cache: "no-store" });
    const html = await response.clone().text();
    await cache.put("/", response);
    const assets = [...html.matchAll(/(?:src|href)="(\/assets\/[^"]+)"/g)].map((match) => match[1]);
    for (const asset of new Set(assets)) {
      const assetResponse = await fetch(asset, { cache: "reload" });
      if (!assetResponse.ok) throw new Error(`Unable to precache ${asset}`);
      await cache.put(asset, assetResponse);
    }
  })());
});

self.addEventListener("activate", (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key)))).then(() => self.clients.claim()));
});

self.addEventListener("message", (event) => {
  if (event.data?.type === "SKIP_WAITING") self.skipWaiting();
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;
  if (event.request.mode === "navigate") {
    event.respondWith(fetch(event.request).then((response) => {
      const copy = response.clone();
      caches.open(CACHE).then((cache) => cache.put("/", copy));
      return response;
    }).catch(() => caches.match("/", { ignoreVary: true })));
    return;
  }
  event.respondWith(caches.match(event.request, { ignoreVary: true }).then((cached) => cached || fetch(event.request).then((response) => {
    if (response.ok && ["script", "style", "image", "font"].includes(event.request.destination)) {
      const copy = response.clone();
      caches.open(CACHE).then((cache) => cache.put(event.request, copy));
    }
    return response;
  })));
});
