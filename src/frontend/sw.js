/**
 * sw.js — Service Worker for Digital Twin Dashboard PWA
 * Week19 Day6 — Offline caching strategy
 *
 * Caching strategies:
 *  - App shell: Cache-first (HTML, CSS, JS bundles)
 *  - Static assets: Cache-first (images, fonts, icons)
 *  - API requests: Network-first with cache fallback
 *  - WebSocket: No caching (pass-through)
 *
 * Features:
 *  - Pre-cache critical resources on install
 *  - Stale-while-revalidate for JS/CSS bundles
 *  - Network-first with timeout for API calls
 *  - Offline fallback page
 *  - Background sync for queued actions
 *  - Cache cleanup on activation
 */

// ==================== Configuration ====================

const CACHE_VERSION = 'v1.0.0';
const CACHE_NAMES = {
  APP_SHELL: `dt-shell-${CACHE_VERSION}`,
  STATIC: `dt-static-${CACHE_VERSION}`,
  API: `dt-api-${CACHE_VERSION}`,
  RUNTIME: `dt-runtime-${CACHE_VERSION}`,
};

// Resources to pre-cache on install (app shell)
const PRECACHE_URLS = [
  '/',
  '/index.html',
  '/manifest.json',
  '/favicon.svg',
];

// File extensions for static assets
const STATIC_EXTENSIONS = /\.(png|jpg|jpeg|gif|svg|webp|ico|woff|woff2|ttf|eot)$/;

// Routes that should use network-first strategy
const API_ROUTES = ['/api/'];

// Maximum age for cached API responses (in milliseconds)
const API_CACHE_MAX_AGE = 5 * 60 * 1000; // 5 minutes

// Network timeout for network-first strategy
const NETWORK_TIMEOUT = 5000; // 5 seconds

// ==================== Install Event ====================

self.addEventListener('install', (event) => {
  console.log('[SW] Installing service worker v' + CACHE_VERSION);

  event.waitUntil(
    caches.open(CACHE_NAMES.APP_SHELL)
      .then((cache) => {
        console.log('[SW] Pre-caching app shell');
        return cache.addAll(PRECACHE_URLS);
      })
      .then(() => {
        // Skip waiting to activate immediately
        return self.skipWaiting();
      })
      .catch((err) => {
        console.error('[SW] Pre-cache failed:', err);
      })
  );
});

// ==================== Activate Event ====================

self.addEventListener('activate', (event) => {
  console.log('[SW] Activating service worker v' + CACHE_VERSION);

  event.waitUntil(
    caches.keys()
      .then((cacheNames) => {
        // Delete old caches from previous versions
        const validCaches = Object.values(CACHE_NAMES);
        return Promise.all(
          cacheNames
            .filter((name) => !validCaches.includes(name))
            .map((name) => {
              console.log('[SW] Deleting old cache:', name);
              return caches.delete(name);
            })
        );
      })
      .then(() => {
        // Take control of all clients immediately
        return self.clients.claim();
      })
  );
});

// ==================== Fetch Event ====================

self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests (except for background sync)
  if (request.method !== 'GET') {
    // Queue mutation requests for background sync
    if ('sync' in registration) {
      event.respondWith(handleMutationRequest(request));
    }
    return;
  }

  // Skip WebSocket and cross-origin requests
  if (request.url.startsWith('ws://') || request.url.startsWith('wss://')) {
    return; // Let the browser handle WebSocket connections
  }

  // Skip Chrome extension requests
  if (url.protocol === 'chrome-extension:') {
    return;
  }

  // Determine caching strategy based on request type
  if (isAPIRequest(url)) {
    // API: Network-first with cache fallback
    event.respondWith(networkFirstStrategy(request, CACHE_NAMES.API));
  } else if (isStaticAsset(url)) {
    // Static assets: Cache-first
    event.respondWith(cacheFirstStrategy(request, CACHE_NAMES.STATIC));
  } else if (isAppShell(url)) {
    // App shell: Stale-while-revalidate
    event.respondWith(staleWhileRevalidateStrategy(request, CACHE_NAMES.APP_SHELL));
  } else {
    // Other resources: Runtime cache with stale-while-revalidate
    event.respondWith(staleWhileRevalidateStrategy(request, CACHE_NAMES.RUNTIME));
  }
});

