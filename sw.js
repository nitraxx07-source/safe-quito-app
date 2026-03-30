const CACHE_NAME = 'safequito-v1';
const ASSETS = [
  './',
  './index.html',
  './manifest.json',
  './icon-100.png'
];

self.addEventListener('install', (evt) => {
  evt.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS);
    })
  );
});

self.addEventListener('fetch', (evt) => {
  evt.respondWith(
    fetch(evt.request).catch(() => caches.match(evt.request))
  );
});
