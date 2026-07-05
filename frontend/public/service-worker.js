/* Fatin Penhores service worker — minimal install/activate for PWA A2HS support.
 * We intentionally do NOT cache API responses (financial data must always be
 * live). This SW exists mainly to satisfy the "installable" criteria browsers
 * check for the Add-to-Home-Screen prompt. */
const CACHE_NAME = "fatin-penhores-shell-v1";
const SHELL = ["/", "/index.html", "/manifest.json", "/brand/logo.jpg"];

self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(caches.open(CACHE_NAME).then((c) => c.addAll(SHELL).catch(() => {})));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))),
    ).then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  // Never cache API traffic — always network for /api/*
  if (url.pathname.startsWith("/api/")) return;
  // Cache-first for static shell only
  if (event.request.method !== "GET") return;
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request).catch(() => cached)),
  );
});
