# Mealbro

A personal meal-prep and grocery optimizer. Build rules: [`CLAUDE.md`](CLAUDE.md). Product vision:
[`docs/PRD.md`](docs/PRD.md). Build plan and progress: [`docs/BUILD_PLAN.md`](docs/BUILD_PLAN.md).
Data provenance: [`docs/data-sources.md`](docs/data-sources.md).

Status: Phase 0 (data foundation): schema, USDA nutrition cache, seed data and calculators. No LLM, no frontend.

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
uv run alembic upgrade head
uv run python -m app.cli usda-import     # reads USDA_RAW_DIR (default ../data/raw/usda)
uv run python -m app.cli seed
uv run uvicorn app.main:app --reload
```

## API (Phase 0)

- `GET /health`
- `GET /api/v1/ingredients?q=` — alias and fuzzy search, with diet status (allowed / excluded / held)
- `GET /api/v1/ingredients/{id}` — nutrition per 100 g, named units, aliases, current price per store
- `POST /api/v1/calculations/recipe` — nutrition and per-store cost for a list of lines; optional
  `scale_to_portions` rounds every line to a practical amount first
- `GET /api/v1/recipes/seed` — the draft seed recipes with per-serving nutrition and cost, or why they're incomplete

Errors are `application/problem+json`.
