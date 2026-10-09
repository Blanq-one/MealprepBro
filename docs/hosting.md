# Hosting comparison (A3)

**Status:** research only, 2026-10-09. No code was written and no accounts were created. Prices come from each provider's own pricing and docs pages on that date (links below). Most pricing pages carry no date. Anything I couldn't confirm on a provider's own page is marked *(unverified)*. Check prices again before you sign up.

## What has to be hosted

- **FastAPI backend.** One Docker image (Python 3.12, numpy, the HiGHS solver). A plan request returns `202` and then solves for about 5–15 s of CPU in a FastAPI background task while the app polls. It needs about 1 GB of RAM to be comfortable.
- **PostgreSQL.** Small: well under 1 GB. It holds your settings, recipes, prices, inventory, plans and ratings, so it needs backups.
- **Next.js PWA.** Static files plus a service worker. iOS installs PWAs and runs service workers **only over HTTPS**.
- **Use pattern.** One user (you), a few dozen requests a day. It has to be up and quick when you're standing in the store.

## The options

| Option | Monthly cost | Setup effort | Cold starts | Postgres | HTTPS | Single-user auth |
|---|---|---|---|---|---|---|
| **A. Railway Hobby** (backend + Postgres + PWA) | **$5**, which includes $5 of usage. An idle API plus a small database probably fits *(estimate)* | Low: deploy the Dockerfile from GitHub, add the Postgres template | None (always on, unless you turn on "Serverless") | Built in, with native backups | Automatic on `*.up.railway.app`; custom domain optional | App password + signed session cookie |
| **B. Fly.io + Neon Free** | **$3.69** (512 MB) to **$6.70** (1 GB) for one always-on machine; Neon free | Medium: two vendors, `fly.toml`, secrets | None if always on. With auto-stop, a wake-up after a few idle minutes (no published timing) | Neon Free: 1 GB, 100 compute-hours a month, sleeps after 5 min idle, wakes in a few hundred ms. Fly's own Managed Postgres is $38/mo | Automatic (`*.fly.dev`) | App password + cookie |
| **C. Your PC at home + Tailscale** | **$0** | Low to medium: Tailscale on the PC and the iPhone, `tailscale serve` | None while the PC is on and awake | Your existing Docker Postgres. Backups are your job | Let's Encrypt certificate for `machine.tailXXXX.ts.net`, issued by Tailscale | The private network is the auth layer (Tailscale Personal: free, up to 6 users) |
| **D. Small VPS + Caddy** (Docker Compose) | Hetzner EU CX23 (2 vCPU / 4 GB) **€5.49 ≈ $6.49**, plus €0.50 IPv4. Hetzner US starts at **$20.49** after its 2026 price rises. DigitalOcean **$6** (1 GB) or **$12** (2 GB). Plus a domain, about **$10.46/yr** (.com, rising to about $11.17 on Nov 1, 2026) *(unverified)* | High: OS updates, firewall, backups, monitoring | None | Self-hosted in Compose. Backups are your job | Caddy fetches and renews Let's Encrypt certificates automatically | App password + cookie, or Cloudflare Access |
| **E. Render** | Free tier unsuitable (see below). Paid: **$7** (Starter, 0.5 CPU) + **$6** (Postgres Basic-256mb) ≈ **$13** | Low | Free: sleeps after 15 min, about **1 min** to wake. Paid: none | Free Postgres **expires after 30 days**. Paid is fine | Automatic | App password + cookie |
| **F. Google Cloud Run + Neon** | Free tier is generous, but see the next column | Medium | Scale to zero, then a cold start | Neon Free | Automatic (`*.run.app`) | App password + cookie |

### Why some options are out

- **Render Free:** 0.1 CPU means a 5–15 s solve could take minutes *(estimate)*. The free database is deleted after 30 days plus a 14-day grace period.
- **Cloud Run, default billing:** the docs say "CPU is only allocated during request processing", and warn against background work after the response. The `202` + background-task design would be starved of CPU.
  - Instance-based billing fixes that, but bills the instance's whole lifetime, roughly $44/mo for one always-on instance *(my arithmetic, unverified)*.
  - Otherwise the backend would need redesigning (solve inside the request, or Cloud Tasks).
