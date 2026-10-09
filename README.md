# Mealbro

A personal meal-prep and grocery optimizer. Build rules: [`CLAUDE.md`](CLAUDE.md). Product vision:
[`docs/PRD.md`](docs/PRD.md). Build plan and progress: [`docs/BUILD_PLAN.md`](docs/BUILD_PLAN.md).
Data provenance: [`docs/data-sources.md`](docs/data-sources.md).

Status: Phase 1 (planning brain, backend only): weekly plans from your settings, seed and saved recipes first,
Groq only for uncovered slots, a PuLP/HiGHS solver, practical rounding, independent validation and a store-grouped
grocery list. No frontend yet (Phase 2).

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

docker compose up backend                # API on http://localhost:8000 (docs at /docs)
```

For the full USDA cache instead of the subset, download the two zips listed in
[`docs/data-sources.md`](docs/data-sources.md) into `data/raw/usda/` and run `usda-import` with no arguments.

## Local development (uv)

```bash
cd backend
uv sync                                  # Python 3.12 + locked dependencies
docker compose up -d db db-test
uv run pytest                            # all tests
uv run pytest --cov=app/domain           # domain coverage
uv run ruff check . && uv run ruff format --check . && uv run mypy app conftest.py
../scripts/fresh_clone_check.sh          # end of every phase: clone HEAD, build, test in Docker
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
this trip, and without it the cost is minimized and reported. `inventory` buys nothing unless you allow `--topup`;
when nothing fits it says exactly what's missing. The daily protein target (default 100 g, `--protein`) is a floor,
never a reward.

It prints each day's meals, daily and weekly kcal and protein, hands-on and start-to-finish time per cook day, the
week's money (cash this trip, food eaten, leftovers carried into inventory, expected waste), cost by store (with the
Price Rite split rule) or the top-up buy list, freeze-on-shopping-day instructions for raw protein, notes and
warnings, or the reasons no plan fits. Without `--dry-run` the plan is saved as a draft; `--accept` makes it the
week's active plan.

LLM tests use scripted responses. One opt-in smoke test calls Groq for real:
`RUN_LIVE_LLM_TESTS=1 uv run pytest -m live_llm -s`.

## API

Phase 1:

- `POST /api/v1/plans` → `202` with a run id; poll `GET /api/v1/generation-runs/{id}`
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
