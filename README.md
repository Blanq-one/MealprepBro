# Mealbro

A personal meal-prep and grocery optimizer. Build rules: [`CLAUDE.md`](CLAUDE.md). Product vision:
[`docs/PRD.md`](docs/PRD.md). Build plan and progress: [`docs/BUILD_PLAN.md`](docs/BUILD_PLAN.md).
Data provenance: [`docs/data-sources.md`](docs/data-sources.md).

Status: Phase 2 (mobile PWA): the planning brain from Phase 1 (seed and saved recipes first, Groq only for
uncovered slots, a PuLP/HiGHS solver, practical rounding, independent validation) behind an installable,
mobile-first PWA: the week, recipes with full instructions, inventory with quick add, a store-grouped grocery
checklist, plan generation with live progress, and Mark cooked. One password signs you in. Deployment target:
Vercel Hobby + Neon Free, $0/month (`docs/hosting.md`, `docs/deploy.md`; not deployed yet).

## Quickstart (Docker only)

Needs Docker Desktop (or Docker Engine + Compose v2).

```bash
cp .env.example .env
docker compose up -d db db-test          # Postgres 17 (dev) and a throwaway test database
docker compose build backend

# Run the tests (uses db-test and the committed USDA subset; no download needed)
docker compose run --rm backend uv run --frozen pytest

# Create the schema and load data into the dev database
docker compose run --rm backend uv run --frozen alembic upgrade head
docker compose run --rm backend uv run --frozen python -m app.cli usda-import \
    app/testing/fixtures/usda_subset/FoodData_Central_foundation_food_csv_2026-04-30 \
    app/testing/fixtures/usda_subset/FoodData_Central_sr_legacy_food_csv_2018-04
docker compose run --rm backend uv run --frozen python -m app.cli seed
docker compose run --rm backend uv run --frozen python -m app.cli ingredient-report
docker compose run --rm backend uv run --frozen python -m app.cli safety-table
docker compose run --rm backend uv run --frozen python -m app.cli mapping-review   # docs/review/usda_mappings.md

docker compose run --rm backend uv run --frozen python -m app.cli plan-week --no-llm --dry-run

docker compose up backend frontend       # PWA on http://localhost:3000, API on :8000 (docs at /docs)
```

Sign-in needs two lines in `.env` (once): `cd backend && uv run python -m app.cli hash-password` prints
`AUTH_PASSWORD_HASH=...` and `SESSION_SECRET=...`; paste both into `.env` and restart the backend.

## Run it on your phone over home Wi-Fi

1. Put `AUTH_PASSWORD_HASH` and `SESSION_SECRET` in `.env` (above). Keep `SESSION_COOKIE_SECURE=false` there:
   home Wi-Fi is plain http, and a Secure cookie would never come back.
2. `docker compose up -d db db-test`, then `docker compose run --rm backend uv run --frozen alembic upgrade head`
   (and `seed`, if this database is new), then `docker compose up backend frontend`.
3. Find this PC's Wi-Fi address: `ipconfig` → "Wireless LAN adapter Wi-Fi" → IPv4 (for example `10.0.0.186`).
4. On the iPhone, on the same Wi-Fi, open **Safari** at `http://<that address>:3000` and sign in.
   If it can't connect, Windows Firewall is blocking port 3000: allow Docker Desktop (or Node, without Docker)
   on **private** networks.
