/* Web-push handlers, imported into the Workbox-generated service worker via
 * vite.config.js `workbox.importScripts`. The generated SW only does precache /
 * runtime-cache — without these listeners an installed PWA silently drops every
 * push sent by Flask (pywebpush), so subscriptions look alive but nothing shows.
 * Payload shape (see notifier.py): { title, body, url?, tag? }. */

self.addEventListener('push', (event) => {
  let data = { title: 'MOCA', body: '' }
  if (event.data) {
    try { data = event.data.json() } catch (e) { data.body = event.data.text() }
  }
  const options = {
    body: data.body || '',
    icon: '/icons/icon-192.png',
    badge: '/icons/icon-192.png',
    dir: 'rtl',
    lang: 'he',
    vibrate: [200, 100, 200],
    tag: data.tag || 'moca-update',
    renotify: true,
    data: { url: data.url || '/' },
  }
  event.waitUntil(self.registration.showNotification(data.title || 'MOCA', options))
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const target = (event.notification.data && event.notification.data.url) || '/'
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        // Reuse an open tab of ours when possible; navigate it to the target.
        if ('focus' in client) {
          if ('navigate' in client && target !== '/') {
            return client.navigate(target).then((c) => (c || client).focus())
          }
          return client.focus()
        }
      }
      return self.clients.openWindow(target)
    })
  )
})