- **Supabase Free as the database:** projects pause after 7 days without activity, which is likely after a quiet week.
- **Fly Managed Postgres:** $38/mo is out of proportion for one user. The old free "Fly Postgres" is no longer maintained or supported.

### Frontend options

- **Serve it from the backend's host.** One origin is simplest: no CORS, and the session cookie just works.
- **Vercel Hobby** (free, non-commercial personal use allowed) or **Cloudflare Pages/Workers** (free; a static `next export` is the simple route).
- Either way, have the service worker cache the plan and grocery list, so a dead zone in the store doesn't matter.

## Recommendation: A, Railway Hobby

- **Cost:** about **$5/mo**, all in, if usage stays inside the included $5.
- **Fits the current code as is:** the backend runs always on, with no cold start, and the `202` + background-task solve keeps its CPU after the response. Nothing about the current backend design needs to change.
- **Database:** Railway's Postgres template, with native backups.
- **Frontend:** served as static files by the same service, so there's one origin. A second Railway service also works.
- **HTTPS:** automatic on the Railway domain, which is all the iPhone PWA needs. A custom domain is optional.
- **Auth:** one password, set as an environment secret, exchanged for a signed `HttpOnly; Secure; SameSite=Lax` session cookie (stdlib HMAC, as planned). Long-lived, so the installed PWA stays signed in. Add a simple rate limit on the login endpoint.
- **Before relying on it:** check the first month's usage on the dashboard. Railway bills overage beyond the included $5 *(I couldn't verify whether a hard spending cap is available)*. Keep Serverless mode **off**: its first request after sleeping can return a 502, which would break polling.

**Runner-up: B, Fly.io + Neon Free** (about $4–7/mo). Choose it if you'd rather not be on usage-based billing. It means two vendors to manage.

**For development and Phase 2 testing: C, your PC + Tailscale.** It's free and there's no deploy step, but it depends on the PC being on and awake while you're at the store. That makes it a poor fit for daily use.

## Sources (checked 2026-10-09)

- **Railway:** railway.com/pricing; docs.railway.com/reference/app-sleeping; docs.railway.com/guides/postgresql
- **Fly.io:** docs.fly.io/about/pricing; docs.fly.io/launch/autostop-autostart; docs.fly.io/mpg; docs.fly.io/unmanaged-postgres
- **Neon:** neon.com/pricing; neon.com/docs/introduction/plans; neon.com/docs/introduction/scale-to-zero
- **Render:** render.com/docs/free; render.com/docs/compute-plans; render.com/changelog/updated-plans-for-render-workspaces; render.com/articles/how-much-does-cloud-application-hosting-cost-for-small-businesses (July 8, 2026)
- **Google Cloud Run:** docs.cloud.google.com/free/docs/free-cloud-features (updated 2026-10-07); Cloud Run billing settings, general tips, instance autoscaling and min-instances pages (updated 2026-10-07). Per-second prices are from search snippets of cloud.google.com/run/pricing *(unverified)*.
- **Supabase:** supabase.com/pricing; supabase.com/docs/guides/platform/upgrading
- **Vercel:** vercel.com/docs/limits/fair-use-guidelines (updated 2026-09-14)
- **Cloudflare:** developers.cloudflare.com/workers/platform/pricing (Oct 2, 2026); developers.cloudflare.com/pages/platform/limits (Sep 5, 2026); Workers Next.js guide (Aug 25, 2026); cloudflare.com/plans (Zero Trust Free, 50 users)
- **Hetzner:** docs.hetzner.com/general/infrastructure-and-availability/price-adjustment (updated 2026-07-08)
- **DigitalOcean:** digitalocean.com/pricing/droplets
- **Tailscale:** tailscale.com/pricing; tailscale.com/kb/1153 (HTTPS certificates); tailscale.com/kb/1312 (serve)
- **Caddy:** caddyserver.com/docs/automatic-https
- **.com wholesale price:** industry reports citing Verisign's Q1 2026 results *(unverified)*
