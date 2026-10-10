# Mealbro Build Plan

**Status:** v3, **approved** 2026-10-08 with the changes recorded in §12.1. Phase 0 approved. Phase 1 approved 2026-10-09 (with C1–C8 and D1–D22); a post-approval round (C9–C14, D23–D28) is done. A3 is answered in `docs/hosting.md`; the hosting decision changed at the Phase 2 kickoff to Vercel Hobby + Neon Free, $0/month (K1, §12.1). Phase 2 (PWA, deploy prep only) was approved 2026-10-10. **Phase 2b (cook-first redesign) was added and its spec approved 2026-10-10** (with changes E10–E13, §12.1): the spec is `docs/FLOW_SPEC.md` and the build steps are in §9. Building starts with step 2b.1.
**Source documents:** `CLAUDE.md` (build rules, wins on conflict), `docs/PRD.md` (product vision; "Primary user flow" at the top), `docs/FLOW_SPEC.md` (screens and backend work for Phase 2b).

This plan covers Phases 0–6, plus Phase 2b. One phase per session; Phase 2b is split into build steps, one per session (§9). A phase or step is done only when its acceptance criteria are met, its tests pass, and the test output has been shown.

**How to read this plan in a session** (per CLAUDE.md): read only the current phase's section in §9 plus the shared sections: §1 progress, §2 design decisions, §3 repo structure, §4 schema, §5 LLM/solver/validator flow, §6 Pydantic models, §7 cross-cutting rules and conventions, §10 dependencies, §12 decisions and open items. Read §13 (seed recipes) only in phases that touch seed data. Phase 2b sessions also read the `docs/FLOW_SPEC.md` sections their step names.

---

## 1. Progress tracker

| Phase | Name | Status | Started | Completed | Notes |
|---|---|---|---|---|---|
| — | Repo setup (git init, .gitignore, initial commit) | Done | 2026-10-08 | 2026-10-08 | Commit `3c7a499`. Done before Phase 0 per instruction. |
| — | Build plan | Approved (v3) | 2026-10-08 | 2026-10-08 | v1 reviewed → v2 (seed library, per-phase migrations, narrow prose filter, rounded-plan validator, strict/best-effort). v3 = approval changes: table audit (§4.2a), exposure logging → Phase 2, beef-only exclusion + pork frequency cap, R1–R7 answers, A2 label values. |
| 0 | Data foundation | Approved | 2026-10-08 | 2026-10-08 | 321 tests pass (local + Docker), domain coverage 99.6% (domain tests alone), ruff/mypy clean. 185 ingredients, 649 aliases, 9 draft seeds. Open: FoodSafety.gov chart (A1), powder carbs/fat (A2), R8. Deviations in the Phase 0 outcome note (§9). |
| — | Pre-Phase 1 tasks | Done | 2026-10-08 | 2026-10-08 | Package-label data (tortillas, protein powder), USDA mapping review sheet (`docs/review/usda_mappings.md`), raw/dry/as-sold rule + check (§7.8), CLAUDE.md machine-boundaries rule. Round 2: FoodSafety.gov chart transcribed (53 rows, §7.2), top-25 mappings approved, tortilla renamed, Docker rule clarified, fresh-clone check made a per-phase step. |
| 1 | Planning brain | Approved 2026-10-09; post-approval round done | 2026-10-08 | 2026-10-09 | First pass: 645 tests, fresh-clone check passed; D1–D13 and C1–C3 approved 2026-10-09. Fix-up round (C4–C8: budget per request with inventory/shop modes, cash vs food eaten, freeze-on-shopping-day and waste, 100 g protein floor, elapsed time): 705 tests pass (the opt-in live test skips), domain coverage 99%, ruff/mypy clean, fresh-clone check passed; deviations D14–D22 in the fix-up note. Approved 2026-10-09. Post-approval round (C9–C14: powder prices, stock-up items, shelf-life fix, regular chicken packs, two-week steady-state check, A3 hosting): 721 tests pass (the opt-in live test skips), domain coverage 99%; deviations D23–D28. |
| 2 | Mobile PWA + cloud deploy (deploy prep only, K7) | Approved 2026-10-10 | 2026-10-09 | 2026-10-09 | Pre-work K2–K6 done; PWA, auth, shopping, Mark cooked, quick add, exposure log. 800 backend tests pass (2 opt-in skipped), 78 frontend tests; not deployed (your step, `docs/deploy.md`). Deviations D29–D43 in the Phase 2 outcome note (§9). |
| 2b | Cook-first flow redesign | Spec approved 2026-10-10; building not started | 2026-10-10 | | `docs/FLOW_SPEC.md`; PRD "Primary user flow"; 8 build steps (2b.1–2b.8, §9); changes F1–F18 approved (FLOW_SPEC §16); decisions E1–E14 (§12.1). No code yet. |
| 3 | Feedback loop | Not started | | | Favorites moved to 2b. |
| 4 | Daily overrides | Not started | | | |
| 5 | Grocery intelligence | Not started | | | |
| 6 | Learned ranker | Not started | | | |

---

## 2. Key design decisions (and why)

1. **Code does all math; the LLM only names things and writes text.** LLM output schemas have no fields for calories, macros, cost, safe internal temperatures or storage durations. A narrow prose filter (§7.3) blocks exactly those five topics plus health claims in LLM text. Cooking instructions (appliance temperatures, cook/flip/rest times, water ratios) always pass.
2. **The solver builds the plan; the LLM supplies candidates.** The PRD (§32–33) describes the LLM generating the plan. CLAUDE.md rule 4 overrides that (§11).
3. **Meal-prep is modeled as cook batches.** A batch is one recipe cooked on one of your cook days (Mon, Wed, Thu, Sat, Sun) for N portions. Each portion fills a meal within the 3-day fridge window, or goes to the freezer. Tue and Fri meals come from leftovers. The cook schedule is an editable setting.
4. **Exact decimals for quantities, integer cents for money.** Values are `NUMERIC` in the DB and `Decimal` in domain code, and become `float` only inside PuLP.
5. **Practical quantities are the single source of truth after scaling, and the validator checks them.** Scaled recipes are rounded to measurable amounts (whole eggs, ⅛ tsp, 5 g). Nutrition, cost, packages and every validation run on that **rounded plan**, never on the solver's raw output.
6. **Nutrition is stored per 100 g in a long table keyed to the canonical ingredient** (`ingredient_nutrient`). New nutrients or modes add rows, not migrations.
7. **USDA data comes from bulk CSV downloads** (Foundation Foods Apr 2026, SR Legacy) imported into local `usda_*` tables. No API key, offline-testable.
8. **Enums are stored as `text` and validated by Python `StrEnum`.** New values never need a migration.
9. **The full schema is designed now and migrated phase by phase.** Migration `0001` (Phase 0) creates only the 31 tables Phases 0–1 use; the table audit (§4.2a) names the Phase 0 or Phase 1 test that touches each one. Each later phase adds its own additive migration (new tables, or nullable columns on existing ones). Nothing is ever renamed or restructured (§4).
10. **Recipe versions are immutable; families group variations.** An edit always creates a new version. `recipe.default_version_id` points at your latest version. Seed recipes are versions marked `is_draft`.
11. **Diet rules are enforced by tag, in code (§7.4).**
    - **Beef is excluded**, including everything derived from it (beef broth/stock, tallow, bovine gelatin, beef bouillon, …), in the solver, the prompts and the recipe validator.
    - **Possibly-beef items are excluded by default** ("held"): gelatin of unspecified source, and anything else whose beef content can't be ruled out. An `allow` decision per item releases them; the code never guesses.
    - **Pork is allowed but rare.** Pork as a *meal component* (sausage, pepperoni, bacon, ham, pork cuts) is limited by a **general frequency cap** setting (default 1 meal/week) and is never favored by nutrition, price or inventory-use scoring. *Trace* pork-derived ingredients (lard in tortillas, pork gelatin) are unlimited.
12. **Prices are per store.** Every price observation has a store. Deal detection compares within one store, and grocery lists can be grouped by store (Stop & Shop primary, Price Rite secondary).
13. **Cold start needs zero LLM calls** for slots covered by the seed recipe library (§13).
14. **Generation finishes inside its request, and the structured-output mode is configurable.** `POST /plans` runs the plan in the request (serverless hosting stops a function at 300 s, so nothing may continue after the response; K2) and streams NDJSON progress lines, then the finished plan. Run records are kept. (Phase 1 returned `202` + a run id and solved in a background task.) `LLM_STRUCTURED_MODE` is `strict` (constrained decoding) or `best_effort` (Pydantic validation + retry). Never combined with streaming or tool use.
15. **The frontend does no nutrition, unit or cost math.** The API returns computed numbers and display strings.
16. **Two engines behind the Cook tab (Phase 2b).** "A meal now" ranks candidates with a deterministic scoring function, because one meal is coupled to nothing else. Meal prep, swaps and grocery advice use the weekly solver, where packages, fridge windows, cook time, calories and budget interact. Both use the same rounding, nutrition, cost, exclusion, cap and validator code (`docs/FLOW_SPEC.md` §14).

---

## 3. Repository structure

Final shape after Phase 6. The phase that creates each item is noted.

```
Mealbro/
├── CLAUDE.md
├── README.md                          # P0: quickstart (compose up, migrate, import, seed, test)
├── .gitignore                         # done (repo setup)
├── .gitattributes                     # P0: force LF for *.py, *.sh, Dockerfile, *.ts(x)
├── .env.example                       # P0, extended every phase
├── docker-compose.yml                 # P0: db, db-test, backend · P2: frontend
├── docs/
│   ├── PRD.md
│   ├── BUILD_PLAN.md
│   ├── data-sources.md                # P0: USDA releases, FoodSafety.gov chart, (P5) seasonality source
│   └── sources/                       # P0: saved copies of cited reference pages, if needed
├── data/raw/                          # gitignored: USDA zip downloads
├── vercel.json                        # P2: Vercel Services config (web + api); docs/deploy.md
├── backend/
│   ├── Dockerfile · pyproject.toml · alembic.ini · conftest.py
│   ├── migrations/versions/
│   │   ├── 0001_initial.py            # P0: the 31 tables Phases 0–1 use
│   │   ├── 0002_settings_v2_budget_per_request.py · 0003_stock_up_and_other_store.py  # P1 (data, column)
│   │   ├── 0004_pwa_and_exposure_log.py  # P2 (planned as 0002)
│   │   ├── 0005_cook_flow.py          # P2b: favorites, saved, feedback_event, cook_search, meal_plan.kind, settings v3
│   │   ├── 0006_feedback_loop.py      # P3 (planned as 0003)
│   │   ├── 0007_daily_overrides.py    # P4 (planned as 0004)
│   │   ├── 0008_grocery_intelligence.py  # P5 (planned as 0005)
│   │   └── 0009_ranker.py             # P6 (planned as 0006)
│   └── app/
│       ├── main.py · config.py · cli.py
│       ├── db/                        # P0: base (naming convention), session, types, models/
│       ├── domain/                    # PURE logic: no DB, HTTP or LLM imports (enforced by test)
│       │   ├── enums.py · units.py · quantities.py · scaling.py · nutrition.py
│       │   ├── cost.py · packages.py · inventory_math.py · calories.py
│       │   ├── food_safety.py         # P0: hardcoded table, FoodSafety.gov citation comment
│       │   ├── exclusions.py          # P0: diet-tag exclusion + held-item resolution
│       │   ├── frequency_caps.py      # P0: per-ingredient / per-tag meals-per-week caps (pork = 1)
│       │   ├── text_rules.py          # P1: the narrow prose filter (§7.3)
│       │   ├── dish_category.py       # P2b: deterministic dish-category classifier (FLOW_SPEC §4.4)
│       │   ├── preferences.py         # P3
│       │   ├── price_stats.py         # P5
│       │   └── tests/
│       ├── schemas/                   # Pydantic models at every boundary (API, LLM, JSONB);
│       │                              # P0: settings (validates the seeded user_settings JSONB), seed files, API
│       ├── usda/                      # P0: CSV importer + subset builder (+ tests/fixtures/)
│       ├── services/                  # orchestration + DB access (+ tests/)
│       ├── seed/                      # P0
│       │   ├── data/
│       │   │   ├── nutrients.json · ingredients.json   # each ingredient carries its aliases, named
│       │   │   │                                       # units, density and piece weight (USDA portion ids)
│       │   │   ├── stores.json · products_prices.json      # estimates flagged source=estimate
│       │   │   ├── label_inputs.json  # values you fill from labels (protein powder, tortillas)
│       │   │   ├── substitutions.json # accepted pairs, e.g. chapati → flour tortilla
│       │   │   ├── settings_default.json   # cook schedule, exclusions, stores, calorie defaults
│       │   │   └── recipes/           # draft seed recipes (§13), one JSON file per recipe
│       │   ├── loader.py
│       │   └── tests/
│       ├── llm/                       # P1: the ONLY package that knows about Groq
│       │   ├── client.py              # LLMClient protocol + GroqLLMClient (sole `import groq`)
│       │   ├── structured.py          # strict / best-effort request building, parse → validate → retry
│       │   ├── pacing.py · fake.py · prompts/ · tests/
│       ├── planning/                  # P1
│       │   ├── constraint_builder.py · resolver.py · recipe_validator.py · candidates.py
│       │   ├── rendering.py · post_solve.py · plan_validator.py · grocery_list.py · orchestrator.py
│       │   ├── solver/ (model.py · objective.py · absorption.py · diagnostics.py)
│       │   └── tests/
│       ├── auth/                      # P2: single-user passphrase session
│       ├── cook/                      # P2b: answers → requests, single-meal ranking, substitutes, search memory,
│       │                              #      grocery advice reasons (planning/pins.py: the swap's pinned re-solve)
│       ├── feedback/ · preferences/ · substitutions/   # P3
│       ├── overrides/                 # P4
│       ├── grocery/                   # P5
│       ├── ranking/                   # P6
│       ├── api/ (deps.py · errors.py · routes/ · tests/)
│       └── testing/ (factories.py · fixtures/{usda_subset/, label_values.json, llm_responses/ (P1)})
└── frontend/                          # P2
    ├── Dockerfile · package.json · tsconfig.json · next.config.ts · vitest.config.ts
    ├── public/ (icons/, sw.js)
    └── src/
        ├── app/ (layout, manifest, plan/, plan/[date]/, plan/new/, recipes/[versionId]/,
        │         inventory/, grocery/, settings/, login/ · P2b welcome/, cook/ (home, ask, results, plan, saved),
        │         recipe/, grocery/advice/, pantry/, settings/edit/ (old plan/, day/, inventory/ redirect)
        │         · P3 history/, learned/ · P4 today/ (now the Cook home Today card) · P5 store/)
        ├── components/ · lib/{api, offline, format}/ · test/setup.ts
```

**Tests** sit next to the layer they test. Shared fixtures live in `app/testing/`. Pytest markers: `db`, `slow`, and `live_llm` (opt-in real Groq call).

---

## 4. Database schema (full design, migrated per phase)

### 4.1 Conventions

- **Migration policy.** Each table is created, with all its designed columns, in the migration of the first phase that uses it. A column that references a table created later is added in that later migration as a nullable column. Later migrations only add tables, nullable columns, indexes or CHECKs; they never rename, retype or drop.
- **Primary keys:** `bigint GENERATED ALWAYS AS IDENTITY`. USDA tables use the FDC id.
- **Timestamps:** `timestamptz`. Calendar days use `date`, interpreted in the user's timezone.
- **Quantities:** `numeric(12,3)` plus a `unit` column, CHECK `IN ('g','ml','count')`.
- **Nutrients:** `numeric(12,4)`. **Densities/fractions:** `numeric(8,4)` / `numeric(4,3)`.
- **Money:** `integer` cents, CHECK ≥ 0.
- **Enums:** `text` validated by `StrEnum`; no DB CHECK, except the fixed three-value `unit`.
- **JSONB:** only for snapshots and typed payloads. Each has a Pydantic model and a `schema_version`.
- **Naming convention:** `pk_`, `fk_`, `uq_`, `ix_`, `ck_`. **Deletes:** RESTRICT on history, CASCADE on version/plan children. Things are archived, not hard-deleted.
- **Extension:** `pg_trgm` (fuzzy ingredient search).

### 4.2 Migration map

