# Deploying Mealbro ($0/month: Vercel Hobby + Neon Free)

Why this setup, and its limits: `docs/hosting.md`. Nothing here has been run yet: no accounts exist and nothing
is deployed. These are the steps for you to follow.

```
browser ──https──▶ Vercel project (one domain)
                    ├─ /api/*, /health ─▶ "api" service: FastAPI as one Python function (backend/)
                    └─ everything else ─▶ "web" service: the Next.js PWA, static export (frontend/)
                    api ──pooled connection──▶ Neon Postgres (AWS us-east-1)
```

`vercel.json` (repo root) defines both services and the routing. The API function may run up to 300 s;
planning budgets 180 s of that (`PLAN_TIME_BUDGET_SECONDS`) and streams progress while it works.

## 1. Neon (database)

1. Sign up at neon.com (Free plan). Create a project **mealbro**, Postgres **17**, region **AWS US East
   (N. Virginia)**, which is next to Vercel's default function region (`iad1`).
2. In **Connect**, copy two connection strings for the `neondb` database:
   - **pooled** (Connection pooling on; the host contains `-pooler`): this is `DATABASE_URL`.
   - **direct** (pooling off): this is `DATABASE_URL_UNPOOLED`. Migrations, `pg_dump` and the one-time
     data load use it, because the pooler runs PgBouncer in transaction mode.

## 2. Load the database once, from your PC

From `backend/`, with the direct string (PowerShell: `$env:DATABASE_URL = "postgresql://..."` instead of
`export`):

```bash
export DATABASE_URL='postgresql://<user>:<password>@ep-xxxx.us-east-1.aws.neon.tech/neondb?sslmode=require'
uv run python -m app.cli migrate        # creates the schema (alembic upgrade head)
uv run python -m app.cli usda-import    # the full USDA cache from data/raw/usda (64 MB; COPY, a minute or two)
uv run python -m app.cli seed           # ingredients, stores, prices, seed recipes, your default settings
uv run python -m app.cli plan-week --no-llm --dry-run   # sanity check against the cloud database
```

The full USDA import is what lets you approve new ingredients later (it maps them to a USDA food). It fits
Neon Free easily; `usda-import app/testing/fixtures/usda_subset/*` loads only the foods the seed uses.

## 3. Your password

```bash
cd backend && uv run python -m app.cli hash-password
```

It asks for the password twice and prints two lines, `AUTH_PASSWORD_HASH=...` and `SESSION_SECRET=...`, for
the next step. The hash has no `$`. A new `SESSION_SECRET` signs out every device.

## 4. Vercel (app)

1. Push this repository to a private GitHub repo (Vercel deploys from Git; it has no remote yet).
2. Sign up at vercel.com (Hobby). **Add New → Project**, import the repo, leave **Root Directory** as the
   repo root (`vercel.json` there defines the two services). Don't add a framework preset by hand.
3. **Settings → Environment Variables**, all for the **Production** environment only (preview deployments
   then have no database and can't touch your data):

   | Variable | Value |
   |---|---|
   | `DATABASE_URL` | the **pooled** Neon string |
   | `DATABASE_URL_UNPOOLED` | the **direct** Neon string |
   | `AUTH_PASSWORD_HASH` | from step 3 |
   | `SESSION_SECRET` | from step 3 |
   | `GROQ_API_KEY` | your Groq key |
   | `LLM_MODEL` | e.g. `openai/gpt-oss-120b` (a Groq model with strict structured outputs) |
   | `LLM_STRUCTURED_MODE` | `strict` |
   | `RUN_MIGRATIONS_ON_DEPLOY` | `1` (see step 5), or leave unset and migrate by hand |

   Everything else has a working default (`.env.example` lists them). Don't copy
   `SESSION_COOKIE_SECURE=false` from your local `.env`: on Vercel it must stay unset (true). On Vercel the app itself switches to
   one connection per request (`DB_POOL` null), secure cookies and no public `/docs`.
4. Deploy. Then open `https://<project>.vercel.app/health` (`{"status": "ok", "database": "ok"}`: this also wakes the database) and the app's sign-in page.

## 5. Migrations on deploy

The backend's build step is `python -m app.deploy`. With `RUN_MIGRATIONS_ON_DEPLOY=1` on a **production**
deployment it runs `alembic upgrade head` over the direct connection before the new code goes live; on preview
deployments it does nothing. That is safe while the old code is still serving, because every migration is
additive (BUILD_PLAN §4.1: new tables, nullable columns, indexes; nothing renamed or dropped).

If you'd rather not migrate from the build, leave the flag unset and run `uv run python -m app.cli migrate`
from your PC (step 2's direct `DATABASE_URL`) before pushing a change that adds a migration.

## 6. On the iPhone

Open the `https://<project>.vercel.app` address in **Safari**, sign in, then **Share → Add to Home Screen**.
It launches full screen with its own icon; the sign-in cookie lasts 180 days and renews itself as you use it.
After one online visit the plan, its recipes, the inventory and the grocery list open offline; check-offs
and prices you enter offline are sent once you're back online.

## Backups

- Neon Free keeps **6 hours** of history you can restore in its console.
- For real backups, from the repo root: `DATABASE_URL_UNPOOLED='postgresql://...' scripts/backup.sh` writes
  `backups/mealbro-<time>.dump` (gitignored). It runs `pg_dump` from the `postgres:17` Docker image unless you
  have pg_dump 17 installed.
- Restore test (do it once): create a second, empty Neon branch or a local database, then
  `scripts/backup.sh restore backups/<file>.dump '<that database URL>'`.

## If Vercel Services (beta) gives you trouble

Fallback with two Vercel projects from the same repo:

1. **API project**, Root Directory `backend/`: Vercel detects FastAPI from `pyproject.toml` and `app/main.py`.
   Set the environment variables above and the build command `python -m app.deploy`.
2. **Web project**, Root Directory `frontend/`: add `frontend/vercel.json` with
   `{"rewrites": [{"source": "/api/:path*", "destination": "https://<api-project>.vercel.app/api/:path*"}]}`
   (and the same for `/health`). The browser still talks to one origin, so the session cookie keeps working.

## On your phone at home (before deploying)

See README.md, "Run it on your phone over home Wi-Fi". That runs over plain http, so sign-in uses a non-Secure
cookie (`SESSION_COOKIE_SECURE=false`, set by docker compose) and iOS won't run the service worker; offline
use needs the https deploy.