// ==================== Caching Strategies ====================

/**
 * Cache-first strategy: Try cache, then network
 * Used for static assets that rarely change
 */
async function cacheFirstStrategy(request, cacheName) {
  const cached = await caches.match(request);
  if (cached) {
    return cached;
  }

  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch (err) {
    console.warn('[SW] Cache-first failed for:', request.url, err);
    return getOfflineFallback(request);
  }
}

/**
 * Network-first strategy: Try network, fallback to cache
 * Used for API requests where fresh data is preferred
 */
async function networkFirstStrategy(request, cacheName) {
  try {
    // Race network against a timeout
    const response = await Promise.race([
      fetch(request),
      createTimeout(NETWORK_TIMEOUT),
    ]);

    if (response && response.ok) {
      // Cache successful response
      const cache = await caches.open(cacheName);
      // Add timestamp for cache age tracking
      const responseClone = response.clone();
      const headers = new Headers(responseClone.headers);
      headers.set('sw-cached-at', Date.now().toString());
      const cachedResponse = new Response(await responseClone.blob(), {
        status: responseClone.status,
        statusText: responseClone.statusText,
        headers: headers,
      });
      cache.put(request, cachedResponse);
      return response;
    }

    // Network returned error, try cache
    return await getCachedWithAgeCheck(request, cacheName) || response;
  } catch (err) {
    console.warn('[SW] Network-first failed for:', request.url, 'trying cache');
    const cached = await getCachedWithAgeCheck(request, cacheName);
    if (cached) {
      return cached;
    }
    return getOfflineFallback(request);
  }
}

/**
 * Stale-while-revalidate: Serve from cache, update in background
 * Used for app shell and JS/CSS bundles
 */
async function staleWhileRevalidateStrategy(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);

  // Fetch in background to update cache
  const fetchPromise = fetch(request)
    .then((response) => {
      if (response && response.ok) {
        cache.put(request, response.clone());
      }
      return response;
    })
    .catch(() => null);

  // Return cached version immediately if available
  if (cached) {
    return cached;
  }

  // No cache, wait for network
  const response = await fetchPromise;
  if (response) {
    return response;
  }

  return getOfflineFallback(request);
}

// ==================== Helper Functions ====================

/**
 * Check if URL is an API request
 */
function isAPIRequest(url) {
  return API_ROUTES.some((route) => url.pathname.startsWith(route));
}

/**
 * Check if URL is a static asset
 */
function isStaticAsset(url) {
  return STATIC_EXTENSIONS.test(url.pathname);
}

/**
 * Check if URL is part of the app shell
 */
function isAppShell(url) {
  return url.pathname === '/' ||
         url.pathname === '/index.html' ||
         url.pathname.startsWith('/assets/') ||
         url.pathname.endsWith('.js') ||
         url.pathname.endsWith('.css');
}

/**
 * Create a timeout promise for network race
 */
function createTimeout(ms) {
  return new Promise((_, reject) => {
    setTimeout(() => reject(new Error('Network timeout')), ms);
  });
}

/**
 * Get cached response with age check for API data
 */
async function getCachedWithAgeCheck(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  if (!cached) return null;

  // Check cache age
  const cachedAt = cached.headers.get('sw-cached-at');
  if (cachedAt) {
    const age = Date.now() - parseInt(cachedAt);
    if (age > API_CACHE_MAX_AGE) {
      // Cache is too old, but still return it as last resort
      console.log('[SW] Serving stale API cache (age:', Math.round(age / 1000), 's)');
    }
  }

  return cached;
}

/**
 * Get offline fallback response
 */
