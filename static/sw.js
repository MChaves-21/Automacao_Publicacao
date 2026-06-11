// sw.js — Service Worker para PWA offline-first
const CACHE_NAME = "mktauto-v6";
const STATIC_ASSETS = ["/", "/login", "/static/manifest.json"];

// ── Instalação: cache dos assets estáticos ──────────────────────────────────
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch(() => {});
    })
  );
  self.skipWaiting();
});

// ── Ativação: limpar caches antigos ─────────────────────────────────────────
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

// ── Fetch: network-first para API, cache-first para assets ──────────────────
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // API: sempre network, sem cache
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/youtube/")) {
    return;
  }

  // Uploads e arquivos estáticos: cache-first
  if (
    url.pathname.startsWith("/static/") ||
    url.pathname.startsWith("/uploads/")
  ) {
    event.respondWith(
      caches.match(event.request).then(
        (cached) => cached || fetch(event.request).then((resp) => {
          const clone = resp.clone();
          caches.open(CACHE_NAME).then((c) => c.put(event.request, clone));
          return resp;
        })
      )
    );
    return;
  }

  // Páginas: network-first com fallback para cache
  event.respondWith(
    fetch(event.request)
      .then((resp) => {
        if (resp.ok) {
          const clone = resp.clone();
          caches.open(CACHE_NAME).then((c) => c.put(event.request, clone));
        }
        return resp;
      })
      .catch(() => caches.match(event.request))
  );
});

// ── Push notifications (estrutura base) ─────────────────────────────────────
self.addEventListener("push", (event) => {
  if (!event.data) return;
  const data = event.data.json();
  self.registration.showNotification(data.title || "MktAuto", {
    body: data.body || "",
    icon: "/static/manifest.json",
    badge: "/static/manifest.json",
    tag: data.tag || "mktauto",
    data: { url: data.url || "/" },
  });
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = event.notification.data?.url || "/";
  event.waitUntil(clients.openWindow(url));
});
