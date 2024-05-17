
self.addEventListener('install', (event) => {
    console.log('Service Worker installing.');
    event.waitUntil(
        caches.open('qr-inventory-cache').then((cache) => {
            return cache.addAll([
                '/',
                '/static/icons/icon-192x192.png',
                '/static/icons/icon-512x512.png',
                '/manifest.json'
            ]);
        })
    );
});

self.addEventListener('fetch', (event) => {
    event.respondWith(
        caches.match(event.request).then((response) => {
            return response || fetch(event.request);
        })
    );
});
