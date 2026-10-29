/* VERDICT service worker: the app can be installed; styles, scripts, images and fonts come from the cache, pages always
 * from the network (they are personal and never stored) — with a «Нет связи» page when the network is gone.
 * A new version of the site (VERSION) starts a new cache and drops the old one. */
const VERSION = {{ version|tojson }};
const CACHE = 'verdict-' + VERSION;
const OFFLINE = '/offline';
const KEEP = [OFFLINE, '/assets/img/icon-192.png', '/assets/img/favicon.svg'];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(KEEP)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(caches.keys()
    .then((keys) => Promise.all(keys.filter((k) => k.startsWith('verdict-') && k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

const fromCache = async (request) => {
  const cache = await caches.open(CACHE);
  const hit = await cache.match(request);
  if (hit) return hit;
  const response = await fetch(request);
  if (response.ok) cache.put(request, response.clone());  // never opaque answers: they eat the storage quota
  return response;
};

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  const own = url.origin === self.location.origin;
  if ((own && url.pathname.startsWith('/assets/')) || url.hostname === 'fonts.gstatic.com' || url.hostname === 'fonts.googleapis.com') {
    event.respondWith(fromCache(request));
  } else if (request.mode === 'navigate' && own) {
    event.respondWith(fetch(request).catch(() => caches.match(OFFLINE)));
  }
});
