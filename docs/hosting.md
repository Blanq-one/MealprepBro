# Hosting (A3, revised)

**Decision (2026-10-09):** the deployment must cost **$0 a month**: **Vercel Hobby** (the Next.js PWA and the
FastAPI backend as Python functions, in one project) and **Neon Free** (Postgres). Railway is out. This
replaces the first comparison's recommendation (Railway Hobby, about $5/mo). Deploy steps: `docs/deploy.md`.

Facts below come from each provider's own pages, checked 2026-10-09 (links at the end). Check them again
before you sign up.

## The setup

| Part | Where | Notes |
|---|---|---|
| PWA (static files + service worker) | Vercel Hobby, Next.js service | Built as a static export, served from Vercel's CDN over HTTPS (iOS needs HTTPS for the service worker). |
| API (FastAPI) | Vercel Hobby, Python service | One Vercel Function (`app/main.py`), Python 3.12. `/api/*` and `/health` route to it on the **same domain** as the PWA, so the session cookie is first-party. |
| Database | Neon Free, AWS us-east-1 | Next to Vercel's default function region (`iad1`, Washington DC). The app uses the pooled (`-pooler`) connection string; migrations use the direct one. |

Both parts deploy together from one `vercel.json` using Vercel **Services** (beta, available on all plans):
one project, one domain, and each part built on its own.

## Limits that matter here

| Limit | Value | What it means for Mealbro |
|---|---|---|
| Function max duration (Hobby) | 300 s, default and maximum | Plan generation runs **inside the request**. The work has a 180 s budget (`PLAN_TIME_BUDGET_SECONDS`); validating and saving come after it. Nothing runs after the response. |
| Function memory / CPU (Hobby) | 2 GB / 1 vCPU | Enough for the solver (HiGHS, one thread). |
| Python bundle size | 500 MB uncompressed | The backend with all dependencies is about 230 MB. |
| Request/response body | 4.5 MB | Responses are small. |
| Hobby included usage, per month | 4 CPU-hours active CPU, 360 GB-hours memory, 1M invocations, 100 GB transfer | A plan uses roughly 10–60 s of CPU, so a few hundred plans a month fit. Over a limit, Hobby pauses that feature for 30 days; it never bills. |
| Hobby use | Personal, non-commercial only | Fits: one user. |
| Neon Free storage | 1 GB per project on Neon's pricing page today (you quoted 0.5 GB) | The dev database is **64 MB**, the full USDA cache included, so either figure fits. |
| Neon Free compute | 100 CU-hours per project per month; scales to zero after 5 idle minutes (can't be turned off on Free) | One user at 0.25 CU uses a small share. The first request after an idle spell waits for the compute to wake (usually well under a second); connecting retries cover a dropped first attempt. |
| Neon Free egress | 5 GB per month | Far more than one person's use. |
| Neon Free history | 6 hours of instant restore | Plus `scripts/backup.sh` (pg_dump) for longer-lived backups. |

## What changed in the app for serverless (Phase 2 pre-work)

- **Plan generation finishes inside the request.** `POST /api/v1/plans` used to return `202` and solve in a
  background task. On a serverless function, work after the response can be frozen or killed, so the
  request now runs the solve (and any LLM calls) and **streams progress lines** (NDJSON) until the finished
  plan arrives. The stream also keeps iOS Safari from dropping a request that stays silent for about a
  minute. Run records are still kept; a run that never finished is marked "interrupted" later.
- **A time budget.** Every LLM call, rate-limit wait and solve checks what's left of the 180 s budget. When
  it runs out during recipe generation, the recipes made so far are saved and the week is planned with them;
  planning again carries on from there.
- **Connections.** On Vercel each request opens its own short-lived connection (no pool to go stale) to Neon's
  PgBouncer endpoint, without psycopg's server-side prepared statements, and connecting retries with back-off
  while a compute wakes from scale-to-zero. Migrations use the direct connection.
- **Sign-in rate limiting** is counted in the database, since function instances share no memory.

## Options considered before (for the record)

The first comparison (Railway Hobby ≈ $5/mo, Fly.io + Neon ≈ $4–7/mo, a home PC + Tailscale at $0, a VPS +
Caddy, Render, Cloud Run + Neon) is in this file's git history. Your PC + Tailscale stays a $0 alternative,
but it depends on the PC being on while you're at the store.

## Sources (checked 2026-10-09)

- Vercel: vercel.com/docs/functions/limitations (updated 2026-08-24); vercel.com/docs/functions/runtimes/python
  (2026-08-12); vercel.com/docs/frameworks/backend/fastapi (2026-08-27); vercel.com/docs/services,
  /docs/services/routing and /docs/services/config-reference (2026-06-30 to 2026-08-10); vercel.com/docs/plans/hobby
  (2026-09-14)
- Neon: neon.com/pricing; neon.com/docs/introduction/plans; neon.com/docs/connect/connection-pooling
- iOS Safari's ~60 s idle cutoff: WebKit bug reports 19758 and 165897 and Apple developer forum threads (older
  reports; not confirmed for current iOS, so the app streams regardless)
