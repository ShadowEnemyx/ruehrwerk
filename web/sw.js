// Service Worker: macht die App installierbar und hält die Oberfläche sowie bereits geladene Rezepte offline bereit.
const VERSION = 'ruehrwerk-v1';
const SHELL = ['/', '/style.css', '/app.js', '/manifest.webmanifest', '/icons/icon-192.png', '/icons/icon-512.png', '/icons/apple-touch-icon.png'];

self.addEventListener('install', (ev) => {
  ev.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (ev) => {
  ev.waitUntil(
    caches.keys().then((namen) => Promise.all(namen.filter((n) => n !== VERSION).map((n) => caches.delete(n)))).then(() => self.clients.claim()),
  );
});

async function netzZuerst(anfrage) {
  const cache = await caches.open(VERSION);
  try {
    const antwort = await fetch(anfrage);
    if (antwort.ok) cache.put(anfrage, antwort.clone());
    return antwort;
  } catch (fehler) {
    const treffer = await cache.match(anfrage);
    if (treffer) return treffer;
    throw fehler;
  }
}

self.addEventListener('fetch', (ev) => {
  const anfrage = ev.request;
  const url = new URL(anfrage.url);
  if (anfrage.method !== 'GET' || url.origin !== location.origin) return;
  // Rezepte und Bilder: Netz zuerst, bei Funkloch der zuletzt gesehene Stand
  if (url.pathname.startsWith('/api/rezepte/') || url.pathname.startsWith('/api/bild/')) {
    ev.respondWith(netzZuerst(anfrage));
    return;
  }
  if (url.pathname.startsWith('/api/')) return; // alles andere nie zwischenspeichern
  // Oberfläche: Netz zuerst (damit Updates ankommen), sonst Zwischenspeicher
  ev.respondWith(netzZuerst(anfrage));
});
