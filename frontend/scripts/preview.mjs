// Serve the static build (out/) like the deployed app, so the service worker and offline mode can be tried on
// http://localhost (browsers allow service workers there without HTTPS). /api and /health are proxied to the
// backend, keeping one origin for the session cookie. No dependencies.
//
//   npm run build && npm run preview            (BACKEND_ORIGIN defaults to http://localhost:8000, PORT to 4173)
import { createReadStream, existsSync, statSync } from "node:fs";
import http from "node:http";
import { extname, join, normalize, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(fileURLToPath(new URL("..", import.meta.url)), "out");
const BACKEND = new URL(process.env.BACKEND_ORIGIN ?? "http://localhost:8000");
const PORT = Number(process.env.PORT ?? 4173);
const HOST = process.env.HOST ?? "0.0.0.0";
const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json",
  ".webmanifest": "application/manifest+json",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".txt": "text/plain; charset=utf-8",
  ".woff2": "font/woff2",
};

if (!existsSync(ROOT)) {
  console.error("No out/ folder: run `npm run build` first.");
  process.exit(1);
}

function proxy(req, res) {
  const upstream = http.request(
    {
      protocol: BACKEND.protocol,
      hostname: BACKEND.hostname,
      port: BACKEND.port || 80,
      method: req.method,
      path: req.url,
      headers: { ...req.headers, host: BACKEND.host, "x-forwarded-host": req.headers.host ?? "" },
    },
    (answer) => {
      res.writeHead(answer.statusCode ?? 502, answer.headers);
      answer.pipe(res); // streams NDJSON line by line
    },
  );
  upstream.on("error", (error) => {
    res.writeHead(502, { "content-type": "text/plain" });
    res.end(`backend unreachable: ${error.message}`);
  });
  req.pipe(upstream);
}

function fileFor(pathname) {
  const safe = normalize(decodeURIComponent(pathname)).replace(/^([/\\])+/, "");
  const candidate = join(ROOT, safe);
  if (!candidate.startsWith(ROOT + sep) && candidate !== ROOT) return null;
  if (existsSync(candidate) && statSync(candidate).isDirectory()) return join(candidate, "index.html");
  if (existsSync(candidate)) return candidate;
  if (existsSync(`${candidate}.html`)) return `${candidate}.html`;
  return null;
}

http
  .createServer((req, res) => {
    const url = new URL(req.url ?? "/", "http://preview.invalid");
    if (url.pathname.startsWith("/api/") || url.pathname === "/health") return proxy(req, res);
    const file = fileFor(url.pathname);
    if (!file || !existsSync(file)) {
      const notFound = join(ROOT, "404.html");
      res.writeHead(404, { "content-type": TYPES[".html"] });
      return existsSync(notFound) ? createReadStream(notFound).pipe(res) : res.end("Not found");
    }
    const headers = { "content-type": TYPES[extname(file)] ?? "application/octet-stream" };
    if (url.pathname === "/sw.js") headers["cache-control"] = "no-cache";
    res.writeHead(200, headers);
    createReadStream(file).pipe(res);
  })
  .listen(PORT, HOST, () => {
    console.log(`Mealbro preview on http://localhost:${PORT} (API -> ${BACKEND.origin})`);
  });