5. **Share → Add to Home Screen** works here too, but over plain http iOS won't run the service worker, so
   offline use needs the https deploy (`docs/deploy.md`). The installable/offline build can be tried on this PC
   with `cd frontend && npm run build && npm run preview` (http://localhost:4173, proxying /api to :8000).

Without Docker for the PWA: `cd frontend && npm ci && npm run dev` (it proxies `/api` to `BACKEND_ORIGIN`,
default `http://localhost:8000`) and `cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000`.


For the full USDA cache instead of the subset, download the two zips listed in
[`docs/data-sources.md`](docs/data-sources.md) into `data/raw/usda/` and run `usda-import` with no arguments.

## Frontend (Next.js + TypeScript, `frontend/`)

```bash
cd frontend
npm ci
npm run dev          # http://localhost:3000, proxies /api and /health to BACKEND_ORIGIN
npm test             # Vitest
npm run typecheck    # tsc --noEmit
npm run build        # static export to out/ (what Vercel serves)
npm run gen:api      # regenerate src/lib/api/schema.d.ts from src/lib/api/openapi.json
```

The API types come from the backend's OpenAPI schema: `cd backend && uv run python -m app.cli openapi`, then
`npm run gen:api`. The PWA does no nutrition, unit or cost arithmetic; every number arrives from the API
(`src/test/no-math.test.ts` audits the source for it).

The app has four tabs: **Cook** (opens here), **Grocery**, **Pantry** and **Settings**. The first launch runs a
nine-screen setup (`/welcome/`) pre-filled from your saved settings. Light is the default; Settings → Appearance
switches to Dark or Match my phone (stored on each device).

## Local development (uv)

```bash
cd backend
uv sync                                  # Python 3.12 + locked dependencies
docker compose up -d db db-test
uv run pytest                            # all tests
uv run pytest --cov=app/domain           # domain coverage
uv run ruff check . && uv run ruff format --check . && uv run mypy app conftest.py
../scripts/fresh_clone_check.sh          # end of every phase: clone HEAD, build, test backend + frontend in Docker
RUN_PERF_TESTS=1 uv run pytest -m perf   # opt-in: the timed 30-candidate solve (wall clock, production limits)
uv run alembic upgrade head
uv run python -m app.cli usda-import     # reads USDA_RAW_DIR (default ../data/raw/usda)
uv run python -m app.cli seed
uv run uvicorn app.main:app --reload
```

## Planning a week (Phase 1)

```bash
cd backend
uv run python -m app.cli plan-week --week 2026-10-12 --no-llm --dry-run   # seed recipes only, 0 LLM calls
uv run python -m app.cli plan-week --week 2026-10-12                     # LLM fills uncovered slots (needs GROQ_API_KEY + LLM_MODEL)
uv run python -m app.cli plan-week --budget 60                           # shop mode with a hard $60 cash limit
uv run python -m app.cli plan-week --mode inventory                      # cook from what you have, buy nothing
uv run python -m app.cli plan-week --mode inventory --topup 15           # ...or allow $15 for missing items
uv run python -m app.cli plan-week --slot dinner=550 --slot drink=100 --minutes mon=60 --protein 120
```

Modes: `shop` (default) uses your inventory first, then builds the grocery list; `--budget` is a hard limit on cash
this trip for regular groceries (stock-up items such as protein powder, rice and oil are listed separately as "also buy
this week"), and without it the cost is minimized and reported. `inventory` buys nothing unless you allow `--topup`;
when nothing fits it says exactly what's missing. The daily protein target (default 100 g, `--protein`) is a floor,
never a reward.

It prints each day's meals, daily and weekly kcal and protein, hands-on and start-to-finish time per cook day, the
week's money (cash this trip, food eaten, leftovers carried into inventory, expected waste), cost by store (with the
Price Rite split rule) or the top-up buy list, freeze-on-shopping-day instructions for raw protein, notes and
warnings, or the reasons no plan fits. Without `--dry-run` the plan is saved as a draft; `--accept` makes it the
week's active plan.

Steady-state check (dry run): `uv run python -m app.cli simulate-weeks --week 2026-10-12 --weeks 2 --last-week-budget 50`
plans each week from the leftovers of the week before and prints regular cash, stock-up cash, food eaten, expected
waste and protein per day.

Hosting options for Phase 2 are compared in `docs/hosting.md`.

LLM tests use scripted responses. One opt-in smoke test calls Groq for real:
`RUN_LIVE_LLM_TESTS=1 uv run pytest -m live_llm -s`.

## API

Every `/api/v1` route needs a signed-in session cookie, except sign-in; changes must come from the app's own
origin. `GET /health` is open.

Phase 2b (cook-first flow, `docs/FLOW_SPEC.md`):

- `PATCH /api/v1/settings` (only the fields sent), `POST /api/v1/settings/preview` (field errors, "kcal a day
  planned" and summary lines; nothing saved), `GET /api/v1/settings/always-have` (the Always-have list, common
  staples first), `GET/POST /api/v1/stores`
- `PUT/DELETE /api/v1/recipes/{id}/favorite` and `/saved`, `GET /api/v1/recipes/saved?list=favorites|later`
- `GET /api/v1/inventory/quick-picks` carries `amount_options` and `custom_units`; `POST /api/v1/inventory/bulk`
  takes an `amount_option` key or a `custom_amount` + `custom_unit`

Phase 2:

- `POST /api/v1/auth/login` (`{"password"}` → 204 + HttpOnly cookie; 429 after too many tries),
  `POST /api/v1/auth/logout`, `GET /api/v1/auth/session`
- `POST /api/v1/plans` plans the week **inside the request** and streams `application/x-ndjson`: `started` (run
  id), `progress` and `heartbeat` lines, then one `result` with the plan summary or the problem.
  `GET /api/v1/plans` lists recent plans and marks the current one; `GET /api/v1/generation-runs/{id}` is the
  kept run record
- `GET /api/v1/plans/{id}/grocery-list?group_by=store|category|none` (stock-up, "from your inventory",
  "check you have" and unpriced items in their own sections), `PATCH /api/v1/grocery-items/{id}` (check off,
  actual weight and price; repeatable), `POST /api/v1/grocery-lists/{id}/complete` ("Done shopping": inventory
  lots + per-store prices, exactly once)
- `GET /api/v1/cook-batches/{id}` (the recipe at the batch's practical quantities),
  `POST /api/v1/cook-batches/{id}/cooked` (deducts inventory, open packages first; 409 the second time)
- `POST /api/v1/inventory/parse` (natural-language note → preview, nothing saved), `POST /api/v1/inventory/bulk`,
  `GET /api/v1/inventory/quick-picks`
- `POST /api/v1/prices` takes an optional `client_ref` (an offline entry is stored once)

Phase 1:

- `POST /api/v1/plans` (Phase 1 returned `202` and solved in the background; replaced in Phase 2, see above)
- `GET /api/v1/plans/{id}` (the weekly summary), `POST /api/v1/plans/{id}/accept`,
  `GET /api/v1/plans/{id}/grocery-list?group_by=store`
- `GET /api/v1/recipes/{id}`, `GET /api/v1/recipe-versions/{id}?portions=&portion_size=` (rendered, with safety lines)
- `GET/PUT /api/v1/settings`, `PUT/DELETE /api/v1/settings/ingredient-preferences/{ingredient_id}`
- `GET/POST /api/v1/inventory`, `PATCH /api/v1/inventory/{id}`, `POST /api/v1/inventory/{id}/discard`
- `GET/POST /api/v1/products`, `PATCH/DELETE /api/v1/products/{id}`, `POST /api/v1/prices` (a store is required)
- `GET /api/v1/ingredients/suggested`, `POST /api/v1/ingredients/suggested/{name}/approve`

Phase 0:

- `GET /health`
- `GET /api/v1/ingredients?q=` — alias and fuzzy search, with diet status (allowed / excluded / held)
- `GET /api/v1/ingredients/{id}` — nutrition per 100 g, named units, aliases, current price per store
- `POST /api/v1/calculations/recipe` — nutrition and per-store cost for a list of lines; optional
  `scale_to_portions` rounds every line to a practical amount first
- `GET /api/v1/recipes/seed` — the draft seed recipes with per-serving nutrition and cost, or why they're incomplete

Errors are `application/problem+json`.
