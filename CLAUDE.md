# CLAUDE.md - Personal Meal-Prep AI

Read this file and `docs/PRD.md` at the start of every session. The PRD is the product vision. This file is the set of rules for how it gets built. If they ever conflict, this file wins and you flag the conflict to me.

Each session, read only the current phase's section of `docs/BUILD_PLAN.md` plus its shared sections (architecture, schema, conventions: §1–§7, §10, §12, as listed at the top of that file), not the whole file.

## What this app is

A personal meal-prep and grocery optimizer, not a recipe app. Given calorie goals, nutrition priority, budget, inventory, prices, equipment, time, and preferences, it produces a weekly plan, recipes with real cooking instructions, and a grocery list, then learns from my ratings.

## Stack

- Backend: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic migrations
- Database: PostgreSQL
- Optimization: PuLP (linear programming solver)
- LLM: Groq API (OpenAI-compatible), accessed ONLY through `backend/app/llm/client.py`
- Nutrition data: USDA FoodData Central, cached locally in Postgres
- Frontend: Next.js + TypeScript, built as an installable mobile-first PWA
- Testing: pytest (backend), Vitest (frontend)
- Local dev: Docker Compose (Postgres + backend + frontend)

Ask me before adding any dependency not listed here.

## Core architecture rules (non-negotiable)

1. **Code does math. The LLM never does.** Calories, macros, scaling, unit conversion, cost, inventory subtraction, weekly totals, and budget math are deterministic Python with unit tests. Never trust a number the LLM produces.
2. **The LLM does creative work only.** Recipe ideas, ingredient lists, cooking instructions, substitutions, flavor reasoning, natural-language inventory parsing, and explanations.
3. **Nutrition comes from the database, never the LLM.** The LLM names ingredients and quantities. Code maps each ingredient to a canonical entry and computes nutrition from stored per-100g values.
4. **The solver fits constraints.** The LLM generates candidate recipes. The PuLP solver chooses which recipes and how many portions to hit the calorie budget, macro priorities, and grocery budget. The validator then double-checks the final plan.
5. **Every LLM output is validated.** All LLM responses are parsed into Pydantic models. On parse or validation failure, retry with the error message included, up to a capped number of attempts, then fail gracefully with a clear error.
6. **The LLM provider is swappable.** Nothing outside `backend/app/llm/` imports the Groq SDK. The model name comes from an environment variable (`LLM_MODEL`), never hardcoded. Prefer a Groq model that supports strict structured outputs for generation calls. Do not combine structured outputs with streaming or tool use in the same call.
7. **Respect free-tier rate limits.** Persist every generated recipe and reuse it. Generate candidates in batches, not one call per meal. Cache substitution suggestions per ingredient. "Cook Again" reuses the saved user version and only calls the LLM if constraints changed.

## Data model rules

- One canonical ingredient table. Aliases ("chicken thigh", "boneless thighs") map to one canonical row.
- Store all quantities internally as grams (mass), milliliters (volume), or count. Count-based items ("1 head cabbage") carry a typical gram weight. Volume to mass conversion uses a per-ingredient density.
- Store money as integer cents. Never floats for money.
- Store nutrition per 100 g on the canonical ingredient.
- Recipes are versioned. A user edit creates a new version linked to the original; the user's latest version is the default next time.
- Every rating, substitution, actual cook time, actual cost, and leftover/waste event is logged as structured data for the future ranker.

## Food safety rules

Safe internal temperatures and storage/reheating guidance come from a hardcoded lookup table in code, injected into instructions. The LLM never sets these values. Baseline (USDA):

- Poultry (whole, parts, ground): 165 F
- Ground beef, pork, lamb, veal: 160 F
- Whole cuts of beef, pork, lamb, veal: 145 F plus 3-minute rest
- Fish and shellfish: 145 F
- Egg dishes: 160 F
- Reheated leftovers: 165 F

## Dietary rules (enforced in code: solver, LLM prompts, exclusion check)

- **Beef is excluded**, including every beef-derived ingredient (beef broth/stock, tallow, bovine gelatin, beef bouillon, etc.).
- **Possibly-beef items are excluded by default**: gelatin with an unspecified source, and anything else whose beef content isn't ruled out. Pork-labeled gelatin is allowed. The user can allow an item explicitly; never guess.
- **Pork is allowed but rare.** Pork as a meal component (sausage, pepperoni, bacon, ham, pork cuts) is limited by a general per-ingredient/per-tag frequency-cap setting (default 1 meal per week). Trace pork-derived ingredients (lard in tortillas, pork gelatin) have no limit.
- The solver never favors a capped (pork-component) meal for nutrition, price or inventory use; it's included only when it fits within the cap. Seed recipes use no pork component.

## Nutrition claims

- Never make medical or health claims. Describe nutrient content only ("high in iron"), not effects ("treats anemia").
- Iron mode distinguishes heme and non-heme iron.
- "Seasonal" and "cheapest" are different labels. Only say an item is cheap or a good deal when stored price data supports it.
- "Cheap" and "deal" are cost claims: only code produces them, from stored price data. The LLM never says them in prose.

## Build workflow (non-negotiable)

1. The full build plan lives in `docs/BUILD_PLAN.md`. Do not start building until I have approved it.
2. Build exactly ONE phase per session. Never start the next phase on your own.
3. A phase is done only when: all its acceptance criteria are met, its tests pass, and you have shown me the test output.
4. At the end of each phase, give me a short summary: what was built, key decisions made and why, anything deferred, and any deviation from the plan. Then stop and wait for my approval.
5. Mark progress in `docs/BUILD_PLAN.md` (phase status, date, notes).
6. If something in the plan turns out to be wrong mid-phase, stop and tell me before changing direction.
7. Commit at the end of each phase with a clear message.

## Machine boundaries

- Never install system-level software, change machine settings, or start/stop applications outside the repo without asking me first.

## Code conventions

- Type hints everywhere. Pydantic models at every API boundary.
- Small, focused modules. Business logic lives in services, not in route handlers.
- Secrets in `.env` only, never committed. Keep `.env.example` up to date.
- Tests live next to the layer they test, with fixtures for sample ingredients and recipes.
- Prefer clear, boring code over clever code.

## Phase outline (details live in BUILD_PLAN.md)

- Phase 0: Data foundation (schema, units, USDA nutrition cache, deterministic calculators, tests). No LLM.
- Phase 1: Planning brain (constraint object, LLM adapter, candidate generation, solver, validator, retry loop). Backend only.
- Phase 2: Mobile PWA (weekly plan, recipe view, inventory, grocery list).
- Phase 3: Feedback loop (favorites, ratings, recipe versioning, preference profile, Cook Again).
- Phase 4: Daily overrides (time/mood swaps for one day, dynamic calorie rebalancing, strict-daily vs weekly mode).
- Phase 5: Grocery intelligence (price history, deal detection, seasonal tags, grocery list modes, cart optimizer).
- Phase 6: Learned ranker (only once enough rating data exists; weighted scoring function until then).
