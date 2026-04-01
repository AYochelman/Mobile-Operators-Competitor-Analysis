// Mass Market Service Worker

self.addEventListener('install', event => {
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(self.clients.claim());
});

// Push notification received
self.addEventListener('push', event => {
  let data = { title: 'השוואת סלולר', body: 'יש עדכון חדש בחבילות' };
  if (event.data) {
    try { data = event.data.json(); } catch (e) {}
  }
  const options = {
    body: data.body,
    icon: '/static/icon-192.png',
    badge: '/static/icon-192.png',
    dir: 'rtl',
    lang: 'he',
    vibrate: [200, 100, 200],
    tag: 'mass-market-update',
    renotify: true,
    data: { url: '/' }
  };
  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

// Notification clicked — open or focus the app
self.addEventListener('notificationclick', event => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(clients => {
      for (const client of clients) {
        if ('focus' in client) return client.focus();
      }
      return self.clients.openWindow(target);
    })
  );
});
