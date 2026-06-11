const CACHE = "budget-v5";

self.addEventListener("install", e => {
  self.skipWaiting();
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.map(key => caches.delete(key)))
    ).then(() => clients.claim())
  );
});

self.addEventListener("fetch", e => {
  e.respondWith(fetch(e.request));
});

self.addEventListener("push", e => {
  const data = e.data ? e.data.json() : {};
  e.waitUntil(
    self.registration.showNotification(data.title || "Budget Planner", {
      body: data.body || "Don't forget to save today! 💰",
      icon: "/static/icons/icon-192.png",
      badge: "/static/icons/icon-192.png",
    })
  );
});

self.addEventListener("notificationclick", e => {
  e.notification.close();
  e.waitUntil(clients.openWindow("/"));
});
