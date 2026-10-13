# Deploying Mealbro: a step-by-step checklist ($0/month: Vercel Hobby + Neon Free)

Why this setup, and its limits: `docs/hosting.md`. **Nothing here has been done yet**: no accounts exist, the repo
has no GitHub remote and nothing is deployed. Work down the list and tick each box. It takes about an hour the
first time. If a screen looks different from what's described, or a command prints an error, stop there and send
me a screenshot or the output; don't improvise.

```
iPhone ──https──▶ Vercel project (one address, e.g. https://mealbro.vercel.app)
                    ├─ /api/*, /health ─▶ "api" service: FastAPI as one Python function (backend/)
                    └─ everything else ─▶ "web" service: the Next.js PWA, a static export (frontend/)
                    api ──pooled connection──▶ Neon Postgres (AWS us-east-1)
```

`vercel.json` (repo root) defines both services and the routing. The API function may run up to 300 s; planning
budgets 180 s of that (`PLAN_TIME_BUDGET_SECONDS`) and streams progress while it works.

**Where each secret lives.** Your password hash, session secret, Groq key and Neon connection strings go into
**Vercel's settings page only** (step 6), and into the terminal for the one-time database load (step 5). Never
into a file in the repo, never into `.env.example`. Both free plans stay free: over a limit, Vercel Hobby pauses
the feature for 30 days and Neon Free pauses the database; neither bills you.

Commands below are for **Git Bash** (it came with Git for Windows). PowerShell equivalents are given where they
differ.

---

## 1. Check that nothing secret is in the repo

- [ ] In Git Bash, from the repo folder:

  ```bash
  git status                                    # "nothing to commit, working tree clean"
  git ls-files | grep -i "\.env"                # only: .env.example
  git log --all -p | grep -cE "gsk_[A-Za-z0-9]{20,}|scrypt:[0-9]+:[0-9]+:[0-9]+:[A-Za-z0-9_-]{16,}:"   # 0
  ```

  The last line looks through every commit ever made for a Groq key or a password hash: it must print `0`. (I ran
  the same checks on 2026-10-13: `.env` has never been committed, only `.env.example`, which holds placeholders.)
  Your real `.env` stays on your PC; `.gitignore` keeps it out.

## 2. Push the code to a private GitHub repository

- [ ] Sign in at **github.com** (or create a free account).
- [ ] Click **+** (top right) → **New repository**. Name: `mealbro`. Choose **Private**. Leave "Add a README",
  ".gitignore" and "license" **off** (the repo already has them). Click **Create repository**.
- [ ] Back in Git Bash, in the repo folder (replace `<you>` with your GitHub user name):

  ```bash
  git remote add origin https://github.com/<you>/mealbro.git
  git push -u origin master
  ```

  The first push opens a browser window to sign in to GitHub; approve it.
- [ ] On the repository's GitHub page: it says **Private** next to the name, and there is no `.env` in the file
  list (`.env.example` is fine).

From now on, every `git push` of `master` deploys the app (once step 6 is done).

## 3. Create the Neon database

- [ ] Sign up at **neon.com** (Free plan; "Sign up with GitHub" is fine).
- [ ] Create a project: name `mealbro`, Postgres version **17**, region **AWS US East 1 (N. Virginia)**. That's
  next to Vercel's default function region (`iad1`), so every database call is short.
- [ ] On the project dashboard, click **Connect**. Database `neondb`. Copy two connection strings into a password
  manager or a note **outside the repo folder**:
  - with **Connection pooling on** (the host contains `-pooler`): this is the **pooled** string, `DATABASE_URL`.
  - with **Connection pooling off**: this is the **direct** string, `DATABASE_URL_UNPOOLED`. Migrations and the
    one-time load use it, because the pooler runs PgBouncer in transaction mode.

  Both look like `postgresql://<user>:<password>@ep-xxxx.us-east-1.aws.neon.tech/neondb?sslmode=require`. They
  contain the database password: treat them like a password.

## 4. Make a new password and session secret for the live app

