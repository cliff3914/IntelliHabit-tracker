// IntelliHabit Tracker Service Worker
const CACHE_NAME = 'intellihabit-v1';

// Install event - cache important files
self.addEventListener('install', event => {
    console.log('Service Worker installed');
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            return cache.addAll([
                '/',
                '/dashboard',
                '/static/icon-192.png'
            ]);
        })
    );
});

// Fetch event - serve from cache first
self.addEventListener('fetch', event => {
    event.respondWith(
        caches.match(event.request).then(response => {
            return response || fetch(event.request);
        })
    );
});

// Push event - receive and show notification
self.addEventListener('push', function(event) {
    console.log('Push notification received');
    
    let data = {};
    if (event.data) {
        try {
            data = event.data.json();
        } catch (e) {
            data = { title: 'IntelliHabit Reminder', body: event.data.text() };
        }
    }
    
    const title = data.title || 'IntelliHabit Reminder';
    const options = {
        body: data.body || 'Time to complete your habit!',
        icon: '/static/icon-192.png',
        badge: '/static/icon-72.png',
        vibrate: [200, 100, 200],
        tag: 'habit-reminder',
        requireInteraction: true
    };
    
    event.waitUntil(self.registration.showNotification(title, options));
});

// Notification click event - open dashboard
self.addEventListener('notificationclick', function(event) {
    console.log('Notification clicked');
    event.notification.close();
    event.waitUntil(
        clients.openWindow('/dashboard')
    );
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
    console.log('Service Worker activated');
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cache => {
                    if (cache !== CACHE_NAME) {
                        console.log('Deleting old cache:', cache);
                        return caches.delete(cache);
                    }
                })
            );
        })
    );
});