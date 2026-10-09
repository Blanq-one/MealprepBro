import type { NextConfig } from "next";

// Production builds are a static export (out/): Vercel serves the files from its CDN and the service worker
// can cache every page for offline use. In development, `next dev` proxies the API to the FastAPI backend so the
// browser (or your phone on the home Wi-Fi) talks to one origin and the session cookie just works.
const isDev = process.env.NODE_ENV !== "production";
const backend = process.env.BACKEND_ORIGIN ?? "http://localhost:8000";

// Next blocks dev assets requested from another host; allow the private LAN ranges (your phone opens
// http://<PC address>:3000) plus anything in DEV_ALLOWED_ORIGINS (comma-separated host names).
const privateLan = [
  "192.168.*.*",
  "10.*.*.*",
  ...Array.from({ length: 16 }, (_, i) => `172.${16 + i}.*.*`),
  "*.local",
];
const extra = (process.env.DEV_ALLOWED_ORIGINS ?? "")
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean);

const config: NextConfig = {
  reactStrictMode: true,
  trailingSlash: true,
  images: { unoptimized: true },
  agentRules: false, // don't let `next dev` write AGENTS.md / CLAUDE.md into the repo
  ...(isDev
    ? {
        // trailingSlash would 308-redirect /api/v1/plans to /api/v1/plans/ before the proxy below runs
        skipTrailingSlashRedirect: true,
        allowedDevOrigins: [...privateLan, ...extra],
        async rewrites() {
          return [
            { source: "/api/:path*", destination: `${backend}/api/:path*` },
            { source: "/health", destination: `${backend}/health` },
          ];
        },
      }
    : { output: "export" }),
};

export default config;