Use a **new** password, not the one on your PC: the live app is on the internet. A long passphrase is best
(four or more unrelated words); the minimum is 8 characters.

- [ ] In Git Bash:

  ```bash
  cd backend
  uv run python -m app.cli hash-password
  ```

  It asks for the password twice and prints two lines:

  ```
  AUTH_PASSWORD_HASH=scrypt:32768:8:1:...
  SESSION_SECRET=...
  ```

  Keep both lines with the Neon strings (outside the repo); they go into Vercel in step 6. The hash is made with the
  full work factor, and the secret is 64 random characters. The live app refuses to start with your PC's values,
  `.env.example`'s placeholders, or a hash made for tests (`app/production.py`).

## 5. Load the Neon database once, from your PC

This fills the new database: the schema (migrations), the USDA nutrition cache, then the seed (ingredients, stores,
prices, the seed recipes and your default settings). The live app starts fresh: the plans, inventory and settings
on your PC stay on your PC (if you want them copied over, ask me first).

- [ ] Docker isn't needed for this step. In a **new** Git Bash window, from the repo's `backend` folder, paste the
  **direct** string from step 3 between the quotes:

  ```bash
  export DATABASE_URL='postgresql://<user>:<password>@ep-xxxx.us-east-1.aws.neon.tech/neondb?sslmode=require'
  export DATABASE_URL_UNPOOLED="$DATABASE_URL"
  uv run python -m app.cli migrate        # the schema; the last line: "Running upgrade 0011 -> 0012, ..."
  uv run python -m app.cli usda-import    # the full USDA cache from data/raw/usda (a few minutes over the internet)
  uv run python -m app.cli seed           # ingredients, stores, prices, seed recipes, default settings
  uv run python -m app.cli plan-week --no-llm --dry-run   # a test plan from the cloud database; saves nothing
  ```

  (PowerShell instead of `export`: `$env:DATABASE_URL = '...'` and `$env:DATABASE_URL_UNPOOLED = $env:DATABASE_URL`.)

  These two variables win over your `.env`, so every command here talks to Neon, not to your PC's database. The
  last command prints a week of meals with its totals; if any command prints an error instead, stop and send it to
  me.
- [ ] **Close this terminal window** when done, so a later command can't reach Neon by accident.

The full USDA import is what lets you approve new ingredients later (it maps them to a USDA food); it fits Neon
Free easily (your PC's database is about 64 MB with it).

## 6. Create the Vercel project and set its variables

- [ ] Sign up at **vercel.com** with **Continue with GitHub**, on the **Hobby** plan.
- [ ] **Add New… → Project**. Under "Import Git Repository", connect GitHub; when GitHub asks which repositories
  Vercel may see, choose **Only select repositories** → `mealbro`. Click **Import** next to `mealbro`.
- [ ] On the configure screen: leave **Root Directory** as the repo root (`./`) and don't change the framework
  preset: `vercel.json` in the repo defines the two parts. Don't add variables here. Click **Deploy**.
- [ ] **This first deployment fails on purpose.** Its build log ends with
  `app.deploy: refusing to deploy to production: SESSION_SECRET is missing; AUTH_PASSWORD_HASH is missing; DATABASE_URL points at localhost, a local database, not your Neon one`.
  That's the production safety check doing its job: there are no settings yet.
- [ ] Open the project → **Settings → Environment Variables**. Add each row below. For **every** row, tick
  **Production only** (untick Preview and Development), so preview deployments have no database and can't touch
  your data. Turn on **Sensitive** for the rows marked so (Vercel then never shows the value again). Paste the
  value only: no quotes, no `NAME=` in front.

  | Name | Value | Sensitive |
  |---|---|---|
  | `DATABASE_URL` | the **pooled** Neon string (step 3, host has `-pooler`) | yes |
  | `DATABASE_URL_UNPOOLED` | the **direct** Neon string (step 3) | yes |
  | `AUTH_PASSWORD_HASH` | from step 4, everything after `AUTH_PASSWORD_HASH=` | yes |
  | `SESSION_SECRET` | from step 4, everything after `SESSION_SECRET=` | yes |
  | `GROQ_API_KEY` | a Groq key: at console.groq.com → **API Keys → Create API Key**, name it `mealbro-vercel` (its own key, so you can revoke it alone) | yes |
  | `LLM_MODEL` | `openai/gpt-oss-120b` (a Groq model with strict structured outputs) | no |
  | `LLM_IDEAS_MODEL` | `openai/gpt-oss-20b` (the faster model for meal ideas, as on your PC) | no |
  | `LLM_STRUCTURED_MODE` | `strict` | no |
  | `RUN_MIGRATIONS_ON_DEPLOY` | `1` (each production deploy runs new migrations first; see "Later deploys") | no |

  **Don't add** anything else from your `.env`. In particular not `SESSION_COOKIE_SECURE` (it must stay unset,
  which means true: https only; `false` makes the app refuse to start), `VERCEL` or `VERCEL_ENV` (Vercel sets them),
  `DB_POOL`, `TRUSTED_PROXIES`, `APP_ENV`, `TEST_DATABASE_URL`, `POSTGRES_*` or `BACKEND_ORIGIN`. Everything else has
  a working default (`.env.example` lists them all). On Vercel the app by itself uses one database connection per
  request, a Secure sign-in cookie, the client address Vercel reports for the sign-in limit, and no public `/docs`.

  Groq's free allowance (about 200K tokens a day) belongs to your Groq account, so your PC and the live app share
  it.
