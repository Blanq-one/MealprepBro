# Mealbro Build Plan

**Status:** v3, **approved** 2026-10-08 with the changes recorded in §12.1. Phase 0 in progress.
**Source documents:** `CLAUDE.md` (build rules, wins on conflict), `docs/PRD.md` (product vision).

This plan covers Phases 0–6. One phase per session. A phase is done only when its acceptance criteria are met, its tests pass, and the test output has been shown.

**How to read this plan in a session** (per CLAUDE.md): read only the current phase's section in §9 plus the shared sections: §1 progress, §2 design decisions, §3 repo structure, §4 schema, §5 LLM/solver/validator flow, §6 Pydantic models, §7 cross-cutting rules and conventions, §10 dependencies, §12 decisions and open items. Read §13 (seed recipes) only in phases that touch seed data.

---

## 1. Progress tracker

| Phase | Name | Status | Started | Completed | Notes |
|---|---|---|---|---|---|
| — | Repo setup (git init, .gitignore, initial commit) | Done | 2026-10-08 | 2026-10-08 | Commit `3c7a499`. Done before Phase 0 per instruction. |
| — | Build plan | Approved (v3) | 2026-10-08 | 2026-10-08 | v1 reviewed → v2 (seed library, per-phase migrations, narrow prose filter, rounded-plan validator, strict/best-effort). v3 = approval changes: table audit (§4.2a), exposure logging → Phase 2, beef-only exclusion + pork frequency cap, R1–R7 answers, A2 label values. |
| 0 | Data foundation | In progress | 2026-10-08 | | |
| 1 | Planning brain | Not started | | | |
| 2 | Mobile PWA + cloud deploy | Not started | | | |
| 3 | Feedback loop | Not started | | | |
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
14. **Generation is asynchronous and the structured-output mode is configurable.** `POST /plans` returns a run id. `LLM_STRUCTURED_MODE` is `strict` (constrained decoding) or `best_effort` (Pydantic validation + retry). Never combined with streaming or tool use.
15. **The frontend does no nutrition, unit or cost math.** The API returns computed numbers and display strings.

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
├── deploy/                            # P2: provider config for the cloud deploy
├── backend/
│   ├── Dockerfile · pyproject.toml · alembic.ini · conftest.py
│   ├── migrations/versions/
│   │   ├── 0001_initial.py            # P0: the 31 tables Phases 0–1 use
│   │   ├── 0002_pwa_and_exposure_log.py  # P2
│   │   ├── 0003_feedback_loop.py      # P3
│   │   ├── 0004_daily_overrides.py    # P4
│   │   ├── 0005_grocery_intelligence.py  # P5
│   │   └── 0006_ranker.py             # P6
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
│       │   ├── preferences.py         # P3
│       │   ├── price_stats.py         # P5
│       │   └── tests/
│       ├── schemas/                   # Pydantic models at every boundary (API, LLM, JSONB);
│       │                              # P0: settings (validates the seeded user_settings JSONB), seed files, API
│       ├── usda/                      # P0: CSV importer + subset builder (+ tests/fixtures/)
│       ├── services/                  # orchestration + DB access (+ tests/)
│       ├── seed/                      # P0
│       │   ├── data/
│       │   │   ├── nutrients.json · ingredients.json · units.json
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
        │         inventory/, grocery/, settings/, login/ · P3 history/, learned/ · P4 today/ · P5 store/)
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
| `0002_pwa_and_exposure_log` | 2 | plan_candidate (exposure log; starts with real use, can't be backfilled) | `price_observation.client_ref` (offline idempotency) |
| `0003_feedback_loop` | 3 | prepared_portion, feedback_event, recipe_favorite, preference_profile | `plan_meal.prepared_portion_id`, `inventory_event.prepared_portion_id` + CHECK |
| `0004_daily_overrides` | 4 | day_override, consumption_entry | — |
| `0005_grocery_intelligence` | 5 | region, ingredient_seasonality, cart_session | `price_observation.cart_session_id` |
| `0006_ranker` | 6 | ranker_model | — |

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
          │                  └─ [P2] plan_candidate
          ├─ [P3] feedback_event · recipe_favorite · preference_profile
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
  nutrition_source        text NN      -- usda | label | manual
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
  source            text NN      -- usda | label | manual | derived
  fdc_id            integer NULL
  PK (ingredient_id, nutrient_id)               -- missing row = unknown, never zero

ingredient_unit                                 -- named portions; override density
  id                bigint PK
  ingredient_id     bigint NN FK→ingredient
  unit_name         text NN      -- clove | head | slice | can | scoop | tortilla | cup_chopped | large | …
  grams             numeric(10,3) NN CHECK > 0
  source            text NN      -- usda_portion | label | manual
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
-- 0002_pwa_and_exposure_log (Phase 2) ------------------------------------------------
ALTER price_observation ADD client_ref uuid NULL UNIQUE      -- offline price entries replay exactly once

plan_candidate                                  -- exposure log for the ranker; written for every plan from P2
  id, generation_run_id FK, meal_plan_id NULL FK, recipe_version_id FK, source text NN
  (seed | saved | favorite | user_version | llm_new), eligible_slots text[] NN, filtered_reason text NULL,
  heuristic_score numeric(8,4) NULL, score_components jsonb NULL, features jsonb NULL,
  selected bool NN, portions_selected smallint NN DEFAULT 0, created_at

-- 0003_feedback_loop (Phase 3) -------------------------------------------------------
prepared_portion                                -- cooked leftovers / frozen meal-prep portions
  id, user_id FK→app_user, recipe_version_id FK→recipe_version, cook_batch_id NULL FK→plan_cook_batch,
  portions smallint NN CHECK ≥ 0, portion_size text NN, location text NN (fridge | freezer),
  cooked_on date NN, use_by date NN (from the food-safety table), status text NN (available | eaten | discarded),
  created_at, updated_at

feedback_event                                  -- append-only; services never UPDATE/DELETE
  id, user_id FK, event_type text NN (rating | cook_completed | substitution | recipe_edited | leftover | waste |
  favorite_added | favorite_removed | meal_skipped | meal_swapped | off_plan_food | inventory_correction),
  occurred_at timestamptz NN, recipe_id NULL FK, recipe_version_id NULL FK, plan_meal_id NULL FK,
  cook_batch_id NULL FK, ingredient_id NULL FK, payload jsonb NN, payload_version smallint NN, created_at
  IX (user_id, event_type, occurred_at) · IX (recipe_id)

recipe_favorite      (user_id FK, recipe_id FK, created_at, PK (user_id, recipe_id))
preference_profile   (id, user_id FK, computed_at, through_event_id FK→feedback_event, profile jsonb NN, schema_version)

ALTER plan_meal       ADD prepared_portion_id bigint NULL FK→prepared_portion
ALTER inventory_event ADD prepared_portion_id bigint NULL FK→prepared_portion
ALTER inventory_event ADD CHECK (inventory_item_id IS NOT NULL OR prepared_portion_id IS NOT NULL)

-- 0004_daily_overrides (Phase 4) -----------------------------------------------------
day_override        (id, meal_plan_id FK, day date NN, cook_minutes smallint NULL, mood text NULL,
                     slots text[] NN, reason text NULL, generation_run_id NULL FK, created_at)
consumption_entry   (id, user_id FK, consumed_on date NN, slot text NULL, plan_meal_id NULL FK, description text NN,
                     kcal integer NN CHECK ≥ 0, protein_g numeric(8,2) NULL, source text NN (planned_meal | manual | parsed),
                     is_estimate bool NN, parsed_items jsonb NULL, created_at)

-- 0005_grocery_intelligence (Phase 5) ------------------------------------------------
region                 (code text PK, name text NN)
ingredient_seasonality (ingredient_id FK, region_code text FK→region.code, month smallint CHECK 1–12,
                        availability text NN (peak | available), source text NN, PK (ingredient_id, region_code, month))
cart_session           (id, user_id FK, store_id NN FK→store, started_at, ended_at NULL, status text NN)
ALTER price_observation ADD cart_session_id bigint NULL FK→cart_session

-- 0006_ranker (Phase 6) --------------------------------------------------------------
ranker_model (id, version integer NN UNIQUE, algorithm text NN, trained_at timestamptz NN, train_window jsonb NN,
              n_examples integer NN, feature_spec jsonb NN, weights jsonb NN, metrics jsonb NN,
              is_active bool NN DEFAULT false, created_at)   UQ partial (is_active) WHERE is_active
```

### 4.6 Why later phases don't need a rewrite

- **Solver:** its inputs (recipe versions, nutrition, per-store prices, inventory including open packages) and outputs (plans, batches, practical batch quantities, meals, store-assigned grocery lists) all exist in `0001`.
- **Versioning:** the family / recipe / immutable version / `default_version_id` structure covers seeds, edits, branches, reverts and Cook Again.
- **Price history:** `price_observation` is append-only, per store, and normalized to base units. Within-store deal detection is pure computation over it.
- **Ranker logging:** `plan_candidate` arrives in `0002` (exposures logged from the first real use) and `feedback_event` in `0003`, both as new tables that reference existing ones. `inventory_event`, `llm_call`, `plan_cook_batch.status` and `meal_plan.totals` already carry timestamped history from Phase 1.
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
- Values are transcribed from the **FoodSafety.gov Cold Food Storage Chart** (`https://www.foodsafety.gov/food-safety-charts/cold-food-storage-charts`), with a code comment citing that URL and the access date.
- Coverage: cooked leftovers, plus the raw categories used for inventory expiry estimates (fresh poultry pieces and ground poultry, fish, eggs, soups/stews, and any dairy rows the chart lists).
- Your fixed defaults: cooked leftovers **3 days** in the fridge (`leftover_fridge_days`, editable, capped at the chart's upper bound), and reheat to **165 F**.
- The fridge window means a batch cooked on day *d* can be eaten on *d* through *d + 3*.
- Freezer times are shown with the chart's own wording.
- The chart page returned HTTP 403 to automated fetches on 2026-10-08 (planning) and again at the Phase 0 retry. Until you save the chart PDF into `docs/sources/` (A1), every chart-derived value is stored as **pending** (no number). Only your fixed values (leftovers 3 days, reheat 165 F) are live, and `leftover_fridge_days` cannot be raised above 3 until the chart's upper bound is transcribed.

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
- **End of phase:** full `pytest` (and `vitest` from Phase 2) output pasted in the summary.

### 7.6 LLM budget facts (checked 2026-10-08)

- **Groq strict structured outputs:** `openai/gpt-oss-20b`, `openai/gpt-oss-120b`, `qwen/qwen3.8-27b`. **Best-effort:** those plus `openai/gpt-oss-safeguard-20b`. Neither works with streaming or tool use.
- **Published base limits** for those models: 30 req/min, 1K req/day, **8K tokens/min**, 200K tokens/day. The client reads `x-ratelimit-*`/`retry-after` rather than hardcoding limits.
- **Implications:** 2–3 recipes per call, compact prompts, low reasoning effort, a daily token guard, and the seed library plus reuse to avoid calls.

### 7.7 API and config conventions

- REST under `/api/v1`. Errors are `application/problem+json`. Long operations return `202` + a run id.
- Environment-only config; `.env.example` updated in every phase.

---

## 8. PRD coverage map

| PRD § | Topic | Phase(s) |
|---|---|---|
| 1 | Core concept | all |
| 2 | Calorie planning | 0 (math) · 1 · 2 (display) |
| 3 | Nutrition priority modes | 0 (data, heme estimate) · 1 (protein/carb/iron/balanced; registry for future modes) |
| 4 | Weekly configuration | 1 (API) · 2 (UI) |
| 5 | Recipe mood | 1 (per-day) · 4 (change a day after planning) |
| 6 | Cooking time | 1 (cook schedule, minutes) · 4 |
| 7 | Portion size | 0 (math) · 1 · 2 |
| 8 | Meal-prep quantity, package sizes | 0 (math) · 1 (batches, freezer, absorption pass) · 2 (open packages via "Mark cooked") |
| 9 | Recipe editing | 3 |
| 10 | Substitution engine | 0 (accepted pairs) · 1 (applied in planning) · 3 (engine) |
| 11 | Cooking instructions | 0 (safety table, seed drafts) · 1 (generation + injection) · 2 (display) |
| 12 | Grocery recommendations | 1 (plan − inventory, expiring, open packages) · 5 (full engine) |
| 13 | Grocery list modes | 1 (balanced default) · 5 |
| 14 | Grocery recommendation engine | 5 |
| 15 | Price tracking | 0 (per-store schema, estimates) · 1 (manual entry) · 2 (price at check-off) · 5 (history, within-store deals) |
| 16 | Seasonal recommendations | 5 |
| 17 | Favorites | 3 |
| 18 | Ratings | 3 |
| 19 | Preference learning | 3 · 6 |
| 20 | Feedback pipeline | 3 |
| 21 | Future ML pipeline | 6 |
| 22 | Personal learning loop | 2 (cook deduction) · 3 · 4 · 6 |
| 23 | Recipe versioning | 0 (schema, seed drafts) · 3 (edit behavior) |
| 24 | Cook Again | 3 |
| 25 | Weekly planning screen | 1 (data) · 2 (UI) |
| 26 | Daily adjustment | 4 |
| 27 | Dynamic calorie rebalancing | 4 |
| 28 | Strict daily vs weekly | 1 (both modes in solver, approved) · 4 (toggle UX, rebalancing) |
| 29 | Protein desserts | 0 (seed pudding) · 1 · 2 |
| 30 | Meal categories | 0 · 1 |
| 31 | Prompting architecture | 0 · 1 |
| 32 | Constraint engine | 1 |
| 33 | Validation layer | 1 |
| 34 | Mobile-first PWA | 2 (+ screens in 3–6) |
| 35 | Grocery Store Mode | 5 |
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
   - **Ingredients:** ~150–200 canonical ingredients covering the PRD examples and the seed recipes (§13), with FDC mappings, aliases, named units, densities, safety categories, heme fractions, `diet_tags`, shelf life and `assume_in_stock`. Includes `chapati (roti)` and `flour tortilla, small`, and the beef and pork items needed so the resolver can recognize them.
   - **Products and prices:** estimated prices for both stores, flagged `source=estimate` (Price Rite chicken estimated below Stop & Shop chicken). One known price: **Price Rite small flour tortillas, 30 count, $1.99** (`source=manual`).
   - **Protein powder (double chocolate), from your label (A2):** scoop 31 g, 120 kcal, 25 g protein. Carbs and fat per scoop were not in the values sent, so they stay flagged placeholders; until filled, the ingredient is incomplete and recipes using it are not plannable.
   - **Tortillas (A2):** 30-count bag net weight ≈ 23 oz (652 g) → 21.733 g each (computed by code), flagged **estimated** (from a 20–26 oz range) for you to replace with the exact net weight and serving size.
   - **Substitutions:** `chapati → flour tortilla, small` (`accepted`, `count_for_count`).
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
- `domain/tests/test_food_safety.py`: poultry 165; ground pork 160; pork chop 145 + 3 min rest; salmon 145; frittata 160; pancakes no egg note; mixed ground → strictest; reheat 165; leftovers default 3 days; `leftover_fridge_days` above the verified upper bound rejected (above 3 while the chart is pending); chart-derived values report "pending" until transcribed; citation constant present.
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
8. **Accepted substitutions applied:** a resolved `chapati` becomes `flour tortilla, small` via `ingredient_substitution` (count for count), recorded as `adjustment=substituted`.
9. **Recipe validator:** exclusions (ingredient level + step text naming an excluded food); units valid for the ingredient; plausible per-serving amounts; equipment ⊆ available; time and complexity vs mood; **prose filter §7.3**.
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

---

### Phase 3: Feedback loop

**Goal.** Make the app learn you: favorites, ratings, cook logs (actual time and cost), leftovers and waste, recipe editing with versioning (including adjusting the seed drafts), a substitution engine, a transparent preference profile that steers planning, and Cook Again that reuses your version without unnecessary LLM calls.

**PRD sections.** §9, §10, §17, §18, §19, §20, §22, §23, §24, §21 (weighted scoring precursor).

**Deliverables**
1. **Favorites:** ❤️ per lineage; events; solver bonus; reused first.
2. **Ratings:** 👍/😐/👎 required, 1–5 stars optional, quick tags, comment. The LLM parses comments into validated tags. `rating` events use the PRD §20 shape.
3. **Cook log:** extends Phase 2's "Mark cooked" with actual minutes, actual cost and portions made → `cook_completed` event. Leftover and frozen portions become `prepared_portion` rows (`use_by` from the chart), which also enables cross-week carry-over. Waste and leftover events.
4. **Editing and versioning:** quantity, seasoning, protein/vegetable/carb/sauce (via substitution), cooking method (LLM step rewrite); portion size is a plan parameter, not a version. Saving creates an immutable new version (`change_set`, `change_summary`); the default pointer moves; revert; branching. **Editing a seed draft creates your confirmed version** (`is_draft=false`).
5. **Substitution engine:**
   - Accepted pairs (chapati → tortilla) are listed first.
   - Otherwise, a cache lookup in `ingredient_substitution` by context → on a miss, one LLM call → resolve → drop excluded, held and disliked items.
   - Code computes inventory availability, price delta (only with price data, within one store), and nutrition-preserving quantities (protein keeps protein grams; vegetables keep mass; carbs keep kcal).
   - Ranking is deterministic. Applying a substitution triggers a validated step rewrite → new version.
6. **Preference profile:** deterministic, smoothed aggregation from events (recipe and family scores, ingredient affinities by mass share, tag affinities, complexity and time tendencies, portion preference, repeat and never-finished rates, budget pattern). A "What I've learned" screen shows threshold-gated, templated statements.
7. **Weighted scoring function:** `preference_score` in [−1, 1] → solver preference term, reuse order, prompt hints. Its score and components are written into the `plan_candidate` rows that Phase 2 already logs. Capped never-favored items get no preference-score boost from nutrition, price or inventory features (§7.4).
8. **Cook Again:** your default version is re-scaled and re-costed deterministically (0 LLM calls). It calls the LLM once only on the triggers (excluded/disliked ingredient, missing equipment, can't fit calories/time by scaling, or "adapt to what I have"). Adapted versions apply to that cook unless you save them.

**Files and folders.** Creates `app/feedback/`, `app/preferences/`, `app/substitutions/`, `app/domain/preferences.py`, `app/schemas/feedback.py`, prompts (comment_tags, substitution, step_rewrite, adaptation), API routes (favorites, ratings, cook_logs, recipe_versions, substitutions, cook_again, profile), `migrations/versions/0003_feedback_loop.py`; frontend `history/`, `learned/`, rating sheet, editor, substitution sheet, ❤️.

**Database.** Migration `0003_feedback_loop`: `prepared_portion`, `feedback_event`, `recipe_favorite`, `preference_profile`; `plan_meal.prepared_portion_id`; `inventory_event.prepared_portion_id` + CHECK (§4.5).

**Acceptance criteria**
1. Favorites persist, and with otherwise-equal candidates the favorite wins.
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
- **Frontend:** rating sheet, editor diff, substitution list, ❤️ optimistic update.

**Depends on.** Phases 1–2.

**Risks and mitigations**
- *Overfitting to few ratings.* Priors, minimum counts.
- *Version sprawl.* Only explicit saves and accepted adaptations create versions.
- *Unsafe rewrites.* The same validators and safety injection run on every version.

---

### Phase 4: Daily overrides

**Goal.** Let real life change one day without wrecking the week: swap a meal for time or mood, log off-plan food, see what's left for today and the week, and rebalance under strict daily (hard daily ceiling) or weekly (hard weekly ceiling, ±150 kcal day band) mode.

**PRD sections.** §5, §6 (day-level), §26, §27, §28.

**Deliverables**
1. **Today screen:** meals, consumed vs remaining for the day and week, quick actions.
2. **Day override:**
   - A partial re-solve of the targeted day/slot(s) with everything else fixed. Purchased inventory and open packages count as zero cost; new purchases are penalized.
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

**Files and folders.** Creates `app/overrides/`; extends `app/domain/calories.py`; prompt `off_plan_parse`; API routes (days, consumption, rebalance); frontend `today/`; `migrations/versions/0004_daily_overrides.py`.

**Database.** Migration `0004_daily_overrides`: `day_override`, `consumption_entry`.

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

**Depends on.** Phases 1–3.

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
5. **Next-list recommendations:** planned needs, expiring items and open packages, usual items from history (a separate dismissible section), budget, deals → templated, data-backed sentences.
6. **Grocery Store Mode:** a `cart_session` per store; "+ Add Grocery" entries; **Optimize My Cart** in two modes, quick (recipes fixed, cheapest packages) and full re-plan, returning the cheapest combination, nutritional value, meals, servings and cost per serving.

**Files and folders.** Creates `app/grocery/`, `app/domain/price_stats.py`, `app/seed/data/seasonality_new_england.json`, API routes (price_history, deals, recommendations, cart_sessions), frontend `store/`, history views, mode selector, badges, `migrations/versions/0005_grocery_intelligence.py`. Changes `objective.py` and `docs/data-sources.md`.

**Database.** Migration `0005_grocery_intelligence`: `region`, `ingredient_seasonality`, `cart_session`, `price_observation.cart_session_id`.

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
1. **Dataset builder:** examples come from `feedback_event` + `plan_candidate` exposures, with features only from data before each occasion (ingredient categories and mass shares, family, protein source, cuisine/tags, mood, estimated vs actual time, cost/serving, nutrition/serving, repeats, recency, waste, slot). Label: 👍 or ≥ 4 stars.
2. **Model:** a regularized logistic regression implemented in pure Python (no new dependencies); weights stored as JSON in `ranker_model`.
3. **Evaluation:** time-based split; AUC, log loss and top-k precision vs the weighted baseline; `cli ranker-eval`.
4. **Gating:** activate only after ≥ 100 rated meals across ≥ 25 distinct recipes over ≥ 8 weeks **and** a configured margin over baseline.
5. **Serving:** blended score → solver preference term; exploration allowance (e.g. one new recipe per week); top features shown in "What I've learned".
6. **Retraining:** `cli ranker-train`, version registry, one-command rollback.

**Files and folders.** Creates `app/ranking/`, CLI commands, API `ranker/status`, a frontend settings panel, `migrations/versions/0006_ranker.py`. Changes the preference-term source in `objective.py`.

**Database.** Migration `0006_ranker`: `ranker_model`.

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

No other dependencies are planned. Auth uses the stdlib, and the solver uses PuLP's bundled CBC. If one becomes necessary, I'll ask first with a one-line justification.

---

## 11. Conflicts between PRD and CLAUDE.md (resolved per CLAUDE.md)

1. **PRD §32:** "The LLM then generates a plan within these constraints." **CLAUDE.md rule 4:** the solver chooses. → The LLM generates candidates; the solver builds the plan.
2. **PRD §33:** "ask the AI to revise it" → revision applies to candidate recipes; plan-level violations → re-solve / targeted generation.
3. **PRD §31:** "meal-plan reasoning" → the LLM may explain; it never decides.
4. **PRD §24:** Cook Again "should regenerate". **CLAUDE.md rule 7:** reuse unless constraints changed. → Deterministic re-scale by default; LLM only on the Q20 triggers.
5. **PRD §10:** "not a static substitution table". **CLAUDE.md rule 7:** cache per ingredient. → Cache culinary candidates only; inventory, price and nutrition ranking is recomputed live.
6. **CLAUDE.md outline** puts strict/weekly modes in Phase 4. → **Approved:** the solver supports both from Phase 1; Phase 4 adds the toggle UX and rebalancing.

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
| P2 | Exposure logging | `plan_candidate` moves to Phase 2 (migration `0002_pwa_and_exposure_log`), since real use starts there and exposures can't be backfilled. Ratings stay in Phase 3. |
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

### 12.2 Remaining questions (from applying your answers)

- **R8. Other possibly-beef items.** I applied your gelatin rule ("source not stated → excluded by default, since it may be bovine") to the other items from the old R2 list that could contain beef. All are **held** (excluded until you allow them), and none is in a seed recipe, so nothing is blocked today:
  - cheese (rennet may come from calves)
  - bouillon/stock cubes and "natural flavors" (may contain beef fat or extract)
  - collagen peptides (often bovine)
  - marshmallows (gelatin)
  - generic pepperoni and salami (often pork + beef; a pork-only product can be allowed and then counts toward the pork cap)

  Allow any of these outright (e.g. "all cheese is fine"), per product, or keep them held?
- *Resolved by R2 (pork allowed):* chicken/turkey sausage in pork casing and refried beans made with lard are now `pork_trace` (unlimited); lard itself is `pork_trace` too, since it's a cooking fat rather than a meal component.

### 12.3 Action items for you

- **A1. FoodSafety.gov chart.** The page returned HTTP 403 again at the Phase 0 retry (2026-10-08, both fetch methods). Please save it as a PDF into `docs/sources/`. Until then, every chart-derived storage value is stored as *pending* and is never shown or used; your fixed values (leftovers 3 days, reheat 165 F) are live.
- **A2 (remaining).** Protein powder: **carbs and fat per scoop** (plus fiber, sugar, sodium and iron if listed) — the pudding and overnight oats stay "incomplete" until these are in `backend/app/seed/data/label_inputs.json`. Tortillas: exact net weight and serving size from the bag, to replace the 652 g estimate.
- **A3. Cloud provider (before Phase 2).** At the end of Phase 1 I'll bring a short comparison (cost, managed Postgres, HTTPS, cold starts) for you to choose from.

---

## 13. Seed recipe library (DRAFTS: quantities for you to adjust)

All seeds are loaded as `origin=seed`, `created_by=system`, `is_draft=true`. They are usable by the planner on cold start and shown with a "draft" badge. Editing one creates your confirmed version. **Quantities are raw/dry as purchased, for the stated base servings. Calories, macros and cost are computed by code in Phase 0 and deliberately not written here.** Full step text is written into the seed JSON in Phase 0 and passes the same prose filter and safety injection as LLM recipes. **9 versions in 5 families.** No seed uses beef, a held (possible-beef) item or a pork component (R2). Defaults accepted (R6).

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

**Family 2: Chicken gravy with flour tortillas used as chapati** (lunch, dinner; `chapati → flour tortilla, small` is an accepted substitution)

- **2a. Everyday chicken curry gravy.** Medium · stovetop · base 4 · gravy freezer-friendly (tortillas separate) · ≈ 50 min.
  - *Ingredients:* chicken thigh, boneless skinless 680 g · vegetable oil 3 tbsp · yellow onion 2 medium · tomato 3 medium · garlic 5 cloves · ginger root 15 g · ground turmeric ½ tsp · chili powder 1 tsp · ground coriander 2 tsp · ground cumin 1 tsp · garam masala 1½ tsp · salt 1¼ tsp · water 250 ml · cilantro 10 g (optional) · flour tortilla, small 8 (2 per serving).
  - *Outline:* brown onions; add ginger-garlic, then tomatoes and spices until the oil separates; add chicken and water and simmer until cooked through; finish with garam masala and cilantro; warm tortillas on a dry pan like chapati.
- **2b. Yogurt chicken gravy.** Medium · stovetop · base 4 · gravy freezer-friendly · ≈ 50 min + marinate 30 min to overnight.
  - *Ingredients:* chicken thigh, boneless skinless 680 g · Greek yogurt, plain nonfat 200 g · yellow onion 2 medium · garlic 4 cloves · ginger root 15 g · tomato paste 2 tbsp · garam masala 2 tsp · ground turmeric ½ tsp · chili powder 1 tsp · ground cumin 1 tsp · salt 1 tsp · vegetable oil 2 tbsp · water 200 ml · flour tortilla, small 8.
  - *Outline:* marinate chicken in half the yogurt and spices; brown onions, ginger-garlic and tomato paste; add chicken and simmer; stir in the remaining yogurt off high heat; warm tortillas.
- **2c. Chicken and spinach gravy.** Medium · stovetop · base 4 · gravy freezer-friendly · ≈ 45 min.
  - *Ingredients:* chicken thigh, boneless skinless 680 g · fresh spinach 300 g · yellow onion 1 medium · tomato 2 medium · garlic 4 cloves · ginger root 15 g · ground cumin 1 tsp · ground coriander 1 tsp · garam masala 1 tsp · ground turmeric ½ tsp · chili powder 1 tsp · salt 1 tsp · vegetable oil 2 tbsp · water 150 ml · flour tortilla, small 8.
  - *Outline:* wilt and chop spinach; build the onion-tomato-spice base; simmer chicken; stir in spinach; warm tortillas.

**Family 3: Protein pudding** (protein dessert, snack)

- **3a. Double chocolate protein pudding.** Simple · no-cook · base 2 · ≈ 5 min + chill 30 min.
  - *Ingredients:* protein powder, double chocolate 2 scoops (31 g each, from your label) · Greek yogurt, plain nonfat 340 g · unsweetened cocoa powder 1 tbsp · milk (2%) 60 ml · vanilla extract ½ tsp (optional).
  - *Outline:* whisk powder, cocoa and milk into a smooth paste; fold into the yogurt; divide into 2 cups; chill.
  - *Note:* not plannable until the powder's carbs and fat per scoop are filled (A2).

**Family 4: Egg breakfast** (breakfast; R3)

- **4a. Egg, spinach and pepper breakfast wraps.** Simple · stovetop · base 4 · freezer-friendly (wrap individually) · ≈ 25 min.
  - *Ingredients:* egg, large 8 · fresh spinach 100 g · bell pepper 1 · yellow onion ½ · milk (2%) 2 tbsp · olive oil 1 tbsp · salt ½ tsp · black pepper ¼ tsp · flour tortilla, small 8 (2 per serving).
  - *Outline:* dice pepper and onion; whisk eggs with milk, salt and pepper; soften pepper and onion in oil over medium heat; wilt spinach; add eggs and stir gently until fully set (egg doneness line injected by code); warm tortillas; fill and roll 2 per serving; portion.

**Family 5: Protein oats** (breakfast; R3)

- **5a. Chocolate protein overnight oats.** Simple · no-cook · base 2 · ≈ 5 min + refrigerate overnight.
  - *Ingredients:* old-fashioned rolled oats 80 g · protein powder, double chocolate 2 scoops · milk (2%) 300 ml · Greek yogurt, plain nonfat 100 g · chia seeds 1 tbsp · banana 1 (optional, for topping).
  - *Outline:* whisk powder into the milk until smooth; stir in yogurt, oats and chia; divide into 2 jars; refrigerate overnight; top with sliced banana when serving.
  - *Note:* not plannable until the powder's carbs and fat per scoop are filled (A2).
