const CACHE_NAME = 'ammas-farm-cache-v1';
const ASSETS_TO_CACHE = [
  '/landing',
  '/static/css/style.css',
  '/static/images/logo.png',
  '/static/manifest.json'
];

// Install Event - Caching basic offline shell
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('🌾 [Service Worker] Pre-caching offline shell');
      return cache.addAll(ASSETS_TO_CACHE);
    }).catch(err => {
      console.error('Service Worker pre-caching failed:', err);
    })
  );
  self.skipWaiting();
});

// Activate Event - Clean up old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cache) => {
          if (cache !== CACHE_NAME) {
            console.log('🌾 [Service Worker] Removing old cache:', cache);
            return caches.delete(cache);
          }
        })
      );
    })
  );
  self.clients.claim();
});

// Fetch Event - Cache-first with network fallback strategy
self.addEventListener('fetch', (event) => {
  // Avoid caching non-GET requests or external API/admin calls
  if (event.request.method !== 'GET' || !event.request.url.startsWith(self.location.origin)) {
    return;
  }

  // Skip dynamic pages or admin pages from hard caching
  if (event.request.url.includes('/admin/') || event.request.url.includes('/auth/')) {
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      if (cachedResponse) {
        return cachedResponse;
      }
      
      return fetch(event.request).then((networkResponse) => {
        // Cache new static assets dynamically
        if (event.request.url.includes('/static/')) {
          return caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, networkResponse.clone());
            return networkResponse;
          });
        }
        return networkResponse;
      }).catch(() => {
        // Offline fallback
        if (event.request.mode === 'navigate') {
          return caches.match('/landing');
        }
      });
    })
  );
});
