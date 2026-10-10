/* Mealbro service worker (hand-written, no build step).
 *
 * Offline (Q18): the app shell and everything already loaded stay readable without a connection.
 * - App pages: network first, the cached page when offline (query strings ignored: one page per screen).
 * - /_next/static/* and icons: cache first (file names change with every build).
 * - API GETs under /api/v1/ (not /api/v1/auth/): network first, the last good answer when offline, marked
 *   with `x-mealbro-cache: hit` so the screen can say it is showing the offline copy.
 * - Anything that isn't a GET is never cached (the page's own offline queue handles check-offs).
 */
const VERSION = "v2"; // v2 (Phase 2b): the four tabs, onboarding and the Settings editors
const SHELL_CACHE = `mealbro-shell-${VERSION}`;
const STATIC_CACHE = `mealbro-static-${VERSION}`;
const API_CACHE = `mealbro-api-${VERSION}`;
const SHELL_PAGES = [
  "/",
  "/cook/",
  "/welcome/",
  "/plan/",
  "/plan/new/",
  "/day/",
  "/recipe/",
  "/pantry/",
  "/inventory/",
  "/grocery/",
  "/settings/",
  "/settings/edit/",
  "/login/",
];
const SHELL_FILES = [
  "/manifest.webmanifest",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/icons/apple-touch-icon.png",
];
const CACHE_HEADER = "x-mealbro-cache";

/** Which strategy serves a request: "page" | "data" | "static" | "api" | "network". Pure, so it can be
 * tested. */
function strategyFor(url, method) {
  const u = typeof url === "string" ? new URL(url, "https://app.invalid") : url;
  if ((method || "GET").toUpperCase() !== "GET") return "network";
  const path = u.pathname;
  if (path.startsWith("/api/v1/auth/")) return "network";
  if (path.startsWith("/api/")) return "api";
  if (path === "/health") return "network";
  if (path.startsWith("/_next/static/") || path.startsWith("/icons/")) return "static";
  if (path === "/manifest.webmanifest" || path === "/sw.js") return "network";
  if (path.startsWith("/_next/")) return "network";
  const last = path.split("/").pop() || "";
  if (last.endsWith(".txt")) return "data"; // the page data Next fetches on in-app navigation
  if (path.endsWith("/") || !last.includes(".") || last.endsWith(".html")) return "page";
  return "network";
}

/** The /_next/static/ files a page's HTML loads, so a page opened offline for the first time still works. */
function assetsIn(html) {
  const found = new Set();
  const pattern = /(?:src|href)="(\/_next\/static\/[^"?#]+)"/g;
  let match = pattern.exec(html);
  while (match) {
    found.add(match[1]);
    match = pattern.exec(html);
  }
  return Array.from(found);
}

function pageKey(url) {
  const u = new URL(url);
  let path = u.pathname;
  if (!path.endsWith("/") && !path.split("/").pop().includes(".")) path += "/";
  return new Request(u.origin + path);
}

async function precache() {
  const shell = await caches.open(SHELL_CACHE);
  const staticCache = await caches.open(STATIC_CACHE);
  await Promise.all(
    SHELL_FILES.map((file) => shell.add(file).catch(() => undefined)),
  );
  for (const page of SHELL_PAGES) {
    try {
      const response = await fetch(page, { credentials: "same-origin" });
      if (!response.ok) continue;
      await shell.put(page, response.clone());
      const assets = assetsIn(await response.text());
      await Promise.all(assets.map((asset) => staticCache.add(asset).catch(() => undefined)));
    } catch {
      // offline during install: the next visit fills the cache
    }
  }
}

function markCached(response) {
  const headers = new Headers(response.headers);
  headers.set(CACHE_HEADER, "hit");
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers });
}

async function networkFirstPage(request) {
  const cache = await caches.open(SHELL_CACHE);
  try {
    const response = await fetch(request);
    if (response.ok) await cache.put(pageKey(request.url), response.clone());
    return response;
  } catch {
    const cached = (await cache.match(pageKey(request.url))) || (await cache.match("/cook/"));
    return cached || Response.error();
  }
}

async function cacheFirst(request) {
  const cache = await caches.open(STATIC_CACHE);
  const cached = await cache.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok) await cache.put(request, response.clone());
  return response;
}

async function networkFirstApi(request) {
  const cache = await caches.open(API_CACHE);
  try {
    const response = await fetch(request);
    if (response.ok) await cache.put(request, response.clone());
    return response;
  } catch {
    const cached = await cache.match(request);
    return cached ? markCached(cached) : Response.error();
  }
}

if (typeof self !== "undefined" && typeof self.addEventListener === "function") {
  self.addEventListener("install", (event) => {
    event.waitUntil(precache().then(() => self.skipWaiting()));
  });

  self.addEventListener("activate", (event) => {
    const keep = new Set([SHELL_CACHE, STATIC_CACHE, API_CACHE]);
    event.waitUntil(
      caches
        .keys()
        .then((keys) => Promise.all(keys.filter((k) => k.startsWith("mealbro-") && !keep.has(k)).map((k) => caches.delete(k))))
        .then(() => self.clients.claim()),
    );
  });

  self.addEventListener("fetch", (event) => {
    const request = event.request;
    const url = new URL(request.url);
    if (url.origin !== self.location.origin) return;
    const strategy = strategyFor(url, request.method);
    if (strategy === "page" && request.mode === "navigate") event.respondWith(networkFirstPage(request));
    else if (strategy === "static") event.respondWith(cacheFirst(request));
    else if (strategy === "api" || strategy === "data") event.respondWith(networkFirstApi(request));
  });

  self.addEventListener("message", (event) => {
    if (event.data === "clear-api-cache") event.waitUntil(caches.delete(API_CACHE));
  });
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { strategyFor, assetsIn, SHELL_PAGES };
}
