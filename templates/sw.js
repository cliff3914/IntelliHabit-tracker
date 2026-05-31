// Service Worker for IntelliHabit Tracker
const CACHE_NAME = 'intellihabit-v1';
const urlsToCache = [
  '/',
  '/static/icon-192.png'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => response || fetch(event.request))
  );
});

// Push notification handler
self.addEventListener('push', function(event) {
  const data = event.data ? event.data.json() : {};
  const title = data.title || 'IntelliHabit Reminder';
  const options = {
    body: data.body || 'Time to complete your habit!',
    icon: '/static/icon-192.png',
    badge: '/static/icon-72.png',
    vibrate: [200, 100, 200]
  };
  
  event.waitUntil(self.registration.showNotification(title, options));
});