function getOfflineFallback(request) {
  // For navigation requests, return the cached index.html
  if (request.mode === 'navigate') {
    return caches.match('/index.html');
  }

  // For API requests, return a JSON error response
  if (isAPIRequest(new URL(request.url))) {
    return new Response(
      JSON.stringify({
        error: 'offline',
        message: 'You are currently offline. Please check your connection.',
        cached: false,
      }),
      {
        status: 503,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }

  // For images, return a placeholder SVG
  if (isStaticAsset(new URL(request.url))) {
    return new Response(
      '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100"><rect width="100" height="100" fill="#1a1a2e"/><text x="50" y="50" text-anchor="middle" fill="#555" font-size="12">Offline</text></svg>',
      { headers: { 'Content-Type': 'image/svg+xml' } }
    );
  }

  // Default: empty response
  return new Response('', { status: 503, statusText: 'Offline' });
}

/**
 * Handle mutation requests (POST/PUT/DELETE) with background sync
 */
async function handleMutationRequest(request) {
  try {
    return await fetch(request);
  } catch (err) {
    // Queue for background sync
    if ('sync' in registration) {
      const cache = await caches.open(CACHE_NAMES.RUNTIME);
      const requestId = `mutation-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      await cache.put(
        new Request(requestId),
        new Response(JSON.stringify({
          url: request.url,
          method: request.method,
          headers: Object.fromEntries(request.headers.entries()),
          body: await request.text(),
        }))
      );
      await registration.sync.register('sync-mutations');
    }

    return new Response(
      JSON.stringify({ error: 'offline', message: 'Request queued for sync' }),
      { status: 503, headers: { 'Content-Type': 'application/json' } }
    );
  }
}

// ==================== Background Sync ====================

self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-mutations') {
    event.waitUntil(syncQueuedMutations());
  }
});

/**
 * Process queued mutation requests when connection is restored
 */
async function syncQueuedMutations() {
  const cache = await caches.open(CACHE_NAMES.RUNTIME);
  const requests = await cache.keys();
  const mutationRequests = requests.filter((req) =>
    req.url.includes('mutation-')
  );

  for (const req of mutationRequests) {
    const cached = await cache.match(req);
    const data = JSON.parse(await cached.text());

    try {
      const response = await fetch(data.url, {
        method: data.method,
        headers: data.headers,
        body: data.body,
      });

      if (response.ok) {
        await cache.delete(req);
        console.log('[SW] Synced mutation:', data.url);

        // Notify clients of successful sync
        const clients = await self.clients.matchAll();
        clients.forEach((client) => {
          client.postMessage({
            type: 'sync-success',
            url: data.url,
            status: response.status,
          });
        });
      }
    } catch (err) {
      console.error('[SW] Failed to sync mutation:', data.url, err);
    }
  }
}

// ==================== Message Handler ====================

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }

  if (event.data && event.data.type === 'GET_VERSION') {
    event.ports[0].postMessage({ version: CACHE_VERSION });
  }

  if (event.data && event.data.type === 'CLEAR_CACHE') {
    event.waitUntil(
      Promise.all(
        Object.values(CACHE_NAMES).map((name) => caches.delete(name))
      ).then(() => {
        event.ports[0].postMessage({ cleared: true });
      })
    );
  }
});

// ==================== Push Notification Support ====================

self.addEventListener('push', (event) => {
  if (!event.data) return;

  try {
    const data = event.data.json();
    const options = {
      body: data.body || 'New alert from Digital Twin',
      icon: '/favicon.svg',
      badge: '/favicon.svg',
      tag: data.tag || 'dt-notification',
      renotify: true,
      data: data.data || {},
      actions: data.actions || [],
    };

    event.waitUntil(
      self.registration.showNotification(
        data.title || 'Digital Twin Alert',
        options
      )
    );
  } catch (err) {
    console.error('[SW] Push notification error:', err);
  }
});

// Handle notification click
self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  const targetUrl = event.notification.data.url || '/';

  event.waitUntil(
    clients.matchAll({ type: 'window' }).then((clientList) => {
      // Focus existing window if open
      for (const client of clientList) {
        if (client.url.includes(targetUrl) && 'focus' in client) {
          return client.focus();
        }
      }
      // Open new window
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});

console.log('[SW] Service worker loaded v' + CACHE_VERSION);
