// Keeps the app working offline once it's been opened.
//
// - The page itself: from the network when online (so updates arrive), from
//   the saved copy when not.
// - Scripts, styles, fonts and page data: saved the first time they're used,
//   then served from the saved copy. Page data is refreshed in the background.
// - Recitations are not handled here: the app saves those itself, only when
//   you choose to download them (see src/recite.ts).

const CACHE = 'hifz-app-v2';

// On install, save the page, the scripts and styles it names, and the page index,
// so the app opens offline even if the first visit ended before they were reused.
self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    const page = await fetch('./');
    const html = await page.clone().text();
    await cache.put('./', page);
    const assets = [...html.matchAll(/(?:src|href)="(?:\.\/)?(assets\/[^"]+)"/g)].map((m) => m[1]);
    await cache.addAll([...new Set(assets), 'manifest.webmanifest', 'data/index.json', 'icons/icon-192.png']);
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith('hifz-app-') && k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

async function fromNetwork(request) {
  const res = await fetch(request);
  if (res.ok) (await caches.open(CACHE)).put(request, res.clone());
  return res;
}

self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin) return;

  if (request.mode === 'navigate') {
    event.respondWith(fromNetwork(request).catch(async () => (await caches.match(request)) ?? caches.match('./')));
    return;
  }
  const isData = url.pathname.includes('/data/');
  // Ayah and word timings: always the latest (they get corrected), the saved copy only offline.
  if (/\/data\/(timings|words)\//.test(url.pathname)) {
    event.respondWith(fromNetwork(request).catch(async () => (await caches.match(request)) ?? Response.error()));
    return;
  }
  event.respondWith(caches.match(request).then((saved) => {
    if (saved) {
      if (isData) event.waitUntil(fromNetwork(request).catch(() => undefined));
      return saved;
    }
    return fromNetwork(request);
  }));
});