- [ ] **Deployments** tab → the failed deployment's **⋯** menu → **Redeploy**. This time the build log shows
  `app.deploy: migrating the production database` (nothing to do: step 5 already did it) and the deployment turns
  **Ready**. The first Python build takes a few minutes.

## 7. Check the live app (on your PC's browser)

- [ ] The project page shows its address under **Domains** (e.g. `https://mealbro.vercel.app`; Vercel adds a suffix
  if the name is taken). Open `https://<your address>/health`. It shows `{"status": "ok", "database": "ok"}` (the
  first visit may take a few seconds while Neon wakes up).
- [ ] Open `https://<your address>/`, sign in with the **new** password from step 4. (Five wrong tries within 15
  minutes pause sign-in from that device for a while, so don't test that on purpose.)
- [ ] `https://<your address>/docs` is **not found** (no public API docs on the live app).
- [ ] Make one plan: on the **Cook** tab choose meal prep, answer the questions, pick a budget card, and let it
  build. It finishes inside the request (progress lines while it works).

## 8. Check solve times in the run records

Every planning run keeps a record of what its solves took (`generation_run.progress["solve"]`). On your PC your dev
week plans in about 62 s of its 180 s; a Vercel function has one CPU, so it may be slower. Check after your first
few plans, and again after any change to the planner.

- [ ] In the Neon console, open your project → **SQL Editor**, paste this and click **Run**:

  ```sql
  select id, purpose, status,
         finished_at - started_at                     as took,
         progress->'solve'->>'seconds'                 as solver_seconds,
         progress->'solve'->>'week_solves'             as week_solves,
         progress->'solve'->>'repairs'                 as day_repairs,
         progress->'solve'->>'stopped_on_time'         as stopped_on_time,
         progress->'solve'->>'ran_out_of_time'         as ran_out_of_time,
         progress->'solve'->>'proven_best'             as proven_best
  from generation_run
  where progress ? 'solve'
  order by id desc
  limit 10;
  ```

- [ ] Healthy: `status` is `succeeded`, `took` is well under 3 minutes, `ran_out_of_time` is `false`. A
  `stopped_on_time` above 0 now and then is fine (that solve kept its best plan so far). If any row says
  `ran_out_of_time = true`, or `took` is over about 2.5 minutes, copy the rows and send them to me: the time limits
  may need tuning for Vercel's CPU.
- [ ] The budget cards share 90 s between them and show up one by one. If a card says "Taking longer than usual",
  it can still be picked, and Try again prices just the missing ones. Each request keeps a run record that says
  why (a cold start: the database or the function waking up; or the time budget):

  ```sql
  select id, status, created_at,
         progress->>'slow'                       as slow,
         progress->'timed_out'                   as timed_out,
         progress->'start'->>'cold_start'         as cold_start,
         progress->'start'->>'db_connect_s'       as db_connect_s,
         progress->'start'->>'process_age_s'      as process_age_s,
         progress->>'elapsed_s'                  as elapsed_s,
         progress->'cached'                      as cached
  from generation_run
  where purpose = 'tier_cards'
  order by id desc
  limit 10;
  ```

(Signed in on the live app, `https://<your address>/api/v1/generation-runs/<id>` shows one run's full record too.)

## 9. Check it on the iPhone

- [ ] Open your address in **Safari** (not another browser: only Safari can add a web app to the Home Screen with
  offline support). Sign in.
- [ ] **Share → Add to Home Screen → Add**. Open Mealbro from its new icon: it opens full screen, without Safari's
  address bar.
- [ ] Open this week's plan, a recipe, Inventory and the grocery list once while online.
- [ ] Turn on **Airplane Mode**, close Mealbro (swipe it away) and open it again from the icon: the plan, its
  recipes, the inventory and the grocery list still open. Tick one grocery item.
- [ ] Turn Airplane Mode off and open Mealbro again: the tick is still there (it was sent once you were back online).
- [ ] Days later: you're still signed in. The sign-in cookie lasts 180 days and renews itself as you use the app.

## Later deploys

- Every `git push` of `master` builds and deploys production, so only you push (CLAUDE.md: I commit, never push). The build step (`python -m app.deploy`) first runs
  the safety checks, then, with `RUN_MIGRATIONS_ON_DEPLOY=1`, any new migrations over the direct connection before
  the new code goes live. That's safe while the old code is still serving, because every migration is additive
  (BUILD_PLAN §4.1: new tables, nullable columns, indexes; nothing renamed or dropped). New seed recipes or prices
  need `uv run python -m app.cli seed` against Neon, as in step 5.
- Rather migrate by hand? Set `RUN_MIGRATIONS_ON_DEPLOY` to `0` and run step 5's `migrate` line before pushing a
  change that adds a migration.
- Something broke? **Deployments** → the last good one → **⋯ → Promote to Production** (Instant Rollback) puts the
  previous code back in seconds; the additive migrations mean the older code still works on the newer schema.
- Changing the password: run step 4 again, replace both `AUTH_PASSWORD_HASH` and `SESSION_SECRET` on Vercel, then
  Redeploy. A new `SESSION_SECRET` signs every device out.
- Branches other than `master` get preview deployments without any of step 6's settings: they build, but have no
  database and no keys, so they can't touch your data. That's intended.

## If something goes wrong

| What you see | What it means |
|---|---|
| Build log: `refusing to deploy to production: ...` | A setting in step 6 is missing or wrong; the message names it. Fix it on Vercel, then Redeploy. |
| `SESSION_SECRET looks like a dev or example value` | A placeholder or a short, made-up value: use step 4's. |
| `AUTH_PASSWORD_HASH isn't a password hash` | Usually quotes, a space, or `AUTH_PASSWORD_HASH=` pasted along with it. |
| `DATABASE_URL points at localhost` | The variable isn't set for **Production**, or holds your PC's URL. |
| `/health` shows `"database": "error"` | The pooled string is wrong, or the Neon project is paused; check it in the Neon console. |
| Sign-in always says the password is wrong | The hash on Vercel isn't from the password you're typing: run step 4 again. |
| A plan stops with a Groq message | The key, `LLM_MODEL` or the day's Groq allowance; the message says which. |
| "Taking longer than usual" with Try again | The database didn't answer in time (Neon waking from scale-to-zero) or a budget card ran out of time; Try again. The tier cards' run record (step 8) says which. |

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
use needs the https deploy. At home every device shares one sign-in counter (five wrong tries in 15 minutes
pause sign-in for all of them): the Next dev server passes a device's own `X-Forwarded-For` along unchanged, so
the backend believes no forwarded address there. On Vercel each device gets its own counter.