| Migration | Phase | Tables created | Columns/constraints added to existing tables |
|---|---|---|---|
| `0001_initial` | 0 | **31:** app_user, user_settings, ingredient_preference, nutrient, usda_food, usda_nutrient, usda_food_nutrient, usda_food_portion, ingredient, ingredient_alias, ingredient_nutrient, ingredient_unit, ingredient_substitution, store, product, price_observation, inventory_item, inventory_event, recipe_family, recipe, recipe_version, recipe_ingredient, recipe_step, generation_run, llm_call, meal_plan, plan_cook_batch, plan_batch_ingredient, plan_meal, grocery_list, grocery_list_item | — |
| `0002_settings_v2_budget_per_request` | 1 (fix-up) | — | data only: settings v2 (D20) |
| `0003_stock_up_and_other_store` | 1 (post-approval) | — | `ingredient.stock_up`, `store.kind` (C10, D23) |
| `0004_pwa_and_exposure_log` (planned as 0002) | 2 | plan_candidate (exposure log; starts with real use, can't be backfilled), login_attempt (rate limiting across serverless instances) | `price_observation.client_ref` (offline idempotency) |
| `0005_cook_flow` | 2b | recipe_favorite and feedback_event (both pulled forward from P3, unchanged), recipe_saved, cook_search | `meal_plan.kind`; data: settings v3 |
| `0006_feedback_loop` (planned as 0003) | 3 | prepared_portion, preference_profile | `plan_meal.prepared_portion_id`, `inventory_event.prepared_portion_id` + CHECK |
| `0007_daily_overrides` (planned as 0004) | 4 | day_override, consumption_entry | — |
| `0008_grocery_intelligence` (planned as 0005) | 5 | region, ingredient_seasonality, cart_session | `price_observation.cart_session_id` |
| `0009_ranker` (planned as 0006) | 6 | ranker_model | — |

### 4.2a Table audit for `0001_initial` (2026-10-08)

Rule: a table stays in `0001` only if a Phase 0 or Phase 1 test touches it; otherwise it moves to the migration of the phase that first uses it. The migration-shape test (AC 0.1) touches every table and is deliberately **not** counted.

| # | Table | Purpose (one line) | Test that touches it (phase) |
|---|---|---|---|
| 1 | app_user | The single user that owns settings, recipes, plans and inventory | `seed/tests/test_seed.py::test_creates_single_user` (P0) |
| 2 | user_settings | JSONB `UserSettings`: cook schedule, calorie mode, frequency caps, stores, split threshold | `seed/tests/test_seed.py::test_default_settings` (P0) |
| 3 | ingredient_preference | Your explicit allow / exclude / dislike decisions | `services/tests/test_ingredient_search.py::test_allow_releases_held_item` (P0) |
| 4 | nutrient | The tracked nutrients, their FDC numbers and daily values | `usda/tests/test_importer.py`, `seed/tests/test_seed.py` (P0) |
| 5 | usda_food | Cached USDA foods (Foundation + SR Legacy) | `usda/tests/test_importer.py::test_idempotent` (P0) |
| 6 | usda_nutrient | USDA nutrient definitions | `usda/tests/test_importer.py::test_idempotent` (P0) |
| 7 | usda_food_nutrient | USDA per-100 g values | `usda/tests/test_importer.py::test_energy_falls_back_to_958` (P0) |
| 8 | usda_food_portion | USDA household portions (gram weights) | `usda/tests/test_importer.py::test_portions`, `seed/tests/test_seed.py::test_usda_units_link_to_portions` (P0) |
| 9 | ingredient | The canonical ingredient table | `seed/tests/test_seed.py` (P0) |
| 10 | ingredient_alias | Name variants mapped to one ingredient | `services/tests/test_ingredient_search.py::test_alias_hit` (P0) |
| 11 | ingredient_nutrient | Nutrition source of truth per 100 g | `seed/tests/test_seed.py::test_nutrition_complete`, `api/tests/test_calculations.py` (P0) |
| 12 | ingredient_unit | Named portions (clove, scoop, tortilla, cup_chopped) | `seed/tests/test_seed.py::test_label_units` (P0) |
| 13 | ingredient_substitution | Accepted pairs (chapati → tortilla); P3 suggestion cache | `seed/tests/test_seed.py::test_chapati_pair`, `db/tests/test_constraints.py` (P0) |
| 14 | store | Stop & Shop, Price Rite | `services/tests/test_pricing.py` (P0) |
| 15 | product | Purchasable forms with package sizes | `services/tests/test_pricing.py` (P0) |
| 16 | price_observation | Append-only per-store price history | `services/tests/test_pricing.py`, `db/tests/test_constraints.py` (P0) |
| 17 | inventory_item | Stock lots, incl. open packages; a planning input | `services/tests/test_inventory_service.py` (P1, **added by this audit**) |
| 18 | inventory_event | Append-only stock ledger | `services/tests/test_inventory_service.py` (P1, **added by this audit**) |
| 19 | recipe_family | Groups variations ("Chicken over rice") | `seed/tests/test_seed.py::test_seed_recipes` (P0) |
| 20 | recipe | One lineage of versions; default version pointer | `seed/tests/test_seed.py::test_seed_recipes` (P0) |
| 21 | recipe_version | Immutable recipe versions (seed drafts) | `seed/tests/test_seed.py`, `db/tests/test_constraints.py` (P0) |
| 22 | recipe_ingredient | Version ingredient lines in base units | `api/tests/test_seed_recipes.py` (P0) |
| 23 | recipe_step | Version instruction steps | `seed/tests/test_seed.py::test_seed_steps` (P0) |
| 24 | generation_run | One planning/generation run and its status | `planning/tests/test_orchestrator.py` (P1) |
| 25 | llm_call | Every LLM attempt, its mode and outcome | `llm/tests/test_structured.py` (P1) |
| 26 | meal_plan | A week's plan, totals and validation report | `db/tests/test_constraints.py` (P0), `planning/tests/test_orchestrator.py` (P1) |
| 27 | plan_cook_batch | One recipe cooked on one cook day for N portions | `planning/tests/test_orchestrator.py` (P1) |
| 28 | plan_batch_ingredient | Practical batch quantities after rounding + absorption | `planning/tests/test_orchestrator.py` (P1) |
| 29 | plan_meal | Each slot on each day, filled from a batch | `planning/tests/test_orchestrator.py` (P1) |
| 30 | grocery_list | The plan's shopping list | `api/tests/test_plans_api.py` (P1) |
| 31 | grocery_list_item | Per-item need, packages, store and cost | `api/tests/test_plans_api.py::test_group_by_store` (P1) |

**Result: 31 before, 31 after, 0 moved.** Every table is used by a Phase 0 or Phase 1 deliverable. Three had no *named* test in v2, and the audit added them: `ingredient_preference` (P0 search test) and `inventory_item` / `inventory_event` (new P1 `test_inventory_service.py`). Separately, `plan_candidate` moved from `0003` to `0002` (exposure logging starts in Phase 2).

### 4.3 Entity map (later-phase tables marked)

```
app_user ─┬─ user_settings (1:1)            ├─ ingredient_preference
          ├─ inventory_item ── inventory_event ── [P3] prepared_portion
          ├─ recipe_family ── recipe ── recipe_version ─┬─ recipe_ingredient
          │                     ▲ default_version_id    └─ recipe_step
          ├─ meal_plan ─┬─ plan_cook_batch ── plan_batch_ingredient
          │             ├─ plan_meal ── [P3] prepared_portion · [P4] day_override
          │             └─ grocery_list ── grocery_list_item ── store
          ├─ generation_run ─┬─ llm_call
          │                  ├─ [P2] plan_candidate
          │                  └─ [P2b] cook_search (also → meal_plan)
          ├─ [P2b] feedback_event · recipe_favorite · recipe_saved
          ├─ [P3] preference_profile
          ├─ [P4] consumption_entry
          └─ [P5] cart_session ── store

nutrient ── ingredient_nutrient ── ingredient ─┬─ ingredient_alias
                                               ├─ ingredient_unit ── usda_food_portion
                                               ├─ ingredient_substitution (from → to)
                                               ├─ product ── price_observation ── store
                                               └─ [P5] ingredient_seasonality ── region
usda_food ─┬─ usda_food_nutrient ── usda_nutrient
           └─ usda_food_portion
[P6] ranker_model
```

### 4.4 Migration `0001_initial` (Phase 0): 31 tables

`FK→t` = foreign key to `t.id`. `NN` = NOT NULL.

#### A. User, settings and explicit preferences

```
app_user
  id               bigint PK
  display_name     text NN
  timezone         text NN DEFAULT 'America/New_York'
  created_at       timestamptz NN

user_settings                                   -- 1:1 with app_user
  user_id          bigint PK FK→app_user
  settings         jsonb NN     -- UserSettings model: daily kcal target, calorie mode + band, slot allocations,
                                -- priorities, grocery mode, budget, equipment, cook schedule (per weekday:
                                -- is_cook_day, minutes, mood), leftover_fridge_days, excluded_diet_tags,
                                -- frequency_caps (e.g. tag pork ≤ 1 meal/week, never favored),
                                -- store preference order, store_split_min_savings_cents (500),
                                -- portion size, region, units preference
  schema_version   smallint NN
  updated_at       timestamptz NN

ingredient_preference                           -- explicit decisions only; learned scores arrive in P3
  user_id          bigint FK→app_user
  ingredient_id    bigint FK→ingredient
  preference       text NN      -- exclude | dislike | like | allow (allow = held item reviewed and OK)
  reason           text NULL
  created_at       timestamptz NN
  PK (user_id, ingredient_id)
```

#### B. Nutrient reference and USDA cache

```
nutrient
  id               smallint PK
  code             text NN UNIQUE   -- energy_kcal, protein_g, carbohydrate_g, fat_g, fiber_g, sugars_g,
                                    -- saturated_fat_g, sodium_mg, iron_mg, calcium_mg, potassium_mg,
                                    -- vitamin_c_mg, vitamin_d_ug, vitamin_b12_ug, folate_dfe_ug, magnesium_mg, zinc_mg
  display_name     text NN
  unit             text NN          -- kcal | g | mg | ug
  fdc_number       text NN          -- legacy FDC number: '208' energy, '203' protein, '303' iron, …
  is_core          bool NN          -- energy/protein/carbs/fat required for an ingredient to be plannable
  daily_value      numeric(10,3) NULL   -- FDA DV for "good source / high in" labels
  sort_order       smallint NN

usda_food
  fdc_id           integer PK
  data_type        text NN          -- foundation_food | sr_legacy_food
  description      text NN
  food_category    text NULL
  publication_date date NULL
  source_release   text NN
  imported_at      timestamptz NN
  IX trigram(description)

usda_nutrient
  id               integer PK       -- FDC nutrient id (e.g. 1008)
  name             text NN
  unit_name        text NN
  nutrient_nbr     text NULL        -- '208'; energy alternates '957' (Atwater general), '958' (specific)

usda_food_nutrient
  fdc_id           integer FK→usda_food.fdc_id
  usda_nutrient_id integer FK→usda_nutrient.id
  amount           numeric(12,4) NN   -- per 100 g edible portion
  PK (fdc_id, usda_nutrient_id)

usda_food_portion
  id               bigint PK
  fdc_id           integer FK→usda_food.fdc_id
  amount           numeric(10,3) NULL
  measure_unit     text NULL
  modifier         text NULL
  gram_weight      numeric(10,3) NN
```

#### C. Canonical ingredients

```
ingredient
  id                      bigint PK
  name                    text NN UNIQUE
  slug                    text NN UNIQUE
  category                text NN      -- protein | vegetable | fruit | grain | legume | dairy | fat_oil |
                                       -- spice | condiment | sweetener | supplement | beverage | other
  default_unit_kind       text NN      -- mass | volume | count
  density_g_per_ml        numeric(8,4) NULL
  count_unit_weight_g     numeric(10,3) NULL
  count_rounding_step     numeric(4,2) NN DEFAULT 1
  edible_fraction         numeric(4,3) NN DEFAULT 1.000
  cooked_yield_factor     numeric(5,3) NULL
  heme_iron_fraction      numeric(4,3) NN DEFAULT 0    -- 0.40 meat, poultry, fish, shellfish; 0 plants, eggs, dairy (§7.4)
  diet_tags               text[] NN DEFAULT '{}'       -- what it is/contains: poultry, fish, shellfish, egg, dairy,
                                                       -- lamb, beef, possible_beef, pork (meal component), pork_trace
  diet_review_note        text NULL    -- why it is held, e.g. "gelatin source not stated; may be bovine"
  safety_category         text NULL    -- poultry | ground_meat | whole_cut_meat | fish_shellfish | egg
  is_perishable           bool NN
  shelf_life_days_pantry  smallint NULL    -- raw-ingredient expiry estimates (from the FoodSafety.gov chart)
  shelf_life_days_fridge  smallint NULL
  shelf_life_days_freezer smallint NULL
  typical_location        text NULL
  assume_in_stock         bool NN DEFAULT false   -- salt, pepper, water, common spices
  nutrition_source        text NN      -- usda | package_label | manual
  fdc_id                  integer NULL FK→usda_food.fdc_id
  nutrition_reviewed_at   timestamptz NULL
  notes                   text NULL
  archived_at             timestamptz NULL
  created_at, updated_at  timestamptz NN

ingredient_alias
  id                bigint PK
  ingredient_id     bigint NN FK→ingredient
  alias             text NN
  alias_normalized  text NN UNIQUE
  source            text NN      -- seed | user | llm_confirmed
  created_at        timestamptz NN
  IX trigram(alias_normalized)

ingredient_nutrient                             -- nutrition source of truth, per 100 g edible portion
  ingredient_id     bigint FK→ingredient
  nutrient_id       smallint FK→nutrient
  amount_per_100g   numeric(12,4) NN
  source            text NN      -- usda | package_label | manual | derived (per nutrient row)
  fdc_id            integer NULL
  PK (ingredient_id, nutrient_id)               -- missing row = unknown, never zero

ingredient_unit                                 -- named portions; override density
  id                bigint PK
  ingredient_id     bigint NN FK→ingredient
  unit_name         text NN      -- clove | head | slice | can | scoop | tortilla | cup_chopped | large | …
  grams             numeric(10,3) NN CHECK > 0
  source            text NN      -- usda_portion | package_label | manual
  usda_portion_id   bigint NULL FK→usda_food_portion
  UQ (ingredient_id, unit_name)

ingredient_substitution                         -- accepted pairs now; LLM suggestion cache from P3
  id                  bigint PK
  from_ingredient_id  bigint NN FK→ingredient
  to_ingredient_id    bigint NN FK→ingredient
  context_key         text NN DEFAULT ''        -- '' = any context; P3 adds role + method + equipment keys
  status              text NN      -- accepted | suggested | rejected
  source              text NN      -- seed | user | llm
  quantity_rule       jsonb NN     -- {"mode":"count_for_count"} | {"mode":"match_nutrient","nutrient":"protein_g"} |
                                   -- {"mode":"same_mass"} | {"mode":"ratio","ratio":"0.9"}
  culinary_note       text NULL
  preparation_changes text NULL
  llm_call_id         bigint NULL FK→llm_call
  created_at          timestamptz NN
  UQ (from_ingredient_id, to_ingredient_id, context_key) · CK (from_ingredient_id <> to_ingredient_id)
```

#### D. Stores, products and price history

```
store
  id            bigint PK
  name          text NN UNIQUE     -- "Stop & Shop", "Price Rite"
  priority      smallint NN        -- 1 = primary, 2 = secondary
  region_code   text NULL
  is_active     bool NN DEFAULT true
  notes         text NULL
  created_at    timestamptz NN

product                                         -- a purchasable form of an ingredient
  id                  bigint PK
  ingredient_id       bigint NN FK→ingredient
  store_id            bigint NULL FK→store      -- set only for store-brand items (e.g. Price Rite tortillas)
  name                text NN
  brand               text NULL
  package_amount      numeric(12,3) NULL        -- NULL = sold loose
  package_unit        text NN CHECK IN (g, ml, count)
  is_variable_weight  bool NN DEFAULT false
  price_basis         text NN      -- per_package | per_weight | per_count
  display_unit        text NN      -- lb | oz | head | bag | each
  is_default          bool NN DEFAULT false
  archived_at         timestamptz NULL
  created_at, updated_at timestamptz NN
  IX (ingredient_id)

price_observation                               -- append-only price history, always tied to a store
  id               bigint PK
  product_id       bigint NN FK→product
  store_id         bigint NN FK→store
  observed_on      date NN
  price_cents      integer NN CHECK ≥ 0
  priced_quantity  numeric(12,3) NN CHECK > 0   -- base units covered: $1.99/lb → 453.592 g; 30 tortillas → 30
  priced_unit      text NN CHECK IN (g, ml, count)
  is_sale          bool NN DEFAULT false
  source           text NN      -- manual | in_store | receipt | estimate | api
  note             text NULL
  created_at       timestamptz NN
  IX (store_id, product_id, observed_on DESC)
  -- unit price = price_cents / priced_quantity, derived in code
```

#### E. Inventory

```
inventory_item                                  -- one row per lot
  id                  bigint PK
  user_id             bigint NN FK→app_user
  ingredient_id       bigint NN FK→ingredient
  product_id          bigint NULL FK→product
  quantity            numeric(12,3) NN CHECK ≥ 0
  unit                text NN CHECK IN (g, ml, count)
  location            text NN      -- pantry | fridge | freezer
  acquired_on         date NULL
  opened_on           date NULL    -- set ⇒ open package (gets a "use it" boost in the next plan)
  expires_on          date NULL
  expiry_is_estimate  bool NN DEFAULT true
  status              text NN      -- active | depleted | discarded
  notes               text NULL
  created_at, updated_at timestamptz NN
  IX (user_id, status, expires_on)

inventory_event                                 -- append-only stock ledger
  id                   bigint PK
  user_id              bigint NN FK→app_user
  occurred_at          timestamptz NN
  inventory_item_id    bigint NULL FK→inventory_item   -- required by services until P3 adds prepared portions
  ingredient_id        bigint NULL FK→ingredient
  delta_quantity       numeric(12,3) NN
  unit                 text NN CHECK IN (g, ml, count)
  reason               text NN      -- purchase | cook_consume | waste | expired | manual_adjust | parse_add |
                                    -- freeze | thaw | eat (P3)
  cook_batch_id        bigint NULL FK→plan_cook_batch
  grocery_list_item_id bigint NULL FK→grocery_list_item
  note                 text NULL
  created_at           timestamptz NN
  IX (user_id, reason, occurred_at)
```

#### F. Recipes, families and versions

```
recipe_family                                   -- groups variations: "Chicken over rice"
  id          bigint PK
  user_id     bigint NN FK→app_user
  name        text NN
  notes       text NULL
  created_at  timestamptz NN
  UQ (user_id, name)

recipe                                          -- one lineage of versions
  id                  bigint PK
  user_id             bigint NN FK→app_user
  family_id           bigint NULL FK→recipe_family
  title               text NN
  origin              text NN      -- seed | llm | user
  default_version_id  bigint NULL FK→recipe_version (use_alter; deferrable)
  archived_at         timestamptz NULL
  created_at          timestamptz NN

recipe_version                                  -- IMMUTABLE once written
  id                  bigint PK
  recipe_id           bigint NN FK→recipe
  version_number      integer NN
  parent_version_id   bigint NULL FK→recipe_version
  created_by          text NN      -- system (seed) | llm | user
  is_draft            bool NN DEFAULT false     -- seed recipes: usable, shown as "draft, adjust me"
  change_summary      text NULL
  change_set          jsonb NULL
  title               text NN
  description         text NN
  meal_slots          text[] NN
  mood                text NN
  cuisine             text NULL
  flavor_tags         text[] NN DEFAULT '{}'
  base_servings       smallint NN CHECK > 0
  active_minutes      smallint NN CHECK > 0
  total_minutes       smallint NN CHECK ≥ active_minutes
  equipment           text[] NN     -- may be empty for no-cook recipes
  freezer_friendly    bool NN
  content_hash        text NN
  prompt_version      text NULL
  source_llm_call_id  bigint NULL FK→llm_call
  generation_run_id   bigint NULL FK→generation_run
  status              text NN DEFAULT 'active'
  created_at          timestamptz NN
  UQ (recipe_id, version_number) · IX (content_hash)

recipe_ingredient
  id                 bigint PK
  recipe_version_id  bigint NN FK→recipe_version ON DELETE CASCADE
  position           smallint NN
  ingredient_id      bigint NN FK→ingredient
  quantity           numeric(12,3) NN CHECK > 0   -- base unit, for base_servings, raw/dry as purchased
  unit               text NN CHECK IN (g, ml, count)
  authored_quantity  numeric(12,3) NN
  authored_unit      text NN
  preparation        text NULL
  role               text NN      -- protein | carb | vegetable | fruit | dairy | fat | sauce | seasoning | garnish | other
  component          text NULL
  is_optional        bool NN DEFAULT false
  UQ (recipe_version_id, position)

recipe_step
  id                            bigint PK
  recipe_version_id             bigint NN FK→recipe_version ON DELETE CASCADE
  position                      smallint NN
  section                       text NN
  text                          text NN
  duration_minutes              smallint NULL
  appliance_temp_f              smallint NULL
  doneness_check_ingredient_id  bigint NULL FK→ingredient
  UQ (recipe_version_id, position)
```

#### G. LLM provenance

```
generation_run
  id               bigint PK
  user_id          bigint NN FK→app_user
  purpose          text NN      -- weekly_plan | daily_override | cook_again | substitution | inventory_parse | …
  status           text NN      -- pending | running | succeeded | failed | infeasible
  constraints      jsonb NULL
  progress         jsonb NULL
  error            jsonb NULL   -- structured error / infeasibility diagnostics
  llm_call_count   integer NN DEFAULT 0
  total_tokens     integer NN DEFAULT 0
  started_at, finished_at  timestamptz NULL
  created_at       timestamptz NN

llm_call
  id                 bigint PK
  generation_run_id  bigint NULL FK→generation_run
  parent_call_id     bigint NULL FK→llm_call
  purpose            text NN
  provider           text NN
  model              text NN      -- value of LLM_MODEL at call time
  structured_mode    text NN      -- strict | best_effort
  prompt_version     text NN
  attempt            smallint NN
  request_messages   jsonb NN
  response_schema    text NULL
  response_text      text NULL
  finish_reason      text NULL
  outcome            text NN      -- ok | parse_error | validation_error | domain_error | rate_limited | transport_error
  error_detail       jsonb NULL   -- includes unresolved ingredient names (feeds the "suggested ingredients" queue)
  prompt_tokens      integer NULL
  completion_tokens  integer NULL
  latency_ms         integer NULL
  created_at         timestamptz NN
  IX (created_at)
```

#### H. Plans, batches and grocery lists

```
meal_plan
  id                  bigint PK
  user_id             bigint NN FK→app_user
  week_start          date NN
  status              text NN      -- draft | active | superseded | completed
  constraints         jsonb NN     -- PlanConstraints snapshot
  constraints_hash    text NN
  generation_run_id   bigint NULL FK→generation_run
  supersedes_plan_id  bigint NULL FK→meal_plan
  solver_status       text NN
  solver_objective    numeric NULL
  totals              jsonb NN     -- PlanTotals, computed from the ROUNDED plan
  validation_report   jsonb NN
  created_at          timestamptz NN
  accepted_at         timestamptz NULL
  UQ partial (user_id, week_start) WHERE status = 'active'

plan_cook_batch
  id                 bigint PK
  meal_plan_id       bigint NN FK→meal_plan ON DELETE CASCADE
  recipe_version_id  bigint NN FK→recipe_version
  cook_on            date NN           -- always one of your cook days
  portions           smallint NN CHECK > 0
  portions_to_freeze smallint NN DEFAULT 0
  portion_size       text NN
  portion_multiplier numeric(5,3) NN
  scale_factor       numeric(8,4) NN
  planned_minutes    smallint NN
  status             text NN DEFAULT 'planned'   -- planned | cooked | skipped | cancelled
  created_at         timestamptz NN

plan_batch_ingredient                           -- practical quantities after rounding + absorption
  id                    bigint PK
  cook_batch_id         bigint NN FK→plan_cook_batch ON DELETE CASCADE
  recipe_ingredient_id  bigint NULL FK→recipe_ingredient
  ingredient_id         bigint NN FK→ingredient
  quantity              numeric(12,3) NN
  unit                  text NN CHECK IN (g, ml, count)
  adjustment            text NULL       -- absorbed_full_package | substituted (e.g. chapati → tortilla)

plan_meal
  id                       bigint PK
  meal_plan_id             bigint NN FK→meal_plan ON DELETE CASCADE
  eat_on                   date NN
  slot                     text NN
  position                 smallint NN DEFAULT 0
  cook_batch_id            bigint NULL FK→plan_cook_batch
  from_freezer             bool NN DEFAULT false
  planned_kcal             integer NN
  status                   text NN DEFAULT 'planned'   -- planned | eaten | skipped | replaced
  replaced_by_plan_meal_id bigint NULL FK→plan_meal
  override_reason          text NULL
  created_at, updated_at   timestamptz NN
  UQ partial (meal_plan_id, eat_on, slot, position) WHERE status <> 'replaced'

grocery_list
  id            bigint PK
  user_id       bigint NN FK→app_user
  meal_plan_id  bigint NULL FK→meal_plan
  mode          text NN
  status        text NN      -- open | shopping | done
  created_at, updated_at timestamptz NN

grocery_list_item
  id                          bigint PK
  grocery_list_id             bigint NN FK→grocery_list ON DELETE CASCADE
  position                    smallint NN
  ingredient_id               bigint NN FK→ingredient
  product_id                  bigint NULL FK→product
  store_id                    bigint NULL FK→store     -- where to buy it; lists group by this
  needed_quantity             numeric(12,3) NN
  inventory_used_quantity     numeric(12,3) NN
  to_buy_quantity             numeric(12,3) NN
  expected_remainder_quantity numeric(12,3) NULL       -- e.g. 0.3 lb left over → becomes an open package
  unit                        text NN CHECK IN (g, ml, count)
  packages                    smallint NULL
  estimated_cost_cents        integer NULL             -- NULL = no price data
  price_observation_id        bigint NULL FK→price_observation
  is_manual                   bool NN DEFAULT false
  reason                      jsonb NN
  checked_at                  timestamptz NULL
  purchased_quantity          numeric(12,3) NULL
  actual_price_cents          integer NULL
```

### 4.5 Later migrations (designed now, applied in their phase)

```
-- 0004_pwa_and_exposure_log (Phase 2; planned as 0002) ------------------------------
login_attempt (id, client_key text NN (HMAC of the client address), succeeded bool NN, occurred_at)
  IX (occurred_at) · IX (client_key, occurred_at)          -- added in Phase 2 (D31)
ALTER price_observation ADD client_ref uuid NULL UNIQUE      -- offline price entries replay exactly once

plan_candidate                                  -- exposure log for the ranker; written for every plan from P2
  id, generation_run_id FK, meal_plan_id NULL FK, recipe_version_id FK, source text NN
  (seed | saved | favorite | user_version | llm_new), eligible_slots text[] NN, filtered_reason text NULL,
  heuristic_score numeric(8,4) NULL, score_components jsonb NULL, features jsonb NULL,
  selected bool NN, portions_selected smallint NN DEFAULT 0, created_at

-- 0005_cook_flow (Phase 2b) ---------------------------------------------------------
feedback_event                                  -- pulled forward from P3, unchanged; append-only (never UPDATE/DELETE)
  id, user_id FK, event_type text NN (rating | cook_completed | substitution | recipe_edited | leftover | waste |
  favorite_added | favorite_removed | saved_added | saved_removed (2b) | meal_skipped | meal_swapped |
  off_plan_food | inventory_correction),
  occurred_at timestamptz NN, recipe_id NULL FK, recipe_version_id NULL FK, plan_meal_id NULL FK,
  cook_batch_id NULL FK, ingredient_id NULL FK, payload jsonb NN, payload_version smallint NN, created_at
  IX (user_id, event_type, occurred_at) · IX (recipe_id)
  -- 2b writes favorite_added/removed, saved_added/removed, meal_swapped; the rest start in P3

recipe_favorite      (user_id FK, recipe_id FK, created_at, PK (user_id, recipe_id))   -- pulled forward from P3
recipe_saved         (user_id FK, recipe_id FK, created_at, PK (user_id, recipe_id))   -- "save for later", no ranking effect

cook_search                                     -- last answers per mode, result cache, meal-now exposures
  id, user_id FK NN, mode text NN (now | prep | grocery), answers jsonb NN (CookAnswers + schema_version),
  answers_hash text NN, cache_key text NN, generation_run_id NULL FK, meal_plan_id NULL FK,
  results jsonb NULL, status text NN (running | done | failed), created_at
  IX (user_id, mode, created_at DESC) · IX (user_id, cache_key)

ALTER meal_plan ADD kind text NULL              -- meal_prep | single | grocery_advice; NULL = Phase 1–2 week plans
-- data: UserSettings v3 (household_size 1, always_have [], default_budget_cents null, onboarding_completed false)

-- 0006_feedback_loop (Phase 3; planned as 0003) --------------------------------------
prepared_portion                                -- cooked leftovers / frozen meal-prep portions
  id, user_id FK→app_user, recipe_version_id FK→recipe_version, cook_batch_id NULL FK→plan_cook_batch,
  portions smallint NN CHECK ≥ 0, portion_size text NN, location text NN (fridge | freezer),
  cooked_on date NN, use_by date NN (from the food-safety table), status text NN (available | eaten | discarded),
  created_at, updated_at

preference_profile   (id, user_id FK, computed_at, through_event_id FK→feedback_event, profile jsonb NN, schema_version)

ALTER plan_meal       ADD prepared_portion_id bigint NULL FK→prepared_portion
ALTER inventory_event ADD prepared_portion_id bigint NULL FK→prepared_portion
ALTER inventory_event ADD CHECK (inventory_item_id IS NOT NULL OR prepared_portion_id IS NOT NULL)

-- 0007_daily_overrides (Phase 4; planned as 0004) ------------------------------------
day_override        (id, meal_plan_id FK, day date NN, cook_minutes smallint NULL, mood text NULL,
                     slots text[] NN, reason text NULL, generation_run_id NULL FK, created_at)
consumption_entry   (id, user_id FK, consumed_on date NN, slot text NULL, plan_meal_id NULL FK, description text NN,
                     kcal integer NN CHECK ≥ 0, protein_g numeric(8,2) NULL, source text NN (planned_meal | manual | parsed),
                     is_estimate bool NN, parsed_items jsonb NULL, created_at)

-- 0008_grocery_intelligence (Phase 5; planned as 0005) -------------------------------
region                 (code text PK, name text NN)
ingredient_seasonality (ingredient_id FK, region_code text FK→region.code, month smallint CHECK 1–12,
                        availability text NN (peak | available), source text NN, PK (ingredient_id, region_code, month))
cart_session           (id, user_id FK, store_id NN FK→store, started_at, ended_at NULL, status text NN)
ALTER price_observation ADD cart_session_id bigint NULL FK→cart_session

-- 0009_ranker (Phase 6; planned as 0006) ---------------------------------------------
ranker_model (id, version integer NN UNIQUE, algorithm text NN, trained_at timestamptz NN, train_window jsonb NN,
              n_examples integer NN, feature_spec jsonb NN, weights jsonb NN, metrics jsonb NN,
              is_active bool NN DEFAULT false, created_at)   UQ partial (is_active) WHERE is_active
```

### 4.6 Why later phases don't need a rewrite

- **Solver:** its inputs (recipe versions, nutrition, per-store prices, inventory including open packages) and outputs (plans, batches, practical batch quantities, meals, store-assigned grocery lists) all exist in `0001`.
- **Versioning:** the family / recipe / immutable version / `default_version_id` structure covers seeds, edits, branches, reverts and Cook Again.
- **Price history:** `price_observation` is append-only, per store, and normalized to base units. Within-store deal detection is pure computation over it.
- **Ranker logging:** `plan_candidate` arrives in `0004` (exposures logged from the first real use) and `feedback_event` in `0005` (Phase 2b, so favorite and swap history starts with the new flow), both as new tables that reference existing ones. `inventory_event`, `llm_call`, `plan_cook_batch.status` and `meal_plan.totals` already carry timestamped history from Phase 1.
- **Overrides:** `plan_meal.status` + `replaced_by_plan_meal_id` exist from `0001`; Phase 4 adds leaf tables only.
- **Substitution cache:** reuses `ingredient_substitution` (`source = llm`, `status = suggested`), so no new table is needed.

---

## 5. How the LLM adapter, solver and validator interact

```
UserSettings (cook schedule, exclusions, stores, targets) + week + inventory + per-store prices + preferences
        │
        ▼
[1] ConstraintBuilder (code) ──► PlanConstraints
     • resolves exclusions: beef diet tag + held possible-beef items + your exclude list + any frequency
       cap set to 0 → ingredient ids; frequency caps (pork components ≤ 1 meal/week) → cap constraints
     • Tue/Fri get is_cook_day = false (0 minutes); fridge window = leftover_fridge_days (3)
        │
        ▼
[2] CandidatePool
     a. Reuse seed drafts + saved versions that pass hard filters (favorites/user versions first) → 0 LLM calls
     b. Gap analysis per (slot, mood): only uncovered slots go to the LLM
     c. LLM batch generation via llm/client.py, LLM_STRUCTURED_MODE = strict | best_effort,
        2–3 recipes per call; prompt states the never-use list (beef and everything derived, held items);
        never-favored capped ingredients (pork components) are left out of the generation vocabulary,
        trace pork ingredients (lard-containing tortillas, pork gelatin) stay in it
     d. Per recipe: Pydantic parse → resolve names → accepted substitutions applied (chapati → tortilla) →
        RecipeValidator (exclusions, units, plausible quantities, equipment, time vs mood, prose filter §7.3)
        → failed recipes sent back with their errors (≤ LLM_MAX_ATTEMPTS) → still invalid = dropped + logged
     e. Persist recipe + version 1; nutrition and cost computed by code
        │
        ▼
[3] Solver (PuLP MILP): batches on cook days, portions, slot assignments, packages per (product, store)
     • frequency caps: meals containing a capped ingredient ≤ max per week; never-favored capped items
       get no nutrition, price or inventory-use bonus (§7.4)
     • infeasible → elastic re-solve → diagnostics → targeted generation (≤ 2 rounds) or graceful failure
        │
        ▼
[4] PostSolve (code + a small PuLP pass)
     a. practical rounding of every batch quantity
     b. package absorption pass: absorb a leftover remainder by scaling the WHOLE batch proportionally
        and re-rounding (R5), only if the ROUNDED plan still meets the calorie limits; otherwise keep it
        as an expected open package
     c. recompute packages, store assignment, costs and kcal from the final quantities
     ──► RoundedPlan (the only thing downstream code ever sees)
        │
        ▼
[5] PlanValidator(RoundedPlan): independent recomputation from the DB; never reads solver variables
     • hard error (e.g. rounding pushed Thursday over the ceiling, or a hard budget over) → re-solve with
       that bound tightened (≤ 2) → still failing = clear error
     • also re-checks exclusions and frequency caps on the final meals
     • warnings (soft-budget overrun, unused expiring item, open package left) → attached to the plan
        │
        ▼
[6] Persist meal_plan, batches, practical quantities, meals, grocery list → generation_run succeeded
    (from Phase 2 also: plan_candidate exposure log)
```

**The LLM is trusted with:** recipe ideas, ingredient *names*, raw quantities for its base servings, step text (including appliance temperatures and cook/flip/rest times, which are range-checked), time estimates (labeled "est."), substitution ideas, and free-text parsing. **Never trusted with:** calories, macros, cost, scaling, totals, safe internal temperatures, storage durations, health claims, or "cheap/deal" claims.

**Caps** (env-configurable): `LLM_MAX_ATTEMPTS=3` per call; transport retries for 429/timeouts counted separately (≤ 3, honoring `retry-after`); ≤ 2 targeted-generation rounds; ≤ 2 re-solves after rounding; `LLM_MAX_CALLS_PER_RUN=12`. Hitting any cap gives a clear, structured error, and partial garbage is never persisted.

---

## 6. Pydantic models

### 6.1 Shared enums (`app/domain/enums.py`, Phase 0)

```python
from enum import StrEnum


class MealSlot(StrEnum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"
    PROTEIN_DESSERT = "protein_dessert"
    DRINK = "drink"


class NutritionPriority(StrEnum):
    PROTEIN = "protein"
    CARB = "carb"
    IRON = "iron"
    BALANCED = "balanced"
    # Future modes (PRD §3): accepted by the enum, rejected by the planner until implemented.
    FIBER = "fiber"
    LOWER_FAT = "lower_fat"
    SATIETY = "satiety"
    VEGETABLE = "vegetable"


class CalorieMode(StrEnum):
    STRICT_DAILY = "strict_daily"   # hard daily ceiling
    WEEKLY = "weekly"               # hard weekly ceiling + per-day band


class RecipeMood(StrEnum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    FANCY = "fancy"


class PortionSize(StrEnum):
    SMALL = "small"              # 0.75
    NORMAL = "normal"            # 1.00
    LARGE = "large"              # 1.25
    EXTRA_LARGE = "extra_large"  # 1.50


class GroceryMode(StrEnum):
    BALANCED = "balanced"
    CHEAPEST = "cheapest"
    HEALTHIER = "healthier"
    SEASONAL = "seasonal"


class Equipment(StrEnum):
    STOVETOP = "stovetop"
    OVEN = "oven"
    AIR_FRYER = "air_fryer"
    MICROWAVE = "microwave"
    RICE_COOKER = "rice_cooker"
    PRESSURE_COOKER = "pressure_cooker"
    SLOW_COOKER = "slow_cooker"
    BLENDER = "blender"
    FOOD_PROCESSOR = "food_processor"
    GRILL = "grill"
```

### 6.2 Constraint object (`app/schemas/constraints.py`, Phase 1)

```python
from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import (
    CalorieMode, Equipment, GroceryMode, MealSlot, NutritionPriority, PortionSize, RecipeMood,
)

SUPPORTED_PRIORITIES = frozenset({
    NutritionPriority.PROTEIN, NutritionPriority.CARB,
    NutritionPriority.IRON, NutritionPriority.BALANCED,
})


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SlotTarget(_Frozen):
    slot: MealSlot
    kcal: int = Field(gt=0, le=3000, description="kcal allocated to this slot per day")
    portion_size: PortionSize | None = None  # None -> PlanConstraints.default_portion_size


class DaySpec(_Frozen):
    day: date
    slots: tuple[MealSlot, ...] = Field(min_length=1)
    is_cook_day: bool                                  # from the cook schedule (Tue/Fri = False by default)
    cook_minutes_available: int = Field(ge=0, le=600)  # start-to-finish, all cooking that day combined
    mood: RecipeMood
    kcal_target: int = Field(gt=0, le=10_000)          # computed by code from settings

    @model_validator(mode="after")
    def _check(self) -> "DaySpec":
        if len(set(self.slots)) != len(self.slots):
            raise ValueError(f"{self.day}: duplicate slot")
        if not self.is_cook_day and self.cook_minutes_available != 0:
            raise ValueError(f"{self.day}: not a cook day, so cook minutes must be 0")
        return self


class CalorieTolerance(_Frozen):
    # Ceilings are hard in both modes. The under-target allowances are the accepted defaults.
    weekly_under_pct: float = Field(default=3.0, ge=0, le=25)   # weekly mode: week ≥ W × (1 − 3%)
    daily_under_pct: float = Field(default=5.0, ge=0, le=50)    # strict mode: day ≥ T × (1 − 5%)
    daily_band_kcal: int = Field(default=150, ge=0, le=1000)    # weekly mode: each day within T ± 150 kcal


class ResolvedFrequencyCap(_Frozen):
    """A FrequencyCap setting (target = one ingredient or one tag) resolved by code to ingredient ids.
    A meal counts once if any of its batch's ingredients is a member."""
    label: str                                         # "Pork as a meal component"
    member_ingredient_ids: frozenset[int]
    max_meals_per_week: int = Field(ge=0, le=21)       # 0 => members are excluded instead (§7.4)
    never_favor: bool = True                           # no nutrition / price / inventory-use bonus


class PortionRequest(_Frozen):
    """'Make 7 portions', 'I need lunch for Monday-Friday', 'make 10 and freeze half'."""
    slot: MealSlot
    days: tuple[date, ...] = Field(min_length=1)
    portion_size: PortionSize | None = None
    same_recipe: bool = True
    extra_portions_to_freeze: int = Field(default=0, ge=0, le=20)


class PlanConstraints(_Frozen):
    schema_version: Literal[1] = 1
    week_start: date
    days: tuple[DaySpec, ...] = Field(min_length=1, max_length=14)
    calorie_mode: CalorieMode
    daily_kcal_target: int = Field(ge=800, le=6000)
    weekly_kcal_target: int = Field(gt=0)
    tolerance: CalorieTolerance = CalorieTolerance()
    slot_targets: tuple[SlotTarget, ...] = Field(min_length=1)
    nutrition_priority: NutritionPriority
    secondary_priority: NutritionPriority | None = None
    grocery_mode: GroceryMode = GroceryMode.BALANCED
    weekly_budget_cents: int | None = Field(default=None, ge=0)
    budget_is_hard: bool = False                       # PRD §33: "within budget when possible"
    default_portion_size: PortionSize = PortionSize.NORMAL
    portion_nudge_pct: float = Field(default=10.0, ge=0, le=25)  # solver may use ±10% portion variants
    portion_requests: tuple[PortionRequest, ...] = ()
    equipment: frozenset[Equipment] = Field(min_length=1)
    leftover_fridge_days: int = Field(default=3, ge=0, le=4)   # never above the FoodSafety.gov chart value
    store_ids: tuple[int, ...] = Field(min_length=1)           # preference order: primary first
    store_split_min_savings_cents: int = Field(default=500, ge=0)  # R4: separate Price Rite trip only if ≥ $5 saved
    excluded_diet_tags: frozenset[str] = frozenset({"beef"})
    excluded_ingredient_ids: frozenset[int] = frozenset()      # resolved by code: tags + held items + your list
                                                               # + members of any cap set to 0
    frequency_caps: tuple[ResolvedFrequencyCap, ...] = ()      # e.g. pork components ≤ 1 meal/week
    disliked_ingredient_ids: frozenset[int] = frozenset()
    favorite_recipe_ids: frozenset[int] = frozenset()
    max_portions_per_recipe: int = Field(default=5, ge=1, le=14)
    region_code: str | None = None

    @model_validator(mode="after")
    def _consistency(self) -> "PlanConstraints":
        expected = [self.week_start + timedelta(days=i) for i in range(len(self.days))]
        if [d.day for d in self.days] != expected:
            raise ValueError("days must be consecutive and start at week_start")
        if self.weekly_kcal_target != sum(d.kcal_target for d in self.days):
            raise ValueError("weekly_kcal_target must equal the sum of day targets")
        target_slots = [t.slot for t in self.slot_targets]
        if len(set(target_slots)) != len(target_slots):
            raise ValueError("duplicate slot target")
        used = {s for d in self.days for s in d.slots}
        if missing := used - set(target_slots):
            raise ValueError(f"no kcal allocation for slots: {sorted(missing)}")
        if sum(t.kcal for t in self.slot_targets) > self.daily_kcal_target:
            raise ValueError("slot allocations exceed the daily kcal target")
        if self.secondary_priority == self.nutrition_priority:
            raise ValueError("secondary priority must differ from primary")
        for p in (self.nutrition_priority, self.secondary_priority):
            if p is not None and p not in SUPPORTED_PRIORITIES:
                raise ValueError(f"nutrition priority '{p}' is not supported yet")
        if not any(d.is_cook_day for d in self.days):
            raise ValueError("at least one cook day is required")
        days_by_date = {d.day: d for d in self.days}
        for req in self.portion_requests:
            for day in req.days:
                if day not in days_by_date or req.slot not in days_by_date[day].slots:
                    raise ValueError(f"portion request {req.slot} on {day} is not a planned slot")
        return self
```

**Phase 1 notes.** As built: `DaySpec.cook_minutes_available` counts **hands-on** minutes (C1); the weekly `max_portions_per_recipe` cap applies only to `VARIETY_CAPPED_SLOTS` = breakfast, lunch, dinner (C2); `held_ingredient_ids` (the held subset of `excluded_ingredient_ids`) was added so diagnostics can list items to review; `DaySpec.kcal_target` is the day's slot allocations added up (unallocated calories stay unplanned).

**Phase 1 fix-up (2026-10-09, C4 and C7).** `schema_version` is 2. `weekly_budget_cents` and `budget_is_hard` are gone: `planning_mode` (`inventory` | `shop`) and `purchase_limit_cents` (a hard limit on cash this trip: shop mode's optional budget, or inventory mode's top-up, default 0) come from each plan request, never from settings. `daily_protein_target_g` (settings default 100, request override) is a floor per calorie mode: strict daily = every day, weekly = the week total. `UserSettings` is version 2 too (migration 0002 moves your stored settings: data only).

**Phase 2b (planned, `docs/FLOW_SPEC.md` §13.3).** `PlanConstraints` gains:
- `household_size` (a meal is h portions; limits apply to your portion);
- `protein_reward` (only with the High protein tile), capped: each day's protein earns a reward only up to 1.5 × `daily_protein_target_g` (E11);
- `allowed_purchase_ingredient_ids` (could-buy items in "use what I have" mode);
- `always_have_ingredient_ids` (unlimited owned stock);
- `pinned` (the swap's fixed meals and batches);
- calendar-week cap allowances (`cap_used_by_week`, from other plans and one-meal plans).

`favorite_recipe_ids` is filled from `recipe_favorite`. `UserSettings` becomes version 3 (household size, Always have, default budget as a pre-fill only, onboarding flag; data migration in `0005_cook_flow`). Each addition is optional with a default, so existing callers and stored snapshots stay valid.

Mapping from PRD §32's example: `daily_calorie_limit` → `daily_kcal_target`; `weekly_calorie_limit` → `weekly_kcal_target`; `meals_per_day` → `DaySpec.slots`; `portion_size` → `default_portion_size`; `cooking_time`/`recipe_mood` → per-day `cook_minutes_available`/`mood`; `budget_priority` → dropped in favor of `grocery_mode` (Q12); `equipment` → `equipment`.

### 6.3 LLM-generated recipe (`app/schemas/llm_recipe.py`, Phase 1)

```python
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import Equipment, MealSlot, RecipeMood


class LLMUnit(StrEnum):
    G = "g"; KG = "kg"; OZ = "oz"; LB = "lb"
    ML = "ml"; L = "l"; TSP = "tsp"; TBSP = "tbsp"; CUP = "cup"; FL_OZ = "fl_oz"
    COUNT = "count"; CLOVE = "clove"; SLICE = "slice"; CAN = "can"; HEAD = "head"; SCOOP = "scoop"
    # Named units must exist in ingredient_unit for that ingredient, else a domain error.


class IngredientRole(StrEnum):
    PROTEIN = "protein"; CARB = "carb"; VEGETABLE = "vegetable"; FRUIT = "fruit"; DAIRY = "dairy"
    FAT = "fat"; SAUCE = "sauce"; SEASONING = "seasoning"; GARNISH = "garnish"; OTHER = "other"


class InstructionSection(StrEnum):
    PREP = "prep"; MARINATE = "marinate"; STOVETOP = "stovetop"; OVEN = "oven"
    AIR_FRYER = "air_fryer"; RICE = "rice"; MICROWAVE = "microwave"; NO_COOK = "no_cook"
    ASSEMBLY = "assembly"; PORTIONING = "portioning"; STORAGE = "storage"; REHEATING = "reheating"


_SECTION_EQUIPMENT = {
    InstructionSection.OVEN: Equipment.OVEN,
    InstructionSection.AIR_FRYER: Equipment.AIR_FRYER,
    InstructionSection.STOVETOP: Equipment.STOVETOP,
    InstructionSection.MICROWAVE: Equipment.MICROWAVE,
}


class LLMIngredient(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=80, description="Name from the provided ingredient list")
    quantity: float = Field(gt=0, le=5000, description="Raw/dry, as-purchased amount for base_servings")
    unit: LLMUnit
    preparation: str | None = Field(default=None, max_length=80)
    role: IngredientRole
    component: str | None = Field(default=None, max_length=40)
    optional: bool = False


class LLMStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    section: InstructionSection
    text: str = Field(min_length=5, max_length=500)   # cooking temps/times welcome; see §7.3
    duration_minutes: int | None = Field(default=None, ge=0, le=720)
    appliance_temp_f: int | None = Field(
        default=None, ge=150, le=550,
        description="Oven / air-fryer / pan setting. Never an internal food temperature.",
    )
    doneness_check_for: str | None = Field(
        default=None, max_length=80,
        description="Ingredient whose doneness is checked here; the app inserts the safe temperature.",
    )


class GeneratedRecipe(BaseModel):
    """Creative content only. Deliberately has NO calorie, macro, cost, safe-temperature or
    storage-duration fields: code computes or injects all of those."""
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=3, max_length=80)
    description: str = Field(max_length=300)
    meal_slots: list[MealSlot] = Field(min_length=1, max_length=3)
    mood: RecipeMood
    cuisine: str | None = Field(default=None, max_length=40)
    flavor_tags: list[str] = Field(default_factory=list, max_length=6)
    base_servings: int = Field(ge=1, le=12)
    active_minutes: int = Field(ge=1, le=240)
    total_minutes: int = Field(ge=1, le=720)
    equipment: list[Equipment] = Field(default_factory=list)   # empty allowed for no-cook recipes
    freezer_friendly: bool
    ingredients: list[LLMIngredient] = Field(min_length=2, max_length=25)
    steps: list[LLMStep] = Field(min_length=3, max_length=30)

    @model_validator(mode="after")
    def _structure(self) -> "GeneratedRecipe":
        if self.total_minutes < self.active_minutes:
            raise ValueError("total_minutes must be >= active_minutes")
        names = [i.name.strip().lower() for i in self.ingredients]
        if len(set(names)) != len(names):
            raise ValueError("duplicate ingredient names; combine them into one line")
        sections = {s.section for s in self.steps}
        if InstructionSection.PREP not in sections:
            raise ValueError("include at least one PREP step")
        if InstructionSection.PORTIONING not in sections:
            raise ValueError("include a PORTIONING step")
        missing = {eq for sec, eq in _SECTION_EQUIPMENT.items() if sec in sections and eq not in self.equipment}
        if missing:
            raise ValueError(f"steps use equipment not listed in 'equipment': {sorted(missing)}")
        for sec in (InstructionSection.OVEN, InstructionSection.AIR_FRYER):
            sec_steps = [s for s in self.steps if s.section == sec]
            if sec_steps and all(s.appliance_temp_f is None for s in sec_steps):
                raise ValueError(f"{sec} steps must state an appliance temperature")
        return self


class GeneratedRecipeBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipes: list[GeneratedRecipe] = Field(min_length=1, max_length=6)
```

**Strict vs best-effort.** `llm/structured.py` derives a transport JSON schema from these models (types, enums, all properties required, `additionalProperties: false`, nullable as unions; that is what Groq strict mode requires).
- **`strict`:** sends it with `strict: true`, so the provider constrains decoding.
- **`best_effort`:** sends the same schema with `strict: false` and also summarizes it in the system prompt. Correctness then rests entirely on Pydantic validation + retry.

Both modes share one parse/validate/retry path, the same caps and the same `llm_call` logging. If the provider rejects strict mode for the configured `LLM_MODEL`, the adapter raises a configuration error that says to set `LLM_STRUCTURED_MODE=best_effort`. No model names are hardcoded.

---

## 7. Cross-cutting rules

### 7.1 Numbers and rounding

| Thing | Representation | Rule |
|---|---|---|
| Quantities | `Decimal`, base units g / ml / count | Float only inside PuLP |
| Unit constants | exact | 1 lb = 453.59237 g · 1 oz = 28.349523125 g · tsp = 4.92892159375 ml · tbsp = 3 tsp · US cup = 236.5882365 ml · fl oz = 29.5735295625 ml |
| Practical rounding (any scale ≠ 1) | per kind | count → half-up to `count_rounding_step`, minimum one step · mass < 10 g → 1 g; 10–250 g → 5 g; > 250 g → 10 g · volume < 1 tbsp → ⅛ tsp; < ¼ cup → ½ tbsp; else nearest standard cup measure (¼ ⅓ ½ ⅔ ¾, whole). Rounding happens in the display unit, so display = computed. Scale = 1 keeps authored quantities. Calorie-dense dry goods are authored in grams. |
| Money | `int` cents | Decimal intermediate; ROUND_HALF_UP once per grocery line (or per batch for consumed cost); totals = sum of rounded lines |
| kcal shown | `int` | Per-meal half-up; day/week totals = sum of displayed per-meal values |

### 7.2 Food-safety lookup (hardcoded in `domain/food_safety.py`, never from the LLM)

**Safe internal temperatures** (CLAUDE.md baseline):

| Key | Applies to | Value |
|---|---|---|
| `poultry` | chicken, turkey, duck: whole, parts, ground | 165 F |
| `ground_meat` | ground beef, pork, lamb, veal | 160 F |
| `whole_cut_meat` | steaks, chops, roasts of beef, pork, lamb, veal | 145 F + 3-minute rest |
| `fish_shellfish` | fish and shellfish | 145 F |
| `egg_dish` | dishes where eggs are a primary component | 160 F |
| `leftovers_reheat` | any reheated leftovers | 165 F |

Beef rows stay in the table (they are part of the CLAUDE.md baseline); the beef exclusion keeps those foods out of plans. Pork is allowed (capped), so its rows are live.

**Storage and reheating.**
- **Source:** the **FoodSafety.gov Cold Food Storage Chart** (`https://www.foodsafety.gov/food-safety-charts/cold-food-storage-charts`, "Date Last Reviewed: September 19, 2023").
  - Saved copy: `docs/sources/Cold Food Storage Chart _ FoodSafety.gov.pdf` (printed 2026-10-08).
  - All 53 rows are transcribed in `domain/storage_chart.py`, worded as printed, with day ranges parsed by code.
  - `APP_STORAGE` maps the rows the app uses, e.g. cooked leftovers, raw poultry pieces, ground meat or poultry, eggs, fish, shrimp, soups and stews, egg casseroles.
- **Your fixed defaults:** cooked leftovers **3 days** in the fridge, and reheat to **165 F** (CLAUDE.md; the chart has no reheating guidance).
  - `leftover_fridge_days` is editable up to the chart's upper bound for cooked meat or poultry: 3 to 4 days, so at most 4.
- The fridge window means a batch cooked on day *d* can be eaten on *d* through *d + 3*.
- **Freezer times** are shown in the chart's own wording, with its note that they're for quality only: frozen foods stored continuously at 0 °F or below can be kept indefinitely.

**Injection rules.**
- Every step with `doneness_check_for` gets the matching temperature line.
- A recipe containing a `safety_category` ingredient but no doneness step gets one appended automatically.
- STORAGE and REHEATING sections always end with the table's text.
- Mixed ground meats use the strictest applicable value.

### 7.3 Prose filter (`domain/text_rules.py`): exactly six blocked categories

The filter runs on all LLM text that is displayed. It blocks only these six categories:

| # | Category | Blocked examples | Passes (must not be blocked) |
|---|---|---|---|
| 1 | Calories | "about 450 calories", "a light, low-calorie lunch", "300 kcal" | — |
| 2 | Macros | "40 g protein per serving", "high-protein", "low-carb", "packed with protein" | "whisk the protein powder into the milk", "protein pudding", "sear the protein" |
| 3 | Cost | "$2.50 a serving", "costs about $10", "a cheap dinner", "cheapest option", "budget-friendly", "good deal", "on sale" | "saves time", "makes 4 servings" |
| 4 | Safe internal temperatures | "cook until the internal temperature reaches 165°F", "thermometer should read 145", "165 F in the thickest part" | "air fry at 400F for 18 minutes, flip at 9", "preheat the oven to 425°F", "bake at 375°F until cooked through" |
| 5 | Storage durations | "keeps 5 days in the fridge", "refrigerate for up to 3 days", "freezes well for 3 months" | "marinate 2–12 hours", "chill 30 minutes", "freeze 20 minutes to firm up before slicing", "refrigerate overnight to marinate" |
| 6 | Health claims | "helps prevent anemia", "boosts immunity", "good for your heart", "detox", "burns fat" | "toss with oil to prevent sticking", "helps the sauce thicken" |

**Everything else passes:**
- appliance temperatures, cook/flip/rest/marinate times
- water ratios ("1 cup rice to 1½ cups water"), pressure-cooker settings
- portion counts and weights ("about 350 g per container")
- ingredient quantities

How the filter decides:
- **Temperatures:** blocked only when tied to doneness or a thermometer (cue words such as "internal", "thermometer", "registers", "thickest part", "until it reaches … °F").
- **Storage durations:** blocked only when the unit is days, weeks or months in a keeping or storage context.
- **Retry message:** a rejection names the exact offending phrase and says what to remove (e.g. "remove the internal-temperature clause; keep the oven temperature").
- **Cost category (R7, confirmed):** "cheap", "cheapest", "budget-friendly", "good deal" and "on sale" are cost claims. Only code can produce them, from stored price data; the LLM can't say them in prose.

**Separate from the prose filter: exclusion enforcement** (approved). Recipe steps may only use listed ingredients. A step naming an excluded food (beef, beef broth, tallow, bovine gelatin, unspecified gelatin, …) fails the exclusion check, not the prose filter. Pork words are not exclusion errors; a step naming an unlisted pork component ("add 2 strips of bacon") fails the ordinary "step uses an unlisted ingredient" check. Nutrient-content labels ("good source of iron") and "Seasonal in your region" / "good deal" labels are generated by code only.

### 7.4 Iron, heme and diet tags

- **Heme iron estimate (Q3 + R1):** 40% of total iron for meat (pork, lamb), poultry, fish and shellfish; 0% for plant foods, eggs and dairy. The UI always labels it "estimated".
- **Diet tags** (set at seed time, on the canonical ingredient):

  | Tag | Meaning | Examples | Effect |
  |---|---|---|---|
  | `beef` | is or is derived from beef | ground beef, beef broth/stock, beef tallow, bovine gelatin, beef bouillon | **excluded** (`excluded_diet_tags` default `{"beef"}`) |
  | `possible_beef` | may be beef-derived; the source isn't stated | gelatin (unspecified), marshmallows, collagen peptides, bouillon cubes, pepperoni and salami (often pork + beef), cheese with possible calf rennet | **held** = excluded by default, listed for review; an `allow` decision releases one item |
  | `pork` | pork as a meal component | sausage, pepperoni, bacon, ham, pork chops, ground pork | allowed, **frequency-capped** (default ≤ 1 meal/week), never favored |
  | `pork_trace` | trace pork-derived ingredient | lard, pork gelatin, refried beans made with lard, chicken sausage in pork casing | allowed, **no limit** |

  An item can carry two tags: generic pepperoni and salami are `pork` + `possible_beef`, so they stay held until you allow a pork-only product, and then count toward the pork cap. Tortillas and plain Greek yogurt (no gelatin) carry no exclusion tag (R2).
- **Exclusion resolution** (`domain/exclusions.py`, pure), in order:
  1. **Excluded:** `diet_tags` intersect `excluded_diet_tags`; or an `exclude` preference; or the ingredient is a member of a frequency cap whose max is 0. An `allow` decision never overrides a hard tag exclusion.
  2. **Held:** tagged `possible_beef` with no `allow` decision. Held items are never silently allowed.
  3. Otherwise **allowed** (pork components carry their cap).
- **Frequency caps** (`domain/frequency_caps.py`, pure; a general setting, not a pork rule): `FrequencyCap(target_type = ingredient | tag, target, max_meals_per_week, never_favor = true)`. A tag is used for "category" because the culinary `category` column can't single out pork (sausage and chicken are both `protein`). A meal counts once if any ingredient of its batch is a member. A cap of 0 turns into an exclusion of its members; ingredients outside the cap (`pork_trace`) are unaffected. `never_favor` removes the nutrition, price and inventory-use bonuses, so a capped meal is chosen only when it fits within the cap on other grounds.
- **Prompts** include a plain-language never-use list (beef and everything derived from it, held items). Never-favored capped ingredients are left out of the generation vocabulary. The resolver turns any excluded name into a domain error, which triggers a retry.

### 7.5 Testing strategy

- **Layers:** `domain/` tests are pure and fast. `services/`, `usda/`, `seed/` and `planning/` tests use the `db-test` Postgres (tmpfs; migrations run once per session; each test in a rolled-back transaction). `api/` tests use TestClient.
- **LLM:** automated tests use `FakeLLMClient` fixtures, in both `strict` and `best_effort` modes. Real Groq runs only in `pytest -m live_llm` and the CLI.
- **Architecture tests:** `domain/` imports nothing from `db`/`api`/`llm`/`sqlalchemy`/`fastapi`. `groq` is imported only in `app/llm/client.py`. No model-name literals in `app/`. Every `*_cents` column is `Integer`. No `stream`/`tools` with structured outputs. `PlanValidator` accepts only `RoundedPlan`.
- **No wall-clock dependence (Phase 2, K6):** in tests every MILP runs with no wall-clock cut (`conftest.py` replaces its time limit with 300 s and fails a test whose solve still stops on the clock). Single-threaded HiGHS with gap stops is deterministic, so an identical model reuses the answer within a session (tests marked `solve_cache_off` always solve). Orchestration tests that re-solve use 3-day weeks; the timed 30-candidate test is opt-in (`perf` marker, `RUN_PERF_TESTS=1`).
- **End of phase:** full `pytest` (and `vitest` from Phase 2) output pasted in the summary, plus the fresh-clone Docker test check (`scripts/fresh_clone_check.sh`), run after committing even when dependencies didn't change.

### 7.6 LLM budget facts (checked 2026-10-08)

- **Groq strict structured outputs:** `openai/gpt-oss-20b`, `openai/gpt-oss-120b`, `qwen/qwen3.8-27b`. **Best-effort:** those plus `openai/gpt-oss-safeguard-20b`. Neither works with streaming or tool use.
- **Published base limits** for those models: 30 req/min, 1K req/day, **8K tokens/min**, 200K tokens/day. The client reads `x-ratelimit-*`/`retry-after` rather than hardcoding limits.
- **Implications:** 2–3 recipes per call, compact prompts, low reasoning effort, a daily token guard, and the seed library plus reuse to avoid calls.
- **Phase 2b estimates** (`docs/FLOW_SPEC.md` §15): a meal-now search makes 0–1 calls (≈ 6–7K tokens with a narrowed vocabulary, measured in step 2b.3); a typical meal prep and a swap make 0; worst cases are capped by the gap rules, the 180 s request budget and the 8K tokens/min limit.
- **Observed in the Phase 1 live runs (2026-10-09, `openai/gpt-oss-120b`, strict):** a two-recipe batch is ~5.9K prompt + ~1.8K completion tokens, so a second call in the same minute gets a 429 (retry-after 7–39 s, handled). Strict mode still returned `json_validate_failed` once (retried as a parse error). A retry that re-sent the whole failed reply grew to 11.4K requested tokens and was refused with HTTP 413, so retries now re-send only short replies and `LLM_MAX_COMPLETION_TOKENS` defaults to 3000.

### 7.7 API and config conventions

- REST under `/api/v1`. Errors are `application/problem+json`. Long operations finish inside the request and stream `application/x-ndjson` progress (heartbeat every 5 s) ending in one result line (Phase 2, K2); every LLM call, rate-limit wait and solve fits `PLAN_TIME_BUDGET_SECONDS` (180 s). Phase 2b's `/cook/meal-now`, `/cook/meal-prep`, swap and `/grocery/advice` use the same pattern; meal now also streams intermediate `results` lines. This is HTTP response streaming only: LLM calls never stream (CLAUDE.md rule 6).
- Environment-only config; `.env.example` updated in every phase.

### 7.8 Raw / dry / as-sold rule (added before Phase 1)

- **Recipe quantities are raw, dry or as-sold weights** unless a line explicitly says otherwise (`state`:
  `raw`, `dry`, `cooked` or `as_sold`).
- **Every nutrition mapping has a state,** read from its USDA description by `domain/food_state.py`. A
  segment that starts with a cooking word (cooked, boiled, roasted, fried…) means `cooked`; "dry",
  "dried", "uncooked" or a spice means `dry`; USDA's "raw" for grains and legumes means `dry`;
  canned / frozen / cured / packaged foods are `as_sold`. Package-label foods are always `as_sold`.
- **The check** (`line_state_error`) fails a line when:
  - it uses the default (raw/dry/as-sold) and the mapping is cooked;
  - it says `cooked` and the mapping isn't;
  - it says `dry` or `raw` and the mapping is as-sold, which may be canned and hydrated.

  The seed loader enforces it today, and the Phase 1 recipe validator will reuse it.
- Explicit line states are validated but not stored yet: `recipe_ingredient` has no state column, and no line needs one. If Phase 1 needs one, I'll flag it before adding a column.

---

## 8. PRD coverage map

| PRD § | Topic | Phase(s) |
|---|---|---|
| top | Primary user flow (4 tabs, Cook flow, Grocery advice, onboarding, favorites + save for later, look and feel) | 2b (`docs/FLOW_SPEC.md`) |
| 1 | Core concept | all |
| 2 | Calorie planning | 0 (math) · 1 · 2 (display) |
| 3 | Nutrition priority modes | 0 (data, heme estimate) · 1 (protein/carb/iron/balanced; registry for future modes) |
| 4 | Weekly configuration | 1 (API) · 2 (UI) · 2b (onboarding, Settings tab, goal tiles) |
| 5 | Recipe mood | 1 (per-day) · 2b (mood per search) · 4 (change a day after planning) |
| 6 | Cooking time | 1 (cook schedule, minutes) · 2b (Quick time limit) · 4 |
| 7 | Portion size | 0 (math) · 1 · 2 · 2b (household size) |
| 8 | Meal-prep quantity, package sizes | 0 (math) · 1 (batches, freezer, absorption pass) · 2 (open packages via "Mark cooked") · 2b (portions / days & meals, extra to freeze) |
| 9 | Recipe editing | 3 |
| 10 | Substitution engine | 0 (accepted pairs) · 1 (applied in planning) · 2b (deterministic suggestions for missing items) · 3 (engine) |
| 11 | Cooking instructions | 0 (safety table, seed drafts) · 1 (generation + injection) · 2 (display) · 2b (cooking mode) |
| 12 | Grocery recommendations | 1 (plan − inventory, expiring, open packages) · 2b (basic "What should I buy?") · 5 (full engine) |
| 13 | Grocery list modes | 1 (balanced default) · 2b (Cheap tile → cheapest weights) · 5 |
| 14 | Grocery recommendation engine | 2b (templated reasons from current prices) · 5 (deals, history) |
| 15 | Price tracking | 0 (per-store schema, estimates) · 1 (manual entry) · 2 (price at check-off) · 5 (history, within-store deals) |
| 16 | Seasonal recommendations | 5 |
| 17 | Favorites | 2b (♥, Saved section, ranking + solver boost; plus save for later) · 3 (weighted preference score) |
| 18 | Ratings | 3 |
| 19 | Preference learning | 3 · 6 |
| 20 | Feedback pipeline | 3 |
| 21 | Future ML pipeline | 6 |
| 22 | Personal learning loop | 2 (cook deduction) · 3 · 4 · 6 |
| 23 | Recipe versioning | 0 (schema, seed drafts) · 3 (edit behavior) |
| 24 | Cook Again | 3 |
| 25 | Weekly planning screen | 1 (data) · 2 (UI) · 2b (meal-prep results: Today first, Recipes / Shopping list) |
| 26 | Daily adjustment | 2b (swap one meal, rest fixed) · 4 (day-level time/mood overrides) |
| 27 | Dynamic calorie rebalancing | 4 |
| 28 | Strict daily vs weekly | 1 (both modes in solver, approved) · 4 (toggle UX, rebalancing) |
| 29 | Protein desserts | 0 (seed pudding) · 1 · 2 |
| 30 | Meal categories | 0 · 1 |
| 31 | Prompting architecture | 0 · 1 |
| 32 | Constraint engine | 1 |
| 33 | Validation layer | 1 |
| 34 | Mobile-first PWA | 2 · 2b (question screens, minimal typing, light/dark) (+ screens in 3–6) |
| 35 | Grocery Store Mode | 5 (in the Grocery tab) |
| 36 | Final vision | all |

---

## 9. Phases

### Phase 0: Data foundation

**Goal.** Build the deterministic core: the Phase 0–1 schema, a trustworthy local USDA nutrition database, seed data (ingredients, stores, estimated prices, exclusions, your cook schedule, and a draft recipe library), and fully tested calculators for units, scaling, nutrition, cost, packages, inventory, calories, food safety and exclusions. No LLM, no frontend.

**PRD sections.** §1, §2 (math), §3 (nutrient data, heme estimate), §7, §8 (math), §10 (accepted substitution pairs), §11 (safety table, seed instructions), §15 (per-store price storage), §23 (versioned seed drafts), §29 (seed dessert), §30, §31.

**Deliverables**
1. **Infra:** `docker-compose.yml` (Postgres 17 `db`, tmpfs `db-test`, `backend`), backend `Dockerfile`, `pyproject.toml` (approved deps), `.env.example`, `.gitattributes`, `README.md`.
2. **Schema:** SQLAlchemy 2.0 models and Alembic `0001_initial` for the **31 tables** in §4.4, plus `pg_trgm`. Later tables are *not* created.
3. **Domain calculators** (pure, typed, `Decimal`):
   - `units`: normalize names; convert within kind; volume → mass via density; count ↔ mass via unit weight; named portions win.
   - `quantities`: display formatting.
   - `scaling`: exact + practical quantities (§7.1).
   - `nutrition`: line/recipe/portion totals; energy fallback 208 → 958 → 957 → Atwater (flagged); heme estimate; FDA-DV labels; missing ≠ zero; label conversion (per serving + serving grams → per 100 g).
   - `cost`: unit price; consumed vs purchase cost; half-up; partial totals with unpriced items listed.
   - `packages`: `purchase_need(...)` → packages, remainder, absorb flags.
   - `inventory_math`: FIFO by expiry, open packages first, shortfall.
   - `calories`: weekly target, largest-remainder distribution, slot targets, validation.
   - `food_safety`: §7.2 table + FoodSafety.gov citation comment.
   - `exclusions`: §7.4 resolution.
   - `frequency_caps`: cap membership, meals-per-week counting, violations, cap 0 → exclusion (§7.4).
4. **USDA importer:** Foundation + SR Legacy CSV zips → `usda_*` tables; idempotent. A `usda-subset` command writes the committed test fixture (only the foods the seed references) so tests run offline without the full download.
5. **Seed data** (`app/seed/data/`):
   - **Stores:** Stop & Shop (priority 1), Price Rite (priority 2).
   - **Ingredients:** ~150–200 canonical ingredients covering the PRD examples and the seed recipes (§13), with FDC mappings, aliases, named units, densities, safety categories, heme fractions, `diet_tags`, shelf life and `assume_in_stock`. Includes `chapati (roti)` and `flour tortilla (Price Rite, 37 g)`, and the beef and pork items needed so the resolver can recognize them.
   - **Products and prices:** estimated prices for both stores, flagged `source=estimate` (Price Rite chicken estimated below Stop & Shop chicken). One known price: **Price Rite small flour tortillas, 30 count, $1.99** (`source=manual`).
   - **Protein powder (double chocolate), from your label (A2):** scoop 31 g, 120 kcal, 25 g protein. Carbs and fat per scoop were not in the values sent, so they stay flagged placeholders; until filled, the ingredient is incomplete and recipes using it are not plannable.
   - **Tortillas (A2):** 30-count bag net weight ≈ 23 oz (652 g) → 21.733 g each (computed by code), flagged **estimated** (from a 20–26 oz range) for you to replace with the exact net weight and serving size.
   - **Substitutions:** `chapati → flour tortilla (Price Rite, 37 g)` (`accepted`, `count_for_count`).
   - **Diet tags (§7.4):** beef and beef-derived → `beef` (excluded); possibly-beef items → `possible_beef` (held); pork components → `pork` (capped); trace pork → `pork_trace` (unlimited).
   - **Default settings:** cook days Mon/Wed/Thu/Sat/Sun (Tue/Fri off), 45 minutes and medium mood per cook day (editable), `leftover_fridge_days = 3`, 1,800 kcal/day, weekly mode with a ±150 kcal band, Stop & Shop then Price Rite, `store_split_min_savings_cents = 500`, `excluded_diet_tags = ["beef"]`, frequency cap `tag pork ≤ 1 meal/week, never_favor`.
   - **Seed recipe library (§13):** 9 draft versions in 5 families (incl. the 2 breakfast seeds from R3), loaded as `origin=seed`, `created_by=system`, `is_draft=true`. No seed uses beef or a pork component.
6. **Services:** ingredient search (alias + trigram); nutrition loading; per-store current price and cheapest current option.
7. **API:** `GET /health`; `GET /api/v1/ingredients?q=`; `GET /api/v1/ingredients/{id}`; `POST /api/v1/calculations/recipe`; `GET /api/v1/recipes/seed` (seed drafts with computed nutrition/cost, or "incomplete" reasons).
8. **CLI:**
   - `usda-import`, `seed`
   - `ingredient-report`: errors; placeholders (label values); held diet-review items; Atwater mismatches; unreviewed mappings
   - `safety-table`: prints the transcribed chart values with their citation for your review
9. **Docs:** `docs/data-sources.md`.

**Files and folders.** Creates `.gitattributes`, `.env.example`, `README.md`, `docker-compose.yml`, `docs/data-sources.md`, `docs/sources/` (if needed), and `backend/` (Dockerfile, pyproject, alembic.ini, conftest, `migrations/versions/0001_initial.py`, `app/{main,config,cli}.py`, `app/db/`, `app/domain/` + tests, `app/schemas/` (ingredients, calculations, seed recipe file model), `app/services/` + tests, `app/usda/` + tests, `app/seed/` (data, loader, tests), `app/api/` + tests, `app/testing/`).

**Database.** Migration `0001_initial`: 31 tables (§4.4). Nothing else.

**Acceptance criteria**
1. `alembic upgrade head` on an empty DB creates exactly the 31 `0001` tables; `downgrade base` removes them; `alembic check` reports no drift.
2. `cli usda-import` loads the Foundation + SR Legacy zips. Re-running leaves row counts unchanged.
3. `cli seed` is idempotent and loads:
   - ≥ 150 ingredients and ≥ 300 aliases
   - 2 stores with priorities 1 and 2
   - a store on every price observation
   - the Price Rite tortilla observation (199 ¢ / 30 count, `manual`); all other prices `estimate`
   - the chapati → tortilla substitution
   - default settings with the Mon/Wed/Thu/Sat/Sun cook schedule, the pork frequency cap and the $5 split threshold
   - 9 draft seed recipe versions in 5 families
4. `cli ingredient-report` shows **zero errors**. Its expected-placeholder list (protein powder carbs/fat, tortilla net weight flagged estimated) and held list (possible-beef items) are shown to you.
5. The 7 seed recipes without protein powder return full nutrition and cost from `POST /calculations/recipe` and `GET /recipes/seed`. The pudding and the overnight oats return "incomplete: protein powder carbohydrate_g, fat_g label values missing" and become complete in a test once fixture label values are supplied.
6. Every `beef` ingredient resolves as excluded (an `allow` decision does not release it); every `possible_beef` item resolves as held until a decision exists; `pork` and `pork_trace` items resolve as allowed; with the pork cap set to 0, `pork` items resolve as excluded and `pork_trace` items stay allowed.
7. `cli safety-table` prints the transcribed FoodSafety.gov values with their citation, and you confirm them.
8. Calculation outputs match the hand-computed fixture expectations (including 1.7 lb vs 2 lb and the heme estimate). All tests pass. `app/domain/` line coverage ≥ 95%. `ruff` and `mypy` are clean. Architecture tests pass.
9. A fresh clone reaches a passing test run using only `README.md`.

**Test plan**
- `domain/tests/test_units.py`: lb↔g exact; oz vs fl_oz distinct; tsp/tbsp/cup ↔ ml; 1 cup flour (0.53 g/ml) ≈ 125 g; 1 tbsp honey (1.42) ≈ 21 g; ml → g without density raises; 1 head cabbage via unit weight; 2 large eggs = 100 g; `cup_chopped` beats density; 30 tortillas → 652 g via the estimated piece weight (652 / 30 = 21.733 g); unit normalization; `T`/`t` rejected; zero/negative rejected; property round trip g → lb → g (hypothesis).
- `domain/tests/test_scaling.py` (odd portion counts): base 4 → 5 (×1.25): 3 eggs → **4**; → 7 (×1.75): **5**; → 3 (×0.75): **2**; → 6: 4.5 → **5**; base 6 → 1: 1 onion (step ½) → **½**; base 3 → 10 large (×4.1667); 8 tortillas base 4 → 5 portions = 10 tortillas (count step 1); scale 1.0 leaves authored values byte-identical; 1 tsp × 1.25 → 1¼ tsp; × 1.1 → 1⅛ tsp; 137 → 135 g, 7.4 → 7 g, 263 → 260 g; ⅓ cup × 3 → "1 cup"; invalid portions/factor > 10 → error; per-portion nutrition uses practical quantities.
- `domain/tests/test_nutrition.py`: per-100 g identity; sums; per-portion division; energy fallback chain (P20 F10 C0 → 170 kcal `derived`); missing micronutrient flagged incomplete; heme: chicken thigh iron × 0.40, shrimp × 0.40, pork chop × 0.40, spinach 0, egg 0, milk 0, labeled estimated; DV label boundaries at 10% / 20%; Atwater mismatch flagged; label conversion from your label: 120 kcal and 25 g protein per 31 g scoop → 387.097 kcal and 80.645 g protein per 100 g; missing carbs/fat → incomplete.
- `domain/tests/test_cost.py`: $1.99/lb → 0.43872 ¢/g; 1.7 lb consumed → **338 ¢**; 2 lb tray → **398 ¢**; Price Rite tortillas 199 ¢ / 30 → 8 tortillas consumed = 53.07 → **53 ¢**; $2.99 / 5 lb; half-cent up; ints only; unpriced → partial + list.
- `domain/tests/test_packages.py` (package rounding): need 1.7 lb, package 2 lb → **1 package**, remainder 136.078 g, absorb-up flag; exactly 2 lb → 1; 907.19 g → 1 (1 g tolerance); 2.1 lb → 2 packages + absorb-down flag (−4.8%); 0.5 lb on hand + need 1.7 → 1 package; on hand ≥ need → 0; 1.3 heads → 2; loose per-lb → exact; bone-in edible fraction 0.75; need 10 tortillas from 30-count bag with 25 on hand → 0 packages.
- `domain/tests/test_inventory_math.py`: FIFO by expiry; open package consumed before an unopened lot of the same ingredient; partial lots; cross-unit; shortfall; never negative.
- `domain/tests/test_calories.py`: 1800 × 7 = 12,600; 5-day plan; 12,000 / 7 → five 1714 + two 1715; allocations valid/invalid; unallocated remainder.
- `domain/tests/test_food_safety.py`: poultry 165; ground pork 160; pork chop 145 + 3 min rest; salmon 145; frittata 160; pancakes no egg note; mixed ground → strictest; reheat 165; leftovers default 3 days; `leftover_fridge_days` above the chart's upper bound (4) rejected; all 53 chart rows transcribed, with day ranges parsed by code; citation constants (URL, saved PDF, last-reviewed date) present.
- `domain/tests/test_exclusions.py`: ground beef, beef broth, beef tallow, bovine gelatin, beef bouillon → excluded via the `beef` tag; `allow` on a beef item → still excluded; unspecified gelatin, marshmallows, collagen → held; `allow` releases a held item; `exclude` excludes any item; bacon, ham, pork sausage, pork chop → allowed; lard, pork gelatin → allowed; flour tortilla and plain Greek yogurt → allowed; chicken → allowed; empty excluded tags → only held/explicit exclusions apply; pork cap 0 → bacon/ham/sausage excluded with reason "frequency cap 0", lard and pork gelatin still allowed.
- `domain/tests/test_frequency_caps.py`: membership by tag and by single ingredient; a meal with bacon counts once even with two pork lines; trace pork (lard tortilla) never counts; week with 1 pork meal under cap 1 → ok; 2 pork meals → violation naming the cap and the meals; cap 0 → members become exclusions; ingredient-target cap (e.g. salmon ≤ 2) works the same way; `never_favor` flag carried through.
- `usda/tests/test_importer.py`: fixture CSVs; idempotent; Foundation food without 208 resolves via 958; malformed rows reported.
- `seed/tests/test_seed.py`: idempotent; single user; completeness rules; alias uniqueness; FDC ids exist; USDA-sourced units link to a portion of the same food with matching grams; every price has a store; tortilla price exact; tortilla net weight flagged estimated; scoop = 31 g; Price Rite chicken estimate < Stop & Shop; 9 seed versions with `is_draft=true`, 5 families, version 1, `default_version_id` set; seed recipes reference no `beef`, `possible_beef` or `pork` ingredient; chapati → tortilla pair present; settings: cook schedule Mon/Wed/Thu/Sat/Sun, `excluded_diet_tags = ["beef"]`, pork cap 1, split threshold 500.
- `services/tests/test_ingredient_search.py`: alias hit ("boneless thighs"), trigram hit ("chiken"), archived hidden, held items marked in results, an `allow` decision in `ingredient_preference` releases a held item, beef items marked excluded.
- `services/tests/test_pricing.py`: current price per store = latest observation at that store; a newer Price Rite price doesn't change Stop & Shop's current price; cheapest current option across active stores.
- `api/tests/`: calculations round trip; `/recipes/seed` returns incomplete reason for the pudding; problem+json 422s.
- `db` tests: CHECKs (negative cents, invalid unit), `UQ(recipe_id, version_number)`, partial unique active plan, `price_observation.store_id` NOT NULL, `ingredient_substitution` from ≠ to.

**Depends on.** Repo setup (done).

**Risks and mitigations**
- *Wrong USDA mapping.* Atwater check, review report, `nutrition_reviewed_at`; you review the top ~50 mappings before Phase 1.
- *Missing protein-powder carbs/fat block the pudding and the oats.* Listed in the report on day one, so you can fill them before Phase 1 (A2).
- *FoodSafety.gov blocks automated fetch.* Retry, else you save the page into `docs/sources/` (A1). Values are never taken from secondary sources.
- *Estimated prices mislead.* `source=estimate` is shown as "est." and never used for deal or cheap labels; real entries supersede it.
- *Windows line endings.* `.gitattributes`.

**Outcome (2026-10-08).** All acceptance criteria were met except AC 7, which waited on the chart (A1). That's now unblocked: the chart was transcribed from your saved PDF during the pre-Phase 1 tasks (L6), and `cli safety-table` prints it for your confirmation. Deviations from the plan, all small:
- `units.json` is folded into `ingredients.json`. Each ingredient lists its aliases, named units, density and piece weight, referencing USDA portion ids; the loader checks each portion belongs to the same FDC food and is the stated measure.
- The `UserSettings` model and the seed-file schemas were built now (the plan had them in Phase 1), because the seed has to validate the settings JSONB. `InstructionSection` and `IngredientRole` live in `domain/enums.py` so the seed files and the Phase 1 LLM schema share them.
- New CLI command `usda-subset` writes the committed test fixture (`app/testing/fixtures/usda_subset/`, ~180 foods), so tests and a fresh clone don't need the 10 MB download.
- Cost rules: optional lines (cilantro, vanilla, banana topping) are listed and not counted. Unpriced `assume_in_stock` staples (salt, spices, water) are listed as "not costed" without making the cost incomplete.
- The Atwater check counts fiber at 2 kcal/g. This cut false flags from 27 to 7; the 7 left are USDA's food-specific factors (citrus acids, cocoa, alcohol in vanilla, vinegar).
- Search ranks exact aliases first, then per-word trigram similarity, so "chiken" finds chicken, not "green chile".
- SQLAlchemy is pinned below 2.1 to match CLAUDE.md's "SQLAlchemy 2.0". Python 3.12 runs through uv locally and in the `python:3.12-slim` image.
- Seed 5a uses chia 12 g instead of 1 tbsp, because USDA has no spoon measure for chia.
- Pepperoni maps to the only USDA pepperoni (Foundation 2759006, "beef and pork"), which has no energy/protein/fat yet. It's held regardless.
- Collagen peptides aren't in the ingredient table, since USDA has no entry for them.
- The `price_observation` index is ascending; Postgres scans it backwards for "latest".
- The pork frequency cap is implemented and tested at the domain and service level (counting, violations, cap 0 → exclusion while trace pork stays allowed). The solver-level "a plan never exceeds the cap" tests are Phase 1, since there's no solver yet.

---

### Phase 1: Planning brain (backend only)

**Goal.** Turn your weekly configuration into a validated weekly plan. Build the constraint object, take candidates from the seed library and saved recipes first (generating only for uncovered slots, through the swappable LLM adapter), let PuLP choose batches on your cook days, round to practical quantities, then validate that rounded plan independently. Retries and failures are bounded and clear.

**PRD sections.** §2, §3, §4, §5, §6, §7, §8, §10 (accepted pairs applied), §11, §12 (basic), §13 (balanced default), §25 (data), §28 (both modes), §29, §30, §31, §32, §33.

**Deliverables**
1. **Settings API:** `GET/PUT /api/v1/settings` over the Phase 0 `UserSettings` model (§4 config, slot allocations, equipment, cook schedule per weekday, `leftover_fridge_days`, calorie mode + band, stores order, split threshold, excluded diet tags, frequency caps, diet-review decisions written to `ingredient_preference`).
2. **Inventory, products, prices (API):** inventory CRUD writing `inventory_event`; products CRUD; manual price entry with a required store.
3. **Constraint builder:** settings + week + per-day choices + portion requests → `PlanConstraints`; resolves exclusions and frequency caps (§7.4); marks Tue/Fri `is_cook_day=false`.
4. **LLM adapter** (`app/llm/`):
   - `LLMClient` protocol; `GroqLLMClient` is the sole Groq import, reads `LLM_MODEL` from env, never streams, never uses tools.
   - **`LLM_STRUCTURED_MODE = strict | best_effort`** (§6.3).
   - Pacing from `x-ratelimit-*`; 429 handling; every call logged to `llm_call` with its mode.
   - `FakeLLMClient`; daily token guard.
5. **Structured retry loop:** one path for both modes; parse → Pydantic → domain hook → retry with concise errors → batch halved on truncation → `LLMOutputError` after the cap.
6. **Prompts** (`candidate_generation`, `recipe_revision`), each with `PROMPT_VERSION`. They include the slot/mood/kcal-per-portion target, the ingredient vocabulary minus excluded, held and never-favored capped items (pork components), the **never-use list** (beef and everything derived from it, unspecified gelatin and other held items), inventory and open packages to use up, the "use flour tortillas where a recipe calls for chapati/roti" rule, and raw/dry quantity rules.
7. **Ingredient resolver:** exact alias → normalized alias → trigram with margin → unresolved (suggestions in the retry message; logged for the "suggested new ingredients" queue derived from `llm_call.error_detail`, approved via `POST /api/v1/ingredients/suggested/{name}/approve`).
8. **Accepted substitutions applied:** a resolved `chapati` becomes `flour tortilla (Price Rite, 37 g)` via `ingredient_substitution` (count for count), recorded as `adjustment=substituted`.
9. **Recipe validator:** exclusions (ingredient level + step text naming an excluded food); raw/dry/as-sold state of every line vs its mapping (§7.8); units valid for the ingredient; plausible per-serving amounts; equipment ⊆ available; time and complexity vs mood; **prose filter §7.3**.
10. **Candidate pool:** seed drafts + saved versions first (0 calls) → gap analysis → batch generation only for uncovered (slot, mood) → targeted revision → dedupe → persist.
11. **Rendering:** sections, injected safety lines, code storage/reheating text, "≈ X g per container", nutrient labels, a "draft" badge for seed versions.
12. **Solver (PuLP + CBC):**
    - *Items:* (recipe version, slot, portion variant), where variants are the chosen size ×{0.9, 1.0, 1.1} (`portion_nudge_pct`).
    - *Variables:* integer portions per item per **cook day**, plus binary batch flags; assignments of portions to days within `cook_on … cook_on + leftover_fridge_days`, or to the freezer for freezer-friendly recipes (thaw-night-before note); integer packages per **(product, store)** option, or a loose amount; budget overrun; slot-kcal deviations.
    - *Constraints:*
      - every planned slot filled exactly once
      - eaten + frozen = cooked
      - no batches on non-cook days (Tue/Fri)
      - cook minutes per cook day
      - mood eligibility
      - ingredient supply (inventory incl. open packages + purchases ≥ need)
      - **calories:** strict = each day in [T(1 − 5%), T] (hard ceiling); weekly = week in [W(1 − 3%), W] (hard ceiling) and each day in [T − 150, T + 150]
      - budget (hard, or soft with overrun)
      - max 5 portions per recipe; no recipe twice in a day
      - portion requests; exclusions
      - **frequency caps:** for each cap, meals eaten this week from batches containing a member ≤ `max_meals_per_week` (pork components ≤ 1)
      - **store split (R4):** buying anything at the secondary store requires the week's savings vs all-primary ≥ `store_split_min_savings_cents` (default 500)
    - *Objective* (weights in `objective.py`): + primary nutrient, + secondary, + preference/heuristic score, − purchase cost, − perishable leftovers, + expiring inventory used, **+ open-package inventory used**, − slot-kcal deviation, − batches, − overrun. Terms are normalized. **Never-favored capped items** (pork components) get zero nutrient, price and inventory-use terms: their nutrient bonus is 0, their cost is counted at no less than the slot's median candidate cost, and inventory they'd use earns no bonus.
    - CBC time limit, fixed ordering, single thread.
13. **Diagnostics:** an elastic re-solve turns infeasibility into human-readable gaps.
14. **Post-solve → `RoundedPlan`:**
    - (a) Practical rounding.
    - (b) **Package absorption pass** (`solver/absorption.py`, PuLP), which applies your Q11 rule. With assignments fixed, each leftover remainder gets a binary choice. *Absorb (R5):* the **whole batch scales proportionally** by the factor that uses the full package (e.g. 2 lb / 1.7 lb = ×1.176), then every line is re-rounded, so flavor ratios stay intact; portion count is unchanged, so each portion is larger. *Keep:* the remainder is recorded as `expected_remainder_quantity` and becomes an open package in inventory when the batch is marked cooked (Phase 2). The pass maximizes absorbed perishable grams, subject to the calorie limits evaluated on the rounded, scaled plan and a maximum absorption scale (default ×1.25). New remainders created by the scaling (other ingredients) are recomputed in (c).
    - (c) Recompute packages, store assignment, costs and kcal.
15. **Plan validator:** input type is `RoundedPlan` only. It recomputes every number from the DB and runs the PRD §33 checks: daily/weekly kcal per mode, quantities, ingredients exist or are on the list, portions, equipment, time, cook days, fridge window, budget (hard = error, soft = warning), exclusions, frequency caps, safety, prose filter. A hard error triggers a re-solve with that bound tightened (≤ 2).
16. **Grocery list:** need − inventory (open packages first) → packages per chosen (product, store); each item carries `store_id`; grouping by store; a Price Rite section appears only when the split rule (R4) is met, with the computed savings; `assume_in_stock` → "check you have"; unknown prices flagged; expected remainders shown.
17. **Orchestrator** + `generation_run` lifecycle + background execution.
18. **API:**
    - `POST /api/v1/plans` (202), `GET /api/v1/generation-runs/{id}`
    - `GET /api/v1/plans/{id}` (§25 summary data), `POST /api/v1/plans/{id}/accept`
    - `GET /api/v1/plans/{id}/grocery-list?group_by=store`
    - `GET /api/v1/recipes/{id}`, `GET /api/v1/recipe-versions/{id}?portions=&portion_size=`
19. **CLI:** `cli plan --week 2026-10-12` for the live demo.

**Files and folders.** Creates `app/llm/` (+tests), `app/planning/` (+tests, `solver/`), `app/domain/text_rules.py`, `app/schemas/{settings,constraints,llm_recipe,plans,recipes,inventory,pricing}.py`, services (settings, inventory, pricing, recipe), API routes (settings, inventory, products, prices, plans, generation_runs, recipes, ingredient suggestions), `app/testing/fixtures/llm_responses/`. Changes `.env.example` (`GROQ_API_KEY`, `LLM_PROVIDER`, `LLM_MODEL`, `LLM_STRUCTURED_MODE`, `LLM_MAX_ATTEMPTS`, `LLM_TIMEOUT_SECONDS`, `LLM_REASONING_EFFORT`, `LLM_DAILY_TOKEN_BUDGET`, `LLM_MAX_CALLS_PER_RUN`, `SOLVER_TIME_LIMIT_SECONDS`) and `cli.py`.

**Database.** No migration; uses the `0001` tables. (If the spike shows a needed column, I'll stop and flag it before adding it.)

**Acceptance criteria**
1. **Cold start:** the FakeLLM fails the test if it is called; protein-powder carbs/fat come from fixtures until you fill them (A2). A 7-day week with breakfast, lunch, dinner and protein-dessert slots is planned from the seed library alone, with **0 LLM calls**. A slot with no seed coverage (e.g. drink) triggers generation for that slot only.
2. The schedule is respected: no batch on Tue or Fri; every Tue/Fri meal comes from a batch cooked within the previous 3 days, or from the freezer per the freeze rule.
3. With FakeLLM fixtures, a full week (3 meals + dessert, protein priority) yields an active plan with zero validation errors. The validator's recomputation from the **rounded** plan equals the stored `totals` and `planned_kcal`.
4. **The validator runs on the rounded plan:** a plan the solver accepted but that rounding pushes over the calorie ceiling or a hard budget is caught by the validator and then re-solved or failed clearly (tests below).
5. **Prose filter:** every must-pass and must-block string in the test table behaves correctly, including **"Air fry at 400F for 18 minutes, flip at 9."** (passes).
6. **Both structured modes:** the full LLM test suite passes with `LLM_STRUCTURED_MODE=strict` and with `best_effort`.
7. Malformed/invalid LLM output is retried with the error and succeeds when a later attempt is valid. After the cap the run fails with a clear problem+json error and nothing partial is persisted.
8. An infeasible week returns `infeasible` with diagnostics in human units, after at most 2 targeted rounds.
9. Beef never appears: excluded at the ingredient level, absent from prompts' vocabulary, named in the never-use list, and caught in step text. Held (possible-beef) items never appear without an `allow` decision.
10. **Pork frequency cap:** no plan ever has more pork-component meals than the cap (default 1/week); with the cap at 0 there are none, while trace pork ingredients (tortillas, pork gelatin) are still used; a pork-component recipe is never chosen over an otherwise-equal recipe because of better nutrition, price or inventory use.
11. Grocery list items carry a store and group by store. Stop & Shop is used unless buying some items at Price Rite saves ≥ the split threshold (default $5) for the week.
12. Architecture tests pass. A 30-candidate, 7-day, 4-slot instance solves in < 15 s (`slow`). Identical input gives an identical plan.
13. A **live smoke run** (`cli plan` with your key) produces a valid plan. Its output, LLM call count and tokens are shown to you.

**Test plan**
- `domain/tests/test_text_rules.py` (prose filter):
  - **must pass:** "Air fry at 400F for 18 minutes, flip at 9." · "Preheat the oven to 425°F; roast 25–30 minutes, turning once." · "Rinse 1 cup rice; add 1½ cups water; simmer covered 15 minutes, rest 10." · "Marinate 2–12 hours in the fridge." · "Refrigerate overnight to marinate." · "Chill the pudding 30 minutes before serving." · "Freeze 20 minutes to firm up before slicing." · "Bake at 375°F until the chicken is cooked through." · "Divide into 4 containers, about 350 g each." · "Toss with oil to prevent sticking." · "Whisk the protein powder into the milk." · "Warm each tortilla on a dry pan 30 seconds per side." · "Pressure cook on high 8 minutes, natural release 10."
  - **must block** (with the offending phrase in the message): "Cook until the internal temperature reaches 165°F." · "A thermometer should read 165 F in the thickest part." · "Keeps 5 days in the fridge." · "Freezes well for up to 3 months." · "About 450 calories per bowl." · "A light, low-calorie lunch." · "40 g protein per serving." · "High-protein and low-carb." · "Costs about $2.50 per serving." · "A cheap weeknight dinner." · "Helps prevent anemia." · "Boosts your immunity."
  - **mixed:** "Bake at 375°F until the internal temperature reaches 165°F" → blocked, and the message says to keep the oven temperature and drop the internal-temperature clause.
- `planning/tests/test_plan_validator.py` (rounded-plan validation):
  - **rounding over calories:** solver raw Thursday = 1,795 kcal under a strict 1,800 ceiling. Thursday's single-portion breakfast, scaled from a base-4 recipe, needs 0.75 egg, and practical rounding makes it 1 egg (+18 kcal) → 1,813 kcal. The validator on the `RoundedPlan` reports `KCAL_DAY_OVER_CEILING` (+13) even though the raw output passed.
  - **rounding over budget:** hard budget $40.00, raw plan $39.20. A chicken need of 905 g rounds to 910 g, which crosses the 907.18 g (2 lb) package, so a second package is needed (+398 ¢) → `BUDGET_OVER_HARD` (+318 ¢). The same case with a soft budget → warning with the amount.
  - **only rounded input accepted:** passing raw solver output is a type error, and an orchestrator spy confirms the validator received 1 egg, not 0.75.
  - **standard checks:** a clean plan passes; a tampered quantity is detected; missing slot; batch on Tue → error; portion eaten beyond the fridge window → error; equipment violation; inventory overuse; excluded ingredient → error; two pork-component meals under a cap of 1 → `FREQUENCY_CAP_EXCEEDED` naming both meals; unknown price → "cost incomplete" warning.
- `planning/tests/test_orchestrator.py`: the rounding-over-calories case → re-solve with tightened bound → final plan valid; two failed re-solves → clear error; happy path; infeasible → targeted round → success; infeasible after 2 rounds → `infeasible`; LLM failure → `failed`; identical rerun → 0 calls; **cold start from seeds → 0 calls**.
- `llm/tests/test_structured.py` (run under both modes): valid first try → 1 call; prose-wrapped JSON → parse_error → retry with error → success, chained `llm_call` rows; truncated JSON → batch halved; wrong types/missing field → retry; extra `"calories"` field → rejected; `total < active` → retry; 3 failures → `LLMOutputError`, nothing persisted; strict transport schema snapshot; request has `strict: true` vs `strict: false` per mode; best-effort output that violates the schema is caught by Pydantic and retried; unknown `LLM_STRUCTURED_MODE` → config error at startup; provider error "strict not supported" → config error suggesting `best_effort`.
- `llm/tests/test_client.py`: 429 + `retry-after` on a fake clock, not counted as a validation attempt; repeated 429 → `LLMRateLimited`; timeout handling; daily token guard; `LLM_MODEL` from env; no `stream`/`tools`.
- `llm/tests/test_architecture.py`: import and model-literal scans.
- `planning/tests/test_resolver.py`: canonical matches, ambiguity suggestions, unknown names logged for the suggestions queue; "beef broth" → excluded-ingredient domain error; "gelatin" → held-ingredient domain error; "bacon" → resolved (pork component, capped); "chapati" → resolved, then substituted to tortilla.
- `planning/tests/test_recipe_validator.py`: unknown ingredient; undefined named unit; implausible per-serving amount; missing equipment; simple mood at 75 min; excluded ingredient; step text "add a splash of beef broth" → exclusion error; step text "add 2 strips of bacon" with no bacon line → unlisted-ingredient error (not an exclusion); "season with garam masala" passes; held ingredient (unspecified gelatin) → error naming the item and how to allow it; poultry without doneness step → safety step appended.
- `services/tests/test_settings_service.py`: PUT settings round trip; an `allow` decision is written to `ingredient_preference` and the constraint builder stops excluding that held item; `dislike` → `disliked_ingredient_ids`; a beef item can't be allowed (422); frequency cap edits validated (target must exist).
- `services/tests/test_inventory_service.py` (table audit): adding a lot writes one `inventory_item` + one `purchase` `inventory_event`; adjust and discard each write one event; the lot quantity always equals the sum of its events; quantities never negative.
- `planning/tests/test_solver.py`:
  - **Schedule:** cook days Mon/Wed/Thu/Sat/Sun with 3-day window → no Tue/Fri batches; Tue lunch served from Mon or Sun batch; Fri from Thu or Wed; a Tue meal from a batch cooked 4+ days earlier is never chosen unless frozen and freezer-friendly.
  - **Calories:** strict keeps every day ≤ T; weekly allows a 1,940-kcal day (T + 140) but rejects 1,960 (T + 160); the week never exceeds W in either mode.
  - **Priorities:** protein vs carb priority flips the choice.
  - **Portions:** odd portions (5, 7, 3); portion variants ±10% help hit a tight day.
  - **Packages and stores:** 1.7 lb with 2 lb pack → 1 pack + absorption decision; 2.5 lb need with 1 lb/3 lb packs → 3 lb; Price Rite saves $5.40 for the week → those items bought at Price Rite; saves $4.90 → everything at Stop & Shop; threshold setting changed to $3 → $4.90 savings now splits; inventory covers rice → none bought; expiring spinach wins a tie; **open package of chicken in inventory → recipe using it chosen over an equal one**.
  - **Frequency caps:** three pork-sausage recipes in the pool, each scoring best on protein and cost → the week has ≤ 1 pork-component meal (property test over random pools and caps 0–3: count never exceeds the cap); a 4-portion sausage batch can feed at most 1 meal this week (rest frozen, or not chosen); cap 0 → no pork-component meals, while recipes with tortillas (lard) and pork gelatin are still chosen; a pork recipe identical to a chicken recipe except higher protein, lower cost and using an open package of bacon in inventory → the chicken recipe is chosen (never favored); an ingredient-target cap (salmon ≤ 2) is honored.
  - **Budget:** soft overrun reported; hard → infeasible with shortfall.
  - **No feasible plan:** no drink candidates → names drink; ceiling below minimum → kcal diagnostic; all candidates need an air fryer → `EmptyCandidatePool`; all cook days at 0 minutes → time diagnostic; every candidate contains a held ingredient → diagnostic lists the held items to review.
  - **General:** determinism; exclusions never appear; performance (`slow`).
- `planning/tests/test_absorption.py`: remainder 0.3 lb chicken on a 1.7 lb need, absorbing keeps every day within its limit → absorbed: the **whole batch** scales ×1.176 (chicken 771 → 907 g, rice, spices and sauce scaled and re-rounded, ratios within rounding of the original), portions unchanged, `adjustment=absorbed_full_package`; absorbing would push a day over → kept, `expected_remainder_quantity` = 136.078 g; two remainders where only one fits → the more perishable is absorbed; a scale above ×1.25 is never applied; the validator checks the scaled, re-rounded batch.
- `planning/tests/test_grocery_list.py`: aggregation; open packages used first; cross-unit netting; store assignment and grouping; `assume_in_stock`; unknown price; int totals = sum of lines; expected remainder shown.
- `planning/tests/test_candidates.py`: seeds + saved sufficient → 0 calls; gap → one call for the missing slot only; partial batch → one revision call for the invalid recipe; dedupe; provenance.
- `api/tests/test_plans_api.py`: 202 + polling; payload schema; `group_by=store`; problem+json errors.
- `live_llm`: one real batch in the configured mode passes all validators.

**Depends on.** Phase 0.

**Risks and mitigations**
- *8K TPM.* The seed library, reuse, gap-only generation, small batches and low reasoning effort keep calls rare; a spike measures real tokens.
- *Missing label values block cold start for the powder recipes.* Diagnostics name them; you fill the protein-powder carbs/fat (A2) before Phase 1.
- *Prose-filter false positives.* Tested on a must-pass table of real instructions; the categories stay narrow.
- *Infeasibility from tight bands.* Portion variants, elastic diagnostics, targeted generation.
- *Cross-week leftovers* (Saturday's cooking feeding next Monday) aren't modeled until prepared portions exist (Phase 3). Each Phase 1 plan is self-contained.
- *Scope.* If the phase runs long, I'll stop and propose splitting it into 1a (adapter + candidates) and 1b (solver + validator).

**Outcome (2026-10-09).** All 13 acceptance criteria are met; test output, the fresh-clone check and a seed-only `plan-week` run are in the phase summary. Your decisions this phase are C1–C3 (§12.1); you approved C1–C3 and D1–D13 on 2026-10-09. What changed from the plan, and why:

- **D1. Portion variants.** One continuous multiplier per batch in [0.9, 1.1], linearized exactly (McCormick on binary × continuous), instead of three discrete copies of every batch. The copies tripled near-identical batches and kept weeks from solving in 30 s. `plan_cook_batch.portion_multiplier` stores size × multiplier × absorption scale.
- **D2. Slot deviation.** The slot-kcal deviation is penalized only beyond ±15% of the slot target. Whole portions can't hit a slot target exactly, so the old term left a gap the LP bound could never close. Day and week limits stay hard.
- **D3. Packages in the solver.** Whole-package integers only for perishable packs of $5 or more (chicken trays, 32 oz yogurt); everything else is costed per unit inside the MILP. Exact packages, stores and costs for every item are computed on the rounded plan as before. All-integer packages took ~56 s on the seed week; this takes ~6–8 s.
- **D4. Store split.** In the MILP, using the secondary store costs a fixed charge equal to the threshold ($5), so it is used only when it saves at least that much. The grocery list applies R4 exactly on the rounded plan (savings vs all-primary ≥ threshold, ties stay at the primary store).
- **D5. Rounding feedback.** Practical rounding moves kcal in steps (whole scoops, a minimum ½ onion), which pushed a seed week 274 kcal over. The first solve now starts from each recipe's typical rounding bias (rounded at 2–5 portions), keeps 5 kcal/day and 20 kcal/week of room inside the limits, and post-solve picks the multiplier whose rounded kcal is closest to the plan. Re-solves (still ≤ 2) add the observed per-recipe bias as well as tightening the failing bound.
- **D6. Solver stopping.** HiGHS stops at a 0.5% relative or 1.0-point absolute gap (≈ $2 of groceries); the time limit is 12 s (AC 12: < 15 s). The seed week proves optimal in ~6–8 s. A week that reaches the limit returns its best plan, marked `feasible`; the 30-candidate test instance does (≈ 12.3 s).
- **D7. Calorie target.** A small reward per planned kcal (0.002) makes plans aim at your target instead of settling at the 97% floor; the ceilings still cap it.
- **D8. Constraint object.** `held_ingredient_ids` added; cook minutes mean hands-on minutes (C1); the variety cap covers meals only (C2). See the Phase 1 notes under §6.2.
- **D9. LLM retries and tokens.** A retry re-sends the failed reply only when it is short (≤ 2,000 characters), and `LLM_MAX_COMPLETION_TOKENS` defaults to 3000, after Groq refused a growing third attempt (§7.6).
- **D10. CLI.** `cli plan` is `plan-week` (your request) with `--no-llm`, `--dry-run`, `--slot`, `--minutes`, `--budget/--hard-budget`, `--priority`, `--accept`.
- **D11. Partial persistence.** If an LLM call fails after its retries, nothing from that call and no plan is saved, but validated recipes from earlier calls in the same run stay saved for reuse (CLAUDE.md rule 7).
- **D12. Compose.** The backend container gets `GROQ_API_KEY`, `LLM_MODEL` and `LLM_STRUCTURED_MODE` from the repo's `.env`.
- **D13. PuLP pinned below 4.** PuLP 4 moved CBC into a separate package; the 3.x line keeps a working CBC fallback.

Also as requested:
- **Unpriced ingredients.** With a hard budget, a recipe with an unpriced, non-staple ingredient that inventory doesn't cover is left out and the plan says why ("protein powder … has no price at your stores, so your hard budget can't be checked"). With a soft or no budget it stays, and the cost shows as incomplete with the item named. Tests cover both.
- **Pork cap at the solver level.** Tested directly (three best-scoring sausage recipes → at most one pork meal; a property test over random pools and caps 0–3; cap 0 keeps trace pork; a better, cheaper pork recipe with an open package of bacon still loses to an otherwise-equal chicken recipe) and on the planned seed week.
- **Live smoke test** (`RUN_LIVE_LLM_TESTS=1`): one batch through the full validation path; a normal `pytest` run skips it.

Open: the protein powder price (costs stay incomplete until you enter it); `LLM_MODEL` isn't in your `.env` yet (the live runs passed `openai/gpt-oss-120b` on the command line); A3 (cloud provider comparison) is due before Phase 2; R8 is still open. The USDA mapping review sheet was regenerated because 3b changes the calorie shares slightly.

**Fix-up round (2026-10-09).** You approved D1–D13 and C1–C3, and asked for five changes (C4–C8 in §12.1). The $89.58 sample had no budget at all (`weekly_budget_cents` null, `budget_is_hard` false, so budget mode "none"): the solver minimized cost at 0.5 points a dollar alongside the protein reward.

- **C4. Budget per request; two modes.** `plan-week --mode inventory|shop --budget X --topup X` and the same fields on `POST /api/v1/plans` (`mode`, `budget_cents`, `topup_cents`). Inventory mode buys nothing unless you allow a top-up, and then lists a short buy list; when nothing fits, the relaxed solve names exactly what's missing and the smallest top-up that works ("chicken thigh, boneless skinless about 2,720 g ($20.94); …"). Shop mode uses inventory first, then builds the list; a budget is a hard limit on cash this trip, and without one the cost is still minimized and reported. A budget that is too low says what the cheapest plan would cost and buy.
- **C5. Cost reporting.** Every plan shows cash this trip (whole packages, the grocery total), food eaten this week (including what comes from inventory, at current prices), leftovers carried into inventory (raw protein to freeze / keeps / at risk) and frozen extra portions. cash + from inventory = eaten + frozen portions + leftover, to the cent.
- **C6. Perishable leftovers.** Raw meat, poultry and fish not cooked within its fridge life of shopping day gets "freeze on shopping day" (with "thaw it in the fridge the night before" for a later cook day), from the FoodSafety.gov chart rows in `app/domain/fridge_life.py`. Open fridge lots of raw protein get the same check against their own dates. The validator recomputes these and fails a plan that lacks one (`SAFETY_MISSING`). The solver penalizes perishable food left over, and more steeply once less than a quarter of a package is used. Expected waste = at-risk leftovers (perishable, in the fridge, no chart life that outlasts next week) plus inventory expiring unused; each at-risk item is a warning.
- **C7. Protein target.** 100 g a day (settings, `--protein`), a floor in the MILP and in the validator; protein earns no reward at all, so above the floor the plan is chosen on cost, waste and fit.
- **C8. Elapsed time.** Each cook day shows hands-on minutes and about how long start to finish, plus any fridge time for no-cook recipes.

What changed from the plan, and why:

- **D14. First-package cash.** An ingredient sold only in packages costs at least its cheapest whole package once any batch that needs it is cooked: one continuous "used" variable per ingredient, tied to the batch decisions and to each meal slot, with no new integer variables. A yes/no per offer for the first package made the seed week take 10–50 s; this solves it in ~4–7 s. Further packages are still costed per unit, so the validator's exact grocery total can be a little higher; a re-solve tightens the limit when that crosses it.
- **D15. No soft budget.** A budget is always a hard limit now (your C4 wording); "no budget" replaces the soft budget, so the unpriced rule reads: any purchase limit excludes recipes with unpriced items not in inventory; no limit keeps them with the cost marked incomplete.
- **D16. Shopping day and fridge life.** The plan assumes you shop on its first day. Fridge life is the short end of the chart's range ("1 to 2 days" → 1, like the 3-day leftover default). Inventory covers the earliest uses (it is allocated first, open packages first).
- **D17. Protein in weekly mode, and "balanced".** Weekly mode checks the week total only (no per-day protein floor), matching how the week's calories work. With protein no longer a reward, the "balanced" priority scores fiber only.
- **D18. Re-solve tightening.** Protein shortfalls after rounding tighten the protein floor (per day or week) and add the observed protein rounding bias; going over the purchase limit also holds back a little inventory where rounding spilled past it, so inventory mode doesn't end up buying a whole pack for 5 g.
- **D19. Elapsed time estimate.** Hands-on work back to back plus the longest cooking wait (simmering, baking) of the day: an upper estimate. A no-cook recipe's wait (overnight oats) is fridge time and is shown separately.
- **D20. Settings v2.** `UserSettings.schema_version` 2, migration 0002 (data only: drops the two budget keys, adds `daily_protein_target_g: 100`, and reverses cleanly).
- **D21. Rounding, solved jointly.** With protein no longer rewarded, the solver leans on the 0.9 portion multiplier to save money, and whole scoops and tortillas don't shrink with it: the seed week rounded 233 kcal over and every plan needed a re-solve. Two changes, both inside D5's approach: (1) each recipe's rounding is fitted as a straight line over the lowest, middle and highest multiplier (rounded ≈ planned × scale + bias), not a constant; (2) after the solve, a small MILP picks every batch's multiplier on the 0.005 grid from the actual rounded values, so the rounded plan meets the day, week and protein limits as the validator counts them, staying closest to the solver's plan (`app/planning/snap.py`; the old per-batch snap is the fallback). The seed week validates on the first solve again (~7 s per plan, the test suite back to ~3 minutes).
- **D22. Money-first diagnostics.** With a budget or top-up, the infeasibility explanation first relaxes only that limit; if everything else fits, it reports what the cheapest plan costs and buys, instead of trading a few dollars against a few minutes of cook time.

Open: the protein powder price (any budget or top-up leaves out every powder recipe until it has a price or is in your inventory; that includes both protein desserts, so `--budget` weeks are infeasible today, by your Phase 1 rule); lemon and lime juice are marked perishable in the seed data, so their leftovers count as at risk; A3 is due before Phase 2; R8 is still open.

**Post-approval round (2026-10-09).** You approved Phase 1 with D14–D22 and asked for six more things (C9–C14 in §12.1).

- **C9. Protein powder prices.** Two products at a new store "Other" (online or in-store, varies), both estimates:
  - 5 lb tub (2,268 g): $62.50, your estimate ($60–65).
  - 682 g tub: $26.31, derived from the 5 lb price per gram plus a typical 40% small-tub premium.
  - The solver and the grocery list buy the pack that is cheaper per gram. Food eaten counts the powder by the gram, about $0.85 a 31 g scoop.
- **C10. Stock-up items.** `ingredient.stock_up` (migration 0003) marks long-life items bought occasionally: powder, rice, oats, flours, oils, seeds, nut butters, sweeteners, cocoa, vanilla, bottled condiments, lemon and lime juice, bouillon.
  - A shop-mode budget covers regular groceries only.
  - Stock-up purchases are listed as "Also buy this week", and cash this trip shows regular + stock-up = total.
  - In the solver they cost what the week uses, at the per-unit price of the cheapest pack.
  - Spices, salt and baking powder/soda are flagged too, but stay "check you have" staples (never bought).
- **C11. Shelf life.** Bottled lemon and lime juice are no longer perishable (they keep for months refrigerated); fresh lemons are. The same mistake was fixed for frozen spinach, peas, corn and edamame.
- **C12. Regular chicken packs.** Thigh and breast at both grocery stores, 1.25 lb (packs run 1–1.5 lb), at the family-pack price per lb + 20%, as estimates. The solver chooses between pack sizes.
- **C13. Steady-state check.** `cli simulate-weeks` is a dry run: each week plans from the leftovers of the one before (raw protein frozen, stock-up remainders kept, at-risk perishables dropped as waste). `--last-week-budget` re-plans the last week with a budget.
- **C14. Hosting (A3).** `docs/hosting.md` compares Railway, Fly.io + Neon, home PC + Tailscale, a VPS + Caddy, Render and Cloud Run. It recommends Railway Hobby, about $5/mo.

What changed from the plan, and why:

- **D23. Store kinds.** Stores now have a kind: `grocery` (yours, ordered in settings) or `other` (where items your stores don't carry come from). Other stores are always a source after your store order, never a trip:
  - The store-split charge applies only to items your primary store also prices.
  - The grocery list's "split" means a real store choice, not an item priced only elsewhere.
  - Per-store recipe costs list your grocery stores and price powder from "Other".
- **D24. Stock-up and limits.** A shop budget excludes stock-up items. An inventory-mode top-up still covers everything bought ("purchases off by default"), at the pack the list would buy.
- **D25. Unpriced rule.** A limit excludes a recipe for an unpriced item only if that limit covers the item: regular items for a shop budget, anything for an inventory top-up.
- **D26. Cheapest-plan fallback.** When a budget leaves the solver no time to find any plan, the cheapest plan that meets every limit is used, and the plan says so.
- **D27. Infeasibility explanations** now also say which recipes were left out and why.
- **D28. Seed week vs a $50 budget.** From an empty inventory, the cheapest seed week is about $52.60 of regular groceries, so a fresh week doesn't fit $50. Week 2, which plans from week 1's leftovers, does. The requested test is therefore synthetic: a week whose regular groceries fit $50 still buys a $62.50 tub as stock-up, shown separately.

Also flagged, not changed:
- Long-keeping fresh items still marked perishable: onions, garlic, potatoes, sweet potatoes, butter, hard cheeses. They weren't bottled, jarred or shelf-stable, so they're left for your call.
- The alias "fresh lemon juice" maps to the bottled-juice ingredient.
- Solver timings this round ran on a busy machine (last round's own seed week took ~20 s instead of ~6 s), so the 12 s limit was often reached, and plans came back "feasible" rather than proven optimal.

---

### Phase 2: Mobile PWA + cloud deploy

**Goal.** Put the planning brain on your phone: an installable, mobile-first PWA for the weekly plan, recipes, inventory and store-grouped grocery list. It is deployed to a real cloud host with single-user login, works offline for anything already loaded, keeps inventory honest with "Mark cooked", and starts the candidate-exposure log, because real usage starts here and exposures can't be backfilled.

**PRD sections.** §4 (UI), §7, §8 (open packages), §11 (display), §15 (price at check-off), §25, §29, §34.

**Deliverables**
1. **Next.js + TypeScript PWA:** manifest, icons, hand-written service worker, iOS standalone metadata, safe areas, bottom nav. CSS Modules; plain fetch hooks; types generated with `openapi-typescript`.
2. **Screens:**
   - **Week:** the §25 summary + day list.
   - **Day:** swipe between meals; that day's cook sessions; Tue/Fri show "leftovers day".
   - **Recipe:** portions/size selector (server-recomputed), practical quantities, package and open-package notes, sectioned instructions, safety lines, storage/reheating, per-portion nutrition, iron split marked "estimated", cost per portion, "draft" badge on seeds.
   - **Inventory:** by location; expiring and open-package badges; fast add; NL quick add with confirm.
   - **Grocery list:** checklist **grouped by store** (toggle: by store / by category); actual price/weight entry; "Done shopping" → lots + per-store price observations.
   - **Settings:** §4 config, slot allocations, equipment, the editable **cook schedule**, fridge days, calorie mode + band, stores + split threshold, frequency caps (pork ≤ 1/week by default), diet-review decisions for held items.
   - **Generate:** progress, diagnostics.
   - **Login.**
3. **Mark cooked** (minimal): deducts the batch's practical quantities FIFO (open packages first) and sets the batch to `cooked`. The opened package's remainder becomes an inventory lot with `opened_on` and an expiry from the safety table. Phase 3 extends this with actual time, cost and ratings.
4. **Offline:** cached plan, recipes, inventory and grocery list, plus a "last synced" indicator. Queued check-offs and price entries are replayed with `client_ref`.
5. **Backend additions:** `POST /api/v1/inventory/parse` (LLM parse → preview, numeric-fidelity check, nothing saved before confirm); `POST /api/v1/inventory/bulk`; idempotent grocery item PATCH; `POST /api/v1/grocery-lists/{id}/complete`; `POST /api/v1/cook-batches/{id}/cooked`.
6. **Cloud deploy + auth:**
   - Backend, frontend and managed Postgres on the provider chosen before this phase (A3), over HTTPS.
   - **Single-user auth:** passphrase checked against a scrypt hash from env; HMAC-signed, httpOnly, Secure, SameSite=Strict session cookie; Origin check on mutations; login rate limiting; logout. Built with stdlib `hashlib`/`hmac`/`secrets`, so no new dependencies.
   - Provider backups + a documented `pg_dump` script.
7. **Candidate-exposure logging (moved here from Phase 3):** every plan run writes one `plan_candidate` row per candidate offered to the solver (seed, saved or newly generated), including candidates filtered out (with `filtered_reason`: excluded, held, frequency cap, equipment, time), the Phase 1 heuristic score and its components, a feature snapshot, and `selected` / `portions_selected`. Ratings stay in Phase 3.

**Files and folders.** Creates `frontend/` (§3), `backend/app/auth/`, `app/schemas/llm_inventory.py`, prompt `inventory_parse`, services (grocery, cooking, exposure log), API routes (`auth`, `inventory_parse`, `grocery`, `cook_batches`), `migrations/versions/0002_pwa_and_exposure_log.py`, `deploy/`, `scripts/backup.sh`. Changes the orchestrator (exposure write), `docker-compose.yml` and `.env.example` (`AUTH_PASSPHRASE_HASH`, `SESSION_SECRET`, frontend API URL, deploy settings).

**Database.** Migration `0002_pwa_and_exposure_log`: `plan_candidate` (§4.5); `price_observation.client_ref uuid NULL UNIQUE`.

**Acceptance criteria**
1. The app is deployed at an HTTPS URL. Unauthenticated API calls get 401, except `/health`. Login and logout work.
2. It installs on your iPhone from the deployed URL (standalone launch, icon, name). Lighthouse installability passes.
3. All screens work at 375 px with no horizontal scroll and tap targets ≥ 44 px.
4. After one online load, the plan, its recipes, the inventory and the grocery list open in airplane mode. Offline check-offs and price entries sync exactly once.
5. The grocery list groups by store. "Done shopping" writes price observations with the store and does not duplicate on double submit.
6. "Mark cooked" deducts inventory correctly and creates the open-package lot equal to the plan's expected remainder.
7. The frontend contains no nutrition, unit or cost arithmetic (only cents → dollars formatting).
8. NL quick add never saves without confirmation, and invalid LLM output is retried.
9. Every plan run writes `plan_candidate` rows for every offered candidate, with `selected` and `filtered_reason` correct.
10. `vitest` and `pytest` pass. You complete the manual iPhone checklist.

**Test plan**
- **Frontend (Vitest + testing-library):** offline queue (enqueue, ordered replay, `client_ref` kept, 4xx conflict surfaced, network error kept); cache strategy; `format/money`; `WeekSummary`; `GroceryChecklist` grouping by store and by category; `NLQuickAdd` confirm flow; `RecipeView` safety lines, "estimated" heme label, draft badge; login form error states; problem+json mapping.
- **Backend:**
  - `test_auth.py`: wrong passphrase → 401; rate limit after N failures; tampered or expired cookie → 401; cross-origin mutation rejected.
  - `test_inventory_parse.py`: "2 lb chicken thighs and half a cabbage" → 907.185 g + 0.5 count; invalid JSON → retry; unresolved item; hallucinated quantity → `needs_confirmation`; excluded item ("ground beef") → flagged as excluded, not saved; "a pack of bacon" → saved normally (pork is allowed in inventory; the cap applies to meals).
  - `test_grocery_complete.py`: per-store observations; idempotent; actual weight overrides nominal.
  - `test_mark_cooked.py`: FIFO; open package used first; remainder lot with `opened_on`, expiry from the chart, quantity = expected remainder; cooking twice → 409.
  - `test_exposure_log.py`: a plan writes one `plan_candidate` per offered candidate with `selected` correct; a candidate dropped by the pork cap or a held ingredient has the matching `filtered_reason`; a 0-LLM-call cold-start plan still logs its seed candidates; a failed run logs nothing partial.
- **Manual checklist:** install, offline open, check-off sync, recipe readability while cooking, login persistence.

**Depends on.** Phase 1; cloud provider chosen (A3).

**Risks and mitigations**
- *iOS PWA quirks.* Test on device early; small offline footprint.
- *Hosting cost and cold starts.* Provider comparison at the end of Phase 1 (A3).
- *Auth mistakes.* Stdlib primitives, tests for tampering and rate limits, no custom crypto beyond HMAC signing.
- *Data loss once real use begins.* Managed backups + `pg_dump` script, with a restore test.

**Outcome (2026-10-09).** Built as specified with deploy prep only (K7): nothing is deployed and no accounts
exist. Backend: 800 tests pass, 2 opt-in tests skipped (live LLM, wall-clock perf); ruff and mypy clean.
Frontend: typecheck clean, 78 Vitest tests, static export of 11 routes. Acceptance criteria:

- **Met:** AC 1 except the deployed URL (401 without a session except `/health`, login/logout, tests),
  AC 5 (store-grouped list; "Done shopping" writes per-store prices once, double submit safe), AC 6 (Mark
  cooked; the leftover equals the grocery list's bought-minus-needed), AC 7 (no nutrition, unit or cost
  arithmetic in the frontend: money is formatted and parsed by string operations), AC 8, AC 9, AC 10 (the
  automated part).
- **Built, not yet verified on the device:** AC 2 (manifest, icons, iOS tags, service worker; installing from
  the https URL and Lighthouse need the deploy), AC 3 (375 px layout, 44 px targets: written in CSS, not checked
  in a real browser), AC 4 (offline cache + replayed queue: unit-tested; airplane mode needs the https deploy).
  The manual iPhone checklist is yours.

Pre-work (K2–K6):

- **K2:** `POST /api/v1/plans` runs the plan inside the request and streams NDJSON (D29). Run records stay;
  a run left unfinished is marked "interrupted" by the next request (`PLAN_STALE_AFTER_SECONDS`).
- **K3:** the dev database is **65 MB** (USDA tables 52 MB). No trim: a subset-only database measured 11 MB,
  but the full cache is what lets you approve new ingredients, and it fits Neon Free (D39).
- **K4:** NullPool on Vercel, pooled `-pooler` URL for the app, direct URL for migrations, psycopg prepared
  statements off, `connect_timeout` 15 s and three retries with back-off for a waking compute; `postgres://`
  URLs accepted.
- **K5:** shelf lives for onions, garlic, potatoes and butter (D38); hard cheeses untouched (held, R8).
- **K6:** the audit found every seed-week solve hitting the 12 s wall-clock limit on this PC (about 20 tests),
  so their plans depended on machine speed; the timed 30-candidate test did by design. Fix in D34.

What changed from the plan, and why:

- **D29. Streamed, not plain JSON.** iOS Safari drops a request that receives nothing for about a minute, and
  generation with Groq's rate limits can take longer. The plan request streams `started`, `progress` (stage
  messages) and a `heartbeat` every 5 s, then one `result` (plan summary or problem). The work still ends before
  the response does. A worker thread runs the orchestrator with its own session.
- **D30. Time budget.** `PLAN_TIME_BUDGET_SECONDS` = 180: an LLM call starts only with 25 s left, its timeout
  is cut to what remains, a rate-limit wait that leaves no room for the call ends generation, and the solver's
  limit is cut to what remains (a solve needs 5 s). When generation runs out of time the recipes made so far
  are saved and the week is planned with them (with a note), so planning again carries on. One `solve()` can
  also run the cheapest-plan fallback and diagnostics, so the worst case passes 180 s; the 120 s left under
  Vercel's 300 s covers it.
- **D31. Schema additions.** `login_attempt` (rate limiting can't live in memory on serverless; it stores an
  HMAC of the address) in migration 0004; `PlanConstraints.capped_out_ingredient_ids` and
  `ExcludedRecipe.codes`, so the exposure log can tell a frequency cap from a diet exclusion.
- **D32. Migration number.** Phase 1 used 0002 and 0003, so this phase's migration is `0004_pwa_and_exposure_log`.
- **D33. Deploy layout.** `vercel.json` sits at the repo root (Vercel reads it there; no `deploy/` folder) and
  uses Vercel Services (beta, on Hobby) for one project and one domain; `docs/deploy.md` has a two-project
  fallback. Migrations run in the backend's build step (`python -m app.deploy`) on production deployments
  only, and only with `RUN_MIGRATIONS_ON_DEPLOY=1`; they're additive, so the old code keeps working meanwhile.
- **D34. Deterministic tests.** `conftest.py` gives every MILP a 300 s limit and fails a test whose solve still
  stops on the clock; identical models reuse the answer (HiGHS single-thread with gap stops is deterministic;
  `solve_cache_off` opts out). Seed-week tests assert properties and now solve to their gap. Three
  orchestration tests that re-solve plan 3-day weeks (83 s → 2 s; on the full week they also ran HiGHS out of
  memory). The perf test is opt-in (`RUN_PERF_TESTS=1`). The suite takes about 5 minutes.
- **D35. Grocery sections.** Stock-up, "from your inventory", "check you have" and unpriced items are their own
  groups; `group_by=category` added; items carry category, check-off state, actual weight and price, product id.
- **D36. Frontend.** Query-parameter routes (`/recipe/?batch=12`) instead of dynamic segments, so the static
  export has one page per screen for the offline shell; dependency versions as in §10; Vitest compiles JSX with
  oxc (Vite 8); `next dev` would write AGENTS.md/CLAUDE.md into `frontend/`, turned off (`agentRules: false`).
- **D37. Auth details.** `AUTH_PASSWORD_HASH` (scrypt, no `$` so compose reads it) and `SESSION_SECRET`;
  `hash-password` CLI; 180-day cookie renewed daily (HttpOnly, SameSite=Strict, Secure on https); the Origin
  check accepts the forwarded host (Next dev proxy, Vercel); 5 failures per client and 20 overall per 15
  minutes; public `/docs` off on Vercel.
- **D38. Shelf lives are estimates.** Seed ingredients gained a `shelf_life` field with its basis: onions
  28 days and garlic 56 days in the pantry, russet potatoes 28 days, butter 30 days in the fridge (180 frozen).
  Sources disagree (an onion is about 2 weeks on the Virginia Dept. of Health chart, about 6 weeks in a
  Canadian guide; butter 1–3 months refrigerated per the University of Kentucky Cooperative Extension). An item counts as waste only if
  it won't keep through the next plan (2 × plan days). Sweet potatoes are still flagged, unchanged.
- **D39. Database size.** 65 MB, below Neon Free's storage (its pricing page now says 1 GB per project; you
  quoted 0.5 GB). Full import recommended for the cloud; the subset is the fallback.
- **D40. Extra endpoints.** `GET /plans` (recent plans and the current one), `GET /cook-batches/{id}` (the
  recipe at the batch's practical quantities, with package and freeze notes), `GET /inventory/quick-picks`,
  and `diet_review` in the settings response for held items.
- **D41. Quick-add statuses.** ok, needs_confirmation (no amount, an amount the note doesn't contain, or no
  usual package size), unresolved (with suggestions), excluded (beef; also refused by `/inventory/bulk`).
  Held items can be saved with a note.
- **D42. Exposure rows only for succeeded runs.** Failed and infeasible runs write none.
- **D43. Not changed, flagged:** on this PC the seed week now needs about 20–28 s to reach its gap, so with
  `SOLVER_TIME_LIMIT_SECONDS=12` production plans usually come back "feasible" (best found) rather than proven
  optimal. With the 180 s budget you could raise it to 30.

Also: the C: drive filled up mid-phase (npm's cache there), which wedged Docker Desktop; npm's cache and temp
for `frontend/` now live in `frontend/.npm-cache` and `.tmp` (gitignored), and Docker Desktop was restarted
with your OK.

---

### Phase 2b: Cook-first flow (redesign)

**Goal.** Rebuild the app around how you cook:
- four tabs (Cook, Grocery, Pantry, Settings);
- a question-per-screen Cook flow for "a meal now" or "meal prep";
- ranked recipe cards that use what you have;
- meal-prep plans that start today, with a swap on every meal;
- "What should I buy?";
- favorites and save for later;
- a first-run onboarding wizard;
- a warm light/dark visual style with its own personality.

Every number still comes from code, and the LLM still only writes recipes.

**Spec.** `docs/FLOW_SPEC.md` (approved 2026-10-10): screens and states, the screen → backend map, endpoints, models, scoring, data model, LLM budget, the approved changes F1–F18 and the answered questions. PRD: "Primary user flow".

**PRD sections.** Primary user flow; §4, §5, §6, §7, §8, §10 (deterministic suggestions), §12 and §14 (basic), §17, §25, §26 (single-meal swap), §34.

**Pulled forward, and what stays** (FLOW_SPEC §17):
- **From Phase 3:** favorites (♥, persistence, ranking and solver boost), the `recipe_favorite` and `feedback_event` tables, and deterministic substitute suggestions. Save for later is new. Ratings, cook logs, prepared portions, recipe editing and versioning, the LLM substitution engine, the preference profile, the weighted preference score and Cook Again **stay in Phase 3**.
- **From Phase 4:** the pinned re-solve, for the single-meal swap. Consumption, day-level overrides, rebalancing and the mode toggle stay in Phase 4.
- **From Phase 5:** a basic "What should I buy?" with templated reasons from current prices. Price history, deals, seasonality, usual items and the cart optimizer stay in Phase 5.

**How the steps run.** Eight build steps, one per session, in order:
- Each step ends exactly like a phase: its acceptance criteria met, `pytest` (and from 2b.2 `vitest`) output shown, a commit, `scripts/fresh_clone_check.sh` after committing, a short summary, then a stop for your approval.
- Each step's session reads this section, the shared sections, and the FLOW_SPEC sections listed with the step.
- The phase-end rules in CLAUDE.md apply to every step (see §11 item 7).

#### 2b.1 Backend foundations

*Reads FLOW_SPEC §11, §13.1 (E7–E9, E11–E17), §13.3, §13.4.*

**Deliverables**
1. Migration `0005_cook_flow` (§4.5) with the settings v3 data migration (reversible, like 0002).
2. Favorites and saved: E7–E9 and their `feedback_event` rows. `favorite_recipe_ids` is filled from `recipe_favorite`, which turns on the solver's favorite bonus and the exposure log's `favorite` source.
3. Settings v3 in the settings API; `POST /settings/preview`; `GET` and `POST /stores`.
4. Always have: unlimited owned lots in the planning problem, grocery list and costs; water never listed; no "0 g" lines.
5. Display additions:
   - `cash_split_display` and `DayOut.cook_note`;
   - per-meal and per-day cost (largest-remainder split of each batch's cost);
   - `dish_category` (classifier) on versions, meals and batches;
   - `kind` on plans.
6. Quick-pick `amount_options` and `custom_units`; bulk add takes an option key or a custom amount.
7. Carried decisions:
   - `SOLVER_TIME_LIMIT_SECONDS` default 30 (`config.py`, `.env.example`);
   - sweet potatoes get a 28-day pantry life (seed data, cited like D38).

**Acceptance criteria**
1. The migration upgrades and downgrades cleanly; settings go v2 → v3 → v2 unchanged apart from the new defaults.
2. ♥ and 🔖 are idempotent, and each real change writes exactly one `feedback_event`. With otherwise-equal candidates, the favorite wins a solve.
3. An Always-have item is never bought and never listed under "check you have"; cash + from inventory = eaten + frozen + leftover still holds to the cent.
4. Meal costs add up to their batch, and day costs add up to food eaten, to the cent.
5. Amount options are right for mass, count and piece items; custom units are converted on the server.
6. Every seed recipe gets its expected dish category.

**Tests.** `test_cook_flow_migration.py`, `test_favorites.py`, `test_settings_v3.py`, `test_always_have.py`, `test_cost_split.py`, `test_quick_pick_amounts.py`, `domain/tests/test_dish_category.py`; grocery-list tests extended (water, 0 g).

#### 2b.2 Look, shell, onboarding, Settings, Pantry (frontend)

*Reads FLOW_SPEC §3–§6, §9–§11.*

**Deliverables**
1. Design tokens: light by default, dark, Match my phone (§4.2–§4.3). Pottle's SVG states; emoji and icon maps.
2. Building blocks (§5): question screen, stepper, slider, tile grid, segmented control (fixed selected state), chips, bottom sheet, recipe card, building steps, and the empty, error and offline patterns.
3. The four-tab shell, opening on Cook. Until 2b.4, Cook home shows the Today card and a link to the existing plan view. Old routes redirect.
4. Onboarding W0–W8: nine screens, related questions paired (E10), and **Skip, use my current settings** on W0. Settings S0–S2, whose editors reuse the question screens; the weekly band is hidden in strict mode.
5. The Pantry tab with the P1 amount picker. The Grocery tab with the existing checklist and the split header.

**Acceptance criteria**
1. Onboarding is nine screens. It pre-fills from saved settings, validates through the API, saves once, and doesn't run again. "Skip, use my current settings" leaves every setting unchanged and marks onboarding done.
2. Every new screen works at 375 px with no horizontal scroll and ≥ 48 px targets; text meets AA contrast in both themes.
3. The frontend still has no nutrition, unit or money arithmetic (the Phase 2 AC 7 check covers the new files).

**Tests (Vitest).** Stepper bounds and hold-repeat; the two-nutrition-goal limit; segmented `aria-pressed`; onboarding draft and final PUT; Skip sends only the onboarding flag; paired screens validate both controls; strict mode hides the band; the amount picker sends the option key; theme switch.

#### 2b.3 A meal now: engine (backend)

*Reads FLOW_SPEC §7 (C2–C5, C8), §13.1 (E1–E3, E17), §13.2, §13.3, §13.5–§13.7, §14, §15.*

**Deliverables**
1. `CookAnswers` and the goal mapping (`app/cook/answers.py`).
2. Ranking (`app/cook/ranking.py`):
   - filters, scaling and rounding, coverage;
   - deterministic substitutes (`app/cook/substitutes.py`);
   - score components, the never-favored rule, favorites;
   - the calendar-week pork-cap count.
3. `POST /cook/meal-now` (NDJSON):
   - saved results first, then the gap rule;
   - the `meal_now_generation` prompt with a narrowed vocabulary;
   - validated recipes merged into the list;
   - fallbacks for the daily guard and the rate limit.
4. `cook_search`: last answers, the cache key, Same as last time; `GET /cook/home`.
5. `POST /cook/meals`: a one-meal plan (`kind = single`, validator scope "single", could-buy grocery list). Mark cooked works on it.
6. The exposure log for meal-now searches, with `selected` set when you cook one.
7. Friendly rate-limit waits on every LLM path: meal now, meal prep, swap, grocery advice and quick-add parse (E13, FLOW_SPEC §5.5 and §13.2).
   - Before each call, the pacer checks the call's estimated tokens against the per-minute allowance left.
   - A predicted overflow or a 429 waits and streams `waiting` with `wait_s`.
   - A wait too long for the request ends it as `partial` with `retry_after_s`, never as a problem error.

**Acceptance criteria**
1. A card's numbers equal `GET /recipe-versions/{id}?portions=h` for the same version.
2. Beef, held items and a used-up pork cap never appear. A pork-component recipe never outranks an otherwise-equal recipe on goal, pantry or cost terms.
3. LLM call counts:
   - 3 or more good matches → 0 calls; fewer → exactly 1;
   - More ideas → 1;
   - an identical repeat → 0 calls and the same order;
   - an LLM failure → saved results plus a note, with status `partial`.
4. Generated recipes pass the recipe validator before they are streamed; nothing unvalidated is saved.
5. A one-meal plan validates, deducts inventory on Mark cooked, and never becomes the current plan.
6. The opt-in live test reports the narrowed prompt's tokens. If a 2-recipe call is over 8K, the batch drops to 1 recipe and the note says so.
7. Two More ideas requests inside one minute never return an error.
   - The second one either waits and finishes (a `waiting` event with a decreasing countdown), or ends `partial` with `retry_after_s` and the saved results intact.
   - The same holds for a 429 reply.
   - Only the daily guard gives the "back tomorrow" note.

**Tests.**
- `cook/tests/test_ranking.py`: golden ordering, components, never-favored, cap week boundaries, more than one person, the per-meal protein cap.
- `test_substitutes.py`.
- `test_meal_now_stream.py`: event order, merge, gap-rule call counts with FakeLLM, cache hit.
- `test_rate_limit_waits.py` (fake clock and fake rate-limit headers): predicted overflow → wait; 429 → wait; too long → `partial` + `retry_after_s`; never a problem response; the same on the meal-prep stream and on quick-add parse.
- `test_single_meal_plan.py`, `test_exposure_meal_now.py`.

#### 2b.4 A meal now: screens (frontend)

*Reads FLOW_SPEC §5, §7 (C0, C2–C5, C7, C8).*

**Deliverables**
1. Cook home (C0), complete: **A meal now** and **Meal prep** are the two dominant buttons at the top, with Same as last time, Today and Saved below them (E12).
2. C2 goals; C3 "What do you have?": toggles, have it / could buy, typed and quick add, chips from last time.
3. Building → C5 streamed results: New badges, More ideas, fallbacks, and the countdown wait state (strip and "Ready in 0:45" button; also in the Pantry quick-add sheet).
4. C7 Saved lists.
5. C8 recipe-page actions:
   - Cook this → a one-meal plan, with a Buy first checklist when needed;
   - cooking mode (screen kept awake);
   - Mark cooked.
6. ♥ and 🔖 optimistic and queued offline.

**Acceptance criteria**
1. The meal-now flow works end to end against the backend.
2. On a 375 × 667 screen, both choice buttons are fully visible without scrolling, with every Cook home section present, and nothing renders above them except the one-line greeting.
3. Every C0–C8 state (loading, empty, error, offline, rate-limit wait) is reachable in tests. A rate-limit wait never shows the error pattern.
4. The frontend still has no nutrition, unit or cost arithmetic (the countdown is only a timer).

**Tests (Vitest).** Stream reducer (results replace, new ids, partial); answers → request (only toggled-off items sent); cards render server strings only; Cook home order (the two buttons first); the countdown from `wait_s` and `retry_after_s` re-enables More ideas at zero; favorites queue replay; cooking-mode navigation.

#### 2b.5 Meal prep: engine (backend)

*Reads FLOW_SPEC §7 (C1, C1b, C3b, C6), §13.1 (E4, E6), §13.3, §13.6.*

**Deliverables**
1. Answers → `PlanRequest`:
   - presets, portions → days, start day, today-only cooking, extra to freeze;
   - have-it and could-buy lots, could-buy-only purchases;
   - shopping with the budget pre-fill;
   - goals (protein reward, low-calorie targets, Quick minutes) and mood.
2. Household size through the solver, post-solve, validator and grocery list.
3. `POST /cook/meal-prep` with the `pricing` stage and friendly messages.
4. Overlap-aware accept.
5. Calendar-week frequency caps across plans.

**Acceptance criteria**
1. "5 lunches from today, cooking today" gives one batch today, freezes the portions past the fridge window, and makes 0 LLM calls with the seed library.
2. A household of 2 doubles purchases and portions; calories and protein are checked per person, and the validator agrees.
3. The High protein tile raises the plan's protein against the same request without it, with the floor still met. Without the tile, protein earns nothing (C7 unchanged).
4. **The protein reward is capped (E11).** Protein above 1.5 × the daily target earns no extra reward:
   - With the tile on, a plan at about 1.5 × the target beats a costlier plan at 2 × the target (e.g. an all-chicken week) whose only advantage is the extra protein.
   - The objective's protein term never exceeds `w_protein × 1.5 × target` per day.
   - Below the cap, more protein still wins at equal cost.
5. Could-buy-only mode never buys outside the could-buy set.
6. A plan that crosses two calendar weeks keeps each week's pork cap, counting other active plans and one-meal plans.
7. Accepting an overlapping plan returns 409 without `replace_overlapping` and supersedes it with the flag.
8. Stages arrive in order: constraints, candidates, (generating), solving, pricing, validating.

**Tests.** `test_answers_to_request.py`, `test_household.py` (solver, validator, grocery), `test_protein_reward.py` (tile vs no tile; `test_reward_capped_at_1_5x_target`: the 1.5× plan beats the costlier 2× all-chicken plan, the term's per-day bound, below-cap monotonicity, weekly and strict modes), `test_could_buy_only.py`, `test_calendar_week_caps.py`, `test_accept_overlap.py`, a stage-order stream test. K6 holds: small instances, no wall-clock dependence.

#### 2b.6 Swap (backend)

*Reads FLOW_SPEC §7 (C6 swap), §13.1 (E5), §13.3 (pinned re-solve), §15.*

**Deliverables**
1. `planning/pins.py`.
2. `POST /plans/{id}/meals/{meal_id}/swap`:
   - takes the swapped-away list and tries the saved pool first;
   - uses the LLM (`allow_llm`) only after "Write a new one";
   - writes a new plan version that supersedes the old one, carrying grocery check-offs over;
   - after shopping, runs in inventory mode with Allow buying;
   - keeps cooked batches fixed and returns `also_changed` lines;
   - Undo re-accepts the previous plan.
3. A `meal_swapped` event; exposure rows under `swap`.

**Acceptance criteria**
1. Every other `plan_meal` keeps its recipe, day, slot and portion size. Only the batches that fed the swapped meal (or one new batch) change, and the new plan passes the full validator.
2. Repeated swaps never return a recipe already swapped away for that meal; when none is left, "no other fits" comes back with 0 LLM calls.
3. "Write a new one" makes at most 1 batch call (plus at most 1 revision). If that call has to wait for the per-minute limit, the swap stream shows the wait (`wait_s`), not an error.
4. Undo restores the previous plan exactly (identical summary).
5. After Done shopping, a swap buys nothing unless you allow it.

**Tests.** `test_pins.py` (a diff test like Phase 4 AC 1); `test_swap_api.py` (cycling, none fits, LLM gating, undo, check-off carry-over, after shopping); event and exposure rows.

#### 2b.7 Meal prep and swap: screens (frontend)

*Reads FLOW_SPEC §7 (C1, C1b, C3b, C4, C6, C8).*

**Deliverables**
1. The C1, C1b and C3b question screens.
2. Building steps from the real stages, including the countdown wait state (also in the swap's "Write a new one" sheet).
3. C6 results:
   - Today first, earlier days folded, day totals, cook notes, meal rows;
   - Swap with progress, toast and Undo, and the no-fit sheet;
   - the Recipes | Shopping list toggle;
   - Use this plan with the overlap sheet;
   - fix buttons on an infeasible plan.
4. The Cook home Today card links to C6; the old plan and day screens are retired.

**Acceptance criteria**
1. The meal-prep flow works end to end; swap and undo work from the UI.
2. Every C6 state is reachable in tests; 375 px.

**Tests (Vitest).** Day order with Today first; swap optimistic states and undo; the overlap confirm; diagnostics → fix buttons; toggle memory.

#### 2b.8 What should I buy?, and phase wrap-up

*Reads FLOW_SPEC §8, §13.1 (E10), §15.*

**Deliverables**
1. `POST /grocery/advice`: a shop-mode draft plan, LLM off by default.
2. Reason templates (`app/cook/grocery_advice.py`) with the comparison rule.
3. The G0–G3 screens, "I always have this", and open one-meal lists.
4. The phase-level checks and the manual iPhone checklist.

**Acceptance criteria**
1. Every reason line comes from a template over computed facts.
   - A "cheapest … per dollar" line appears only when the item is strictly lowest in its comparison set at your stores.
   - Estimated prices say "est.".
   - No "deal" or "seasonal" labels.
2. Use this list accepts the plan behind it, and the Grocery tab shows it as the current list.
3. A budget that's too low reports the cost of the cheapest plan that fits (D22).

**Tests.** `test_grocery_advice.py` (reasons; comparison edge cases including ties and estimates; budget); Vitest for G1–G3.

**Phase 2b acceptance (after 2b.8).**
1. Every step's criteria are met; full `pytest` and `vitest` pass; the fresh-clone check passes.
2. The frontend has no nutrition, unit or cost arithmetic.
3. Every new screen works at 375 px with ≥ 48 px targets, in both themes.
4. Every flow honors the beef exclusion, held items and the pork cap.
5. LLM call counts in tests match FLOW_SPEC §15, and no flow shows a rate limit as an error.
6. You complete the manual iPhone checklist: onboarding, meal now, meal prep, swap, cooking mode, grocery advice, dark mode, offline.

**Files and folders.**
- **Creates:**
  - backend: `app/cook/` (answers, ranking, substitutes, search, grocery_advice, tests), `app/planning/pins.py`, `app/domain/dish_category.py`, `app/llm/prompts/meal_now_generation.py`, `app/schemas/cook.py`;
  - API routes: cook, favorites, stores, grocery advice, swap;
  - `migrations/versions/0005_cook_flow.py`;
  - frontend: `welcome/`, `cook/`, `pantry/`, `grocery/advice/`, `settings/edit/`, and the §5 components.
- **Changes:**
  - `config.py` and `.env.example` (`SOLVER_TIME_LIMIT_SECONDS=30`);
  - `planning/`: constraints, solver, post-solve, validator scope, grocery list, accept;
  - `services/plan_stream.py` (stages);
  - seed `ingredients.json` (sweet potatoes).

**Database.** Migration `0005_cook_flow` (§4.5).

**Dependencies.** None new. Wake Lock is a browser API, icons are emoji and in-house inline SVG, and fonts are system fonts.

**Depends on.** Phase 2 (approved 2026-10-10). The FLOW_SPEC §18 questions are answered.

**Risks and mitigations**
- *Scope.* Eight steps, each shippable. If one runs long, I'll stop and propose a split rather than rush it.
- *Solver size with household and pins.* Pins shrink the model and household size is a constant multiplier; the K6 determinism rules stay.
- *Meal-now latency under 8K tokens a minute.* Saved results come first; one 2-recipe call; a batch of 1 if the measured prompt is too large.
- *The two engines drifting apart.* They share rounding, nutrition, cost and validator code, and a test compares card numbers with the recipe endpoint.
- *Replacing a plan while cooked food remains.* The replace sheet names it; prepared portions arrive in Phase 3 (FLOW_SPEC §18 Q3).

---

### Phase 3: Feedback loop

**Goal.** Make the app learn you: ratings, cook logs (actual time and cost), leftovers and waste, recipe editing with versioning (including adjusting the seed drafts), a substitution engine, a transparent preference profile that steers planning, and Cook Again that reuses your version without unnecessary LLM calls. (Favorites, save for later and their events arrived in Phase 2b.)

**PRD sections.** §9, §10, §17, §18, §19, §20, §22, §23, §24, §21 (weighted scoring precursor).

**Deliverables**
1. **Favorites (built in Phase 2b):** ♥ per lineage, save for later, events and the solver/ranking boost already exist. Phase 3 folds favorites into the weighted preference score (deliverable 7) and adds them to the profile.
2. **Ratings:** 👍/😐/👎 required, 1–5 stars optional, quick tags, comment. The LLM parses comments into validated tags. `rating` events use the PRD §20 shape.
3. **Cook log:** extends Phase 2's "Mark cooked" with actual minutes, actual cost and portions made → `cook_completed` event. Leftover and frozen portions become `prepared_portion` rows (`use_by` from the chart), which also enables cross-week carry-over. Waste and leftover events.
4. **Editing and versioning:** quantity, seasoning, protein/vegetable/carb/sauce (via substitution), cooking method (LLM step rewrite); portion size is a plan parameter, not a version. Saving creates an immutable new version (`change_set`, `change_summary`); the default pointer moves; revert; branching. **Editing a seed draft creates your confirmed version** (`is_draft=false`).
5. **Substitution engine** (Phase 2b already suggests substitutes for missing items deterministically: accepted pairs, then pantry items with the same role. Phase 3 adds the LLM candidates, the cache and applying a substitution):
   - Accepted pairs (chapati → tortilla) are listed first.
   - Otherwise, a cache lookup in `ingredient_substitution` by context → on a miss, one LLM call → resolve → drop excluded, held and disliked items.
   - Code computes inventory availability, price delta (only with price data, within one store), and nutrition-preserving quantities (protein keeps protein grams; vegetables keep mass; carbs keep kcal).
   - Ranking is deterministic. Applying a substitution triggers a validated step rewrite → new version.
6. **Preference profile:** deterministic, smoothed aggregation from events (recipe and family scores, ingredient affinities by mass share, tag affinities, complexity and time tendencies, portion preference, repeat and never-finished rates, budget pattern). A "What I've learned" screen shows threshold-gated, templated statements.
7. **Weighted scoring function:** `preference_score` in [−1, 1] → solver preference term, reuse order, prompt hints. Its score and components are written into the `plan_candidate` rows that Phase 2 already logs. Capped never-favored items get no preference-score boost from nutrition, price or inventory features (§7.4).
8. **Cook Again:** your default version is re-scaled and re-costed deterministically (0 LLM calls). It calls the LLM once only on the triggers (excluded/disliked ingredient, missing equipment, can't fit calories/time by scaling, or "adapt to what I have"). Adapted versions apply to that cook unless you save them.

**Files and folders.** Creates `app/feedback/`, `app/preferences/`, `app/substitutions/`, `app/domain/preferences.py`, `app/schemas/feedback.py`, prompts (comment_tags, substitution, step_rewrite, adaptation), API routes (ratings, cook_logs, recipe_versions, substitutions, cook_again, profile), `migrations/versions/0006_feedback_loop.py`; frontend `history/`, `learned/` (reached from Settings and the Cook tab), rating sheet, editor, substitution sheet. (♥ and 🔖 shipped in Phase 2b.)

**Database.** Migration `0006_feedback_loop` (planned as 0003): `prepared_portion`, `preference_profile`; `plan_meal.prepared_portion_id`; `inventory_event.prepared_portion_id` + CHECK (§4.5). `feedback_event` and `recipe_favorite` already exist (Phase 2b, `0005_cook_flow`).

**Acceptance criteria**
1. Favorites (from Phase 2b) feed the weighted preference score; with otherwise-equal candidates the favorite still wins.
2. Each feedback action writes exactly one valid `feedback_event`; events are never updated or deleted.
3. Editing creates version N+1 with the correct parent and diff, leaving the original byte-identical. Editing a seed draft yields a non-draft user version, and the next plan uses it. Revert works.
4. "Replace broccoli" returns ranked, code-justified alternatives. "Cheaper" appears only with same-store price data. An identical repeat request makes 0 LLM calls.
5. Cook Again makes 0 calls with unchanged constraints and exactly 1 when a trigger applies.
6. The profile is deterministic, and statements respect their thresholds.
7. `plan_candidate` rows now carry the weighted `preference_score` and its components.
8. All tests pass.

**Test plan**
- **Versioning:** v1 → v2 → v3; branch from v1; default pointer; revert; immutability; `change_set` round trip; seed-draft edit produces `is_draft=false`.
- **Events:** one per action; payload validation; append-only enforcement.
- **Cook log:** FIFO; shortfall; prepared portions with `use_by`; a Saturday batch's leftover portion is used by next week's Monday plan (cross-week carry-over); waste event.
- **Substitution:** accepted pair first; cache hit/miss; protein-preserving quantity (200 g Greek yogurt → 180 g cottage cheese at 11 g/100 g, with cottage cheese allowed in the fixture); held and excluded removed; "cheaper" only within one store's data; LLM invalid JSON → retry; step rewrite passes the prose filter and safety injection.
- **Preferences:** smoothing; mass-share weighting; thresholds; determinism.
- **Scoring:** bounds; monotonicity; recency penalty.
- **Cook Again:** unchanged → 0 calls; price change only → 0 calls, cost updated; excluded ingredient → 1 call.
- **Exposure log scores:** `plan_candidate.heuristic_score` equals the weighted preference score used by the solver.
- **Frontend:** rating sheet, editor diff, substitution list (♥ is tested in Phase 2b).

**Depends on.** Phases 1–2 and 2b.

**Risks and mitigations**
- *Overfitting to few ratings.* Priors, minimum counts.
- *Version sprawl.* Only explicit saves and accepted adaptations create versions.
- *Unsafe rewrites.* The same validators and safety injection run on every version.

---

### Phase 4: Daily overrides

**Goal.** Let real life change one day without wrecking the week: swap a meal for time or mood, log off-plan food, see what's left for today and the week, and rebalance under strict daily (hard daily ceiling) or weekly (hard weekly ceiling, ±150 kcal day band) mode.

**PRD sections.** §5, §6 (day-level), §26, §27, §28.

**Deliverables**
1. **Today:** extends the Cook home "Today" card and the meal-prep results' Today section (Phase 2b) with consumed vs remaining for the day and week and quick actions; no separate `today/` route is needed.
2. **Day override:**
   - A partial re-solve of the targeted day/slot(s) with everything else fixed, built on Phase 2b's pinned re-solve (`planning/pins.py`, used there for single-meal swaps). Purchased inventory and open packages count as zero cost; new purchases are penalized.
   - One targeted LLM call only if no saved or seed candidate fits.
   - Displaced portions are reassigned within the fridge window, frozen, or the batch is cancelled if uncooked.
   - If the override turns a non-cook day (Tue/Fri) into cooking, it asks first and records the change.
   - History is kept via `replaced_by_plan_meal_id` + `day_override`.
3. **Consumption logging:** mark eaten or skipped; off-plan entries with your own kcal, or parsed free text with **code-computed** kcal flagged as an estimate.
4. **Rebalancing:**
   - *Strict:* today's remaining is capped at the daily ceiling and other days are untouched, with a lighter dinner suggested.
   - *Weekly:* the difference is spread across the remaining days within ±150 kcal of each day's target, never exceeding the weekly ceiling.
   - Shown as a diff you confirm.
5. **Mode toggle:** in settings and per plan.
6. **"What's left today" feeds A meal now:** with consumption logged, the meal-now calorie target becomes the remaining calories for today (e.g. 750 kcal), within the same mode rules.

**Files and folders.** Creates `app/overrides/`; extends `app/domain/calories.py`; prompt `off_plan_parse`; API routes (days, consumption, rebalance); frontend Today additions on the Cook tab; `migrations/versions/0007_daily_overrides.py`.

**Database.** Migration `0007_daily_overrides` (planned as 0004): `day_override`, `consumption_entry`.

**Acceptance criteria**
1. A day override changes only the targeted meals; all other `plan_meal` rows are identical before and after.
2. "Today I only have 20 minutes" yields a dinner ≤ 20 min using inventory first, or a clear "nothing fits" with options.
3. Target 1,800, consumed 1,050 → shows **750 kcal remaining** and suggests only dinners ≤ 750.
4. Weekly mode keeps the week ≤ W and each remaining day within ±150 kcal of its target. Strict mode never changes other days.
5. Off-plan text never uses an LLM calorie number.
6. All tests pass.

**Test plan**
- **Partial re-solve:** diff test; expiring item and open package used first; displaced uncooked batch cancelled; displaced cooked portion reassigned or frozen; Tuesday override requests confirmation before scheduling cooking; nothing fits → infeasible with options.
- **Rebalancing math:** 1800 − 1050 = 750. A 400 kcal dessert: strict → "over by 400" + lighter-dinner suggestion; weekly → −100/day over 4 remaining days (within ±150). +700 over 4 days = +175/day > 150 → 100 kcal unabsorbed and reported. Never a negative target. Last day of the week → message only.
- **Time:** 23:59 vs 00:01 in your timezone; DST week.
- **Off-plan parse:** estimate flagged; invalid JSON → retry; user number used as-is.
- **Mode toggle:** golden tests for strict vs weekly on the same consumption.

**Depends on.** Phases 1–3 and 2b.

**Risks and mitigations**
- *Groceries bought for the original meal.* Inventory-first objective; freed items shown as "use soon".
- *Infeasible partial re-solves.* Fall back to prepared portions or a no-cook option.
- *Parsing errors.* Confirm step; estimates labeled.

---

### Phase 5: Grocery intelligence

**Goal.** Make the grocery list smart and honest: per-store price history, deals flagged only when that store's own history supports it, seasonal tags kept separate from price, grocery modes, next-list recommendations, and in-store cart optimization.

**PRD sections.** §12, §13, §14, §15, §16, §35.

**Deliverables**
1. **Price history:** fast in-store entry tied to a store; per-ingredient, per-store history (last, trailing average, min/max); normalized unit price across package sizes.
2. **Deal detection** (`domain/price_stats.py`): **within the same store only.** Compare the per-gram (or per-count) unit price against that store's history for the ingredient. GOOD DEAL needs ≥ 3 prior observations at that store on ≥ 2 dates within 180 days, at ≤ 85% of the trailing average; "above usual" at ≥ 115%. Otherwise no label. "Per gram of protein" comparisons are computed by code.
3. **Seasonality:** curated Massachusetts/New England harvest calendar (cited) → "Seasonal in your region"; never implies price.
4. **Grocery modes:** CHEAPEST / HEALTHIER / SEASONAL / BALANCED as solver weight profiles plus list rules.
5. **Next-list recommendations:** extends Phase 2b's "What should I buy?" (a shop-mode plan with templated reasons from current prices) with expiring items and open packages, usual items from history (a separate dismissible section) and within-store deals, all as templated, data-backed sentences.
6. **Grocery Store Mode** (in the Grocery tab): a `cart_session` per store; "+ Add Grocery" entries; **Optimize My Cart** in two modes, quick (recipes fixed, cheapest packages) and full re-plan, returning the cheapest combination, nutritional value, meals, servings and cost per serving.

**Files and folders.** Creates `app/grocery/`, `app/domain/price_stats.py`, `app/seed/data/seasonality_new_england.json`, API routes (price_history, deals, recommendations, cart_sessions), frontend `store/`, history views, mode selector, badges, `migrations/versions/0008_grocery_intelligence.py`. Changes `objective.py`, `app/cook/grocery_advice.py` (Phase 2b) and `docs/data-sources.md`.

**Database.** Migration `0008_grocery_intelligence` (planned as 0005): `region`, `ingredient_seasonality`, `cart_session`, `price_observation.cart_session_id`.

**Acceptance criteria**
1. Deal labels appear only when the same-store thresholds are met. A lower Price Rite price never marks a Stop & Shop observation as a deal, or vice versa.
2. Unit-price normalization and protein-per-dollar comparisons match hand calculations.
3. Seasonal items never show "cheap" unless price rules independently say so.
4. Directional mode tests pass (CHEAPEST lowers cost, HEALTHIER raises vegetables/fiber).
5. Both Optimize My Cart modes return the §35 outputs, and cost equals the sum of the selected entries.
6. Every recommendation sentence comes from a template over computed facts.
7. All tests pass.

**Test plan**
- **Price stats:** within-store trailing average with gaps; cross-store isolation; outliers; exactly at threshold; insufficient same-store history; package-size normalization; estimates excluded from history.
- **Seasonality:** month boundaries; no region → no tags; wording.
- **Modes:** directional golden tests; weight normalization.
- **Recommendations:** "enough chicken"; no "unusually cheap" without same-store history; usual items (bought ≥ 3 of the last 4 weeks).
- **Cart optimizer:** cheapest combination across sizes; entered items can't cover the plan → missing items reported; deterministic ties; quick vs full re-plan.
- **Frontend:** store mode flow; offline price entry queued and synced.

**Depends on.** Phases 1–4.

**Risks and mitigations**
- *Sparse same-store data.* Labels stay off; "price unknown" shown honestly.
- *Seasonality quality.* A curated, cited source.

---

### Phase 6: Learned ranker

**Goal.** Once enough rating data exists, train a small personal model that predicts how much you'll like a candidate. Blend it into planning only if it beats the weighted scoring function on your own history. The LLM is never retrained.

**PRD sections.** §19, §21, §22.

**Deliverables**
1. **Dataset builder:** examples come from `feedback_event` + `plan_candidate` exposures (including Phase 2b's meal-now searches, whose `selected` is set when you cook one, and swaps, which are negative signals), with features only from data before each occasion (ingredient categories and mass shares, family, protein source, cuisine/tags, mood, estimated vs actual time, cost/serving, nutrition/serving, repeats, recency, waste, slot). Label: 👍 or ≥ 4 stars.
2. **Model:** a regularized logistic regression implemented in pure Python (no new dependencies); weights stored as JSON in `ranker_model`.
3. **Evaluation:** time-based split; AUC, log loss and top-k precision vs the weighted baseline; `cli ranker-eval`.
4. **Gating:** activate only after ≥ 100 rated meals across ≥ 25 distinct recipes over ≥ 8 weeks **and** a configured margin over baseline.
5. **Serving:** blended score → solver preference term; exploration allowance (e.g. one new recipe per week); top features shown in "What I've learned".
6. **Retraining:** `cli ranker-train`, version registry, one-command rollback.

**Files and folders.** Creates `app/ranking/`, CLI commands, API `ranker/status`, a frontend settings panel, `migrations/versions/0009_ranker.py`. Changes the preference-term source in `objective.py` and in `app/cook/ranking.py` (Phase 2b).

**Database.** Migration `0009_ranker` (planned as 0006): `ranker_model`.

**Acceptance criteria**
1. A test proves the dataset is leak-free (features for an occasion use only earlier events).
2. On synthetic data with a known preference, the model reaches AUC ≥ 0.9.
3. Below the threshold, or without beating the baseline, the planner uses the weighted function and the status endpoint says why.
4. When active, plans stay valid; rollback restores previous behavior.
5. Training is reproducible.
6. All tests pass.

**Test plan.** Leakage test; synthetic recovery; gating edges (threshold − 1, tie, sub-margin win); serialization round trip; blended score bounds; exploration respected; solver integration golden test; class imbalance; pure-Python training matches a hand-checked tiny example.

**Depends on.** Phase 2 (exposures) and Phase 3 (events, weighted scoring) with months of real use; Phases 1 and 5.

**Risks and mitigations**
- *Too little data.* Hard gate; the phase may ship infrastructure with the model inactive.
- *Selection bias.* Exposure logs + exploration.
- *Drift.* Recency weighting, periodic re-evaluation.

---

## 10. Dependencies

Listed in CLAUDE.md: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, PostgreSQL, PuLP, Groq SDK, Next.js, TypeScript, pytest, Vitest, Docker Compose.

| Package / tool | Phase | Status | Why (one line) |
|---|---|---|---|
| `uvicorn` | 0 | Approved | ASGI server that runs FastAPI |
| `psycopg[binary]` (v3) | 0 | Approved | Postgres driver for SQLAlchemy |
| `httpx` | 0 | Approved | Required by FastAPI's TestClient |
| `pydantic-settings` | 0 | Approved | Typed config from environment variables |
| `ruff` (dev) | 0 | Approved | Lint + format |
| `mypy` (dev) | 0 | Approved | Enforces "type hints everywhere" |
| `pytest-cov` (dev) | 0 | Approved | Coverage acceptance criterion |
| `hypothesis` (dev) | 0 | Approved | Property tests for conversions and scaling |
| `uv` (tool) | 0 | Approved | Python env + lockfile |
| `pg_trgm` (Postgres extension) | 0 | Approved | Fuzzy ingredient search |
| `@testing-library/react`, `@testing-library/user-event`, `@testing-library/jest-dom`, `jsdom` (dev) | 2 | Approved (Q17 default) | Component tests under Vitest |
| `openapi-typescript` (dev) | 2 | Approved (Q17 default) | Frontend types generated from FastAPI's OpenAPI |
| Tailwind CSS | 2 | Not used (Q17 default) | CSS Modules instead |
| TanStack Query | 2 | Not used (Q17 default) | Plain fetch hooks instead |
| Playwright (dev) | 2 | Not used (Q17 default) | Manual checklist instead |
| `scikit-learn` + `numpy` | 6 | Not used (Q25 default) | Pure-Python logistic regression instead |
| `pulp` (pinned 3.3.x) | 1 | Listed in CLAUDE.md | PuLP 4 moved CBC into a separate `cbcbox` package; 3.x keeps the bundled CBC as a fallback |
| `groq` | 1 | Listed in CLAUDE.md | The Groq SDK, imported only in `app/llm/client.py` |
| `highspy` (pulls in `numpy`) | 1 | **Approved 2026-10-09 (C3)** | HiGHS MILP solver behind PuLP: the CBC bundled for Windows hangs and ignores its time limit |
| `next` 16.3.6, `react` / `react-dom` 19.3.0, `typescript` 5.9.3, `vitest` 4.1.11 | 2 | Listed in CLAUDE.md | Pinned exactly; `@types/react`, `@types/react-dom` 19.3.0 and `@types/node` 22.20.2 come with TypeScript |
| `@testing-library/react` 16.3.3, `user-event` 14.6.7, `jest-dom` 6.9.1, `jsdom` 29.1.1, `openapi-typescript` 7.13.0 | 2 | Approved (Q17) | jsdom 30 needs Node ≥ 22.22 and jest-dom 6.10.0 is deprecated, so the previous releases |
| `@testing-library/dom` 10.4.2 | 2 | Required peer of `@testing-library/react` 16 | Part of the approved testing-library set; nothing else was added |

No other dependencies are planned. Auth uses the stdlib, and the solver uses HiGHS through PuLP (C3). **Phase 2b adds none:** the screen-wake lock is a browser API, icons are emoji and in-house inline SVG, and fonts are system fonts. If one becomes necessary, I'll ask first with a one-line justification.

---

## 11. Conflicts between PRD and CLAUDE.md (resolved per CLAUDE.md)

1. **PRD §32:** "The LLM then generates a plan within these constraints." **CLAUDE.md rule 4:** the solver chooses. → The LLM generates candidates; the solver builds the plan.
2. **PRD §33:** "ask the AI to revise it" → revision applies to candidate recipes; plan-level violations → re-solve / targeted generation.
3. **PRD §31:** "meal-plan reasoning" → the LLM may explain; it never decides.
4. **PRD §24:** Cook Again "should regenerate". **CLAUDE.md rule 7:** reuse unless constraints changed. → Deterministic re-scale by default; LLM only on the Q20 triggers.
5. **PRD §10:** "not a static substitution table". **CLAUDE.md rule 7:** cache per ingredient. → Cache culinary candidates only; inventory, price and nutrition ranking is recomputed live.
6. **CLAUDE.md outline** puts strict/weekly modes in Phase 4. → **Approved:** the solver supports both from Phase 1; Phase 4 adds the toggle UX and rebalancing.
7. **CLAUDE.md phase outline vs Phase 2b (flagged 2026-10-10; resolved: CLAUDE.md updated with your OK the same day).** CLAUDE.md listed favorites under Phase 3, had no Phase 2b, and says "build exactly ONE phase per session". This plan, following your brief, moves favorites to 2b and runs 2b as eight one-session build steps, each ending with the phase-end steps (tests shown, commit, fresh-clone check, summary, stop). The CLAUDE.md wording now in place:
   - add "Phase 2b: Cook-first flow (4 tabs, Cook flow, favorites and save for later, onboarding, swap, grocery advice). Built in steps 2b.1–2b.8, one step per session; each step ends like a phase.";
   - change Phase 3's line to "Feedback loop (ratings, recipe versioning, preference profile, Cook Again)".

---

## 12. Decisions, remaining questions, and action items

### 12.1 Decisions from your review (2026-10-08)

| # | Topic | Decision |
|---|---|---|
| Q1 | Phase 0 dependencies | Approved (§10). Anything new needs a one-line justification. |
| Q2 | User model | Single user with a `user_id` column on owned tables. |
| Q3 | Heme iron | 40% of total iron for poultry and fish; 0% for plant foods and eggs; labeled "estimated". Extended by R1. |
| Q4 | Storage | Values from the FoodSafety.gov Cold Food Storage Chart, cited in a code comment. Cooked leftovers 3 days in the fridge; reheat to 165 F. |
| Q5 | Seed data | Stop & Shop (primary), Price Rite (secondary); flagged estimates overwritten by real entries; Price Rite tortillas 30 ct $1.99; Price Rite chicken estimated cheaper; protein powder 25 g protein/scoop (label values: A2 below); seed recipe families (§13). The original "never beef and pork" rule is **replaced by R2** below. |
| Q6 | Cooking schedule | Cook Mon, Wed, Thu, Sat, Sun; no cooking Tue/Fri (leftovers within the fridge window); editable setting; freeze/thaw extension allowed for freezer-friendly recipes. |
| Q7 | Time meaning | Start-to-finish, all cooking that day combined. |
| Q8 | Mood/time scope | Weekly defaults + per-weekday values at planning; Phase 4 edits a day after planning. |
| Q9 | Calories | Strict = hard daily ceiling. Weekly = hard weekly ceiling + each day within a configurable band (default ±150 kcal). Both modes in the solver from Phase 1. Under-target allowances: weekly 3%, strict daily 5%. |
| Q10 | Portions | 0.75 / 1.0 / 1.25 / 1.5; XL keeps the same calorie target unless you raise it; ±10% portion variants allowed. |
| Q11 | Leftover package | Solver decides: absorb if the rounded plan stays within calories; otherwise keep it as an open package and boost recipes using it next plan. "Absorb" defined by R5. |
| Q12 | Overlapping knobs | Nutrition priority = nutrient to maximize; grocery mode = cost/health/variety/seasonal weighting; "Budget maximum" mode and `budget_priority` dropped. |
| Q13 | Budget | New spend only; staples assumed in stock; soft unless marked hard. |
| Q14 | Variety | Max 5 portions per recipe per week, never twice in a day. |
| Q15 | New ingredients | Reject + retry during planning; "suggested new ingredients" queue you approve. |
| Q16 | Hosting | Real cloud deploy with simple single-user auth; provider decided before Phase 2 (A3). Not a Phase 0 blocker. |
| Q17 | Frontend deps | testing-library + jsdom + openapi-typescript; CSS Modules; plain fetch hooks; no Playwright. |
| Q18 | Offline | Read-only offline + queued grocery check-offs and price entries. |
| Q19 | Ratings | 👍/😐/👎 required, stars optional; liked = 👍 or ≥ 4 stars. |
| Q20 | Cook Again | LLM only on the listed triggers; adapted versions apply to that cook unless saved. |
| Q21 | Deals | Within the same store only, thresholds as in Phase 5. |
| Q22 | Seasonality | Curated MA/New England harvest calendar, cited. |
| Q23 | Optimize My Cart | Both modes; quick (recipes fixed) is the default. |
| Q24 | Usual items | Separate dismissible "usual items" section. |
| Q25 | Ranker | ≥ 100 rated meals, ≥ 25 recipes, ≥ 8 weeks, must beat baseline; pure-Python logistic regression. |

**Plan approval (2026-10-08)**

| # | Topic | Decision |
|---|---|---|
| P1 | Table audit | Every `0001` table must be touched by a named Phase 0/1 test or move to the phase that first uses it. Result: 31 → 31, 0 moved; 3 missing tests named (§4.2a). |
| P2 | Exposure logging | `plan_candidate` moves to Phase 2 (migration `0002_pwa_and_exposure_log`, built as `0004`), since real use starts there and exposures can't be backfilled. Ratings stay in Phase 3. |
| P3 | Approved as proposed | "Mark cooked" in Phase 2; `ingredient_substitution` table now; exclusion check separate from the prose filter. |
| P4 | Session reading | CLAUDE.md: each session reads only the current phase's §9 section plus the shared sections (see the note at the top of this file). |
| R1 | Heme iron | Dairy and eggs 0%. Shellfish 40% (like fish). Lamb and pork 40% (like other meat). All labeled "estimated". |
| R2 | Exclusions (replaces "never beef and pork") | **Beef excluded**, including all beef-derived ingredients (broth/stock, tallow, bovine gelatin, bouillon, …). **Pork allowed**: removed from the exclusion list everywhere (solver, prompts, exclusion check, tests, docs). **Gelatin** of unspecified source excluded by default (may be bovine); pork-labeled gelatin allowed. Plain Greek yogurt with no gelatin allowed. Tortillas allowed (no longer ambiguous). |
| R2+ | Pork frequency | Pork is allowed but **rare**. *Meal components* (sausage, pepperoni, bacon, ham, pork cuts) are capped at **1 meal/week** by default via a **general frequency-cap setting** (ingredient or tag + max meals per week), reusable for other foods. *Trace* pork-derived ingredients (lard in tortillas, pork gelatin) have no limit. The solver never favors pork-component meals for nutrition, price or inventory use; they're included only when they fit within the cap. Seed recipes use no pork component. Tests: a week never exceeds the cap; cap 0 excludes pork components but keeps trace pork. |
| R3 | Breakfast seeds | Two drafts: one egg-based, one oats + protein powder (§13, family 4 and 5). |
| R4 | Store split | Suggest a separate Price Rite trip only when it saves ≥ $5 that week. Threshold is a setting (`store_split_min_savings_cents`, default 500). |
| R5 | "Scale up" | The whole recipe scales proportionally, then rounds, so flavor ratios stay intact. |
| R6 | Seed defaults | Accepted: 4 servings per main, 2 tortillas per serving, mostly boneless thighs. |
| R7 | Cost words | "Cheap" and "deal" are cost claims. Only code can produce them from stored price data; the LLM can't say them in prose. |
| A2 | Label values | Protein powder (double chocolate): scoop 31 g, 120 kcal, 25 g protein. Price Rite small flour tortillas (30 ct, $1.99): net weight ≈ 23 oz (652 g), ≈ 22 g each, an **estimate** from a 20–26 oz range, flagged for exact label values (net weight, serving size) later. |
| A1 | FoodSafety.gov | Retried in Phase 0; if still blocked, you'll save the chart as a PDF into `docs/sources/`. |

**Pre-Phase 1 (2026-10-08)**

| # | Topic | Decision |
|---|---|---|
| L1 | Package labels | Tortillas and protein powder are package-label ingredients (source "package label") that override their USDA mappings. Tortillas: 20 per bag, 37 g each, 740 g, $1.99 (replaces the 30-count / 23 oz estimate; "estimated" flag removed). Powder: 31 g scoop, 120 kcal, 24 g protein (not 25), 22 scoops / 682 g, allergens milk and soy; price pending. |
| L2 | USDA mapping review | `docs/review/usda_mappings.md`: every mapping sorted by share of seed calories, with state and auto-flags; top 25 marked "Krish to review". |
| L3 | Raw / dry rule | Recipe quantities are raw / dry / as-sold unless a line says otherwise; the check is in §7.8. |
| L4 | Pepperoni, salami | Stay held. No further action. |
| L5 | Machine boundaries | CLAUDE.md: never install system-level software, change machine settings, or start/stop applications outside the repo without asking first. |
| L6 | Storage chart | The FoodSafety.gov PDF in `docs/sources/` is transcribed into the food-safety table (all 53 rows), replacing every pending storage duration; the PDF is committed and cited in code. |
| L7 | Mapping review | Greek yogurt stays nonfat (FDC 170894); milk stays 2% (FDC 171267). Everything else in the top 25 is approved as-is (recorded as `nutrition_reviewed_on` 2026-10-08). |
| L8 | Tortilla name | "flour tortilla (Price Rite, 37 g)" is renamed "flour tortilla (Price Rite, 37 g)"; the old name stays as an alias, and the slug `flour-tortilla-small` is unchanged. |
| L9 | Docker rule | Starting/stopping this repo's own containers from `docker-compose.yml` is allowed; launching Docker Desktop or any other application still requires asking. |
| L10 | Fresh-clone check | Run `scripts/fresh_clone_check.sh` at the end of every phase, even when dependencies didn't change. |

**Phase 1 (2026-10-08 / 09)**

| # | Topic | Decision |
|---|---|---|
| C1 | Cook time | A cook day's minutes are **hands-on** minutes: the batches' `active_minutes` added up. Simmering, chilling and soaking overlap with other work. Mood limits use active minutes too (simple ≤ 30, medium ≤ 60, fancy ≤ 240). Replaces Q7's start-to-finish reading, which fit only one seed recipe per 45-minute cook day. |
| C2 | Variety cap | The weekly 5-portion cap applies to breakfast, lunch and dinner; desserts, snacks and drinks are limited only by "never twice in a day". A second protein-dessert seed was added for variety: 3b Chocolate protein chia pudding (it also uses the protein powder). |
| C3 | Solver | HiGHS (`highspy`) runs the MILP through PuLP. The CBC 2.10.3 bundled with PuLP for Windows hangs on these models and ignores its time limit (the Linux build is fine); CBC stays only as a fallback when HiGHS is missing. |
| C4 | Budget and modes (fix-up) | The budget is a per-request parameter, not a setting. Inventory mode ("cook from what I have"): purchases off by default, an optional top-up for missing items listed as a short buy list, and an exact list of what's missing when nothing fits. Shop mode ("what should I buy"): inventory first, then the grocery list; an optional budget is a hard limit on cash this trip; with none, the cost is minimized and reported. |
| C5 | Cost reporting (fix-up) | Show cash spent this trip (whole packages) and the cost of food eaten this week; leftover value carries into inventory. |
| C6 | Perishable leftovers (fix-up) | Raw meat, poultry or fish with no planned use inside its fridge life (FoodSafety.gov chart) gets "freeze on shopping day"; the solver penalizes opening a perishable package for a small fraction of it; expected waste is shown. |
| C7 | Protein target (fix-up) | A daily protein floor of 100 g (configurable), within the daily/weekly mode rules; protein above it earns no reward. |
| C8 | Elapsed time (fix-up) | Each cook day shows total elapsed cooking time next to hands-on time. |
| C9 | Protein powder prices (post-approval) | 5 lb tub (2,268 g) at an estimated $62.50 ($60-65) and the 682 g tub at a derived estimate (+40% per gram), store "Other" (varies). The cheaper pack per gram is bought; food eaten uses the per-gram cost. |
| C10 | Stock-up items (post-approval) | A stock_up flag for long-life items bought occasionally (powder, rice, oils, spices...). A budget covers regular groceries only; stock-up purchases are listed separately; cash this trip shows regular, stock-up and total. |
| C11 | Shelf life (post-approval) | Bottled lemon and lime juice aren't perishable within a week once opened; fresh lemons and limes are. Check other bottled, jarred or shelf-stable items for the same mistake. |
| C12 | Regular chicken packs (post-approval) | A regular pack (about 1-1.5 lb) for thigh and breast at both stores, at an estimated per-lb premium; the solver chooses between pack sizes. |
| C13 | Steady-state check (post-approval) | A two-week dry-run simulation where week 2 plans from week 1's leftovers, reported with and without --budget 50. |
| C14 | Hosting (A3, post-approval) | docs/hosting.md: options, costs, setup, cold starts, Postgres, HTTPS, single-user auth; one recommendation. No code, no accounts. |

**Phase 2 kickoff (2026-10-09).** You approved Phase 1 including D23–D28, then:

| # | Topic | Decision |
|---|---|---|
| K1 | Hosting (replaces C14) | The deployment must cost $0/month: **Vercel Hobby** (Next.js PWA + FastAPI as Python functions) and **Neon Free** Postgres. Railway is out. `docs/hosting.md` and this plan updated. |
| K2 | Serverless planning | Plan generation finishes inside the request: no 202 + background run + polling. The PWA shows progress while it waits; run records stay in the database; nothing relies on work after the response; the whole request well under Vercel Hobby's 300 s. |
| K3 | Database size | Measure the dev database; if near or over Neon's limit (you quoted 0.5 GB), trim the USDA import, keeping the full import available locally. |
| K4 | Connections | Serverless + Neon settings: the pooled connection string, no long-lived connection assumptions, tolerate Neon waking from scale-to-zero. |
| K5 | Shelf life | Onions, garlic, potatoes and butter keep well beyond a week: realistic multi-week shelf lives, so they stop counting as waste. Hard cheeses stay held (R8 undecided). |
| K6 | Test determinism | No test may depend on wall-clock solver time limits: tests that check plan contents use small instances that solve to proven optimality, or assert properties; audit and fix the existing solver tests. |
| K7 | Phase 2 scope | iPhone Safari first; screens: week, recipe, inventory with fast quick add, grocery checklist grouped by store (stock-up items in their own section), generate with progress, Mark cooked; both planning modes with optional budget and top-up; exposure logging; single password, long-lived secure HttpOnly cookie, rate-limited login; **deploy prep only** (Vercel config, Neon connection setup, migrations-on-deploy, env var list, `docs/deploy.md`): no accounts, nothing deployed. |

**Phase 2b kickoff (2026-10-10).** Your redesign brief. No code this session: spec, PRD and plan only.

| # | Topic | Decision |
|---|---|---|
| E1 | Main flow | Four tabs: Cook (opens here), Grocery, Pantry, Settings. Cook: a meal now or meal prep → goals + mood → what you have (have it / could buy) → ranked cards or a meal-prep plan → recipe page. Full spec: `docs/FLOW_SPEC.md`. |
| E2 | Favorites and save for later | Pulled forward from Phase 3: ♥ boosts a recipe in rankings and plans when it fits; 🔖 is a plain bookmark with no boost; both live in the Cook tab's Saved section. Ratings, versioning and the preference profile stay in Phase 3. |
| E3 | UI direction | One question per screen with one large control (steppers, a budget slider, icon tiles), a fixed Continue button, back arrow, progress dots, a one-line why; minimal typing; pre-filled from last answers or settings; real progress stages; a swap on every meal; a Recipes / Shopping list toggle. |
| E4 | Onboarding | A first-run wizard fills Settings once (people, calories, protein, optional budget, stores, diet rules, meals, cook days, equipment), pre-filled from saved settings, with no calculated recommendations. |
| E5 | Visual style | Warm and friendly, light by default with a dark mode, large type, rounded cards, dish-category icons or emoji (no photos, no image generation), an original personality. |
| E6 | Pending UI fixes | Selected state on segmented controls; hide the daily band in strict mode; groceries + stock-up shown separately; no water or "0 g" in "check you have"; an Always-have staples list; a quick-add amount picker; "Nothing to cook, eating prepped meals". |
| E7 | Solver time limit | 30 s (`SOLVER_TIME_LIMIT_SECONDS`; D43). |
| E8 | Sweet potatoes | Multi-week pantry life, like potatoes. |
| E9 | Hosting and variety | Try Vercel Services first; keep the two-project fallback documented (`docs/deploy.md`, already there). Variety caps as a setting ("max servings of one recipe per week") are deferred to a later phase; the built-in Q14 rule is unchanged. |

**Spec approval (2026-10-10).** You approved the spec and Phase 2, with these changes:

| # | Topic | Decision |
|---|---|---|
| E10 | Onboarding length | 9 screens (W0–W8) instead of the draft's 13 (W0–W12), by pairing related questions (calories + protein; meals + their calories; cook days + minutes; people + budget). The first screen offers **Skip, use my current settings**, since settings already exist. |
| E11 | Protein reward cap | The High protein tile's per-request reward (F3) is approved, but capped: protein above **1.5 × the daily target** earns no extra reward, so the tile can't push plans back into expensive all-chicken weeks. The meal-now ranking uses the same cap per meal. Tested in 2b.5 (`test_reward_capped_at_1_5x_target`). |
| E12 | Cook home | **A meal now** and **Meal prep** stay the two dominant buttons at the top; Same as last time, today's meals and Saved sit below them. |
| E13 | Rate limits | When a call would exceed Groq's per-minute limit (e.g. More ideas tapped twice quickly), show a friendly wait state with a short countdown, never an error. Built in 2b.3 (backend, every LLM path) and 2b.4 / 2b.7 (screens). |
| E14 | Approvals | All 18 flagged changes (FLOW_SPEC §16) approved, F3 with E11's cap. All 10 questions answered with the defaults, including Pottle as the mascot (FLOW_SPEC §18). Phase 2 approved. CLAUDE.md updated with the proposed wording (§11 item 7). |

### 12.2 Remaining questions (from applying your answers)

- **Phase 2b questions:** all answered (FLOW_SPEC §18). None open.

- **R8. Other possibly-beef items.** I applied your gelatin rule ("source not stated → excluded by default, since it may be bovine") to the other items from the old R2 list that could contain beef. All are **held** (excluded until you allow them), and none is in a seed recipe, so nothing is blocked today:
  - cheese (rennet may come from calves)
  - bouillon/stock cubes and "natural flavors" (may contain beef fat or extract)
  - collagen peptides (often bovine)
  - marshmallows (gelatin)
  - generic pepperoni and salami (often pork + beef). **Decided (L4): they stay held.**

  Still open for cheese, bouillon cubes, collagen and marshmallows: allow outright (e.g. "all cheese is fine"), per product, or keep them held?
- *Resolved by R2 (pork allowed):* chicken/turkey sausage in pork casing and refried beans made with lard are now `pork_trace` (unlimited); lard itself is `pork_trace` too, since it's a cooking fat rather than a meal component.

### 12.3 Action items for you

- **A1. FoodSafety.gov chart: done** (L6). Transcribed from your saved PDF on 2026-10-08.
- **A2. Label values: done** (L1). Only the protein powder price is still pending.
- **A3. Cloud provider (before Phase 2).** At the end of Phase 1 I'll bring a short comparison (cost, managed Postgres, HTTPS, cold starts) for you to choose from.

---

## 13. Seed recipe library (DRAFTS: quantities for you to adjust)

All seeds are loaded as `origin=seed`, `created_by=system`, `is_draft=true`. They are usable by the planner on cold start and shown with a "draft" badge. Editing one creates your confirmed version. **Quantities are raw/dry as purchased, for the stated base servings. Calories, macros and cost are computed by code in Phase 0 and deliberately not written here.** Full step text is written into the seed JSON in Phase 0 and passes the same prose filter and safety injection as LLM recipes. **10 versions in 5 families** (3b added in Phase 1, C2). No seed uses beef, a held (possible-beef) item or a pork component (R2). Defaults accepted (R6).

**Family 1: Chicken over rice** (lunch, dinner)

- **1a. Chicken over rice with garlic yogurt sauce.** Medium · stovetop · base 4 · freezer-friendly (chicken + rice; sauce and salad kept fresh) · ≈ 45 min.
  - *Ingredients:* chicken thigh, boneless skinless 680 g · long-grain white rice (dry) 300 g · low-sodium chicken broth 540 ml · olive oil 2 tbsp · lemon juice 3 tbsp · garlic 5 cloves · ground cumin 1 tsp · ground coriander 1 tsp · paprika 1 tsp · ground turmeric ½ tsp · dried oregano 1 tsp · salt 1¼ tsp · black pepper ½ tsp · Greek yogurt, plain nonfat 200 g · romaine 150 g · tomato 2 medium.
  - *Outline:* marinate chicken in oil, half the lemon, garlic and spices; cook rice in broth; sear chicken in batches and slice; stir yogurt with the remaining lemon and garlic; portion rice + chicken, with sauce and salad on the side.
- **1b. Air-fryer chicken over rice with broccoli.** Simple · air fryer + stovetop · base 4 · freezer-friendly · ≈ 30 min.
  - *Ingredients:* chicken breast, boneless skinless 680 g · long-grain white rice (dry) 300 g · water 540 ml · broccoli florets 400 g · olive oil 1 tbsp · garlic powder 1 tsp · smoked paprika 1 tsp · ground cumin ½ tsp · salt 1 tsp · black pepper ½ tsp · Greek yogurt, plain nonfat 150 g · lemon juice 1 tbsp.
  - *Outline:* start rice; season chicken; air fry at 400F about 18 minutes, flipping halfway; air fry broccoli in the last batch; quick yogurt-lemon sauce; portion.
- **1c. Sheet-pan chicken and peppers over rice.** Medium · oven + stovetop · base 4 · freezer-friendly · ≈ 45 min.
  - *Ingredients:* chicken thigh, boneless skinless 680 g · bell pepper 2 · red onion 1 · olive oil 2 tbsp · paprika 2 tsp · ground cumin 1 tsp · garlic powder 1 tsp · dried oregano 1 tsp · salt 1 tsp · black pepper ½ tsp · long-grain white rice (dry) 300 g · water 540 ml · Greek yogurt, plain nonfat 150 g · lemon juice 1 tbsp.
  - *Outline:* roast chicken, peppers and onion at 425°F about 25 minutes; cook rice; yogurt-lemon sauce; portion.

**Family 2: Chicken gravy with flour tortillas used as chapati** (lunch, dinner; `chapati → flour tortilla (Price Rite, 37 g)` is an accepted substitution)

- **2a. Everyday chicken curry gravy.** Medium · stovetop · base 4 · gravy freezer-friendly (tortillas separate) · ≈ 50 min.
  - *Ingredients:* chicken thigh, boneless skinless 680 g · vegetable oil 3 tbsp · yellow onion 2 medium · tomato 3 medium · garlic 5 cloves · ginger root 15 g · ground turmeric ½ tsp · chili powder 1 tsp · ground coriander 2 tsp · ground cumin 1 tsp · garam masala 1½ tsp · salt 1¼ tsp · water 250 ml · cilantro 10 g (optional) · flour tortilla (Price Rite, 37 g) 8 (2 per serving).
  - *Outline:* brown onions; add ginger-garlic, then tomatoes and spices until the oil separates; add chicken and water and simmer until cooked through; finish with garam masala and cilantro; warm tortillas on a dry pan like chapati.
- **2b. Yogurt chicken gravy.** Medium · stovetop · base 4 · gravy freezer-friendly · ≈ 50 min + marinate 30 min to overnight.
  - *Ingredients:* chicken thigh, boneless skinless 680 g · Greek yogurt, plain nonfat 200 g · yellow onion 2 medium · garlic 4 cloves · ginger root 15 g · tomato paste 2 tbsp · garam masala 2 tsp · ground turmeric ½ tsp · chili powder 1 tsp · ground cumin 1 tsp · salt 1 tsp · vegetable oil 2 tbsp · water 200 ml · flour tortilla (Price Rite, 37 g) 8.
  - *Outline:* marinate chicken in half the yogurt and spices; brown onions, ginger-garlic and tomato paste; add chicken and simmer; stir in the remaining yogurt off high heat; warm tortillas.
- **2c. Chicken and spinach gravy.** Medium · stovetop · base 4 · gravy freezer-friendly · ≈ 45 min.
  - *Ingredients:* chicken thigh, boneless skinless 680 g · fresh spinach 300 g · yellow onion 1 medium · tomato 2 medium · garlic 4 cloves · ginger root 15 g · ground cumin 1 tsp · ground coriander 1 tsp · garam masala 1 tsp · ground turmeric ½ tsp · chili powder 1 tsp · salt 1 tsp · vegetable oil 2 tbsp · water 150 ml · flour tortilla (Price Rite, 37 g) 8.
  - *Outline:* wilt and chop spinach; build the onion-tomato-spice base; simmer chicken; stir in spinach; warm tortillas.

**Family 3: Protein pudding** (protein dessert, snack)

- **3a. Double chocolate protein pudding.** Simple · no-cook · base 2 · ≈ 5 min + chill 30 min.
  - *Ingredients:* protein powder, double chocolate 2 scoops (31 g each, from your label) · Greek yogurt, plain nonfat 340 g · unsweetened cocoa powder 1 tbsp · milk (2%) 60 ml · vanilla extract ½ tsp (optional).
  - *Outline:* whisk powder, cocoa and milk into a smooth paste; fold into the yogurt; divide into 2 cups; chill.
  - *Note:* nutrition complete from your package label (L1); cost pending until you give the powder's price.

- **3b. Chocolate protein chia pudding** (added in Phase 1, C2). Simple · no-cook · base 2 · ≈ 5 min + chill 2 hours.
  - *Ingredients:* chia seeds 40 g · milk (2%) 1½ cups · protein powder, double chocolate 1 scoop · unsweetened cocoa powder 1 tbsp · vanilla extract ½ tsp (optional).
  - *Outline:* whisk powder and cocoa into the milk; stir in chia, wait 5 minutes and stir again; divide into 2 jars; chill until thick.
  - *Note:* cost pending until you give the powder's price.

**Family 4: Egg breakfast** (breakfast; R3)

- **4a. Egg, spinach and pepper breakfast wraps.** Simple · stovetop · base 4 · freezer-friendly (wrap individually) · ≈ 25 min.
  - *Ingredients:* egg, large 8 · fresh spinach 100 g · bell pepper 1 · yellow onion ½ · milk (2%) 2 tbsp · olive oil 1 tbsp · salt ½ tsp · black pepper ¼ tsp · flour tortilla (Price Rite, 37 g) 8 (2 per serving).
  - *Outline:* dice pepper and onion; whisk eggs with milk, salt and pepper; soften pepper and onion in oil over medium heat; wilt spinach; add eggs and stir gently until fully set (egg doneness line injected by code); warm tortillas; fill and roll 2 per serving; portion.

**Family 5: Protein oats** (breakfast; R3)

- **5a. Chocolate protein overnight oats.** Simple · no-cook · base 2 · ≈ 5 min + refrigerate overnight.
  - *Ingredients:* old-fashioned rolled oats 80 g · protein powder, double chocolate 2 scoops · milk (2%) 300 ml · Greek yogurt, plain nonfat 100 g · chia seeds 12 g (USDA has no spoon measure for chia, so it's authored in grams) · banana 1 (optional, for topping).
  - *Outline:* whisk powder into the milk until smooth; stir in yogurt, oats and chia; divide into 2 jars; refrigerate overnight; top with sliced banana when serving.
  - *Note:* nutrition complete from your package label (L1); cost pending until you give the powder's price.
