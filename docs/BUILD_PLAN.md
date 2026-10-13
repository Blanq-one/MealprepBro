# Mealbro Build Plan

**Status:** v3, **approved** 2026-10-08 with the changes recorded in §12.1. Phase 0 approved. Phase 1 approved 2026-10-09 (with C1–C8 and D1–D22); a post-approval round (C9–C14, D23–D28) is done. A3 is answered in `docs/hosting.md`; the hosting decision changed at the Phase 2 kickoff to Vercel Hobby + Neon Free, $0/month (K1, §12.1). Phase 2 (PWA, deploy prep only) was approved 2026-10-10. **Phase 2b (cook-first redesign) was added and its spec approved 2026-10-10** (with changes E10–E13, §12.1): the spec is `docs/FLOW_SPEC.md` and the build steps are in §9. Step 2b.1 (backend foundations) was built and **approved 2026-10-10, including D44–D53**; step 2b.2 (look, shell, onboarding, Settings, Pantry) started the same day. **Addition (2026-10-10, E15–E17):** two-stage recipe generation (ideas for the cards, steps on first open, and after the first More ideas tap a background batch for later taps) to fit Groq's 8K tokens a minute; the target-0 fallback for the protein cap; and step 2b.3 split into 2b.3a (ranking and cards) and 2b.3b (ideas, steps, background batch). All approved. **Step 2b.2 was approved 2026-10-10, including D54–D64** (H1–H6, §12.1): a footer fix on question screens, a new build order (**2b.3a → 2b.4 → 2b.3b**, then 2b.5–2b.8, so the meal-now flow can be used before LLM ideas exist), notes for 2b.5 and 2b.7 (the plan view's Prep notes row; a "How do you want to cook?" step with four options) and a pre-deploy item (§12.4). Step 2b.3a (ranking and cards) was built the same day and **approved, including D65–D76** (J1–J6, §12.1: culinary groups for vegetable swaps, a Mark cooked fix, and three additions to 2b.4). Step 2b.4 (the meal-now screens, with J2–J6) was built the same day and **approved, including D77–D88** (M1–M20, §12.1); its follow-up fixes were built and committed on their own, and **approved 2026-10-10 (N1–N3, §12.1:
the ground-vs-whole-cut swap rule and the mapping review)**. Step 2b.3b (LLM ideas, steps on first open, More ideas and the background batch, rate-limit waits, the live token test, and the screens that need ideas) was built 2026-10-11 with D89–D101 and **approved the same day (P1–P8, §12.1: fish and shellfish swap groups, a shortlist regression fix, a plainer time/mood message, an ideas-model speed check, faster tests, the ideas pass rate)**; the live findings are in FLOW_SPEC §15.1. The pre-work (P2–P7) was done 2026-10-11 with
D102–D106 (2b.3b's approval note in §9) and **approved the same day, including D102 and D105 (T1–T8, §12.1:
the shortlist keeps each meal's cheapest recipe under a money limit, the freeze-note column, one scoop per
portion, and two notes for 2b.6/2b.7)**. Step 2b.5 (meal prep engine) was built the same day with D107–D126
(2b.5 outcome note, §9) and **approved the same day, including D107–D126 (U1–U5, §12.1)**. At the approval the
ideas pass got its optional freeze note (D127), and two designs were written for your review, nothing built:
**smart prep, "Cook basics, mix and match"** (FLOW_SPEC §19) and **parallel cooking on a cook day** (FLOW_SPEC §20),
with four proposed steps before 2b.6 (2b.9–2b.12, §9) and open questions V1–V17 (FLOW_SPEC §21.3). **Both designs
were approved 2026-10-11, including D127 (X1–X9, §12.1)**: F25–F32 approved, V1–V17 answered, and a new build order
so new screens and a live link come sooner: **2b.9 → 2b.10 → 2b.7 → 2b.13 (deploy) → 2b.11 → 2b.12 → 2b.6 → 2b.8**.
Step 2b.9 (cook-day schedule) was built the same day with D128–D142 (2b.9 outcome note, §9) and **approved the
same day, including D135 (Y1–Y3, §12.1)**. At the approval a time guard was built first (D143–D147, 2b.9 approval
note, §9; open question Y4, §12.2), then step 2b.10 (smart prep data model), built the same day with D148–D156
(2b.10 outcome note, §9). **Step 2b.10 was approved 2026-10-12, including D148–D156 (Z1–Z4, §12.1)**: Y4 answered
with option a (a cook day that runs over is re-solved alone, the rest of the week fixed), built first with D157–D160
(2b.10 approval note, §9), vitest's per-test timeout raised to 15 s, then step 2b.7 (the new plan screens), built
the same day with D161–D167 and Not for me's storage as you chose it (Z5, migration `0010_recipe_hidden`; 2b.7
outcome note, §9). **Step 2b.7 was approved 2026-10-12, including D161–D167 and Z5 (AA1–AA8, §12.1)**: C1's
freezer extras renamed first, then **step 2b.6 before the deploy, expanded** (meal swap with 3–5 alternatives,
ingredient options, budget tiers, the cooking order); new order **2b.6 → 2b.13 (deploy) → 2b.11 → 2b.12 → 2b.8**. Step 2b.6 was
built the same day with D168–D183 (2b.6 outcome note, §9, migration `0011_price_tier`); it awaits your approval.
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
| 2b | Cook-first flow redesign | 2b.1 approved 2026-10-10 (D44–D53); 2b.2 approved 2026-10-10 (D54–D64, H1–H6); 2b.3a approved 2026-10-10 (D65–D76, J1–J6); 2b.4 approved 2026-10-10 (D77–D88, M1–M20); 2b.4 fixes approved 2026-10-10 (N1–N3); 2b.3b approved 2026-10-11 (D89–D101, P1–P8); pre-work P2–P7 done and approved 2026-10-11 (D102–D106, T1–T8); 2b.5 approved 2026-10-11 (D107–D126, U1); freeze note in the ideas pass done (D127, U2); designs for smart prep and parallel cooking approved 2026-10-11 (X1–X9; steps 2b.9–2b.13); 2b.9 approved 2026-10-11 (D128–D142, Y1–Y3); time guard built 2026-10-11 (D143–D147); 2b.10 approved 2026-10-12 (D148–D156, Z1–Z4); day repairs built 2026-10-12 (Y4, D157–D160); 2b.7 approved 2026-10-12 (D161–D167, Z5; AA1–AA8); 2b.6 (expanded: swap, ingredient options, budget tiers, the kitchen order) built 2026-10-12 (D168–D183), awaiting your approval | 2026-10-10 | | `docs/FLOW_SPEC.md`; PRD "Primary user flow"; 14 build steps, built in the order 2b.1, 2b.2, 2b.3a, **2b.4, 2b.3b**, 2b.5, then **2b.9, 2b.10, 2b.7, 2b.13 (deploy), 2b.11, 2b.12, 2b.6, 2b.8** (H3, X8; §9); changes F1–F21 approved (FLOW_SPEC §16); decisions E1–E17 (§12.1). Two-stage generation added the same day (E15, E17; built in 2b.3b). **2b.1 (backend foundations):** 898 backend tests pass (2 opt-in skipped), 78 frontend tests, ruff/mypy clean; deviations D44–D53 in the 2b.1 outcome note (§9). **2b.2 (look, shell, onboarding, Settings, Pantry):** 180 frontend tests (78 before), 899 backend tests pass (2 opt-in skipped), type checks clean, static export builds; AA contrast tested, 375 px not yet checked on a device; deviations D54–D64 in the 2b.2 outcome note (§9). Footer fix H2 done before 2b.3a. **2b.3a (ranking and cards, no LLM calls):** 964 backend tests pass (2 opt-in skipped), 187 frontend tests, ruff, mypy and type check clean; deviations D65–D76 in the 2b.3a outcome note (§9). **2b.4 (A meal now: screens, with J2–J6):** 993 backend tests pass (2 opt-in skipped), 236 frontend tests, ruff, mypy and type check clean, static export builds; migration `0006_pantry_presets`; deviations D77–D88 in the 2b.4 outcome note (§9). **2b.4 fixes (M2–M13, M15, M17, M20):** 1056 backend tests pass (2 opt-in skipped), 244 frontend tests, ruff, mypy and type check clean; no migration; 37 new draft seed recipes (47 in all); solver shortlist; fixes outcome note (§9). **2b.3b (ideas, steps, More ideas, background batch, rate-limit waits, live test, screens; with N2, ground vs whole cuts):** 1132 backend tests pass (2 opt-in skipped), 263 frontend tests, ruff, mypy and type check clean, static export builds; no migration, no new dependency; the live Groq test ran (FLOW_SPEC §15.1); deviations D89–D101 in the 2b.3b outcome note (§9). **2b.3b approval pre-work (P2–P7):** 1143 backend tests pass with `--run-slow` (3 opt-in skipped); the default run is parallel and skips 6 `slow` tests (100 s, was about 20 min); 265 frontend tests; ruff, mypy and type check clean; no migration; new dev dependency pytest-xdist (approved); `LLM_IDEAS_MODEL` (20b by default in compose); deviations D102–D106 in 2b.3b's approval note (§9). **2b.5 (meal prep engine, with T2–T4):** 1218 backend tests pass with `--run-slow` (3 opt-in skipped), 266 (265 before) frontend tests; ruff, mypy and type check clean; migration `0007_recipe_freeze_note`; no new dependency; deviations D107–D126 in the 2b.5 outcome note (§9). **2b.5 approval (U1–U5):** the ideas pass carries an optional freeze note under the seeds' rules (D127): 1218 backend tests pass in the default run (9 skipped: 6 slow, 3 opt-in), ruff and mypy clean, no migration; FLOW_SPEC §19–§21 and the proposed steps 2b.9–2b.12 (§9) are written for your review. **2b.9 (cook-day schedule):** 1353 backend tests pass in the default run (13 skipped: 8 slow, 2 perf, 3 opt-in), 1363 with `--run-slow` and the perf tests (3 opt-in skipped); 266 frontend tests; ruff, mypy and type check clean, static export builds; migration `0008_step_timing`; no new dependency; the live Groq test ran (8.3K tokens); deviations D128–D142 in the 2b.9 outcome note (§9). **Time guard (Y2):** 1361 backend tests pass in the default run (13 skipped), 266 frontend tests; ruff, mypy and type check clean; no migration, no new dependency; your dev seed week went from 245 s to 171 s with a plan marked not proven best; D143–D147 in the 2b.9 approval note (§9). **2b.10 (smart prep data model):** 1497 backend tests pass in the default run (13 skipped), 266 frontend tests; ruff, mypy and type check clean; migration `0009_smart_prep`; the FoodKeeper rows transcribed (V1); 20 draft prep items and 12 assemblies (`docs/review/prep_items.md`); deviations D148–D156 in the 2b.10 outcome note (§9). **Day repairs (Y4):** 1500 backend tests pass in the default run (14 skipped), the slow solver tests pass with `--run-slow`; ruff and mypy clean; no migration, no new dependency; your dev seed week went from 171–245 s to 61.5 s (opt-in perf test), the time guard never cutting a solve short; D157–D160 in the 2b.10 approval note (§9). **2b.7 (the new plan screens, with Not for me):** 1515 backend tests pass in the default run (14 skipped), 304 frontend tests; ruff, mypy and type check clean, static export builds; migration `0010_recipe_hidden` (Z5); later phases' migrations move up by one; deviations D161–D167 in the 2b.7 outcome note (§9). **2b.6 (expanded, AA3–AA8: meal swap, ingredient options, budget tiers, the kitchen order):** 1548 backend tests pass in the default run (14 skipped), 324 frontend tests; ruff, mypy and type check clean, static export builds; migration `0011_price_tier` (later phases' migrations move up by one); deviations D168–D183 in the 2b.6 outcome note (§9). |
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
17. **Recipes are generated in two passes (Phase 2b).**
    - **Ideas:** one call returns 5–8 ideas: ingredients and amounts, method, equipment and times, no steps. Code checks, prices and ranks them like any recipe, so they become cards at once.
    - **Steps:** written once, the first time a recipe is opened, and saved with it.
    - **Why:** each call stays inside Groq's 8K tokens a minute, and steps are written only for recipes you open. After the first More ideas tap in a search, a background batch makes later taps usually instant. `POST /plans` keeps Phase 1's complete-recipe calls (`docs/FLOW_SPEC.md` §13.5, §15).

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
│   │   ├── 0006_pantry_presets.py     # P2b (2b.4, J5): inventory_item.quantity_is_estimate, container
│   │   ├── 0007_recipe_freeze_note.py # P2b (2b.5, T3): recipe_version.freeze_note
│   │   ├── 0008_step_timing.py        # P2b (2b.9): step timing, an idea's tasks, start-to-finish cook days
│   │   ├── 0009_smart_prep.py         # P2b (2b.10): prep items, assemblies, prep batches, finish tasks
│   │   ├── 0010_recipe_hidden.py      # P2b (2b.7, Z5): recipe_hidden (Not for me, F24)
│   │   ├── 0011_price_tier.py         # P2b (2b.6, AA6): ingredient price tiers
│   │   ├── 0012_feedback_loop.py      # P3 (planned as 0003)
│   │   ├── 0013_daily_overrides.py    # P4 (planned as 0004)
│   │   ├── 0014_grocery_intelligence.py  # P5 (planned as 0005)
│   │   └── 0015_ranker.py             # P6 (planned as 0006)
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
│       │   ├── meat_forms.py · prompt_names.py   # P2b (2b.3b): ground vs whole cuts; short names for prompts
│       │   ├── prep_order.py          # P2b (2b.5): a cook day's prep order (retired in 2b.9)
│       │   ├── cook_schedule.py       # P2b (2b.9): tasks, batch growth, the cook-day schedule, the timeline
│       │   ├── prep_storage.py · assembly_text.py   # P2b (2b.10): storage per prep item and state; meal names
│       │   ├── foodkeeper.py          # P2b (2b.10): the USDA FoodKeeper rows the chart lacks, cited per row
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
│       │   │   ├── recipes/           # draft seed recipes (§13), one JSON file per recipe
│       │   │   └── prep_items/ · assemblies/   # P2b (2b.10): draft prep items and assemblies (FLOW_SPEC §19.6)
│       │   ├── loader.py
│       │   └── tests/
│       ├── llm/                       # P1: the ONLY package that knows about Groq
│       │   ├── client.py              # LLMClient protocol + GroqLLMClient (sole `import groq`)
│       │   ├── structured.py          # strict / best-effort request building, parse → validate → retry
│       │   ├── pacing.py · fake.py · prompts/ · tests/
│       ├── planning/                  # P1
│       │   ├── constraint_builder.py · resolver.py · recipe_validator.py · candidates.py
│       │   ├── rendering.py · post_solve.py · plan_validator.py · grocery_list.py · orchestrator.py
│       │   ├── ideas.py · steps.py        # P2b (2b.3b): the ideas pass and steps on first open
│       │   ├── assemblies.py              # P2b (2b.10): item portions, assemblies' numbers, names, one-item
│       │   ├── timing.py                  # P2b (2b.9): each recipe's tasks for the cook-day schedule
│       │   ├── solver/ (model.py · objective.py · absorption.py · diagnostics.py · supply.py (2b.11))
│       │   ├── smart/                 # P2b (2b.11): the smart prep model, rounding, checks, persistence
│       │   └── tests/
│       ├── auth/                      # P2: single-user passphrase session
│       ├── cook/                      # P2b: answers → requests, single-meal ranking, substitutes, search memory,
│       │                              #      ideas and More ideas (2b.3b), grocery advice reasons,
│       │                              #      prep.py · meal_prep.py (2b.5: meal-prep answers → plan request, E4)
│       │                              #      (planning/pins.py: the swap's pinned re-solve)
│       ├── feedback/ · preferences/ · substitutions/   # P3
│       ├── overrides/                 # P4
│       ├── grocery/                   # P5
│       ├── ranking/                   # P6
│       ├── api/ (deps.py · errors.py · routes/ · tests/)
│       └── testing/ (factories.py · ideas.py (2b.9) · fixtures/{usda_subset/, label_values.json, llm_responses/ (P1)})
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
| `0006_pantry_presets` | 2b (2b.4, J5) | — | `inventory_item.quantity_is_estimate`, `inventory_item.container` |
| `0007_recipe_freeze_note` | 2b (2b.5, T3) | — | `recipe_version.freeze_note` |
| `0008_step_timing` | 2b (2b.9, X1) | — | `recipe_step.component`, `.equipment`, `.hands_on_minutes`, `.hands_off_minutes`; `recipe_version.tasks`; data: start-to-finish cook-day minutes (V11) |
| `0009_smart_prep` | 2b (2b.10, X1) | assembly_component, plan_meal_component, plan_finish_task | `recipe_version.kind`, `.stages`, `.pairs_with`, `.label`; `recipe_step.stage`; `plan_cook_batch.stop_stage`, `.stop_state`, `.fridge_until`; `plan_meal.assembly_version_id` |
| `0010_recipe_hidden` | 2b (2b.7, Z5) | recipe_hidden (Not for me, F24: the same shape as recipe_favorite) | — |
| `0011_price_tier` | 2b (2b.6, AA6) | — | `ingredient.price_tier`, `ingredient.price_tier_basis` |
| `0012_feedback_loop` (planned as 0003, then 0008, then 0010, then 0011) | 3 | prepared_portion, preference_profile | `plan_meal.prepared_portion_id`, `inventory_event.prepared_portion_id` + CHECK |
| `0013_daily_overrides` (planned as 0004, then 0009, then 0011, then 0012) | 4 | day_override, consumption_entry | — |
| `0014_grocery_intelligence` (planned as 0005, then 0010, then 0012, then 0013) | 5 | region, ingredient_seasonality, cart_session | `price_observation.cart_session_id` |
| `0015_ranker` (planned as 0006, then 0011, then 0013, then 0014) | 6 | ranker_model | — |

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

recipe_version                                  -- IMMUTABLE once written (2b: an idea gets its steps once, F19)
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
  -- 0005: steps_status text NULL · 0007 (2b.5): freeze_note text NULL ("freeze the chicken and rice; make the
  -- yogurt sauce fresh")
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
ALTER recipe_version ADD steps_status text NULL -- NULL = has its steps; pending = an idea whose steps are written on
                                                -- first open, exactly once (FLOW_SPEC §13.4, F19; used from 2b.3b)
-- data: UserSettings v3 (household_size 1, always_have [], default_budget_cents null, onboarding_completed false)

-- 0006_pantry_presets (Phase 2b, step 2b.4, J5) ---------------------------------------
ALTER inventory_item ADD quantity_is_estimate bool NULL  -- "Not sure": the usual package size, to correct later
ALTER inventory_item ADD container text NULL             -- the preset's package ("bag", "head") for "your bag"

-- 0007_recipe_freeze_note (Phase 2b, step 2b.5, T3) ----------------------------------
ALTER recipe_version ADD freeze_note text NULL      -- how to freeze a recipe that freezes well; NULL = no note

-- Approved 2026-10-11 (X1; FLOW_SPEC §19.3, §20.1); the later migrations below moved up by two
-- 0008_step_timing (step 2b.9) --------------------------------------------------------
ALTER recipe_step    ADD component text NULL, ADD equipment text NULL,
                     ADD hands_on_minutes smallint NULL, ADD hands_off_minutes smallint NULL
ALTER recipe_version ADD tasks jsonb NULL           -- an idea's task list (component, equipment, minutes, temp)
-- data: saved cook-day minutes become start to finish (V11, X4)
-- 0009_smart_prep (step 2b.10) --------------------------------------------------------
ALTER recipe_version ADD kind text NOT NULL DEFAULT 'dish', ADD stages jsonb NULL,
                     ADD pairs_with text[] NULL, ADD label text NULL
ALTER recipe_step    ADD stage smallint NULL
assembly_component   (assembly_version_id FK, position, component_recipe_id FK→recipe, portions, min_portions,
                      max_portions, step; PK (assembly_version_id, position))
ALTER plan_cook_batch ADD stop_stage smallint NULL, ADD stop_state text NULL, ADD fridge_until date NULL
ALTER plan_meal       ADD assembly_version_id bigint NULL FK→recipe_version
plan_meal_component  (id, plan_meal_id FK, cook_batch_id FK, portions numeric(4,1), from_freezer bool,
                      finish_task_id NULL FK)
plan_finish_task     (id, meal_plan_id FK, day, cook_batch_id FK, kind, portions, hands_on_minutes,
                      hands_off_minutes, equipment NULL, status)
-- as built (2b.10): CHECKs min_portions <= portions <= max_portions, step IN (0.5, 1), portions > 0 and
-- minutes >= 0; finish tasks and meal components cascade with their plan and batch

-- 0010_recipe_hidden (Phase 2b, step 2b.7; Z5) -----------------------------------------
recipe_hidden        (user_id FK→app_user, recipe_id FK→recipe, created_at; PK (user_id, recipe_id))
                     -- Not for me (F24): like recipe_favorite; deleting a row is Undo (Hidden recipes)

-- 0011_price_tier (Phase 2b, step 2b.6; AA6) ----------------------------------------------
ALTER ingredient ADD price_tier text NULL        -- cheap | better | fancy; NULL = any tier (seasonings, oils)
ALTER ingredient ADD price_tier_basis text NULL  -- protein_per_dollar | named (AA6) | estimate

-- 0012_feedback_loop (Phase 3; planned as 0003, then 0008, then 0010, then 0011) -----------
prepared_portion                                -- cooked leftovers / frozen meal-prep portions
  id, user_id FK→app_user, recipe_version_id FK→recipe_version, cook_batch_id NULL FK→plan_cook_batch,
  portions smallint NN CHECK ≥ 0, portion_size text NN, location text NN (fridge | freezer),
  cooked_on date NN, use_by date NN (from the food-safety table), status text NN (available | eaten | discarded),
  created_at, updated_at

preference_profile   (id, user_id FK, computed_at, through_event_id FK→feedback_event, profile jsonb NN, schema_version)

ALTER plan_meal       ADD prepared_portion_id bigint NULL FK→prepared_portion
ALTER inventory_event ADD prepared_portion_id bigint NULL FK→prepared_portion
ALTER inventory_event ADD CHECK (inventory_item_id IS NOT NULL OR prepared_portion_id IS NOT NULL)

-- 0013_daily_overrides (Phase 4; planned as 0004, then 0009, then 0011, then 0012) --------
day_override        (id, meal_plan_id FK, day date NN, cook_minutes smallint NULL, mood text NULL,
                     slots text[] NN, reason text NULL, generation_run_id NULL FK, created_at)
consumption_entry   (id, user_id FK, consumed_on date NN, slot text NULL, plan_meal_id NULL FK, description text NN,
                     kcal integer NN CHECK ≥ 0, protein_g numeric(8,2) NULL, source text NN (planned_meal | manual | parsed),
                     is_estimate bool NN, parsed_items jsonb NULL, created_at)

-- 0014_grocery_intelligence (Phase 5; planned as 0005, then 0010, then 0012, then 0013) ---
region                 (code text PK, name text NN)
ingredient_seasonality (ingredient_id FK, region_code text FK→region.code, month smallint CHECK 1–12,
                        availability text NN (peak | available), source text NN, PK (ingredient_id, region_code, month))
cart_session           (id, user_id FK, store_id NN FK→store, started_at, ended_at NULL, status text NN)
ALTER price_observation ADD cart_session_id bigint NULL FK→cart_session

-- 0015_ranker (Phase 6; planned as 0006, then 0011, then 0013, then 0014) -----------------
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
- `protein_reward` (only with the High protein tile), capped: each day's protein earns a reward only up to 1.5 × `daily_protein_target_g`, or 1.5 × the 100 g default when the target is 0 (E11, E16);
- `allowed_purchase_ingredient_ids` (could-buy items in "use what I have" mode);
- `always_have_ingredient_ids` (unlimited owned stock);
- `pinned` (the swap's fixed meals and batches);
- calendar-week cap allowances (`cap_used_by_week`, from other plans and one-meal plans).

**As built in 2b.5:** `protein_reward`, `allowed_purchase_ingredient_ids` (None = anything may be bought),
`preferred_ingredient_ids` (could-buy items on a shopping list), `extra_lots` ("have it" with an amount, this
request only), `cap_week_use` (per Monday and cap label; the solver and validator count per calendar week) and
`daily_amount_caps` (`ResolvedDailyCap`: ingredient, base unit, usual and maximum, display unit and its size).
`PlanRequest` gains the matching optional fields (`grocery_mode`, `household_size`, `protein_reward`,
`could_buy`, `only_buy_could_buy`, `extra_lots`, `have_unlimited`, `pantry_off`, `max_portions_per_recipe`);
POST /plans keeps working unchanged. `UserSettings.daily_amount_caps` (M16) has a default (protein powder:
usually 1 scoop, at most 2), so stored settings need no migration.

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

**Phase 2b (planned, `docs/FLOW_SPEC.md` §13.5).** Two more output models in this file:
- `RecipeIdeaBatch`: ideas are `GeneratedRecipe` without steps, description, cuisine or flavor tags, plus a one-line `method`; their ingredient lines have no preparation, component or optional field.
- `RecipeSteps`: the steps for one saved idea, with `LLMStep` unchanged.

An idea plus its steps is validated as one `GeneratedRecipe`, so the step checks above are reused as they are.

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
- **No wall-clock dependence (Phase 2, K6):** in tests every MILP runs with no wall-clock cut (`conftest.py` replaces its time limit with 300 s and fails a test whose solve still stops on the clock). Single-threaded HiGHS with gap stops is deterministic, so an identical model reuses the answer within a session (tests marked `solve_cache_off` always solve). Orchestration tests that re-solve use 3-day weeks; the timed 30-candidate test is opt-in (`perf` marker, `RUN_PERF_TESTS=1`). The system clock stands still while a MILP runs, so a request's time budget never counts the solver's own seconds in tests (D146); the time guard's one real-clock test is marked `wall_clock`.
- **End of phase:** full `pytest` (and `vitest` from Phase 2) output pasted in the summary, plus the fresh-clone Docker test check (`scripts/fresh_clone_check.sh`), run after committing even when dependencies didn't change.

### 7.6 LLM budget facts (checked 2026-10-08)

- **Groq strict structured outputs:** `openai/gpt-oss-20b`, `openai/gpt-oss-120b`, `qwen/qwen3.8-27b`. **Best-effort:** those plus `openai/gpt-oss-safeguard-20b`. Neither works with streaming or tool use.
- **Published base limits** for those models: 30 req/min, 1K req/day, **8K tokens/min**, 200K tokens/day. The client reads `x-ratelimit-*`/`retry-after` rather than hardcoding limits.
- **Implications:** 2–3 recipes per call, compact prompts, low reasoning effort, a daily token guard, and the seed library plus reuse to avoid calls.
- **Phase 2b estimates** (`docs/FLOW_SPEC.md` §15, two-stage generation, E15). Cautious figures, with the "if the provider's overhead scales" figure in brackets:
  - **Per call:** an ideas call (5–8 ideas, no steps) ≈ 6.8K for meal now and ≈ 7.1K for meal prep and swap [5.6K, 6.3K]; steps for one opened recipe ≈ 4.8K [2.3K].
  - **Meal now:** 0 calls when 3 saved recipes fit well, otherwise 1 ideas call; a search never starts a background batch. The first More ideas tap makes 1 ideas call and then starts a background batch, so later taps are usually instant (≈ 6.8K [5.6K] per tap).
  - **Meal prep and swap:** 0 calls typically. A new recipe costs a steps call only when you open it.
  - **Days:**
    - a typical day ≈ 12K [8K];
    - the heavy day ≈ 75K [50K] of the 150K guard;
    - each More ideas session (a first and a second tap) adds ≈ 20K [17K];
    - background batches stop first, keeping a 30K reserve.
  - **Reasoning effort:** ideas and steps calls use the lowest effort the model supports (`LLM_REASONING_EFFORT`, `low` for `openai/gpt-oss-*`).
  - **Measured in 2b.3b (2026-10-11; FLOW_SPEC §15.1, §15.2 now use these):** an ideas call ≈ 4.7K (1.5K prompt + 3.1K for 8 ideas), a steps call ≈ 1.2K, the Phase 1 batch ≈ 4.1K. The unexplained ≈ 3.5K doesn't exist: prompts are (text + schema JSON) ÷ 4 × 1.03–1.11 plus 40–80 tokens; the ideas schema costs 519 tokens. A typical day ≈ 6K, a heavy day ≈ 37K, a More ideas session ≈ 14K.
- **Each request's prompt + maximum completion stays within 95% of the minute's limit** (the per-call sizing rule; ideas and steps size their own maximum). The 2b.3b live probe showed Groq doesn't count the maximum completion against the minute (8,114 requested against 8,000 went through); the Phase 1 HTTP 413 was the oversized prompt of a retry that re-sent the whole failed reply. The pacer still waits for prompt + maximum completion, which can only overestimate.
- **Observed in the Phase 1 live runs (2026-10-09, `openai/gpt-oss-120b`, strict):** a two-recipe batch is ~5.9K prompt + ~1.8K completion tokens, so a second call in the same minute gets a 429 (retry-after 7–39 s, handled). Strict mode still returned `json_validate_failed` once (retried as a parse error). A retry that re-sent the whole failed reply grew to 11.4K requested tokens and was refused with HTTP 413, so retries now re-send only short replies and `LLM_MAX_COMPLETION_TOKENS` defaults to 3000.

### 7.7 API and config conventions

- REST under `/api/v1`. Errors are `application/problem+json`. Long operations finish inside the request and stream `application/x-ndjson` progress (heartbeat every 5 s) ending in one result line (Phase 2, K2); every LLM call, rate-limit wait and solve fits `PLAN_TIME_BUDGET_SECONDS` (180 s): each solve's time limit is cut to what's left of the request (the time guard, D143), a solve stopped by it returns its best plan marked `proven_best: false`, and the run record keeps the solves' time (`progress["solve"]`). Phase 2b's `/cook/meal-now`, `/cook/meal-prep`, swap and `/grocery/advice` use the same pattern; meal now also streams intermediate `results` lines. This is HTTP response streaming only: LLM calls never stream (CLAUDE.md rule 6).
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

**How the steps run.** Fourteen build steps, one per session, in this order: 2b.1, 2b.2, 2b.3a, **2b.4, 2b.3b**,
2b.5, then **2b.9, 2b.10, 2b.7, 2b.13 (deploy), 2b.11, 2b.12, 2b.6, 2b.8** (X8).
- 2b.3 was split into 2b.3a and 2b.3b on 2026-10-10 (E17).
- **New order (H3, 2026-10-10):** 2b.4 (the meal-now screens) is built right after 2b.3a, with seed and saved recipes only, so you can use the new flow sooner. 2b.3b (LLM ideas, steps, background batch) follows 2b.4 and also takes the screen work that needs ideas (the countdown wait states, the held `prefetched` list, the C8 steps state). Until 2b.3b, More ideas shows disabled with "coming soon".
- The step numbers stay as they are, so earlier references still point to the right step.
- **Added and reordered at the design approval (2026-10-11, X1, X8):** the cook-day schedule (2b.9) and smart prep
  (2b.10–2b.12) from FLOW_SPEC §19–§21, and a deploy step (2b.13). To get new screens and a live link sooner, the
  plan screens (2b.7) come right after smart prep's data model (2b.10), then the deploy, then smart prep's solver
  and ideas, then swap and What should I buy?. What moved between steps because of the new order (mine, X8):
  - **2b.7 builds the plan screens for both shapes** (single-recipe meals and assemblies), so its backend part takes
    the read side of 2b.11's plan view data: each cook day's items and where they go, each meal's sources, finish
    tasks per day and meal instructions, read from 2b.10's tables. Until 2b.11 only test plans written by fixtures
    have assemblies; 2b.11 fills the same tables from the solver.
  - **Swap screens move from 2b.7 to 2b.6** (swap with progress, toast and Undo, the no-fit sheet, the "Write a new
    one" countdown, and Not for me with Hidden recipes), so 2b.6 becomes "Swap (backend and screens)".
  - **The fifth tile, Cook basics, mix and match,** is built in 2b.11 with `cook_style = "basics"`; until then C1b
    shows it disabled with "coming soon" (as H3 did for More ideas).
- Each step ends exactly like a phase: its acceptance criteria met, `pytest` (and from 2b.2 `vitest`) output shown, a commit, `scripts/fresh_clone_check.sh` after committing, a short summary, then a stop for your approval.
- Each step's session reads this section, the shared sections, and the FLOW_SPEC sections listed with the step.
- The phase-end rules in CLAUDE.md apply to every step (see §11 item 7).

#### 2b.1 Backend foundations

*Reads FLOW_SPEC §11, §13.1 (E7–E9, E11–E17), §13.3, §13.4.*

**Deliverables**
1. Migration `0005_cook_flow` (§4.5) with the settings v3 data migration (reversible, like 0002). It includes `recipe_version.steps_status` (unused until 2b.3b).
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

**2b.1 outcome (2026-10-10, approved 2026-10-10 including D44–D53).** Every deliverable and acceptance criterion is met.
898 backend tests pass (2 opt-in skipped: the live Groq call and the timed solve), 78 frontend tests pass,
ruff and mypy are clean. New tests: `db/tests/test_cook_flow_migration.py`, `services/tests/test_favorites.py`,
`services/tests/test_settings_v3.py`, `planning/tests/test_always_have.py`, `planning/tests/test_cost_split.py`,
`services/tests/test_quick_pick_amounts.py`, `domain/tests/test_dish_category.py` (+ `services/tests/test_dishes.py`);
grocery-list tests extended (water, Always have, "0 g"); `domain/tests/test_cost.py` covers the largest-remainder
split.

What changed from the plan, and why:

- **D44. `PATCH /settings` added.** The 2b.2 test "Skip sends only the onboarding flag" needs an endpoint that
  takes one field. PATCH replaces only the top-level fields sent (e.g. `{"onboarding_completed": true}`), then
  validates the whole result; PUT still takes full settings. `POST /settings/preview` takes the same partial body
  (your saved settings with the sent fields replaced), returns field errors (Pydantic and database checks),
  "1,800 of 1,800 kcal a day planned" (also while other fields are invalid) and, when valid, nine summary lines
  keyed by group (people, budget, targets, meals, cook_days, equipment, stores, food_rules, always_have) for W8.
- **D45. Dish categories: title words first.** "First match wins" is applied in two passes: the title words of
  the whole table in order, then the structural rules in order. One pass would make every seed curry a wrap (they
  have a tortilla line), while the spec's own card shows "🍛 Everyday chicken curry". "Chili" counts only as the
  dish ("turkey chili", "chili con carne"), so "chili garlic noodles" is pasta. Seed results: chicken over rice →
  bowl; air-fryer and sheet-pan chicken → roast; the three gravies → curry; both puddings → dessert; breakfast
  wraps → wrap; overnight oats → oats.
- **D46. How Always have works.** An Always-have item is treated like a staple by the solver (no purchase and no
  supply constraint: inventory already costs nothing in the objective, so unlimited owned stock needs no fake
  lot). The rounded plan keeps it as a grocery item of kind `always_have` only so the week's money counts it: it
  is never stored on the list, never shown, and its lots aren't taken or counted as expiring waste. Food eaten
  includes it at its cheapest current price when there is one; an unpriced one is simply not counted (it doesn't
  make the cost incomplete). Mark cooked doesn't deduct it. A beef item can't be Always have (422). Water is always
  Always have (`planning/inputs.py`), and lists saved before this step hide water too.
- **D47. The cost split, and where it's stored.** Each ingredient's used cents (as before) are split across the
  batches by quantity, then each batch's cost over its portions (its meals in plan order first, then the frozen
  extras), both by largest remainder. Food eaten and frozen portions now come from this split: unchanged for
  weeks without frozen extras; with them a cent can move between the two, and the balance still holds to the cent.
  `meal_plan.totals.costs` gains `batch_cents`, `meal_cents` (keyed "date/slot") and `day_cents`; plans saved before
  this step show no per-meal cost (null). Batches carry their cost too (what the meal costs add up to).
- **D48. Saved lists (E9) before pantry coverage.** Cards are most recently saved first, with the dish category,
  badges (favorite, saved, draft), `steps_ready` (always true until 2b.3b) and per-portion numbers of the recipe as
  written: kcal, protein, total minutes, and the cost at the first store in your order with a complete price ("est."
  when estimated). Coverage against your pantry arrives in 2b.3a as planned.
- **D49. Toggle details.** A ♥ or 🔖 change uses `INSERT … ON CONFLICT DO NOTHING` / `DELETE … RETURNING`, so a
  repeated or concurrent request logs one event at most. The event's `recipe_version_id` is the recipe's default
  version at that moment; its payload is an empty typed model (`BookmarkPayload`, version 1).
- **D50. Stores.** `GET /stores` lists grocery stores only, with your order (the "Other" source is never a tile);
  `POST /stores` trims the name, returns the existing store for the same name in any case (200, reactivated if it
  was inactive), refuses the "Other" source, and doesn't add the store to your order (settings do).
- **D51. Amount options.** Mass and volume options are exact fractions of the package; a pack of pieces rounds to
  whole pieces (half-up, at least one); a single piece keeps the fraction ("¼ head"); an option equal to a bigger
  one is dropped (a 2-pack has Full and ½ only). Displays are US first ("½ · 1.5 lb (680 g)", ounces under a pound,
  cups from ¼ cup, else tbsp), grams or ml only with `units: metric`. Custom units: lb, oz, g for mass; cups, fl oz,
  ml for volume; pieces for count items, plus lb, oz, g when the piece weight is known; each with a step and the
  full amount as the start. Bulk add takes exactly one of quantity + unit, `amount_option`, or `custom_amount` +
  `custom_unit`, and refuses a unit the pick doesn't offer.
- **D52. Sweet potatoes cite your decision, not a chart.** 28 days in the pantry (like russet potatoes), with the
  basis "set like russet potatoes (decision E8)". D38's items cite outside sources; I didn't look one up for this
  step.
- **D53. The timed AC 1.12 test keeps the 12 s limit.** With the production limit now 30 s (E7), the opt-in perf
  test (< 15 s) runs with the Phase 1 limit it was written for. The deadline test now expects 30.
  **Changed at approval (2b.2 pre-work):** the test now solves with the production limit
  (`SOLVER_TIME_LIMIT_SECONDS`, 30 s) and must finish within that limit plus the same 3 s headroom AC 1.12 had
  (< 33 s); it took 5.5 s on this PC.

Also: the OpenAPI schema and the generated frontend types were regenerated; the frontend test fixtures gained the
new required fields (no UI changes, 2b.2 builds the screens). `save_plan` takes a `kind` for later steps;
`POST /plans` still saves `kind = NULL`. `cook_search` and `recipe_version.steps_status` exist but are unused until
2b.3a and 2b.3b.

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

**Approved 2026-10-10, including D54–D64 (H1).** Fix at approval (H2), done at the start of the 2b.3a session: the
fixed Continue button covered content on some question screens (the hands-on minutes stepper on "When do you
cook?"). `QuestionScreen` now measures its footer (a `ResizeObserver`, so a secondary button, a footer note, the
safe area or larger iOS text all count) and keeps `--footer-height` on the screen, whose bottom padding is that
height plus a 16 px gap; the old fixed guess is only the first-paint fallback. Every question screen (onboarding
W0–W8 and every Settings editor) uses this component. Tests: `ui/QuestionScreen.test.tsx` (the measured height,
resizes, no `ResizeObserver`, controls stay out of the footer, and a layout check that the padding rule is in the
CSS and no other fixed bottom button exists) and an onboarding test that every screen, "When do you cook?"
included, reserves the footer's height.

**2b.2 outcome (2026-10-10).** Every deliverable is built and the acceptance criteria are met,
with one limit on AC 2 (below). Frontend: 180 Vitest tests pass (78 before), type check clean, the static export
builds 16 pages. Backend: one small endpoint (D54) and its test; 899 tests pass (2 opt-in skipped), ruff and mypy
clean. Pre-work: the opt-in timed solve now uses the 30 s production limit (D53, passed in 5.5 s). New tests:
`ui/Stepper.test.tsx` (bounds, hold-repeat, typing, decimal steps), `ui/GoalTiles.test.tsx` (the two-goal limit),
`ui/Segmented.test.tsx` (`aria-pressed`), `onboarding/Onboarding.test.tsx` (nine screens, the draft and one final
PUT, Skip = PATCH of the flag alone, paired screens, a new meal needs its calories, a typed store, a save error on
W8, offline), `settings/Settings.test.tsx` (strict mode hides the band, theme switch, editors save one field, errors
under the control), `pantry/AmountPicker.test.tsx` (the option key; a custom amount in the server's units),
`cook/TodayCard.test.tsx`, `ui/Blocks.test.tsx` (recipe card, Pottle's five states, building steps, empty and
error patterns, bottom sheet), `lib/theme/theme.test.ts`, `test/contrast.test.ts` (AC 2) and
`test/no-math.test.ts` (AC 3).

- **AC 1:** met (onboarding tests).
- **AC 2:** AA contrast is tested on 51 text/background pairs in both themes. The 375 px layout and 48 px targets
  are written in CSS (two-column tiles, 64 px stepper buttons, 48 px segments, chips, switches, back arrow and
  checkboxes, a 56 px bottom button) but **not checked in a real browser**: opening one is outside the repo, so it
  is on your manual checklist (the steps to open the UI are in the step summary).
- **AC 3:** met; `src/test/no-math.test.ts` scans every app source file for arithmetic on nutrition, amount or
  money values and for sums, and finds none.

What changed from the plan, and why:

- **D54. `GET /settings/always-have` (backend).** S2 needs every ingredient with common staples first, and no
  endpoint lists ingredients without a search term. Common staples are a short fixed list (salt, black pepper,
  olive and vegetable oil, white rice, garlic, onion, flour, sugar, soy sauce) plus every assume-in-stock spice;
  the rest follow by name. Water (always Always have) and beef items (refused, 422) aren't listed. Saving uses
  `PATCH /settings {always_have}`. `ALWAYS_HAVE_SLUGS` moved from `planning/inputs.py` to `services/settings.py` to
  avoid an import cycle (same value).
- **D55. Two text colors added for AA.** FLOW_SPEC §4.2's terracotta `#B5482F` measures 4.35:1 on `--accent-soft`
  and the herb green `#3F7D58` 4.33:1 on `--surface-2`, both under 4.5:1. Text on those backgrounds uses
  `--accent-ink` `#A3412A` and `--herb-ink` `#367050` (light only; dark keeps the spec colors). Fills, buttons and
  selected tiles keep the spec colors. `--herb-soft` was added for the New badge.
- **D56. How the theme is applied.** `<html data-theme>`, set by a tiny script in `<head>` before the first paint
  (no light flash for a dark choice), with the toolbar color following it. "Match my phone" follows the phone
  while the app is open. The manifest now starts at `/cook/` with the cream color.
- **D57. Which old routes redirect now.** `/` → `/cook/` and `/inventory/` → `/pantry/` (query kept). `/plan/` and
  `/day/` stay until 2b.7 retires them, because this step's Cook home links to "the existing plan view"; the Cook
  tab is highlighted there. Sign-in lands on `/cook/`.
- **D58. What onboarding saves before "Start cooking".** Only the held-item Allow switches (W7), which write the
  ingredient decision at once (FLOW_SPEC W7) and so need a connection. Everything else stays in the device draft
  (local storage, so closing the app keeps it). A store typed in on W6 stays in the draft and is created with
  `POST /stores` right before the one `PUT /settings`; until then the preview checks the draft without it, and W8
  shows the store line from the draft order.
- **D59. When the wizard runs, and how it validates.** The app shell checks `GET /settings` once per app start
  and opens `/welcome/` while `onboarding_completed` is false; `/welcome/` opens Cook home once it's done. Continue
  is checked on the phone first (bounds that mirror the API's) and then with `POST /settings/preview`. Each server
  error goes to the screen of its field; a whole-settings check is routed by its message, so "slot allocations
  exceed the daily kcal target" belongs to W3 (lowering calories on W2 doesn't block W2; W3 shows it beside the
  API's planned line). Offline you can still step through.
- **D60. Settings rows and editors.** "Calorie mode" is one row that carries the band in weekly mode ("Weekly ·
  each day within ±150 kcal"); its editor shows the band stepper only in weekly mode. Each editor saves its field
  alone with `PATCH /settings`. "Excluded and disliked" is a search with Never use / Use less (saved at once, like
  held items); frequency caps get one stepper each. Row values are the API's summary lines where one exists,
  otherwise the setting's own values, formatted.
- **D61. Money controls never add to money.** The budget ($0–$200 by $5, then No limit) and the store-split
  threshold ($0–$20 by $1) are the browser's range input in cents. The stepper's − and + work on calories, grams,
  minutes, people and custom amounts (input stepping, with the step's decimals so 0.1 + 0.2 shows 0.3); a unit
  change in the amount picker restarts from the server's value for that unit, never a conversion.
- **D62. Cook home in this step.** The greeting with Pottle, the Today card (built from `GET /plans` and
  `GET /plans/{id}`, since `GET /cook/home` is 2b.3a), then "Your plans" and "Plan a week". The Today card opens the
  existing day view. A meal now and Meal prep arrive with their screens (2b.4, 2b.7).
- **D63. Building blocks waiting for their screens.** The recipe card, building steps (with the wait countdown),
  goal tiles (the two-goal rule), chips and toggle rows are built and tested now and first appear on a screen in
  2b.4. The quick-add rate-limit countdown on the Pantry tab (FLOW_SPEC §9) needs the backend's `waiting` events
  from 2b.3b, so it lands with 2b.4's countdown work.
- **D64. Small Phase 2 touch-ups.** Every segmented control (grocery grouping, the plan form) uses the fixed
  selected state; the grocery checkboxes and `.btn-small` are now 48 px targets; the grocery header shows
  `cash_split_display` ("$37.45 groceries + $62.50 stock-up").

Also: the service worker cache is `v2` with the new pages in its shell; `ApiError` keeps the server's validation
`errors` so a field's message can sit under its control; README lists the 2b endpoints and the four tabs.

#### 2b.3a A meal now: ranking and cards (backend)

*Reads FLOW_SPEC §7 (C2–C5, C8), §13.1 (E1–E3, E9, E17), §13.2, §13.3, §13.7, §14 (ranking and the gap rule).*

**This step makes no LLM calls.** Cards come from seed and saved recipes. The gap rule is computed and recorded, and its generation step is a stub until 2b.3b.

**Deliverables**
1. `CookAnswers` and the goal mapping (`app/cook/answers.py`).
2. Ranking (`app/cook/ranking.py`):
   - filters, scaling and rounding, coverage;
   - deterministic substitutes (`app/cook/substitutes.py`);
   - score components, the never-favored rule, favorites;
   - the calendar-week pork-cap count.
3. `POST /cook/meal-now` (NDJSON):
   - ranked seed and saved results (`results` events);
   - the gap rule, with its outcome (good matches, whether ideas are needed) in the run's progress and the search;
   - the generation step as a stub that makes no call (filled in 2b.3b).
4. `cook_search`: last answers, the cache key, Same as last time; `GET /cook/home`.
5. `POST /cook/meals`: a one-meal plan (`kind = single`, validator scope "single", could-buy grocery list). Mark cooked works on it.
6. The exposure log for meal-now searches, with `selected` set when you cook one.
7. The search-context lines on `GET /recipe-versions/{id}?search=` (coverage, substitutes) and pantry coverage on the Saved lists (E9, E17).

**Acceptance criteria**
1. A card's numbers equal `GET /recipe-versions/{id}?portions=h` for the same version.
2. Beef, held items and a used-up pork cap never appear. A pork-component recipe never outranks an otherwise-equal recipe on goal, pantry or cost terms.
3. Ranking is deterministic: an identical repeat returns the cached result with the same order. Changing the pantry, answers, settings, pool or prices misses the cache.
4. The gap rule reports "ideas needed" exactly when there are fewer than 3 good matches. No request in this step makes an LLM call (FakeLLM records none).
5. A one-meal plan validates, deducts inventory on Mark cooked, and never becomes the current plan.

**Tests.**
- `cook/tests/test_ranking.py`: golden ordering, components, never-favored, cap week boundaries, more than one person, the per-meal protein cap.
- `test_substitutes.py`.
- `test_meal_now_stream.py`: event order, cache hit and miss, gap-rule outcome, 0 LLM calls.
- `test_cook_home.py`, `test_single_meal_plan.py`, `test_exposure_meal_now.py`.

**Approved 2026-10-10, including D65–D76 (J1).** Changes at approval, done at the start of the 2b.4 session: vegetable swaps only inside culinary groups (J2), and Mark cooked on a one-meal plan never takes from items you turned off (J3); see the 2b.4 outcome.

**2b.3a outcome (2026-10-10).** Every deliverable is built and every acceptance criterion is
met. Backend: 964 tests pass (899 before; 2 opt-in skipped: the live Groq call and the timed solve), ruff and mypy clean. Frontend: 187 Vitest tests pass (180 before; the 7 new ones are the H2 footer
fix), type check clean; the frontend types were regenerated from the new OpenAPI schema. No migration, no seed
change, no new dependency. New code: `app/cook/` (`answers`, `coverage`, `substitutes`, `ranking`, `caps`, `pool`,
`cards`, `search`, `stream`, `single_meal`, `saved`, `home`), `app/schemas/cook.py` and `cards.py`,
`app/api/routes/cook.py` (`GET /cook/home`, `POST /cook/meal-now`, `GET /cook/searches/{id}`, `POST /cook/meals`).
New tests (65, in `app/cook/tests/`): `test_ranking.py` (components, never-favored, filters, the protein cap,
sort, gap rule, golden orderings, the pork cap's week boundaries, two people), `test_substitutes.py`,
`test_meal_now_stream.py`, `test_cook_home.py`, `test_single_meal_plan.py`, `test_exposure_meal_now.py`.

- **AC 1:** every card's kcal, protein, minutes and cost equal `GET /recipe-versions/{id}?portions=h` (with the
  card's `portion_size`) for 1, 2 and 3 people; cards use the recipe page's own calculation, with its data loaded
  once (`CalcContext`).
- **AC 2:** beef never appears; a held item appears only once you allow it; a used-up pork cap filters the recipe
  (`frequency_cap`); a pork-component recipe ranks below an otherwise-equal one even when it is better on every
  goal, pantry and cost term.
- **AC 3:** an identical repeat returns the stored result in the same order (no new run, no new exposures);
  changing the pantry, the answers, settings, the pool (a new recipe or a favorite) or a price the cards use
  misses the cache.
- **AC 4:** "ideas needed" exactly below 3 good matches; no request makes an LLM call (the test's client factory
  fails if asked, and `llm_call` stays empty).
- **AC 5:** a one-meal plan passes the validator (scope "single"), Mark cooked deducts its lots, and it is never
  the current plan (not listed, not current, accept refused with 409, no Today card).

What changed from the plan, and why:

- **D65. Never favored: penalties take the pool's worst.** §14 says a pork-component recipe's goal, pantry, use-up
  and cost terms are zero. For the bonuses, zero is the worst value. For the penalties (missing items, could-buy
  lines, the Cheap cost term) zero is the *best* value, so a pork recipe would gain from missing nothing or
  costing little. Those terms take the eligible pool's worst value instead, so it never gains on them; the
  −0.05 tie-break is unchanged.
- **D66. Pantry substitutes: what "same role" means.** A pantry item has no role of its own, so "same role" reads
  as "your recipes use it in that role". Without that rule, tomato paste (a sauce line, category vegetable) would
  become spinach. Seasoning, garnish and "other" lines (broth, water) get no pantry substitute, since they carry
  the flavor or the structure. Each thing you have stands in for at most one line of a recipe. Amounts keep
  protein grams for a protein, kcal for a carb and mass otherwise (fat, dairy, sauce and fruit lines included),
  in the substitute's natural unit (pieces, cups or spoons, grams). **Worth a look:** the category rule still
  suggests "yellow onion → spinach" (both vegetables in your recipes). If that's too loose, I can tighten
  vegetable swaps, e.g. to the same storage place or a short hand-made list; tell me which.
- **D67. Partial stock is "short".** A line you have some of, but not enough, shows in Uses as "chicken thigh
  (some)" and adds a top-up line ("more chicken thigh · buy $5.99", `MissingLineOut.kind = top_up`). It counts
  half toward pantry fit and its top-up counts as a could-buy line and toward cash. §14 had only have, could buy
  and missing.
- **D68. The gap rule with an empty pantry.** "Uses one of your items as its protein or carb" can't hold with
  nothing in the pantry, so every search would ask for ideas. With an empty pantry, passing the filters is
  enough. Otherwise the rule is as written; with the seed library, common aromatics and oil count as missing
  unless they're in Always have.
- **D69. No goal tiles: your Settings priority, protein included.** The solver gives a protein priority no score
  (C7: it's a floor). For one meal, your Settings priority of protein uses the same capped per-meal protein term
  as the High protein tile (E11), so it can't reward more than the meal's share of 1.5 × your target.
- **D70. Card numbers and the Saved lists.** Cards are at your household's portions and your portion size. The
  Saved lists now use the same card builder, so their numbers are at those portions too (D48 had the recipe as
  written), with pantry coverage (`uses`, `missing`; `could_buy` stays empty outside a search). `SavedRecipeOut`
  gains `portion_size`, `uses`, `could_buy` and `missing`; the old card code left `services/favorites.py`.
- **D71. One-meal plans.** `PlanConstraints` gains two optional fields now (both planned for 2b.5):
  `household_size` (the meal is that many portions eaten together: the validator's portion check and the cost
  split use it) and `lots_off_ingredient_ids` (pantry items turned off for the search; the loader and the
  validator's reload skip their lots). "Have it" extras count as Always have for that plan (never bought or
  listed, not deducted). The plan is one cook day in shop mode with no limit, so whatever you lack becomes the Buy
  first list; its day mood and minutes are the search's (Fancy and 600 without one). Cook this again for the same
  search returns that plan (200) until it's cooked; a new one is made after that (201). One-meal plans aren't
  listed by `GET /plans`.
- **D72. Calendar-week caps.** Meals count Monday to Sunday in your timezone from active plans and one-meal plans.
  A one-meal plan counts once cooked, or while it's planned for today or later; an old one never cooked was
  abandoned and doesn't block the week. Cook this refuses a capped recipe once the week's allowance is used (422).
  2b.5 takes the same count into the solver and validator.
- **D73. The cache key** hashes the answers, the day, the resolved meal, people and mood, and what was loaded:
  settings, the pool (recipe, version, steps state), favorites and saved marks, diet statuses, your lots, the
  price observations of the pool's ingredients, the store order, this week's cap use and the accepted pairs. A
  hit is a new `cook_search` row pointing at the run that ranked it, so "Same as last time" stays current and
  Cook this from a cached search marks the original exposure row.
- **D74. API additions.** `GET /cook/searches/{id}` (reopen a search's results). The `result` line carries
  `cached`, `good_matches`, `ideas_needed`, `header` ("Dinner for 1 · High protein, Quick · Simple") and, when
  nothing fits, `empty_reason` and `empty_filter` (the filter that removed the most, for C5's button). Cards
  carry `good_match` and `portion_size`; cost and missing lines carry a `display` string. `GET
  /recipe-versions/{id}` gains `search_context` (with `?search=`) and `steps_ready`. The card line models live in
  `app/schemas/cards.py`, shared with the recipe schemas.
- **D75. Stream lifecycle.** `started` is sent once the search's records are saved (after the pool loads, since a
  cached result reuses the original run id). A later failure marks those same records failed and ends with a
  `failed` result carrying the problem; a failed search writes no exposures and isn't "Same as last time".
- **D76. Names and time.** Cards use canonical names ("chicken thigh, boneless skinless"); short names come with
  2b.3b's prompt names. The meal guess, today's mood and the cap week use your local time (`app_user.timezone`,
  UTC if unknown).

Also: the meal-now filter codes add `mood`; `planning/exposure.source_of` is public; `build_problem` takes the
versions to offer and `load_ingredient_plans` the lots to skip. Nothing changed in the dev database.

#### 2b.3b A meal now: ideas, steps and the background batch (backend, plus the screens that need them)

*Reads FLOW_SPEC §5.5, §7 (C5, C8), §13.1 (E2, E17–E19), §13.2 (stream events, rate-limit waits), §13.4 (`steps_status`, write-once steps), §13.5–§13.7, §14 (gap rule, background batch), §15.*

**Built after 2b.4 (H3).** Besides the backend below, it takes the screen work moved out of 2b.4 (deliverable 11) and turns on More ideas. If the step runs long, I'll stop and propose splitting the screens off rather than rush it.

**Deliverables**
1. Two-stage generation (E15, FLOW_SPEC §13.5), used by meal now here and by meal prep, swap and grocery advice from 2b.5:
   - **ideas pass:** the `recipe_ideas/1` prompt and `RecipeIdeaBatch`. Code picks the count (5–8) so the call fits, runs the idea checks, and saves passing ideas with `steps_status = pending`;
   - **short names** in every new prompt (`domain/prompt_names.py`);
   - **revision:** `idea_revision/1`, only when no idea in a batch passes;
   - **steps pass:** `recipe_steps/1` and `RecipeSteps`, validated with the idea as one `GeneratedRecipe`. Steps are written once (F19), with one call per recipe at a time;
   - **steps endpoint:** `POST /recipe-versions/{id}/steps` (E19, NDJSON) and `steps_ready` on versions and cards.
2. **Reasoning effort:** ideas, steps and idea-revision calls send `LLM_REASONING_EFFORT` at the lowest value the configured model supports. The default `low` is the lowest for `openai/gpt-oss-*`; leave it empty for a model without the setting. A rejected value raises a configuration error naming the variable, and `.env.example` explains the setting.
3. Generation in `POST /cook/meal-now` replaces the 2b.3a stub:
   - the gap rule fires one ideas call with the meal-now additions and the narrowed vocabulary;
   - checked ideas are merged into the list;
   - no background batch from a search;
   - fallbacks for the daily guard and the rate limit.
4. `POST /cook/searches/{id}/more` (E18), with F21 tightened:
   - the first tap in a search makes one ideas call and waits normally;
   - every tap then writes the next background batch (`prefetched` event), which yields to steps calls and keeps `LLM_PREFETCH_DAILY_RESERVE` (30,000) of the daily guard; a batch with no passing idea is dropped without a revision;
   - a later tap shows the held batch at once, or makes one ideas call when none is held.
5. `cook_search`: the cache key includes the held batch.
6. `POST /cook/meals` on an idea gets its steps first.
7. Held ideas are logged as exposures when More ideas shows them.
8. Friendly rate-limit waits on every LLM path: meal now, meal prep, swap, grocery advice, steps and quick-add parse (E13, FLOW_SPEC §5.5 and §13.2).
   - Before each call, the pacer checks the call's estimated tokens against the per-minute allowance left.
   - The estimate is calibrated per purpose from logged calls (the median ratio of real to estimated prompt tokens over the last 20; 2.5 until five are logged).
   - Each call keeps its prompt estimate + per-purpose `max_completion_tokens` ≤ 95% of the header limit.
   - A predicted overflow or a 429 waits and streams `waiting` with `wait_s`.
   - A wait too long for the request ends it as `partial` (`waiting` for steps) with `retry_after_s`, never as a problem error.
9. `LLM_PREFETCH_DAILY_RESERVE` in `config.py` and `.env.example`.
10. The opt-in live test (`llm/tests/test_live.py`, extended) for AC 7.
11. **Screens moved from 2b.4 (H3):**
    - C5: New badges, the "Writing new ideas…" strip, the generation-failed note, and the countdown wait state (strip and "Ready in 0:45" button; also in the Pantry quick-add sheet, D63);
    - More ideas turned on: the first tap in a search calls E18 live (strip or countdown); a later tap shows the held `prefetched` list at once (and calls E18), reads "Writing…" while the background batch is still running, and otherwise calls E18 live;
    - C8 for an idea: the method line, "Writing the steps for this one…", the countdown in the Steps section, Try again, and Cook this as "Writing steps…" until the steps land (E19).

**Acceptance criteria**
1. For an idea, a card's numbers equal `GET /recipe-versions/{id}?portions=h`, and they are identical before and after its steps are written.
2. The diet rules hold for ideas: an idea with beef, a held item or a used-up pork cap is dropped before it is shown.
3. LLM call counts (FakeLLM):
   - 3 or more good matches → 0 calls;
   - fewer → exactly 1 ideas call;
   - a search never starts a background batch;
   - the first More ideas in a search → 1 ideas call before the cards, then at most 1 background batch;
   - a later More ideas with a held batch → 0 calls before the cards, then at most 1 background batch; with none held → 1 ideas call;
   - opening an idea → 1 steps call the first time and 0 after; two opens at once → 1 call; a seed or saved recipe → 0;
   - an identical repeat → 0 calls and the same order;
   - an LLM failure → saved results plus a note, with status `partial`; a failed or skipped background batch changes nothing on screen.
4. Nothing unchecked is saved or shown:
   - ideas pass the idea checks before they are streamed;
   - steps pass the step checks, the prose filter and safety injection before they are saved;
   - steps that use an unlisted ingredient or appliance are rejected and retried with the errors.
5. Ideas, steps and idea-revision calls send the configured reasoning effort (checked on the provider request with the stub client).
6. The background batch:
   - starts only after a More ideas tap;
   - never starts while a steps call for the same user is running or waiting;
   - is skipped when it can't start within the wait limit, the time budget or the daily reserve, and is never revised;
   - is logged as exposures only once shown.
7. **The opt-in live test** makes about 4 calls (≈ 25K tokens), all with the configured reasoning effort:
   - the Phase 1 batch, one ideas call, the same ideas messages in plain JSON mode with no schema, and one steps call;
   - it reports each call's real prompt and completion tokens and the effort used;
   - it reports whether the unexplained ≈ 3.5K shrinks with the smaller ideas schema (the schema/no-schema difference, and the trend across the three schema sizes);
   - it reports whether Groq counts the maximum completion in its per-minute check.

   I record the findings in FLOW_SPEC §15.1 and update the §15 estimates to the measured case. If even 5 ideas don't fit the limit, I stop and tell you.
8. Two More ideas requests inside one minute never return an error.
   - The second one either shows the held batch, waits and finishes (a `waiting` event with a decreasing countdown), or ends `partial` with `retry_after_s` and the saved results intact.
   - The same holds for a 429 reply, and for a steps request.
   - Only the daily guard gives the "back tomorrow" note.
9. **Screens (moved from 2b.4):** every C5 and C8 idea state (writing, rate-limit wait, failed, ready) is reachable in tests; a rate-limit wait never shows the error pattern; the frontend still has no nutrition, unit or cost arithmetic (the countdown is only a timer).

**Tests.**
- `test_ideas_pass.py`: idea checks, the count choice from the token estimate, short names mapping back, revision only when none pass, the reasoning effort sent.
- `test_steps_pass.py`: step checks and retries, write-once (no other column changes), concurrent opens, numbers unchanged, 0 calls for seeds and saved recipes.
- `domain/tests/test_prompt_names.py`: the rule, and no collisions on the seed data.
- `cook/tests/test_ranking.py` (extended): an idea ranks exactly like the same recipe with steps.
- `test_meal_now_stream.py` (extended): gap-rule call counts with FakeLLM, merge, no background batch from a search.
- `test_more_ideas.py`: the first tap waits and calls; later taps show the held batch; `prefetched` events; the next batch; yielding to steps; the reserve; no revision for a background batch; exposures on reveal.
- `test_rate_limit_waits.py` (fake clock and fake rate-limit headers):
  - predicted overflow → wait; 429 → wait; too long → `partial` + `retry_after_s`; never a problem response;
  - the calibrated estimate, and prompt + maximum completion within the limit;
  - the same on the meal-prep stream, the steps stream and quick-add parse.
- `llm/tests/test_live.py` (opt-in): AC 7.
- **Vitest (moved from 2b.4):** stream reducer (new ids and New badges; a held `prefetched` list never shown before the next More ideas tap; the first tap always calls live); the countdown from `wait_s` and `retry_after_s` re-enables More ideas at zero; the C8 steps state (writing, waiting, failed, ready; Cook this disabled until ready).

**2b.3b outcome (2026-10-11).** Every deliverable is built and every acceptance criterion is met, with the
deviations below (D89–D101). Backend: 1132 tests pass (1056 at the 2b.4 fixes; 2 opt-in skipped), ruff and
mypy clean. Frontend: 263 Vitest tests pass (244 before), type check clean, the static export builds. No
migration, no new dependency. The live test ran twice against Groq (findings in FLOW_SPEC §15.1).

- **AC 1:** `test_steps_pass.py::test_nothing_else_changes_and_the_numbers_stay_the_same`: an idea's card equals
  its recipe page at the card's portions, and the page's lines, nutrition, cost, times and equipment are identical
  before and after its steps are written (only the steps and `steps_status` change).
- **AC 2:** `test_meal_now_stream.py::test_ideas_with_beef_held_items_or_a_used_up_pork_cap_are_dropped`, and the
  idea checks in `planning/tests/test_ideas_pass.py`.
- **AC 3:** with FakeLLM: 6 or more good matches make 0 calls; fewer make exactly 1 ideas call; a search never
  writes a background batch (`test_meal_now_stream.py`); the first More ideas tap makes 1 call before its cards and
  then 1 background batch; a later tap with a held batch makes 0 calls before its cards, and 1 ideas call when none
  is held (`test_more_ideas.py`); opening an idea makes 1 steps call, then 0; two opens at once make 1; seed and
  saved recipes make 0 (`test_steps_pass.py`); an identical repeat makes 0 and keeps the order; a failed call keeps
  the saved cards with a note and status `partial`; a failed or skipped background batch changes nothing on screen.
- **AC 4:** ideas pass the idea checks before they are streamed; steps pass the step checks, the prose filter and
  safety injection before they are saved; steps with an unlisted ingredient or appliance, or a storage claim, are
  retried with the errors; after the capped attempts nothing is saved and the idea stays pending.
- **AC 5:** every ideas, revision and steps request carries `reasoning_effort="low"` (checked on FakeLLM's
  requests); a value the model rejects ends as a configuration error naming LLM_REASONING_EFFORT.
- **AC 6:** `test_more_ideas.py`: the background batch starts only after a tap, waits while a steps call for you
  runs and then gives up silently, keeps the 30K reserve, is skipped when it can't start within the wait limit,
  waits for room when it can (about 50 s on the fake clock), is never revised, and its ideas are logged as
  exposures only when a tap shows them.
- **AC 7:** the opt-in live test (`llm/tests/test_live.py`) made the Phase 1 batch, one ideas call, the same ideas
  messages in plain JSON mode, one steps call and a tiny probe, all with effort `low`. Measured: Phase 1 batch
  2,428 + 1,709; ideas 1,533 + 3,117 (8 asked, 5 passed); plain JSON 1,014 (the schema costs 519); steps 710 + 526.
  The ≈ 3.5K overhead doesn't exist (prompts are about 1.03–1.11 × characters ÷ 4, plus 40–80 tokens), and Groq
  doesn't count the maximum completion against the minute (the probe asked for 8,114 of 8,000 and went through).
  8 ideas always fit. Recorded in FLOW_SPEC §15.1; §15.2 and §7.6 now use the measured case.
- **AC 8:** two More ideas taps inside a minute: the second waits with a countdown and finishes, or ends `partial`
  with `retry_after_s` and the cards untouched; the same for a 429 (short: a `waiting` line, then success; long:
  `partial`) and for a steps request (`waiting` with `retry_after_s`). Only the daily guard gives the "back
  tomorrow" note (`test_more_ideas.py`, `test_rate_limit_waits.py`, `test_steps_pass.py`).
- **AC 9:** Vitest covers every C5 and C8 idea state: the strip, the countdown strip, New badges and the toast,
  the failed-call note, More ideas live and from the held list, "Writing…", "Ready in 0:45"; the Steps section
  writing, waiting, failed, daily and offline, and Cook this held as "Writing steps…" until the steps land; the
  quick-add sheet's "Ready in 0:45". No state shows the error pattern for a rate limit, and the no-math audit
  passes (the countdown is only a timer).

**Decisions and deviations (D89–D101).**
- **D89. Ground vs whole cuts (N2).** `meat_forms` in the pantry catalog (ground: ground chicken, turkey, pork,
  beef; whole cuts: the seven chicken cuts, turkey breast, pork chop and tenderloin, sirloin, each with its bone
  and skin) and `domain/meat_forms.py`, checked in every substitute step next to M6. As built the rule is
  symmetric: neither kind stands in for, or is replaced by, something that is neither (eggs, tofu, beans, fish,
  sausage). So chicken thighs no longer stand in for salmon, shrimp or eggs on a card, and the golden ordering and
  gap-rule tests changed accordingly. Fish fillets are "neither" for now (a question in the summary).
- **D90. The pacer.** One rate state per provider and model for the whole process (a second request inside the
  minute knows what the first used), refilled at limit ÷ 60 a second. A wait over LLM_MAX_RATE_WAIT_SECONDS or the
  time budget raises `LLMWaitTooLongError` (a kind of `LLMDeadlineError`, so `POST /plans` still plans with the
  recipes saved so far); before, a long wait was cut to 60 s and slept.
- **D91. Measured estimates.** The calibration counts the schema's characters too and starts at 1.2 (the planned
  2.5 assumed the overhead the live test ruled out); an idea is 360 completion tokens, not 330.
- **D92. Salvage and short retries (live test).** Groq's strict mode still rejected about half the schema replies.
  A rejected or partly invalid ideas batch keeps the ideas that validate on their own (the rest are dropped and
  logged, like ideas that fail the checks); retries carry only the provider's schema message, never the failed
  reply. The ideas rules add "pots and pans aren't equipment" and "fresh herbs and leafy greens in grams".
- **D93. Idea checks for meal now.** The meal, mood up to yours (simpler ideas land in "Simpler options"), hands-on
  time for the mood, the Quick limit on total time, no ingredient of a cap used up this week, and complete
  nutrition. "Must use" is a prompt direction, not a check.
- **D94. The cache.** A search is re-keyed on the pool after its ideas, and after each More ideas tap (held batch
  included), so an identical repeat returns the stored result with 0 calls. `steps_status` left the pool
  fingerprint (writing steps changes no number). A partial result a repeat could fix (a pause, a failed call, the
  daily guard) is never served from the cache; "not set up" is.
- **D95. More ideas bookkeeping.** Each tap is its own run (`more_ideas`); the ideas it shows are logged under it,
  and Cook this marks the cooked recipe across all the search's runs. A cache hit carries the held batch. The
  background batch checks for a running steps call every second while it waits.
- **D96. Steps.** E19 takes the GET's query (portions, portion size, search), so its result is the recipe page
  payload. An idea's page shows no steps, not even the app's safety lines, until they are written. One call per
  recipe: a lock in the process, plus the running `recipe_steps` run for other processes (polled each second).
  Cook this on an idea writes its steps first (up to 90 s), otherwise answers 409 with `retry_after_s`.
- **D97. No LLM set up.** A search that wants ideas keeps its saved cards with "New ideas aren't set up yet (…)"
  and status `partial`; the Cook tests run with no LLM unless they script one.
- **D98. Other LLM paths.** Quick-add parse answers `status: waiting` with `retry_after_s` (HTTP 200). The plan
  stream's `waiting` lines carry `wait_s`; when new recipes would wait too long, the plan carries on with saved
  recipes, with a note and `retry_after_s`.
- **D99. Config.** LLM_TOKENS_PER_MINUTE (8000, until the header arrives) and LLM_PREFETCH_DAILY_RESERVE (30000);
  an empty LLM_REASONING_EFFORT means none; docker compose forwards LLM_REASONING_EFFORT. The API's LLM clock and
  settings are dependencies, so tests never really sleep.
- **D100. Screens.** More ideas state is kept per search outside React; "Writing…" shows only after a tap during
  the background batch (nothing else shows it); the empty state's "Write new recipes" is a More ideas tap; New
  badges come from the server, with a toast; notes are plain notices. The recipe page reloads its GET once the
  steps land.
- **D101. The live test** is one test (the Phase 1 batch, ideas, plain JSON, steps, and the probe as a fifth tiny
  call) in place of Phase 1's single-batch live test. Also: the onboarding flow test gets a 15 s timeout (1.4 s
  alone, over 5 s when every test file runs at once), and the full backend suite now takes about 20 minutes here.

**Dev database.** No migration and no seed change (the catalog's `meat_forms` is read from the seed file at
runtime). Nothing to upgrade.

**Approved 2026-10-11, including D89–D101 (P1).** The approval's pre-work (P2–P7, §12.1) was done the next
session; see the note below.

**2b.3b approval pre-work (P2–P7, 2026-10-11).** All six items are done, with tests. 2b.5 was not started
(P8: it opens with a storage question, below, and doesn't fit the same session).

- **P3, the regression (done first).** Reproduced with your dev settings (seven 45-minute cook days, Tuesday and
  Friday simple, a protein dessert, your pantry): "No plan fits". The hard filters (diet, equipment, the day's
  allowed mood, hands-on time that can fit some cook day) already ran before the shortlist (`build_problem`). The
  cause was the shortlist itself: it kept the best-scoring 3 recipes per meal whatever their hands-on minutes, so
  Monday, which cooks every one of its meals itself, got only slow ones. Each meal's shortlist now always keeps its
  quickest recipe and the quickest one its strictest cook day's mood allows; and when the shortlist finds no plan,
  the planner tries 6 per meal, then every eligible recipe, before it says no plan fits. Your week now plans
  (12 s). Tests: `test_week_always_plans.py` (default settings plus the seed library always plan a shop-mode week
  with no budget; your week plans again, with Monday within its 45 minutes) and a shortlist test. Profiling for
  P6 then showed the widening made weeks with no plan slow: each try ran the diagnostic solve, and on every
  recipe that solve outlasts any time limit (an infeasible inventory-mode test took 372 s; the budget-too-low
  test hit the 300 s test guard). Fixed: each try only checks whether a plan fits (under 0.2 s when none does),
  and the reason is worked out once, on the wider shortlist (that test now takes 16 s). With a money limit the
  planner stops at the wider shortlist (D102).
- **P4, the time/mood message.** One sentence per blocker, each said once, joined with spaces (never ".;"):
  "Monday needs 35 minutes of hands-on cooking; you set 20." and "20 recipes are medium and 6 are fancy, and your
  cook days are set to simple." (the weekday gets its date when a plan has the same weekday twice). Buttons:
  "Allow 35 min on Monday" and "Use simpler recipes" (that day's minutes or mood) or "Allow fancy recipes" (every
  cook day's mood), for this plan only (`day_overrides`; Settings don't change). The other reasons a recipe was
  left out read the same way ("19 recipes use Greek yogurt, plain nonfat, which has no price at your stores, so
  your budget can't be checked (enter a price, or plan without a budget)"; "1 recipe has incomplete nutrition
  data").
- **P2, fish and shellfish.** New swap groups: `fish_fillet` (salmon, tilapia, cod) and `shellfish` (shrimp).
  Canned tuna, eggs and tofu are in no group, so they never stand in for fish or shellfish; fish never swaps with
  chicken. One meal-now test changed with it: with chicken, rice, eggs and chickpeas in stock, the salmon and
  shrimp dishes no longer count as good matches (6, not 8; still no ideas call).
- **P5, the ideas model.** Measured with the opt-in comparison (FLOW_SPEC §15.1): `openai/gpt-oss-20b` answered
  in 3.1 s vs 6.9–7.4 s on 120b, with the same share of ideas passing (15 of 16 each). So the ideas pass has its
  own model setting, `LLM_IDEAS_MODEL`, defaulting to 20b; steps and planning stay on `LLM_MODEL`.
- **P7, the pass rate.** Each ideas call's log row carries `error_detail.ideas = {asked, returned, kept,
  pass_rate}`; a revision call's row carries its own (asked = the ideas sent back).
- **P6, test speed.** Same machine (12 logical CPUs) and the same db-test:

  | Run | Tests | Time |
  |---|---|---|
  | Before: the 2b.3b commit, one process | 1132 | 1218 s (about 20 min) |
  | Today's code, one process, every test (`-n 0 --run-slow`) | 1143 | 626 s |
  | **Default now:** `uv run pytest` (parallel, `slow` skipped) | 1137 (+6 skipped) | **100 s** |
  | Everything in parallel (`--run-slow`, as the fresh-clone check runs it) | 1143 | 305 s |

  Most of the drop from 1218 s to 626 s is the P3 fix above: infeasible weeks used to run the diagnostic solve
  on every tier. Profile (one process): the six tests now marked `slow` take 384 of the 626 s; the inventory-mode
  empty-fridge test alone takes 139 s. The first whole-week solve in a process costs 20–35 s, and identical
  solves after it reuse the answer (the test solve memo), so in parallel each worker pays for its own first one.
  `--dist worksteal` and 8 workers measured the same as the default (97–100 s).

Decisions and deviations:

- **D102. The shortlist keeps a quick recipe per meal** (P3), and the planner widens in three steps (3 per meal,
  6, everything) before "no plan fits"; the old shortlist note is gone. Two limits on "everything", both for
  speed, **for your approval**:
  - *The reason comes from the wider shortlist.* Its fixes (the minutes, the mood, the top-up) always make a
    plan, but with every recipe a smaller one might do: the inventory test's top-up reads about $82.13 where every
    recipe might allow about $79 (the diagnostic solve on every recipe didn't finish in 25 s).
  - *With a money limit* (a budget, or inventory mode's top-up) *the planner stops at the wider shortlist*, as in
    2b.4: proving that no mix of every recipe fits the money took over 300 s, while hands-on time, moods and stock
    are settled in under 0.2 s. A budget week could still miss a cheaper mix outside the shortlist. A possible
    follow-up: the shortlist also keeps each meal's cheapest recipe when there's a money limit.
- **D103. The fix buttons change this plan only** (P4): they resend the request with day overrides. "Use simpler
  recipes" sets the blocked day to simple; "Allow fancy recipes" (or medium) sets every cook day.
- **D104. A swap group decides on its own** (P2): within ground, whole cuts, fish fillets or shellfish, the
  category and role check is skipped, so cod can stand in for salmon though no recipe uses cod yet.
- **D105. Where the 20b default lives** (P5). CLAUDE.md says the model name comes from the environment and is
  never hardcoded, and an architecture test keeps model names out of app code. So the app reads
  `LLM_IDEAS_MODEL` like `LLM_MODEL` (empty = `LLM_MODEL`), and the 20b default is in `docker-compose.yml`
  (`${LLM_IDEAS_MODEL-openai/gpt-oss-20b}`) and `.env.example`, not in code. Your running stack picks it up
  after `docker compose up -d backend`; to keep ideas on `LLM_MODEL`, set `LLM_IDEAS_MODEL=` (empty) in `.env`. A
  cloud deploy needs the variable set there. The ideas pass talks to it through the same client (`OnModel`), paced
  on that model's own per-minute allowance; the run's call cap and the daily guard stay shared.
- **D106. The parallel suite** (P6). Each pytest-xdist worker gets its own database beside db-test's
  (`mealbro_test_gw0`, …, about 14 MB each), created on first use, then migrated and seeded as before. That
  takes 2–5 s per worker, so no template database was needed. The migration tests' scratch databases get the
  worker's name too. `-n auto` is in `addopts`. `-s` turns it off by itself, since a worker's prints never reach
  the terminal and the live test prints its findings; `-n 0` also runs in one process. The 6 tests marked `slow`
  are the heaviest whole-week solves, 50–150 s each when running in parallel: the inventory-mode empty-fridge,
  drink-slot generation, identical-rerun, unpriced-without-budget and budget-too-low orchestrator tests, and the
  week-two simulation. They run with `--run-slow` or `RUN_SLOW_TESTS=1`, and always in the fresh-clone check.
  The P3 regression test stays in the default run.

**Dev database.** No migration and no seed change. After pulling: `docker compose up -d backend` (it picks up
`LLM_IDEAS_MODEL`).

**For 2b.5 (asked before it starts).** Where the freeze note lives (deliverable 9): a nullable
`recipe_version.freeze_note` column (a migration; user versions and later LLM recipes can carry it) or the seed
file only (no migration; seeds only). I recommend the column.

**Pre-work approved 2026-10-11, including D102 and D105 (T1–T8, §12.1).** The D102 follow-up (T2) was built at
the start of 2b.5: with a money limit each meal's shortlist keeps its cheapest recipe per portion and its
cheapest to buy today (whole packages of what your pantry doesn't cover, for the portions one recipe would cook),
alongside the quickest ones (`planning/shortlist.py`); tests in `test_shortlist.py`, including a budget week
whose only plan uses a recipe ranked below the top 6, and an inventory week whose only plan uses the recipe the
pantry covers (the dearest per portion at shop prices). The freeze-note column (T3) and the oats (T4) are in the
2b.5 outcome note.

#### 2b.4 A meal now: screens (frontend)

*Reads FLOW_SPEC §5, §7 (C0, C2–C5, C7, C8). Built right after 2b.3a and before 2b.3b (H3), so it uses seed and saved recipes only.*

**Deliverables**
1. Cook home (C0), complete: **A meal now** and **Meal prep** are the two dominant buttons at the top, with Same as last time, Today and Saved below them (E12). Until 2b.7, **Meal prep** opens the existing plan flow (`/plan/new/`).
2. C2 goals; C3 "What do you have?": toggles, have it / could buy, typed and quick add, chips from last time.
3. Building → C5 streamed results from `POST /cook/meal-now` (seed and saved recipes), with the empty, error and stream-error states. **More ideas** is shown disabled with "coming soon" until 2b.3b.
4. C7 Saved lists.
5. C8 recipe-page actions:
   - Cook this → a one-meal plan, with a Buy first checklist when needed;
   - cooking mode (screen kept awake);
   - Mark cooked.
6. ♥ and 🔖 optimistic and queued offline.

7. **Versions of held items (J4).** When you add, toggle or plan with a held item that comes in versions, the app asks which version, with "Check the label" guidance:
   - pepperoni and salami: pork + beef (excluded), pork only (allowed, counts toward the pork cap), turkey (allowed, no pork cap), chicken (allowed, no pork cap), not sure (stays held);
   - chicken bouillon (cubes or powder): chicken, no beef listed (allowed); contains beef or beef fat (excluded); not sure (stays held).
   Each allowed version is its own ingredient with its own tags and nutrition (estimated where USDA has no exact entry, and flagged). Choosing a version never releases the generic held item. Settings shows the same choices under held items.
8. **Forms and amount presets (J5)** when adding an item to Pantry or to "What do you have?":
   - step 1, the form (fresh, frozen, canned, dried, or the forms that ingredient has), each mapped to its own ingredient entry (nutrition and shelf life differ);
   - step 2, the amount: common package sizes for that form as tap buttons, plus Custom, plus **Not sure** (the most common size, with the lot marked as estimated so you can correct it from Pantry);
   - package presets live in seed data per ingredient and form, realistic US sizes, flagged as estimates.
9. **Recipe amounts in your terms (J6):** for each ingredient you have, the recipe page says how much it uses of what you have ("uses 4 oz, about half your bag · 4 oz left after"). Mark cooked subtracts exactly that; the rest stays in Pantry for later plans and searches.

**Moved to 2b.3b (H3)**, because they need LLM ideas: New badges and the "Writing new ideas…" strip; the countdown wait state (strip, "Ready in 0:45" button, and the Pantry quick-add sheet, D63); More ideas live and the held `prefetched` list; the C8 steps state for an idea.

**Acceptance criteria**
1. The meal-now flow works end to end against the backend, with seed and saved recipes.
2. On a 375 × 667 screen, both choice buttons are fully visible without scrolling, with every Cook home section present, and nothing renders above them except the one-line greeting.
3. Every C0–C8 state that needs no LLM (loading, empty, error, offline) is reachable in tests. More ideas is disabled and says "coming soon".
4. The frontend still has no nutrition, unit or cost arithmetic.
5. **Versions (J4):** turkey pepperoni never counts toward the pork cap; pork + beef pepperoni is always excluded (even if you try to allow it); choosing a version never releases the generic held item.
6. **Presets (J5):** every ingredient you can add has presets for each of its forms; Not sure adds the most common size and marks the lot estimated; a frozen form keeps its frozen shelf life.
7. **Your terms (J6):** the recipe page's note for an item you have matches what Mark cooked takes, to the gram, and the rest stays in Pantry.

**Tests (Vitest).** Stream reducer (`results` replace the list; partial); answers → request (only toggled-off items sent); cards render server strings only; Cook home order (the two buttons first; Meal prep opens the plan flow); More ideas disabled with "coming soon"; favorites queue replay; cooking-mode navigation; the version sheet; form → preset → Not sure in the add flow.

**Tests (backend, for J2–J6).** Culinary groups (every vegetable and herb in one group; yellow onion never becomes spinach; swaps only inside a group); Mark cooked skips the lots you turned off; versions (pork cap, beef exclusion, the generic stays held); presets (coverage, Not sure, estimated flag, frozen shelf life); amounts in your terms (the note equals the deduction).

**2b.4 outcome (2026-10-10).** Every deliverable is built and every acceptance criterion is met, with the
deviations below (D77–D88). Backend: 993 tests pass (964 before; 2 opt-in skipped), ruff and mypy clean; in the
fresh-clone image the review-sheet check is skipped too, since `docs/` isn't part of the backend image.
Frontend: 236 Vitest tests pass (187 before), type check clean, the static export builds (21 pages). One
migration (`0006_pantry_presets`), 20 new seed ingredients (205 now), a new seed catalog, no new dependency.

- **AC 1:** `app/cook/tests/test_meal_now_screens.py` makes the screens' calls in order against the backend
  (Cook home, the add flow, Find recipes with an item turned off and a could-buy item, the stored search, a
  card's recipe page, Cook this, Buy first, cooking mode, Mark cooked, Cook home again); the Vitest tests cover
  each screen against those responses. Not clicked through in a browser here (sign-in needs your password).
- **AC 2:** the two choices are the first section, with only the one-line greeting before them (DOM-order test);
  each is at least 120 px tall and full width (CSS test); with the 40 px greeting and the 64 px tab bar they take
  316 px of a 667 px screen. Checked by layout budget, not yet on a 375 × 667 device.
- **AC 3:** loading, empty (with its fixes), error, stream lost and offline states are reachable in tests for C0,
  C2, C3, C5, C7, C8, Buy first and cooking mode. More ideas is disabled with "New recipe ideas: coming soon."
- **AC 4:** the no-math audit scans the new files and finds nothing; every number on screen is the server's.
- **AC 5 (J4):** `test_pantry_add.py`: turkey pepperoni never counts toward the pork cap; pork + beef pepperoni is
  excluded even if you try to allow it; relabeling a lot never releases the generic held item. Vitest: the
  version sheet (guidance, pork + beef refused, turkey continues to its own sizes, Not sure stays held).
- **AC 6 (J5):** every addable seed ingredient has presets with one default (catalog test); Not sure adds the
  default size with the lot marked estimated, and Pantry's Correct amount clears it; frozen cauliflower keeps 240
  days in the freezer. Vitest: form → size → Custom → Not sure in the add flow.
- **AC 7 (J6):** the recipe page's note for frozen broccoli ("uses 8 oz, about half your bag · 8 oz left after")
  equals what Mark cooked takes, to the gram, and the other 8 oz stays as an active lot.

**Decisions and deviations (D77–D88).**
- **D77. Culinary groups (J2).** 25 groups cover every vegetable and herb in the seed table (listed in
  `docs/review/pantry_catalog.md`). A line in a group (or any vegetable line) is swapped only inside its group,
  whatever its role, so a cilantro garnish can become parsley; one in no group, or alone in its group, gets no
  substitute. Accepted pairs still come first. The catalog's version is part of the meal-now cache key.
- **D78. Mark cooked fix (J3).** A one-meal plan stores the lots of the items you turned off
  (`lots_off_lot_ids` in its constraints; a "have it" extra of the same item isn't turned off); Mark cooked
  skips them.
- **D79. The catalog is seed data, not tables.** `app/seed/data/pantry_catalog.json` (groups, versions, forms,
  package sizes) is written by `backend/scripts/build_pantry_catalog.py`, validated on load
  (`PantryCatalogFile`) and read at runtime with a cache (`app/services/catalog.py`). The script also writes
  the review sheet; a test keeps both in step with it.
- **D80. Versions (J4).** Each version is its own ingredient: pepperoni and salami (pork + beef, pork, turkey,
  chicken) and chicken bouillon (no beef listed, contains beef). Nutrition is estimated and flagged for pork-only
  pepperoni (USDA "Salami, dry or hard, pork") and chicken pepperoni and salami (from the turkey ones).
  Choosing a version for a lot (`POST /inventory/{id}/version`) adds a lot of that version with the same amount,
  place and dates, and empties the old one (manual-adjust events). Held lots can't be toggled in C3 and offer
  "Which version?" there and in Pantry. Settings lists the versions under held items; picking your usual one is
  kept on this device and only pre-selects it in the sheet. Deli meats count as "as sold" even when USDA's
  description says cooked. Asking "when planning" lands with the meal-prep screens (2b.7).
- **D81. Forms and package sizes (J5).** Migration `0006_pantry_presets` adds `inventory_item.quantity_is_estimate`
  and `container`; the later planned migrations move up one (Phase 3 is now `0007_feedback_loop`, through
  `0010_ranker`). The add flow's sizes replace Full/¾/½/¼ in the app (the P1 picker is gone; the API's
  `amount_options` stay). **Not sure** is pre-selected, so an amount you don't pick is honest about being a guess.
  A size added without a date gets an estimated use-by from its shelf life where it's kept. Pantry corrects an
  estimate with `PATCH /inventory/{id}` and a `preset`, or a `quantity` + `unit` (the server converts). In "What
  do you have?", Have it with a size sends that amount to the search; Save to pantry adds the lot instead, which
  then shows as a pantry row.
- **D82. Your terms (J6).** The notes come from the same lots, in the same order, as Mark cooked (open packages
  first, then the soonest use-by), skipping turned-off lots: on the recipe page from a search, on a plan batch
  (`pantry_notes`) and in cooking mode. A recipe opened from a search now opens at that card's portions, so the
  notes match what Cook this cooks.
- **D83. Routes.** `/cook/results/?run=<key>` while the search streams (the answers wait in session storage under
  a one-off key, and the run lives outside React, so a remount never sends it twice), then `?search=<id>`.
  `/cook/saved/?list=`, `/cook/buy/?batch=&plan=` and `/cook/cooking/?batch=` are new; the tab bar hides in
  cooking mode; the service worker (v3) caches the new pages.
- **D84. Cook home.** `GET /cook/home` adds your household `portions` and `portion_size` (saved cards open for
  your household). Same as last time shows meal-now searches only until 2b.7. The Today card reads the home's
  `today` instead of the plan endpoints.
- **D85. Empty state.** Time: "Allow N min" (the next of 10, 15, 20, 30, 45, 60, 90, 120). Mood: the two other
  moods, because a mood filter can rule recipes out in either direction. Equipment and food rules: a link to
  Settings. "Write new recipes (coming soon)" is disabled.
- **D86. Recipe page actions.** A saved recipe's Cook this cooks up to 8 portions (the portions stepper stops at
  `CookMealIn`'s limit). On a plan batch, Cook this opens cooking mode and Mark cooked stays in the batch card.
  Buy first is the one-meal plan's grocery list, checked off with the Grocery tab's queue (a shared hook), with
  "I have everything, start cooking".
- **D87. Cooking mode.** Get ready (the ingredients, with your-terms notes), then one step per screen, then Mark
  cooked. Its Back / Next bar is sticky, not fixed, so the 2b.2 footer rule holds. The screen wake lock is asked
  for again when you come back to the page, and the top bar says "Screen stays on" while it holds.
- **D88. Also.** Settings' `diet_review` items carry their `versions`; the `IngredientSearch`, `AddFlow`,
  `VersionSheet` and `CorrectAmountSheet` components are shared by Pantry and C3; `docs/review/usda_mappings.md`
  was regenerated for the 205 ingredients.

**Dev database.** Upgraded to `0006` and re-seeded (205 ingredients). To undo: `docker compose exec -T backend uv
run --frozen alembic downgrade 0005`.

**Approved 2026-10-10, including D77–D88 (M1).** Follow-ups M2–M13, done at the start of the next session
before 2b.3b; see the fixes outcome note below and §12.1.

**Fixes outcome (2026-10-10): M2–M13, M15, M17 and M20 built; 2b.3b not started.** The fixes took the session
(M1's fallback): they are committed on their own, and 2b.3b starts next session. Tests: 1056 backend tests pass (2 opt-in skipped; 993 at 2b.4), 244 frontend tests in 35 files (236 at 2b.4), ruff, mypy and the type check clean, and the API schema matches the PWA's generated types.

- **M2 Correct amount.** Every Pantry lot has Correct amount. `GET /inventory/{id}/correct-options` gives the
  package (the lot's first stocked amount), quick taps for ¾, ½ and ¼ of it, the presets and the units for
  Custom; `PATCH /inventory/{id}` takes `package_fraction`, a `preset`, or a `quantity` + `unit`.
- **M3 Usual version.** `usual_versions` in settings (held item slug → version slug, checked against the
  catalog); Settings' held items set it and the add flow and version sheet pre-select it. The device-only
  `usualVersions.ts` is gone.
- **M4 Chicken cuts.** Five new ingredients (210 in all), each mapped to its USDA SR Legacy "meat and skin, raw"
  entry: thigh bone-in skin-on (172385), breast bone-in skin-on (171474), drumstick (172373), wing (172390),
  whole chicken (171447). The catalog's `chicken_cuts` records the bone and skin form of all seven chicken cuts;
  forms and package sizes are in the pantry catalog.
- **M5 Refuse.** `refuse` on the seed ingredient (USDA SR28 refuse: thigh 27%, kept at your review as noted in
  the seed, breast 20%, drumstick 33%, wing 38%, whole 32%) sets `edible_fraction`, which the nutrition math
  already applied; recipe pages and cooking mode now pass edible grams to the food-safety and leftover lines too.
- **M6 Strict chicken.** `domain/chicken_cuts.py` reads a stated form ("bone-in", "boneless", "skin-on",
  "skinless", and their spellings) from text. Search drops cuts that conflict with what you typed; the resolver
  never maps a line to a conflicting cut; swaps and substitutes only pair the same bone and skin form. Tests on
  all three paths.
- **M7 Close matches.** 25 close matches in the catalog (garlic paste → garlic, canned peas → frozen peas,
  naan → pita, whole wheat tortilla → chapati, …; never a chicken cut). Each works as a labeled alias: search
  finds it and shows "Closest match: …", and the resolver maps a recipe line through it with `via="close"`.
  They aren't plain aliases, so nothing passes one off as the exact item.
- **M9 Meal choice.** The question screen shows Breakfast, Lunch, Dinner, Snack, Dessert with nothing picked;
  you pick one to go on. The API still guesses from the clock when a client doesn't say (the CLI and tests).
- **M10 Mood is soft.** No mood filter: results come in three sections (your mood, "A bit more effort",
  "Simpler options"), and only your mood's recipes count as good matches for the gap rule. The mood empty
  state is gone (a mood can't empty the list now).
- **M11 Card wording.** `swaps` on cards and the recipe page's search context ("Swap: red onion instead of
  yellow onion (you have it)"); `missing` lists only things to buy; the "Uses N of your items" chip is gone.
- **M12 Card cost.** A card's numbers add "$Y to buy today" (whole packages of what's missing or short, "+
  unpriced items" when some have no price). Cheap ranks on the buy-today total as well as the portion cost.
- **M13 Seed library.** 37 drafts (47 seed recipes in all), written by `backend/scripts/build_seed_recipes_m13.py`:
  7 breakfasts, 8 lunches, 12 dinners, 5 snacks, 5 protein desserts; simple, medium and fancy. No beef, no pork
  component (the CLAUDE.md rule, flagged in M13), no held items (cheese), no blender. The 37 are listed in the
  step summary. 58 ingredients they use had no price: each got one product with an **estimated** price
  (source "estimate", flagged on cards as "est.") so cost and the Cheap goal work; replace them with real
  prices when you shop. Thirteen ingredients the new recipes moved into the top 25 of the mapping review were
  reviewed by you (38 reviewed in all) and `docs/review/usda_mappings.md` is regenerated (210 rows).
- **M15 Portion vs batch.** Recipe lines, plan batch lines and cooking mode carry `portion_note` ("1 scoop
  per portion · 4 scoops for the batch of 4") and scoop-based items show scoops everywhere, including Pantry
  ("22 scoops (682 g)"). Code computes every number (`domain/quantities.py`).
- **M17 No plan fits (the `/plan/new/` part).** The diagnostic carries `suggested_cents` (rounded up to whole
  dollars) and `items`; the screen shows one message, "Allow a $X top-up" and "Switch to shopping" buttons,
  and the items behind "See what it would buy". The `--topup` wording stays in the CLI's text report only.
- **M20 Solver shortlist.** See §12.1 M20.
- **Also: dish categories.** The new titles needed a few classifier words (FLOW_SPEC §4.4): dessert adds parfait
  and "yogurt bowl", curry adds keema and "butter chicken", new snack title words (dip, bites, chaat, "roasted
  chickpeas") are checked right after dessert's, and "burrito bowl" is a bowl. Every seed recipe's category is
  pinned in the tests.
- **Deferred:** M16 (daily amount caps) to 2b.5 deliverable 13; the meal-prep part of M17 to 2b.7; M18 and M19
  to the backlog (§12.5, Phase 4); M8 (Add from USDA) is DF1.

**Left for 2b.3b** (unchanged scope, with M14's gap rule of 6, already in the ranking code and the token
estimates): the ideas pass and its prompts (`recipe_ideas/1`, `idea_revision/1`), steps on first open (E19), More
ideas and the background batch (F21), the pacer and rate-limit waits (E13), the live token test, and the screens
that need ideas (New badges, the "Writing new ideas…" strip, countdown waits, More ideas live, the C8 steps
state).

**Dev database.** Re-seeded (210 ingredients, 47 seed recipes, 89 products, 174 prices); no migration.

**Fixes approved 2026-10-10, including every decision and deviation (N1),** with the ground-vs-whole-cut swap rule
(N2) and the mapping review (N3) recorded in §12.1. N2 was built at the start of the 2b.3b session.

#### 2b.5 Meal prep: engine (backend)

*Reads FLOW_SPEC §7 (C1, C1b, C3b, C6), §13.1 (E4, E6), §13.3, §13.5 (ideas pass), §13.6.*

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
6. Gap generation for `POST /cook/meal-prep` uses the ideas pass from 2b.3b (`recipe_ideas/1`, `idea_revision/1`; F20). `POST /plans` keeps `candidate_generation/1`.
7. **How do you want to cook? (H5, FLOW_SPEC C1b).** Four cook styles in the answers, each mapped to the plan request:
   - **One big cook day:** one cook day you pick, with its own hands-on minutes (up to 600, well above the usual per-day minutes); every batch is cooked that day.
   - **A few sessions:** the cook days you pick, each with its minutes, like the cook-day settings.
   - **Same dish, many portions:** one recipe scaled to any number of portions, cooked on the day you pick. For this request the weekly 5-portion cap (Q14) doesn't apply (F22).
   - **Mix it up:** today's behavior (your cook days and the variety rule).
8. **Fridge and freezer, per day:** portions eaten within the fridge window stay in the fridge; later portions go to the freezer, with a plain instruction to thaw in the fridge the night before. The plan states this per day (API display lines on each day and meal).
9. **Freezes well:** recipes already carry `freezer_friendly` (set on every seed and required on every LLM recipe since Phase 0/1); it is shown as "Freezes well".
   - The seed values are reviewed by hand per H5: rice dishes and curry gravies yes; yogurt sauces and fresh salads no, or yes with a note to freeze the base and add the fresh part later (for example 1a: freeze the chicken and rice; make the yogurt sauce and salad fresh).
   - Ideas carry it as a field (`RecipeIdea.freezer_friendly`), and the idea checks fail an idea without it.
   - Portions past the fridge window may only use recipes that freeze well (the existing planner rule, now also checked by the validator per portion).
   - Where the freeze note lives (a nullable `recipe_version` column in a migration, or seed data only) is settled at the start of 2b.5; I'll flag it before adding a column.
10. **Big cook day time:** code estimates the total hands-on time of every batch cooked that day and checks it against the minutes you set for that day (solver limit and validator). A day that can't fit reports the time fix ("Allow 150 min").
11. **Prep order:** each cook day gets a simple prep order where the recipes allow it, built by code from the batches' step sections and durations: what to start first (oven, rice, simmering, chilling), and what to cook while those run. A day with one batch, or with only hands-on steps, shows no order.
12. **Plan view data (H4, FLOW_SPEC C6):** the plan summary gains one `prep_notes` row ("3 to freeze · 4 may spoil") with its items, instead of a freeze and spoil block; each freeze-on-shopping-day step is also listed on the shopping day itself; days with nothing to cook keep the `cook_note` "Nothing to cook, eating prepped meals" (2b.1).
13. **Daily amount caps (M16, added at the 2b.4 approval):** a per-day amount cap setting for an ingredient, general like the frequency caps but counting the amount eaten per day instead of meals per week (`UserSettings.daily_amount_caps`: ingredient slug, a usual amount, a hard maximum). Protein powder starts at usually 1 scoop (31 g) a day, at most 2 scoops a day.
   - The solver adds a penalty for every day above the usual amount and never exceeds the maximum, counting every meal that day (overnight oats and protein pudding together); the validator checks the maximum per day.
   - Meal-now ranking (2b.3a) filters a recipe whose single portion is above the maximum.
   - Settings shows the cap (a row under Diet, with its editor).
   - Tests: a week with oats and pudding on the same day never exceeds 2 scoops that day, and prefers 1 when the protein targets are still met; a meal-now card is never above the maximum.

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
9. An uncovered slot makes one ideas call whose 5–8 ideas all reach the solver. A plan that uses an idea passes the validator, and its numbers are unchanged after that recipe's steps are written on first open.
10. **One big cook day, a whole week:** lunch and dinner for 7 days cooked on one day puts every batch on that day; their hands-on total is within that day's minutes (and too few minutes gives an infeasible plan with the time fix); every portion past the fridge window comes from the freezer, uses a freezes-well recipe, and its day says to thaw it in the fridge the night before.
11. **Same dish, many portions:** one dish for 8 portions is one batch of one recipe at 8 portions (above the 5-portion cap); the portions within the fridge window stay in the fridge and the rest are frozen; a recipe that doesn't freeze well can't fill the portions past the window.
12. **A few sessions** cooks only on the chosen days, each within its own minutes; **Mix it up** gives the same plan as today's behavior for the same request.
13. **Plan view data:** the prep notes row's counts match its items; each freeze step also appears on the shopping day; every day without a batch has the nothing-to-cook note.
14. **Prep order:** on a day with an oven batch and a stovetop batch, the oven batch starts first and the stovetop one is listed to cook while the oven runs; a day with one batch has no order.
15. **Freezes well:** every seed has its reviewed value; an idea without the field fails the idea checks.

**Tests.** `test_meal_prep_ideas.py` (one ideas call per uncovered slot, ideas in the solver, numbers unchanged after steps), `test_answers_to_request.py`, `test_household.py` (solver, validator, grocery), `test_protein_reward.py` (tile vs no tile; `test_reward_capped_at_1_5x_target`: the 1.5× plan beats the costlier 2× all-chicken plan, the term's per-day bound, below-cap monotonicity, weekly and strict modes), `test_could_buy_only.py`, `test_calendar_week_caps.py`, `test_accept_overlap.py`, a stage-order stream test. For H4 and H5: `test_cook_styles.py` (all four options, including a whole week on one big cook day and one dish for 8 portions), `test_fridge_freezer_days.py` (the per-day split and thaw lines), `test_freezes_well.py` (seed values, the idea field, the past-window rule in solver and validator), `test_big_day_time.py`, `test_prep_order.py`, `test_prep_notes.py`. K6 holds: small instances, no wall-clock dependence (the whole-week test uses a small seed pool so it solves to optimality).

**2b.5 outcome (built 2026-10-11, approved 2026-10-11 including D107–D126).** Every deliverable and acceptance criterion is met, with
tests; the pre-work follow-ups T2–T4 are in too. 1218 backend tests pass with `--run-slow` (3 opt-in
skipped), 266 (265 before) frontend tests; ruff, mypy and the type check are clean; migration
`0007_recipe_freeze_note`; no new dependency.

What was built:
- **Answers → plan request** (`app/cook/prep.py`): presets as portions or days, the start day, the four cook
  styles (one big cook day with up to 600 minutes, a few sessions, same dish for many portions with the 5-portion
  cap lifted (F22), mix it up), extra portions to freeze, pantry toggles, "have it" extras (with an amount: a
  lot for this plan only; without one: enough), could-buy items (the only purchases in "Use what I have", a small
  preference on a shopping list), the budget, the goals (High protein: priority and the capped reward; High
  carb, Iron rich: the priorities in tap order; Low calorie: 85% of each meal; Cheap: cheapest grocery mode;
  Quick: hands-on minutes per cook day) and the mood.
- **`POST /cook/meal-prep`** (`app/cook/meal_prep.py`, E4): a 422 before the stream for answers that can't make a
  plan; then the plan stream with the friendly building steps (constraints → candidates → generating → solving
  → pricing → validating). The search is remembered for "Same as last time" (Cook home shows its line); Save to
  pantry writes the lots first. Gaps use the ideas pass (`IdeaCandidates`, F20); `POST /plans` keeps
  `candidate_generation/1`. The `pricing` stage is now a real stage before validation on every run.
- **Household size** through the solver (a meal is h portions; frozen extras are single portions), the rounded
  plan, the validator and the grocery list; limits stay per person.
- **Overlap-aware accept** (E6): 409 with the overlapping plans and "Replace your current plan (Wed 14 – Fri 16,
  3 meals)?" unless `replace_overlapping=true`.
- **Calendar-week frequency caps** (F7): one cap constraint per Monday–Sunday week the plan touches, after what
  your other plans and one-meal plans already count there; the validator counts the same way.
- **Fridge and freezer per day**: each meal's `storage` and line ("From the freezer, cooked Wed 14 · thaw Sat 17
  night"), the thaw note on the day before, "Freeze 1 portion of … once cooled" on the cook day, each batch's
  fridge and freezer portions ("5 portions (4 fridge, 1 freezer)").
- **Freezes well**: the seed review and 18 freeze notes (the `freeze_note` column, T3); the validator now also
  refuses a frozen meal or frozen extras from a recipe that doesn't freeze well; ideas must carry the field.
- **Prep order** (`domain/prep_order.py`): per cook day, batches that wait start first (chilling, marinating,
  the oven, a cooker, rice, simmering), then hands-on ones "while the oven runs"; none for one batch or only
  hands-on work.
- **Plan view data** (H4): one `prep_notes` row ("3 to freeze · 4 may spoil") with its items; each shopping-day
  freeze step also on that day (`freeze_steps`); "Nothing to cook, eating prepped meals" unchanged; the meal-prep
  `header`.
- **Daily amount caps** (M16): `UserSettings.daily_amount_caps` (protein powder usually 1 scoop, at most 2); the
  solver never exceeds the maximum per day, counting every meal, and pays a penalty per scoop above the usual;
  the validator checks the maximum; meal-now filters a single portion above it; Settings has a Daily caps row
  under Diet with its editor.

Decisions and deviations:
- **D107. Seed revisions.** A changed seed file becomes a new draft version linked to the one it replaces, and
  the default, unless your own version is the default (then nothing is added and the seed report says so).
  Before, a changed file was only a warning, so the oats fix and the freezes-well review would never have
  reached your database. A field added later (`freeze_note`) counts toward a seed's content only when set.
  Your dev database got 19 revisions (the 18 freeze-note seeds and the oats). *My mistake, fixed:* the first
  re-seed revised all 47 seeds (the new field changed every hash); I removed those 47 brand-new versions (no
  plan or exposure used them) and re-seeded with the fixed hash.
- **D108. The oats (T4).** The seed was 2 scoops for 2 jars, so 1 scoop a portion already; a recipe page opened
  without a portion count shows the whole 2-jar recipe, which reads as 2 scoops. It is now a one-jar recipe:
  35 g oats, 1 scoop, 120 ml milk, 60 g Greek yogurt, 5 g chia, ½ banana optional; 374 kcal and 39.6 g protein a
  jar (was 408 kcal, 40.5 g), closer to your 325 kcal breakfast. Every seed has at most 1 scoop a portion (test).
- **D109. Protein for some of your meals.** A meal-prep plan of some of your meals gets that share of your daily
  protein target by their calories (5 lunches: 100 g × 550 / 1,800 = 31 g a day); "My usual week" keeps the
  whole target. Without this, 5 lunches would be held to a whole day's protein. The 1.5× reward cap follows it.
- **D110. Same dish with several meals** is one recipe per meal (never twice a day stays); the extra portions to
  freeze go with the first meal.
- **D111. Limits of the answers.** The cook day (big day, same dish, sessions) must be one of the plan's days;
  "N portions of a meal" goes up to 14 (the plan's 14-day limit; the rest can be extra portions to freeze).
  Both are 422s with the fix in words.
- **D112. "Use what I have"** is inventory mode where only your could-buy items may be bought, with no money
  limit unless one is sent; with no could-buy items it buys nothing. A "have it" item with an amount is a lot
  for this plan only (never in your pantry, so Mark cooked doesn't take from it and may report it as short);
  without an amount it counts as enough, like Always have for this plan.
- **D113. Calendar-week caps.** Your other active plans count only when they don't overlap the new plan
  (accepting it would replace those); one-meal plans count as in meal now (cooked, or planned for today or
  later).
- **D114. Household size** now comes from your settings for `POST /plans` too (it was always 1); yours is 1, so
  nothing changes today.
- **D115. Daily cap settings** are plain numbers (like the percentage settings), so the app keeps one settings
  type; code reads them as exact decimals in grams. The penalty is 1 point per scoop a day above the usual (about
  $2 in plan terms), so a second scoop needs a real reason; a rounding spill over the maximum is fixed by a
  re-solve, like the calorie limits.
- **D116. The protein reward** is 0.02 points per gram of a day's protein up to its cap (10 g ≈ $0.40).
- **D117. Two engine fixes found while testing** (not in the plan):
  - *A batch that can't round into the limits:* with eggs in stock, a 5-lunch big-day plan failed validation
    three times: a 4-portion egg batch moves in whole-egg steps of about 190 kcal a week, wider than the
    week's 82 kcal window, so no nudge could land it. When no nudge combination fits and a plain tightening re-solve already
    failed, the second re-solve leaves the stiffest batch out of that cook day (`snap.stepiest_batch`,
    `Tightening.forbidden`); that plan now succeeds.
  - *Short plans:* the solver kept 20 kcal of rounding room on each side of the week's limits, wider than a
    2-lunch plan's whole window (3% of 1,100 kcal), so it was infeasible by construction. Each margin is now at
    most a quarter of the window.
- **D118. Freeze notes for generated recipes.** The column is there for them, but the ideas prompt doesn't ask
  for one yet (no prompt or token change); your own versions get theirs with Phase 3's editing.
- **D119. The old plan screen** accepts with `replace_overlapping=true` (it always replaced the week's plan) until
  2b.7's sheet.
- **D120. The meal-prep header** ("5 lunches · Wed 14 – Sun 18 · High protein · Simple") is stored with the
  search and returned with the plan.
- **D121. Hands-on time per batch** doesn't grow with batch size (C1 unchanged): a 14-portion batch counts its
  recipe's active minutes. If you want big batches to take longer, that's a rule to add.
- **D122. The prep order** is per batch (which batch to start first), not per step across batches.
- **D123. The freezes-well review** (H5): 18 seeds got a freeze note; the coconut shrimp curry now freezes well (a
  curry gravy) with "reheat only once"; every other value stayed. The full table is in `test_freezes_well.py`.
- **D124. Settings summary** gets its own "Daily caps" line (the Settings row shows it).
- **D126. A money shortfall is explained from the narrow shortlist** (amends D102's first limit, **for your
  approval**). The pantry-only inventory test's "what would it take" solve took 274–281 s on the wider
  shortlist (139 s before this step: the new cheapest picks and the shrimp curry's freezer days made that
  instance harder), right at the tests' 300 s guard; on the narrow shortlist, which now always holds each meal's
  cheapest recipes (T2), it takes 37 s. The suggested top-up is a little higher: about $75.05 ("Allow a $76
  top-up") instead of $69.96; it still always makes a plan. Time and mood blockers are still explained from the
  wider shortlist. Two small related changes: the diagnostic solves stop within 1 penalty point of the best (10
  cents of a top-up, already rounded up to whole dollars), and a batch's portion bound for need sizing is now
  people × days (+20 only when extras are frozen), tighter than the old fixed 21.
- **D125. Tests** (all the plan's files, with these names): `test_answers_to_request.py`,
  `test_meal_prep_api.py` (AC 1, 2, 8, Same as last time, Save to pantry, a 2-lunch plan),
  `test_cook_styles.py` (AC 10–13, the whole week on a 5-recipe pool), `test_meal_prep_ideas.py` (AC 9),
  `test_accept_overlap.py` (AC 7), `test_household.py`, `test_protein_reward.py` (AC 3, 4, both calorie modes),
  `test_could_buy_only.py` (AC 5), `test_calendar_week_caps.py` (AC 6), `test_daily_amount_caps.py` (with the
  oats and pudding seed day), `test_daily_cap_card.py`, `test_freezes_well.py` (AC 15), `test_big_day_time.py`,
  `test_prep_order.py` (AC 14), `test_plan_view.py` (fridge, freezer, thaw and the Prep notes row; the plan-level
  checks are in the cook-style tests), `test_seed_revisions.py`, and the stepiest-batch tests in `test_snap.py`.

**Dev database.** Migrated to 0007 and re-seeded (19 seed revisions). After pulling: `docker compose up -d
backend` is enough (the code reloads).

**Approved 2026-10-11, including D107–D126 (U1).** At the approval (U2–U5, §12.1):

- **D127. The freeze note in the ideas pass (U2, built).** `RecipeIdea.freeze_note` is optional (null in strict
  mode) and follows the seeds' rules (`SeedRecipe`): 5–200 characters, only on a recipe that freezes well (a note
  without it fails that idea, and salvage keeps the others), and the prose filter, so it can't carry a storage time.
  The ideas rules now say when a dish freezes well (rice dishes, curries, gravies and cooked meats yes; mostly
  fresh, raw or creamy dishes no) and when to add a note (what to freeze, what to make fresh), which are H5's rules
  for the seeds. A passing idea saves its note on the version, so a plan's freeze lines and Prep notes show it like a
  seed's; the steps pass carries it along unchanged. The reply schema changed, so the prompts are now
  `recipe_ideas/2` and `idea_revision/2` (provenance only; pacing calibrates by purpose). Prompt size: +225 schema
  and +429 rule characters, about 170 tokens a call; a note adds about 20 completion tokens, a null about 5. This
  replaces D118. Tests: 6 new in `planning/tests/test_ideas_pass.py` (saved with the idea; the seed rules, with the
  same bounds as `SeedRecipe`; salvage keeps the others; the prose filter; the schema and rules). Default run: 1218
  passed, 9 skipped (6 slow, 3 opt-in); ruff and mypy clean; no migration.
- **Designs written for your review (U3, U4), nothing built:** smart prep, "Cook basics, mix and match" (FLOW_SPEC
  §19), and parallel cooking on a cook day (FLOW_SPEC §20). The build order, token impact and open questions V1–V17
  are in FLOW_SPEC §21; the earlier decisions they would change are F25–F32 (FLOW_SPEC §16). The proposed steps
  follow.

#### Steps 2b.9–2b.13 (approved 2026-10-11, X1–X8)

*Build order (X8): **2b.9 → 2b.10 → 2b.7 → 2b.13 (deploy) → 2b.11 → 2b.12 → 2b.6 → 2b.8**. The numbers continue
from 2b.8 so earlier references stay right (as with H3). Each step ends like a phase. Phase 2b has 14 steps; CLAUDE.md's
phase outline was updated with your OK (V16, X6). 2b.7 and 2b.6 follow below in their own sections, with the changes
the new order makes to them.*

##### 2b.9 Cook-day schedule (backend)

*Reads FLOW_SPEC §20, §21.*

**Deliverables**
1. Migration `0008_step_timing`: `recipe_step` gets `component`, `equipment`, `hands_on_minutes` and
   `hands_off_minutes`; `recipe_version` gets `tasks` (jsonb: an idea's task list). V11 is approved (X4): a
   settings data migration doubles saved cook-day minutes (at most 600) and the default becomes 90. The weeknight
   time for finish tasks (V7, X5: per day, default 30) is added to the settings here too, so 2b.7's Settings can show
   it before 2b.11 uses it.
2. Seeds: every step of the 47 seeds tagged by hand (seed revisions, D107), with a review table in the summary.
3. `domain/cook_schedule.py`:
   - tasks from tagged steps, from an idea, or estimated from untagged steps (V15);
   - batch-size growth (V12) and capacity rounds (V13, V14);
   - the list scheduler with the order search;
   - the timeline lines.
4. Solver and validator:
   - the linear per-day limits, then the exact schedule after the solve, with cuts and a re-solve;
   - the validator's check on the rounded plan;
   - the time fix in start-to-finish minutes.
5. Ideas and steps:
   - `recipe_ideas/3` and `idea_revision/3` with the task list (active and total minutes computed by code);
   - `recipe_steps/2` with the four step fields, checked against the idea's tasks;
   - the per-idea token estimate re-measured in an opt-in live test (under 20K tokens).
6. API: each cook day's `timeline`, `elapsed_minutes` and `hands_on_minutes`; `prep_order` is retired.

**Acceptance criteria**
1. The FLOW_SPEC §20.5 tests pass (three dishes on three appliances finish faster together than in sequence; two
   oven dishes overlap only when they fit together; hands never overlap; rounds; determinism; finish tasks on their
   own days).
2. Each seed's tagged hands-on total is within 5 minutes of its stated active minutes.
3. No plan passes the validator with a cook day over its minutes; the default settings and the seed library still
   plan a shop-mode week with no budget (P3's regression test).
4. An idea's numbers are unchanged after its steps arrive.

**Tests.** `domain/tests/test_cook_schedule.py`, `planning/tests/test_schedule_in_solver.py`,
`seed/tests/test_step_timing.py`, `planning/tests/test_idea_tasks.py`, `planning/tests/test_steps_timing.py`, an
opt-in timing test (a 6-dish day in under 50 ms).

**2b.9 outcome (built 2026-10-11, awaiting your approval).** Every deliverable and acceptance criterion is met, with
tests. 1363 backend tests pass with `--run-slow` and the perf tests (3 opt-in skipped; 9.5 min); the default run
passes 1353 (13 skipped: 8 slow, 2 perf, 3 opt-in) in about 2 min 15 s; 266 frontend tests; ruff, mypy and the type
check are clean and the static export builds. Migration `0008_step_timing`; no new dependency.

What was built:
- **The scheduler** (`domain/cook_schedule.py`): tasks from tagged steps, an idea's task list or an estimate
  (V15); hands-on growth (V12) and capacity rounds (V13, V14); list scheduling with the order search; the
  timeline; eating-day finish tasks on their own days (for 2b.11). FLOW_SPEC §20.6 lists the details decided while
  building.
- **Seeds:** every step of the 47 seeds tagged by hand, reviewable in `docs/review/seed_step_timing.md` (per seed
  and per step). Every tagged hands-on total is within 5 minutes of its stated active minutes (none changed).
- **Solver and validator:** start-to-finish limits per cook day (V11), the exact schedule after each solve with
  cuts and re-solves, the time fix ("Monday needs about 1 h 1 min start to finish; you set 1 h", "Allow 1 h 5 min"
  rounded up to 5), the validator's own schedule of the rounded plan (`COOK_TIME_OVER`).
- **Ideas and steps:** `recipe_ideas/3` and `idea_revision/3` with the task list (active and total minutes
  computed by code, the tasks saved on the version); `recipe_steps/2` with each step's component, appliance and
  minutes, checked against the idea's tasks; the opt-in live test (`test_task_lists_token_report`): 8 of 8
  ideas passed, 6.1K tokens for the ideas call and 2.2K for the steps call, 8.3K in all (FLOW_SPEC §21.2).
- **API:** each day's `timeline` (`at_min`, `at_display`, `text`, `kind`, `minutes`, `equipment`, `estimated`,
  plus `dish` and `cook_batch_id` for 2b.7's cooking mode) and `time_display`; `prep_order` is retired
  (`domain/prep_order.py` and its test removed).
- **Settings:** saved cook days doubled (at most 600) with `cook_time_note`, the default 90; `weeknight_minutes`
  per day (V7, default 30), added now so 2b.7's Settings can show it.

Decisions and deviations:
- **D128. The order search** tries only the dish orders that change a tie (skipping orders that swap identical
  batches) and stops at the lower bound, at most 720; a pass takes about 0.5 ms for 30 tasks, a 6-dish day well
  under 50 ms (opt-in test).
- **D129. The fridge isn't the kitchen:** a dish's last wait with no appliance in a no-cook, assembly or portioning
  step (overnight oats, puddings) counts toward when it's ready, not toward the cook day. Without this,
  overnight oats needed 8 hours of a cook day.
- **D130. Steps into tasks:** a step joins the task before it only while that task is all hands-on (hands-on
  stays at the start); storage and reheating steps aren't cook-day work.
- **D131. Estimated timing (V15):** each appliance's steps are their own part, so appliances run side by side;
  marinating belongs to the next cooking step that isn't the rice; steps with no duration share what's left of
  the hands-on minutes. A recipe with no steps is its stated minutes as one task (with no appliance, its wait sets
  in the fridge).
- **D132. Batch size** reads the portion count (household and frozen extras included); the tagged minutes cover the
  rounds the recipe's own servings need. Skillet or pot is decided per task as designed, so a curry's
  onion-browning counts as a skillet: a couple of minutes more on big batches.
- **D133. The solver's limits:** hands-on through the chord of the growth curve; per appliance, its tasks' minutes
  (the stovetop over 4 burners), portions ÷ capacity rounds of hands-off time, and the oven's portion-minutes over
  its 8 portions. A recipe fits a cook day when one meal's batch fits on its own (was: active ≤ the day's minutes).
- **D134. Cuts** are a smallest over-set of (recipe, day, size) batches (the quickest dropped first), cut on that
  day and on every cook day with no more minutes; a re-solve that finds no plan after a cut gives the time fix;
  cuts carry across the shortlist tiers and into the orchestrator's re-solves.
- **D135. Pairs kept apart before the first solve (for your approval):** pairs of batches that would run over a cook
  day together at the most portions each could cook (one meal per day it could feed, up to the variety cap). If
  that leaves no plan, the week is solved without them. Why: every cut costs a whole re-solve (25–90 s in tests);
  the cold-start seed week went from 2 solves (about 60 s) to 1 (16 s). The cost: such a pair can't share a day
  even as smaller batches, the same simplification the approved cuts make.
- **D136. Seed totals:** 11 stated start-to-finish totals differed from their own schedule by more than 5 minutes
  and now use it, rounded to 5: 1b 30 → 40, 2a 50 → 55, 2b 80 → 70, 7c 40 → 30, 7f 45 → 35, 8a 75 → 55, 8b 65 → 55,
  8c 55 → 50, 8d 90 → 115, 8g 40 → 35, 8i 110 → 130. The tandoori drumsticks (an hour's marinade, then 40 minutes in
  the oven) no longer fit a 90-minute day. The tags change every seed, so a re-seed adds 47 draft revisions (D107).
- **D137. Ideas:** a task's `component` is nullable (shared), like a step's, where §19.8 had a string; an
  appliance runs at most 4 hours and a wait with none up to 12; every listed appliance needs a task. Total minutes
  are when it's ready (a last chill included); meal prep also checks start to finish against the longest cook day
  (`max_kitchen_minutes`). The count rule uses the measured 480 tokens an idea. Ideas saved before this step have
  no task list: their stated minutes stand in, and their steps aren't checked against tasks.
- **D138. Steps:** the four fields are required on `recipe_steps/2` replies (`TimedStep`); the steps prompt lists
  the idea's TASKS; `STEPS_MAX_COMPLETION` is 1,800. Phase 1's complete recipes (`POST /plans`) keep their prompt,
  so their steps are estimated.
- **D139. The plan view computes each cook day's schedule when the plan is read**, and the day's hands-on, start to
  finish and fridge minutes come from it, also for plans made before this step.
- **D140. Wording now:** the time fix, the pre-check (a meal with no recipe only because none fits the day's time
  says the time fix, not "No dinner recipes"), the Settings summary ("1 h 30 min start to finish"), and in the
  frontend the cook-day labels, onboarding W4 and the minutes stepper (up to 600). C1b and the weeknight setting's
  screen stay in 2b.7.
- **D141. Two fixes found while testing:** the package absorption scale now comes from the exact amounts (a
  cup-rounded milk line came out 53 ml short and failed validation); the smallest top-up or budget is now the cost
  of the cheapest plan that meets every other limit (the relaxed-limit solve took over 5 minutes with 90-minute
  days; now about 25 s), which amends D126. Before a solve with a money limit, the cheapest plan's LP relaxation
  (under a second) is a floor: when even it is over the limit, the week goes straight to that explanation.
- **D142. Solve time:** with 90-minute days the weekly MILP has more ways to fill each day, so it's harder: a seed
  week takes 16–45 s in tests (about 20 s before) and a cut costs a whole re-solve (production caps each solve at
  30 s, so a plan with cuts can take a minute or two). Proving a tight budget impossible on a whole week takes the
  MILP over 5 minutes, so that test now uses 3 days (K6). The two heaviest tests (a 7-cook-day week, the plan
  stream's countdown) are marked `slow`; the fresh-clone check runs them.

**Dev database.** Migrate to 0008 and re-seed (47 seed revisions); your cook days double (45 → 90).

**2b.9 approval (2026-10-11, Y1–Y3): the time guard, built first, in its own commit.**

Measured first, on your dev settings (7 cook days of 90 minutes, 4 meals a day, no LLM): a seed week took
**245 s**. All 8 weekly solves stopped on their 30 s limit, none reaching its gap: 3 on the narrow shortlist, whose
schedules kept running over, then 5 on the wider one. The 180 s budget was checked only before each shortlist try,
so nothing stopped the run. Each solve found its last plan after 7–25 s and spent the rest trying to prove it.
HiGHS settings (less strong branching, more heuristics) found the same plans at the same times, so none changed.

- **D143. Every solve fits the request.** Each solve's time limit comes from the request's budget
  (`planning/solver/backend.py`, `SolveBudget`): its own limit, cut to what's left after 10 s kept for rounding,
  checking and saving.
  - A solve starts only with at least 5 s; polishing solves (snapping, absorption) may use the reserve and are
    skipped when it's gone.
  - It covers the weekly solves, cut re-solves, wider shortlists, the cheapest-plan fallback, the money floor,
    the explanations (top-up and budget), snapping and absorption, and 2b.11's solves to come.
  - The orchestrator sets the budget for its run (a context variable), so no time parameter is threaded through
    each solve.
- **D144. The best plan so far, marked.** A solve stopped by its limit keeps the best plan it found (`feasible`).
  - Its notes say "This is the best plan found in the time this request had; a better one may exist, so it isn't
    proven the best", and the plan summary has `proven_best: false` (for 2b.7's screens).
  - When too little time is left for the next solve, the run ends as "Planning ran out of time" (503, code
    `deadline`), saying what it was doing.
  - A plan that ran over a cook day or failed validation is never returned.
- **D145. The run record.** `generation_run.progress["solve"]` (`RunSolveRecord`, version 1):
  - seconds in the solver, solves, weekly solves and their seconds, re-solves (weekly solves after the first),
    rounding re-solves, solves stopped on time, shortened and skipped, proven best, ran out of time;
  - plus one log line per run (Vercel's function log).
  - It is JSON in the existing progress column rather than new columns, so no migration (0009 stays smart prep).
- **D146. Tests.** The suite's system clock stands still while a MILP runs (`conftest.py`), so no test can run out
  of time on a slow machine (K6). The one real-clock test is marked `wall_clock`.
- **D147. A fix found on the way.** The money floor treated an LP stopped by its time limit as solved; only a
  finished LP is a floor now.

**Result on your settings:** 171 s and a checked plan marked "not proven best" (the 6th solve, cut to 17 s, found a
plan whose schedule fit). That was luck: on Vercel's slower CPU the same week can end in "ran out of time". Planning
this week reliably inside 180 s needs a change to how the cut re-solves and shortlist tiers spend their time
(question Y4, §12.2).

##### 2b.10 Smart prep: data, storage and seed prep items (backend)

*Reads FLOW_SPEC §19.2–§19.6.*

**Deliverables**
1. Migration `0009_smart_prep` (FLOW_SPEC §19.3).
2. `domain/prep_storage.py`: storage per item and stop state (FLOW_SPEC §19.4, with V1 and V2 as answered, X2 and
   X3):
   - **V1 (X2):** the USDA FSIS FoodKeeper data is the second official source. You save `foodkeeper.json` (English)
     into `docs/sources/`; I transcribe the rows needed (cooked rice and grains, cooked vegetables, cut fresh
     vegetables, salads, sauces, and any other gaps) into the storage table, citing FoodKeeper per row. If the file
     isn't in `docs/sources/` when this step starts, cooked items keep today's 3-day rule and fresh items are made on
     the day, and I say so.
   - **V2 (X3):** partly cooked meat, poultry, fish or eggs is never stored.
3. Seed data:
   - about 16–20 draft prep items split from the seeds, with stages and timing;
   - about 10 draft assemblies;
   - every dish usable as a one-item assembly (computed, no data);
   - nutrition and cost per item portion and per assembly, by code.
4. `domain/assembly_text.py`: assembly names and the eating-day instructions (FLOW_SPEC §19.5).
5. The recipe page payload for prep items and assemblies (E17 extended).

**Acceptance criteria**
1. Every item's fridge window and freezer rule match the §19.4 table, with a test per chart row.
2. No partly cooked protein can be stored.
3. Every seed assembly has its name and instruction.
4. An assembly's numbers equal its items' portions plus its add-ons, to the kcal and the cent.

**Tests.** `domain/tests/test_prep_storage.py`, `domain/tests/test_assembly_text.py`,
`seed/tests/test_prep_items.py`, a migration test.

**2b.10 outcome (built 2026-10-11, awaiting your approval).** Every deliverable and acceptance criterion is met,
with tests. 1497 backend tests pass in the default run (13 skipped: 8 slow, 2 perf, 3 opt-in) in about 2 min 25 s;
266 frontend tests; ruff, mypy and the type check are clean (the fresh-clone check runs the slow tests and the
static export). Migration `0009_smart_prep`; no new dependency.

What was built:
- **Migration `0009_smart_prep`** as designed (FLOW_SPEC §19.3), with CHECKs: an assembly component's portions
  inside its range and its step 0.5 or 1; positive portions and minutes on finish tasks and meal components.
  Every recipe saved before it is a dish (`db/tests/test_smart_prep_migration.py`).
- **Storage per item and state** (`domain/prep_storage.py`), with the FoodKeeper rows (`domain/foodkeeper.py`):
  `foodkeeper.json` was in `docs/sources/`, so the rows were transcribed (V1, X2), each cited by its Product ID
  and checked against the file by a test (in the repo; the backend image has no `docs/`, so it skips there): 174 leftovers without meat, fish, poultry or egg; 178 cooked rice; 177
  cooked pasta; 426 cooked quinoa; and two gaps the chart also had, 148 cooked fish and 162 cooked shellfish.
  **FoodKeeper has no row for cut fresh vegetables, green salads or homemade sauces** (every Product row
  checked: only commercial cut fruit, mayonnaise deli salads and bottled sauces), so those stay made on the
  eating day. Partly cooked meat, poultry, fish or eggs is never stored (V2, X3).
- **Seed drafts:** 20 prep items split from 12 seeds, with stages and §20's timing on every step, and 12
  assemblies (two wraps, a burrito bowl, curries, rice bowls); every dish is also a one-item assembly, computed.
  The full list, with stages, storage and numbers by code: `docs/review/prep_items.md` (for your review, like
  M13's drafts).
- **Names and instructions** (`domain/assembly_text.py`): what an item brings, a composed name per shape of
  meal, and the eating-day templates (reheat to 165°F, from the freezer, a finish stage with its appliance
  setting and safe temperature, add-ons, fresh items, cold dishes).
- **Numbers** (`planning/assemblies.py`): each item's portion and each assembly by code; an assembly's are its
  items' portions plus its add-ons, to the kcal and the cent (tested for all 12).
- **Recipe page** (`GET /recipe-versions/{id}`, E17 extended): `kind`; a prep item's `prep` (label, what it brings,
  pairing styles, each stage with its storage and sources) and each step's `stage`; an assembly's `assembly`
  (name, items with portions and numbers, each opening its own page, instruction), its add-ons as its lines and
  its numbers as the page's `per_portion` and `costs`.

Decisions and deviations:
- **D148. Storage details the table left open:** eggs beaten into a raw mixture keep like the chart's raw egg
  whites and yolks (2 days, freeze); partly cooked items without meat, fish or eggs keep like cooked vegetables
  (FoodKeeper 174); a raw item whose protein has no raw row (canned tuna in a salad) is made on the day; only an
  item that is nothing but hard-cooked eggs gets their week. "Meat, poultry, fish or eggs" is a line with a safety
  category, or a protein-role line tagged as such: a broth or a fish sauce doesn't count.
- **D149. Cooked windows don't change:** with FoodKeeper every cooked item is your 3 days (each row's upper end
  at least 4); the rows add citations and the fish and shellfish rows. A grain row (rice, pasta, quinoa) applies
  only when the item is only that grain.
- **D150. A dish used as a prep item keeps as every dish does today** (your leftover days, its freezes-well
  flag), not by the line rows, so dish plans' windows are unchanged. A dish with no cooking at all (overnight
  oats, puddings) is "Serve 1 portion … cold", never reheated.
- **D151. What an item brings,** by grams per role (seasoning, fat, garnish and water left out): protein lines at
  least 25% bring protein, and with vegetables and sauce at least 40% it is a whole dish; at least 35% sauce or
  dairy is a sauce; at least 50% carbohydrate lines a base. Used only for names now.
- **D152. Names:** two shapes the table didn't have: a base that isn't a grain goes "with" ("Roast chicken
  breast with roasted root vegetables"), and a dish with a flatbread is "Chicken curry with flour tortillas"
  ("Warm 2 flour tortillas to eat with it"), not a wrap. An untitled seed assembly is named by code when it's
  saved (its title), and found again by that title on a re-seed, so renaming an item's label makes a new draft.
- **D153. Assembly money:** each item's portions times its cost per portion, rounded once per item, then the
  add-ons' cost; per store, as today. Nutrition adds up exactly and is rounded once.
- **D154. An assembly version:** base servings 1, 5 active and total minutes (its own eating-day work), no
  equipment, not frozen, its hardest item's mood, a description listing its items, no steps (its page shows the
  instruction).
- **D155. Everything that worked on dishes still sees only dishes:** the planner's candidates, meal now's
  substitute roles and ideas vocabulary, the Saved cards and the USDA mapping review's calorie shares.
  `GET /recipes/seed` lists dishes and prep items (with `kind`). A ♥ or 🔖 on an item or an assembly is saved,
  but shows in Saved only once 2b.7 and 2b.11 give them cards.
- **D156. Draft judgment calls** (in the review file): roasted asparagus doesn't freeze well; the tandoori item
  keeps the chicken's share of the seed's cumin and salt; the chopped salad adds half a cucumber; items keep
  their seed's base servings; proteins and dishes in whole portions, bases and sides in halves (V3).

**Dev database.** Migrated to 0009 and re-seeded: 20 prep items and 12 assemblies added, no dish revised.

**2b.10 approval (2026-10-12, Z1–Z4): the day repairs (Y4, option a), built first, in their own commit.**

- **D157. The repair** (`planning/solver/solve.py`). After a weekly solve whose exact schedule runs a cook day
  over, the cuts are added as before, then only the days that ran over are solved again: every other cook day's
  batches, the meals they feed and their frozen extras are fixed as the solve left them (portion nudges and
  purchases stay free), and the cuts on those fixed days are left out of the repair's model, since those days
  don't change. Up to 3 repairs in a row, each with the cuts the one before found and its own 10 s limit (a repair
  of your week takes 0.1–0.5 s). When a repair finds no plan, or the day that ran over was the only one with
  batches, the whole week is re-solved as before (at most 2 rounds), and its run gets repairs again.
- **D158. Swapped cuts.** A cut now also covers the same set with one of its batches swapped for any other batch
  the day could cook that still runs over at its smallest (one meal's worth). Why: on your week Monday kept two
  5-portion dishes (the curry gravy and the dal) and each repair cut only the third dish that tipped it over, so the
  next repair picked another third and ran over again; the swapped cuts rule them all out at once (93 s → 61 s).
  Like every cut, they ignore portions (D134).
- **D159. A repaired plan is marked not proven best** (solver status `repaired`): it is the best for the days that
  were re-solved only. Its note reads "A cook day ran over its time, so its cooking was re-planned with the rest of
  the week kept as it was; a better plan may exist, so it isn't proven the best". The run record (version 2) counts
  the repairs and their seconds; a version 1 record reads as none.
- **D160. Result on your dev settings** (7 cook days of 90 minutes, 4 meals a day, your pantry, shop mode with no
  budget; the production limits and the real clock, on this laptop): **61.5 s** of the 180 s budget, a checked
  plan, no solve shortened or skipped by the time guard. 2 weekly solves (each stopped on its own 30 s limit, so
  the plan isn't proven best either way) and 2 repairs (0.3 s): the first left Monday at 91 minutes, the second
  found no plan with the rest fixed, and the whole re-solve fit. Before: 171–245 s. The opt-in test
  (`test_a_big_week_on_your_settings_plans_well_inside_the_time_budget`, RUN_PERF_TESTS=1) asserts at most 90 s,
  half the budget. On Vercel's slower CPU the weekly solves still stop at 30 s each, so the time should be close,
  with plans found later inside each solve.
- **Z3.** Vitest's per-test timeout is 15 s (`frontend/vitest.config.ts`).

##### 2b.11 Smart prep: solver and plan (backend)

*Reads FLOW_SPEC §19.7, §19.10.*

**Deliverables**
1. `planning/solver/supply.py`, factored out of `model.py` with no change in behavior (every existing test passes
   unchanged).
2. `planning/smart/`: the shortlist and code's own combinations, the model, rounding, the validator's `smart`
   checks, and persistence (`plan_meal_component`, `plan_finish_task`).
3. `cook_style = "basics"` in `CookAnswers`; `POST /cook/meal-prep` builds it from the seed pool with 0 LLM calls.
   C1b's fifth tile, Cook basics, mix and match, is enabled (shown "coming soon" since 2b.7; X8).
4. Plan view data: the solver's plans fill the tables 2b.7's screens already read (items per cook day and where they
   go, finish tasks per day, meal instructions; X8), plus the shopping list with add-ons; Mark cooked on prep
   batches; Done on finish tasks.

**Acceptance criteria**
1. "Lunch and dinner Mon–Thu, cooking Sunday" from the seeds:
   - every prep batch feeds at least 2 meals and no portion is past its window;
   - every day meets its calories and protein;
   - it uses one cook session when one fits;
   - marinated items are finished within their window or frozen;
   - variety per V5.
2. With a pork item, the pork cap holds; protein powder never exceeds its daily maximum.
3. A household of 2 doubles yields and purchases.
4. It solves in under 10 s on the seed pool, deterministically (K6).
5. Cash + from inventory = eaten + frozen + leftover, to the cent.

**Tests.** `planning/smart/tests/` (model, windows and freezer, uses, variety, effort objective, caps,
household, rounding and validator), `test_supply_refactor.py` (the old model unchanged), API tests.

##### 2b.12 Smart prep: ideas (backend)

*Reads FLOW_SPEC §19.8, §21.2.*

**Deliverables**
1. `prep_ideas/1`, `prep_idea_revision/1` and `prep_steps/1`, with their checks, salvage and pacing.
2. The smart prep gap rule.
3. An opt-in live test (about 15K tokens).

**Acceptance criteria**
1. A gap makes one prep ideas call whose passing items and assemblies all reach the solver.
2. A failing item drops its assemblies; a failing assembly drops alone.
3. A plan's numbers are unchanged after an item's steps are written.

**Tests.** `planning/tests/test_prep_ideas.py`, `planning/tests/test_prep_steps.py`, the live test.

##### 2b.13 Deploy: Vercel + Neon (after 2b.7, X8)

*Reads `docs/deploy.md`, `docs/hosting.md`, §12.4.*

**Deliverables**
1. The pre-deploy list (§12.4), starting with PD1: the login rate limit keyed on the real client address.
2. A dry run of `docs/deploy.md` from the repo side: the Vercel build (`python -m app.deploy`, the static export),
   migrations through `0009` on a fresh database, the USDA import and the seed, with the doc corrected where it's
   wrong.
3. The live deploy, with you: you create the Neon and Vercel accounts, the GitHub remote and the secrets (anything
   outside the repo is yours to do or approve); I walk through each step and check `/health`, sign-in, a meal-now
   search and a meal-prep plan on the live link.

**Acceptance criteria**
1. PD1's tests pass: two clients behind the proxy get separate counters, and a client can't pick its own key by
   sending the header.
2. The live link serves the PWA over https, `/health` is ok, sign-in works, and a meal-prep plan finishes inside the
   request (K2).
3. `docs/deploy.md` matches what was actually done.

**Tests.** The PD1 tests; the deploy smoke checks are listed in the summary (manual, on the live link).

#### 2b.6 Swap (backend)

*Reads FLOW_SPEC §7 (C6 swap), §13.1 (E5), §13.3 (pinned re-solve), §15.*

**Deliverables**
1. `planning/pins.py`.
2. `POST /plans/{id}/meals/{meal_id}/swap`:
   - takes the swapped-away list and tries the saved pool first;
   - uses the LLM (`allow_llm`) only after "Write a new one": one ideas call (F20), whose unused ideas join the pool for the next swap;
   - writes a new plan version that supersedes the old one, carrying grocery check-offs over;
   - after shopping, runs in inventory mode with Allow buying;
   - keeps cooked batches fixed and returns `also_changed` lines;
   - Undo re-accepts the previous plan.
3. A `meal_swapped` event; exposure rows under `swap`.

**Acceptance criteria**
1. Every other `plan_meal` keeps its recipe, day, slot and portion size. Only the batches that fed the swapped meal (or one new batch) change, and the new plan passes the full validator.
2. Repeated swaps never return a recipe already swapped away for that meal; when none is left, "no other fits" comes back with 0 LLM calls.
3. "Write a new one" makes at most 1 ideas call (plus at most 1 idea revision); the swapped-in recipe's steps are written when it's first opened. A later swap of the same meal can use that call's other ideas with 0 calls. If the call has to wait for the per-minute limit, the swap stream shows the wait (`wait_s`), not an error.
4. Undo restores the previous plan exactly (identical summary).
5. After Done shopping, a swap buys nothing unless you allow it.

**Tests.** `test_pins.py` (a diff test like Phase 4 AC 1); `test_swap_api.py` (cycling, none fits, LLM gating, undo, check-off carry-over, after shopping); event and exposure rows.

**Changes (approved 2026-10-11, X1, X8; FLOW_SPEC §19.9, F32):**
- **The swap screens move here from 2b.7 (X8):** Swap with progress, toast and Undo, the no-fit sheet, the "Write a
  new one" countdown, and Not for me with Hidden recipes in Settings. 2b.7's acceptance criterion "swap and undo
  work from the UI" and its swap Vitest tests (optimistic states and undo) are this step's.
- Swap also works on a smart prep meal (an assembly): other meals keep their assemblies and portions; combinations
  of items already in the plan are tried first; at least 2 uses becomes a penalty in a swap.
- **Swap this item** on a prep item.
- Not for me (F24) on dishes, assemblies and prep items, with Hidden recipes listing all three. *Built in 2b.7 instead
  (Z4, Z5: `recipe_hidden`, the recipe page, the meal row's ⋯ sheet and Settings); 2b.6 puts Swap in that sheet, and
  2b.11 makes a hidden prep item hide its assemblies.*
- The cook-day time check goes through the schedule (2b.9).
- "Write a new one" uses the ideas pass for dish plans and the prep ideas pass (2b.12) for smart prep.

**2b.6 outcome (built 2026-10-12 with AA2–AA8, awaiting your approval).** All four parts (A swap, B ingredient
options, C budget tiers, D the kitchen order) and the C1 fix are built, with tests; committed in three parts
(swap, freezer label and kitchen order; ingredient options; budget tiers). 1548 backend tests pass in the default run (14 skipped: slow, perf and opt-in), 324 frontend tests (304 before); ruff, mypy and the type check are clean and the static export builds. Migration `0011_price_tier`;
no new dependency.

What was built:
- **C1 (AA2):** "Cook extra for the freezer (future weeks)", with "Extra portions go straight into the freezer for
  later weeks; they aren't part of this plan's meals." It starts at 0 (unchanged default, now tested).
- **A. Swap (E5, AA4):** `planning/pins.py`, the pinned re-solve (every other meal keeps its recipe, day, slot and
  portion size, every other batch its recipe, day and multiplier; only the swapped meal's slot is free; every limit
  and the exact cook-day schedule hold); `POST /plans/{id}/meals/{meal_id}/swap-options` (NDJSON: 3–5 options sorted
  by what each adds to the groceries, then protein; recipes already swapped away left out; Write a new one makes one
  ideas call, a wait shown as a countdown; after Done shopping, options use your pantry unless Allow buying);
  `POST …/swap` (a new plan version that supersedes the old one: same status, check-offs carried over, cooked
  batches kept as cooked, `meal_swapped` event, exposures under a `swap` run); `POST /plans/{id}/swap/undo`. Screens:
  ⇄ Swap on each dish meal from today on and in its ⋯ sheet, the options sheet, the highlighted new meal and the
  toast with Undo.
- **B. Ingredient options (AA5, AA8):** each recipe line (recipe pages and plan batches) has a ⋯ with Swap it,
  Leave it out, I'm out of this (swap it, or Add to shopping list) and Never use this. An edit saves your own
  version (`POST /recipe-versions/{id}/edits`); Rewrite steps for this change (`…/rewrite-steps`, one LLM call on
  tap); Also update this week's plan (`POST /plans/{id}/batches/{batch}/use-version`, with Undo); Add to shopping
  list (`…/lines/{line}/add-to-list`); Settings → Diet → **Foods I don't eat** with Allow again.
- **C. Budget tiers (AA6, AA8):** `ingredient.price_tier` and `price_tier_basis` in the seed data (review sheet
  `docs/review/price_tiers.md`); a plan's `price_tier` limits what it buys and sets its variety; `POST
  /cook/meal-prep/tiers` for the three cards; the shopping step's cards with Set my own limit.
- **D. The kitchen order (AA7):** every schedule chops and marinates first, cooks the longest chain next and the
  rest while it runs, and portions last, with a test on a three-dish day and a property test on 300 random days.

Decisions and deviations:
- **D168. Swap's options are the pinned re-solve's best fits, one recipe after another** (the best fit, then the
  best without that recipe, …, up to 5). Each shows its own rounded kcal and protein, its cost a portion, and the
  groceries it adds against keeping the meal (the solver's estimate: "+$1.20 groceries"). Sorted by that, then by
  protein; after Write a new one the new ideas come first.
- **D169. A swap may also take one more meal from an uncooked batch already in the plan** (§13.3 allowed only the
  batch that fed the meal or one new batch): it saves a pan; the option says "From Mon 12's Chicken curry" and lists
  the batch growing under Also changes.
- **D170. A swap is a new plan version; Undo restores the old one exactly** (identical summary). Undo is refused
  once you've cooked or done the shopping since.
- **D171. After Done shopping a swap plans from your pantry** (inventory mode, nothing bought); Allow buying plans
  in shop mode without a limit, each option listing what it would buy. What a cooked batch used is counted back as
  stock for the re-solve, since Mark cooked already took it from your pantry.
- **D172. A swap keeps the plan's own meals valid when your rules changed since** (a food you stopped eating, a
  recipe you hid): the batches it keeps aren't failed for it, while everything it brings in is checked against
  your rules as they are now. Pantry items turned off for the plan stay off by lot (the lots you had then), so what
  the plan bought since can be used.
- **D173. A meal from a cooked batch:** the batch stays exactly as cooked, with the freed portion ("Extra portion
  of Curry: eat it another day or freeze it.").
- **D174. Swapping a mix-and-match meal and Swap this item** wait for smart prep's solver (2b.11): the sheet says
  so.
- **D175. Swap it** offers up to 6 allowed ingredients, whether you have them or not, by the existing substitute
  rules (culinary group for vegetables and herbs, chicken by bone and skin, ground never for a whole cut, role and
  category otherwise); pork components (never favored) aren't offered. **Leave it out** is for optional lines,
  garnishes, seasonings, and onions, garlic, ginger, herbs, bay or chillies at most a tenth of the dish's weight; it
  warns when protein drops 5 g or a fifth a portion, or calories 80 kcal or 15%.
- **D176. Your version** is a new recipe_version (parent the one you edited, created by you, not a draft) and the
  recipe's default. Its steps are copied with the names swapped by code; a swap that changes how the food cooks (a
  different cut of meat or fish, frozen for fresh, canned for fresh or dried) flags the steps that name it or check
  its doneness; Rewrite steps makes one more version with the same lines and timing whose steps the steps pass
  writes on first open (its times stay those of the tasks).
- **D177. Also update this week's plan** re-solves the plan with that batch on your version (same day and size,
  every meal it fed) and everything else pinned; "re-solve the batch's portions" is its portion size within the
  plan's ±10% nudge. When none fits it says what a portion would be and that the plan keeps the recipe. Cooked or
  past batches keep theirs.
- **D178. I'm out of this → Add to shopping list** puts the cheapest whole packages of what the plan's batch uses
  (or the recipe as written) on the shopping list of the plan you came from, else your current plan; once per
  item, never on a finished trip.
- **D179. Foods I don't eat** is the existing exclude preference (Phase 0's ingredient_preference): the editor
  "Excluded and disliked" is renamed, beef is shown first, and each item has Allow again. Plans, searches and
  ideas already left excluded items out.
- **D180. The price tiers** (121 ingredients tiered, 85 in any tier): protein per dollar decides for the foods
  bought for protein (≥ 25 g a dollar cheap, ≥ 12 better, less fancy); your list (AA6) where it names one; the rest
  estimated. Two calls to check: boneless breast buys as much protein a dollar as thighs at the seed prices, but is
  in A bit better as your list says; and since your list says A bit better adds *more* Greek yogurt and fresh veg,
  Greek yogurt and the basic salad vegetables (tomato, cucumber, romaine, iceberg) are in Cheapest; without them
  Cheapest could make only 5 of the 47 seed dishes, now 16 (A bit better 40, Fancy 47).
- **D181. A tier limits what the plan buys** (AA8): its ingredients, the any-tier ones and your could-buys; what
  you have and Always-have items always work. Recipes needing something outside the tier that you don't have are
  left out before solving, with one plan note ("12 recipes need items the Cheapest tier doesn't buy"). Variety
  5/4/3 a week (Same dish, many portions keeps its own).
- **D182. The tier cards' quick solve** is the week's MILP on the shortlist (3 recipes a meal, then 10 when that
  can't make a week: Fancy's variety needs more recipes), one 6 s solve with a 5% gap, the cook days held to their
  linear limits only. On your dev week (7 days, 4 meals): all three cards in 9.4 s, Cheapest about $39.05 (130 g
  protein a day), A bit better about $45.12 (129 g), Fancy about $47.75 (128 g). A card whose quick solve finds no
  week says so and can't be picked.
- **D183. The kitchen order costs some minutes.** On 450 seed cook days (2–4 dishes) it kept 237 the same, made 206
  longer (3.4 min on average, 4.9%; at most 32 min) and 7 shorter; 9 days that fit 90 minutes no longer do. Five
  seeds' own times grew by 3–7 minutes; the burrito bowls' stated total went from 30 to 35 minutes (seed data), so
  a Quick 30-minute dinner search no longer offers them. Your dev week (the opt-in perf test) still plans in 61.5 s of the 180 s, the time guard never cutting a solve short. If you'd rather start a long cook as soon as its
  own prep is done (the old interleaving for that step), it is a one-line change.

**Dev database.** Migrated to 0011 and re-seeded (the tiers and the burrito bowls' new draft version). Downgrade:
`alembic downgrade 0010`.

**For 2b.8:** What should I buy? takes the same tier cards (AA6).

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
4. The Cook home Today card links to C6; the old plan and day screens are retired, and Cook home's **Meal prep** button opens C1 instead of the old plan flow.
5. A plan batch whose recipe is an idea opens C8 with the steps state built in 2b.3b.
6. **How do you want to cook? (H5, C1b):** four tiles, One big cook day (day chips and a minutes stepper that goes well above the usual per-day minutes), A few sessions (day chips with minutes per day), Same dish, many portions (one recipe, any number of portions) and Mix it up.
7. **The new plan view (H4, C6):**
   - it starts with Today;
   - freeze and spoil warnings never appear as a block above the days: they collapse into one tappable **Prep notes** row ("3 to freeze · 4 may spoil") that opens a sheet with the items, and each freeze step also shows on the shopping day itself;
   - days with nothing to cook show "Nothing to cook, eating prepped meals";
   - each day says which portions come from the fridge and which from the freezer, with "thaw in the fridge the night before";
   - a cook day shows its prep order when there is one.
   - **"No plan fits" (M17, added at the 2b.4 approval):** never CLI wording ("--topup"), never the same sentence twice, and action buttons instead of a paragraph: **Allow a $X top-up** (the server's whole-dollar suggestion, rounded up) and **Switch to shopping**, with the item list behind **See what it would buy**; a budget shortfall offers **Raise the budget to $X**. The diagnostics carry `suggested_cents` and `items` since the 2b.4 approval fixes, and the old `/plan/new/` screen already uses them.

**Acceptance criteria**
1. The meal-prep flow works end to end; swap and undo work from the UI.
2. Every C6 state is reachable in tests; 375 px.
3. All four cook options work end to end from the UI, including a whole week cooked on one day and one dish for 8 portions.
4. The plan view has no freeze or spoil block above the days, only the one Prep notes row.

**Tests (Vitest).** Day order with Today first; swap optimistic states and undo; the overlap confirm; diagnostics → fix buttons; toggle memory. For H4 and H5: the four cook options → request (big day with minutes above the usual maximum, sessions, same dish for 8 portions, mix); the Prep notes row (collapsed, its text from the API, opens the sheet); freeze steps on the shopping day; the fridge/freezer and thaw lines per day; the prep order.

**Changes (approved 2026-10-11, X1, X8; FLOW_SPEC §19.10, §20.4).** Built right after 2b.10, before the deploy, to
show both single-recipe meals and assemblies:
- the batch view (each cook day's batches or prep items, their stop states and where each portion goes), each
  meal's sources, the Prep notes row, and each cook day's timeline (in place of the prep order), with a cook-day
  cooking mode that steps through it;
- finish tasks at the top of each eating day;
- assembly and prep item recipe pages;
- cook-day minutes shown as start-to-finish time in C1b, onboarding and Settings (V11), and the weeknight time
  setting per day (V7);
- **backend:** the plan view payload for assemblies (read from 2b.10's tables; moved from 2b.11, X8);
- **not here any more (X8):** Swap, its Undo and no-fit sheet, and Not for me move to 2b.6; the fifth tile is shown
  "coming soon" and enabled in 2b.11. AC 1 becomes "the meal-prep flow works end to end", and the swap tests go to
  2b.6.
- **Back here (Z4, Z5, 2026-10-12):** the screen side of Not for me (F24) and a Hidden recipes list in Settings, with
  the storage they need (migration `0010_recipe_hidden`, approved Z5). Swap stays in 2b.6.

**2b.7 outcome (built 2026-10-12, awaiting your approval).** Every deliverable and acceptance criterion is met, with
tests (AC 2's 375 px is laid out fluid but not checked on a phone; AC 1 and AC 3 are covered by Vitest from the taps
to the request and by the backend's end-to-end tests from the request to the plan; the live run on your phone is
yours). 1515 backend tests pass in the default run (14 skipped: slow, perf and opt-in), 304 frontend tests (266
before); ruff, mypy and the type check are clean and the static export builds. Migration `0010_recipe_hidden`; no
new dependency.

What was built:
- **Meal prep's questions** (`/cook/ask/?mode=prep&step=…`): C1 How much (5 lunches, Lunch + dinner 5 days, My
  usual week, or Something else by portions or by days; starting today, tomorrow or a date; extra portions to
  freeze; "Snack has no calories set" with a link); C1b How do you want to cook? (the four tiles with their controls,
  start-to-finish minutes up to 600, the fifth tile "coming soon"); C2 goals, people and mood; C3 What do you have?
  (the meal-now screen, with Next); C3b Shopping for this? (Use what I have, or a shopping list with its budget).
  Pre-filled from your last meal-prep answers; Cook home's Meal prep opens C1, and Same as last time includes meal
  prep.
- **Building** (`/cook/plan/?run=…`): the real stages from the stream (pantry, recipes, calories, groceries,
  checking), the rate-limit countdown and "Adjusting after rounding"; a dropped connection finds the plan by its run.
- **"No plan fits"** (M17, P4): Pottle, one to three reasons each said once (the rest behind More reasons), each with
  its fix as a button: Allow a $X top-up, Switch to shopping, Raise the budget to $X, Allow N min on Monday, Use
  simpler recipes, Allow fancy recipes, Write new recipes; settings fixes (calories, protein, held items, caps) as
  links; what a money fix buys behind See what it would buy; Edit answers. No command-line wording.
- **C6, the plan view** (`/cook/plan/?id=…`, or your current plan): Today first, then the following days, earlier
  days folded; each day's kcal, protein and cost; finish tasks first; the shopping day's freeze steps and the
  thaw-tonight lines on their days; **each cook day's batches and where every portion goes** ("Cook Chicken over rice
  ×4 → Mon lunch, Tue dinner, Wed lunch, Sat dinner (1 to the freezer)", F23) with its timeline (§20.4) and Start
  cooking; "Nothing to cook, eating prepped meals"; each meal row's source ("From the fridge, cooked Mon 12",
  "From the freezer, cooked Mon 12 · thaw Fri 16 night"); assembled meals with their items, portions and eating-day
  instruction; **one Prep notes row** for freezing, spoiling and the plan's own notes (recipes left out, not proven
  best) behind a sheet, nothing above the days; Recipes | Shopping list (remembered on the device; the list
  read-only, Open in Grocery); Use this plan with the "Replace your current plan?" sheet.
- **The cook-day cooking mode** (`/cook/cooking/?plan=…&day=…`): the day's batches, then its timeline one line at a
  time across dishes (each line opens its dish's steps), then Mark cooked for each batch; the screen stays awake.
- **Recipe pages** (C8): a prep item's stages, each with how it keeps; an assembly's items (each opening its page),
  add-ons and "On the day"; a prep batch's "In this plan: marinate on Sun 11, roast on Wed 14."; a plan batch whose
  recipe is an idea keeps 2b.3b's steps state.
- **Not for me** (F24, Z5) on recipe pages and on every plan meal row (behind ⋯), separate from Swap, with Undo; and
  **Settings → Diet → Hidden recipes** (dishes, prep items and meals, each with Show again).
- **Settings → Cooking → Weeknight time** (V7): one value or one per day.
- **Retired:** the old week, day and Plan a week screens redirect to C6 (keeping the plan and day) and to C1; the
  service worker (v4) precaches `/cook/plan/`.
- **Backend, the plan view payload** (X8, read from 2b.10's tables): each batch's `uses` and `uses_display`, kind and
  stop state; each meal's `kind`, `components`, `instruction` and `plan_meal_id`; each day's `finish_tasks`; the Prep
  notes row's `about` items; the batch page's `in_plan`; the Today card with assembled meals.

Decisions and deviations:
- **D161. The batch view's lines come from the API** (`uses`, `uses_display`), like every other line: "Mon lunch, Tue
  dinner (1 to the freezer)"; in a plan longer than a week each day carries its date ("Mon 12 lunch"). A prep
  batch's draws count the same way (per person, times everyone eating), halves shown as "1½".
- **D162. One row for everything that isn't a day's own step:** freeze and spoil items as before, plus the plan's own
  notes and warnings under "About this plan" in the same sheet (you asked for the left-out notes behind the Prep
  notes row; F23 allowed either). The row reads "3 to freeze · 4 may spoil · About this plan".
- **D163. The smart prep read side, as 2b.11 will write it:** an assembled meal is `plan_meal.assembly_version_id` with
  `plan_meal_component` rows; its numbers are its batches' rounded nutrition times its portions per person; its
  instruction comes from 2b.10's templates (`planning/assemblies.py` `planned_instruction`, with a finish stage when
  a batch stopped early). Finish tasks are templated per kind (stage, reheat, put together). Until 2b.11 no plan has
  these; the tests write them the way 2b.11 will. **Left for 2b.11:** a prep batch that stops early still shows all of
  its stages on the cook day's timeline (2b.11 schedules stop stages), and a hidden prep item doesn't yet hide its
  assemblies (the planner doesn't use assemblies yet).
- **D164. C1 "By days" is a day count** (1–14 from the start day), not day chips for 14 days: a plan's days are
  consecutive (`PrepAmount.day_count`). Starting offers the next 7 days as chips.
- **D165. The fixes are the same answers with one change.** A time fix on Mix it up becomes A few sessions on your
  cook days, the same days and minutes with that day raised; Quick is raised to match when it would cap the day; a
  fix with no day (no recipe fits any cook day) raises every cook day. Each fix is offered once.
- **D166. Not for me (Z5):** hidden recipes leave `candidate_versions`, where meal now, the planner and quick picks
  start; plans already made keep the meal (Swap replaces one, 2b.6); the `recipe_hidden` event records the recipe's
  kind and, from a meal row, the plan meal (`?plan_meal=`); a hidden ♥ still shows in Saved, your bookmarks. Not for
  me needs a connection (it isn't queued offline like ♥).
- **D167. Retired screens' components were removed** (WeekSummary, DayList, PlanProgress, `lib/plan/overrides`): the
  old "no plan fits" component became `components/plan/NoPlanFits` with its tests.

**Dev database.** Migrated to 0010 (no re-seed changes). Downgrade: `alembic downgrade 0009`.

#### 2b.8 What should I buy?, and phase wrap-up

*Reads FLOW_SPEC §8, §13.1 (E10), §15.*

**Deliverables**
1. `POST /grocery/advice`: a shop-mode draft plan, LLM off by default (with it on, the ideas pass, as in meal prep).
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

**Approved 2026-10-11 (X1, X7):** unchanged. Grocery advice plans dishes; smart prep for it goes to the backlog
(V17, §12.5 DF4). Its cook days use the schedule from 2b.9.

**Phase 2b acceptance (after 2b.8).**
1. Every step's criteria are met; full `pytest` and `vitest` pass; the fresh-clone check passes.
2. The frontend has no nutrition, unit or cost arithmetic.
3. Every new screen works at 375 px with ≥ 48 px targets, in both themes.
4. Every flow honors the beef exclusion, held items and the pork cap.
5. LLM call counts in tests match FLOW_SPEC §15, and no flow shows a rate limit as an error.
6. You complete the manual iPhone checklist: onboarding, meal now, meal prep, swap, cooking mode, grocery advice, dark mode, offline.

**Files and folders.**
- **Creates:**
  - backend: `app/cook/` (answers, ranking, substitutes, search, ideas, steps, grocery_advice, tests), `app/planning/pins.py`, `app/domain/dish_category.py`, `app/domain/prompt_names.py`, `app/llm/prompts/recipe_ideas.py`, `recipe_steps.py` and `idea_revision.py`, `app/schemas/cook.py`;
  - API routes: cook, favorites, stores, grocery advice, swap, recipe steps;
  - `migrations/versions/0005_cook_flow.py`;
  - frontend: `welcome/`, `cook/`, `pantry/`, `grocery/advice/`, `settings/edit/`, and the §5 components.
- **Changes:**
  - `config.py` and `.env.example` (`SOLVER_TIME_LIMIT_SECONDS=30`, `LLM_PREFETCH_DAILY_RESERVE=30000`);
  - `schemas/llm_recipe.py` (`RecipeIdeaBatch`, `RecipeSteps`); `llm/pacing.py` and `llm/structured.py` (calibrated estimates, per-purpose maximum completion);
  - `planning/`: constraints, solver, post-solve, validator scope, grocery list, accept, and the generator choice (ideas for the 2b flows, Phase 1 prompts for `POST /plans`);
  - `services/plan_stream.py` (stages);
  - seed `ingredients.json` (sweet potatoes).

**Database.** Migration `0005_cook_flow` (§4.5).

**Dependencies.** None new. Wake Lock is a browser API, icons are emoji and in-house inline SVG, and fonts are system fonts.

**Depends on.** Phase 2 (approved 2026-10-10). The FLOW_SPEC §18 questions are answered.

**Risks and mitigations**
- *Scope.* Nine steps, each shippable. If one runs long, I'll stop and propose a split rather than rush it (2b.3 was split this way before building, E17).
- *Solver size with household and pins.* Pins shrink the model and household size is a constant multiplier; the K6 determinism rules stay.
- *Meal-now latency under 8K tokens a minute.* Saved results come first. One ideas call brings 5–8 cards with no steps; steps come only when you open a recipe. After the first More ideas tap, a background batch makes later taps usually instant (E15, E17). Opening a new idea right after a batch can wait 15–30 s for the minute's allowance (cautious case), shown as the countdown.
- *Unknown per-call overhead.* About 3.5K of the measured 5.9K prompt isn't our text; it may be the structured-output schema counted in an expanded form. If it is a fixed cost per call, steps calls are ≈ 4.8K rather than ≈ 2.3K, and daily use is about 50% higher (FLOW_SPEC §15). The 2b.3b live test checks it (with and without the schema) before the counts and reserves are tuned.
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

**Files and folders.** Creates `app/feedback/`, `app/preferences/`, `app/substitutions/`, `app/domain/preferences.py`, `app/schemas/feedback.py`, prompts (comment_tags, substitution, step_rewrite, adaptation), API routes (ratings, cook_logs, recipe_versions, substitutions, cook_again, profile), `migrations/versions/0012_feedback_loop.py`; frontend `history/`, `learned/` (reached from Settings and the Cook tab), rating sheet, editor, substitution sheet. (♥, 🔖 and Not for me shipped in Phase 2b.)

**Database.** Migration `0012_feedback_loop` (planned as 0003): `prepared_portion`, `preference_profile`; `plan_meal.prepared_portion_id`; `inventory_event.prepared_portion_id` + CHECK (§4.5). `feedback_event` and `recipe_favorite` already exist (Phase 2b, `0005_cook_flow`).

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

**Files and folders.** Creates `app/overrides/`; extends `app/domain/calories.py`; prompt `off_plan_parse`; API routes (days, consumption, rebalance); frontend Today additions on the Cook tab; `migrations/versions/0013_daily_overrides.py`.

**Database.** Migration `0013_daily_overrides` (planned as 0004): `day_override`, `consumption_entry`.

**Added at the 2b.4 approval (M19, backlog):** **daily habit items**, a recurring item counted every day toward
calories and protein (a daily shake, a coffee with milk), with a one-tap "had an extra today". It fits the daily
tracking and rebalancing here: the habit is a standing `consumption_entry`, and the day's targets rebalance around it.

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

**Files and folders.** Creates `app/grocery/`, `app/domain/price_stats.py`, `app/seed/data/seasonality_new_england.json`, API routes (price_history, deals, recommendations, cart_sessions), frontend `store/`, history views, mode selector, badges, `migrations/versions/0014_grocery_intelligence.py`. Changes `objective.py`, `app/cook/grocery_advice.py` (Phase 2b) and `docs/data-sources.md`.

**Database.** Migration `0014_grocery_intelligence` (planned as 0005): `region`, `ingredient_seasonality`, `cart_session`, `price_observation.cart_session_id`.

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

**Files and folders.** Creates `app/ranking/`, CLI commands, API `ranker/status`, a frontend settings panel, `migrations/versions/0015_ranker.py`. Changes the preference-term source in `objective.py` and in `app/cook/ranking.py` (Phase 2b).

**Database.** Migration `0015_ranker` (planned as 0006): `ranker_model`.

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
| `pytest-xdist` 3.8.0 (dev; pulls in `execnet` 2.1.2) | 2b | **Approved 2026-10-11 (P6)** | Runs the backend suite in parallel, one test database per worker |

No other dependencies are planned. Auth uses the stdlib, and the solver uses HiGHS through PuLP (C3). **Phase 2b adds no app dependency** (pytest-xdist is a test tool, P6): the screen-wake lock is a browser API, icons are emoji and in-house inline SVG, and fonts are system fonts. If one becomes necessary, I'll ask first with a one-line justification.

---

## 11. Conflicts between PRD and CLAUDE.md (resolved per CLAUDE.md)

1. **PRD §32:** "The LLM then generates a plan within these constraints." **CLAUDE.md rule 4:** the solver chooses. → The LLM generates candidates; the solver builds the plan.
2. **PRD §33:** "ask the AI to revise it" → revision applies to candidate recipes; plan-level violations → re-solve / targeted generation.
3. **PRD §31:** "meal-plan reasoning" → the LLM may explain; it never decides.
4. **PRD §24:** Cook Again "should regenerate". **CLAUDE.md rule 7:** reuse unless constraints changed. → Deterministic re-scale by default; LLM only on the Q20 triggers.
5. **PRD §10:** "not a static substitution table". **CLAUDE.md rule 7:** cache per ingredient. → Cache culinary candidates only; inventory, price and nutrition ranking is recomputed live.
6. **CLAUDE.md outline** puts strict/weekly modes in Phase 4. → **Approved:** the solver supports both from Phase 1; Phase 4 adds the toggle UX and rebalancing.
7. **CLAUDE.md phase outline vs Phase 2b (flagged 2026-10-10; resolved: CLAUDE.md updated with your OK the same day).** CLAUDE.md listed favorites under Phase 3, had no Phase 2b, and says "build exactly ONE phase per session". This plan, following your brief, moves favorites to 2b and runs 2b as nine one-session build steps (eight at first; 2b.3 was split into 2b.3a and 2b.3b on 2026-10-10, E17), each ending with the phase-end steps (tests shown, commit, fresh-clone check, summary, stop). The CLAUDE.md wording now in place:
   - add "Phase 2b: Cook-first flow (4 tabs, Cook flow, favorites and save for later, onboarding, swap, grocery advice). Built in nine steps, one step per session, in the order 2b.1, 2b.2, 2b.3a, 2b.4, 2b.3b, 2b.5–2b.8; each step ends like a phase." (the order changed at your request on 2026-10-10, H3);
   - change Phase 3's line to "Feedback loop (ratings, recipe versioning, preference profile, Cook Again)".

   **Updated again 2026-10-11 (V16, X6, X8)**, when smart prep, parallel cooking and the deploy step were added:
   "Phase 2b: Cook-first flow (4 tabs, Cook flow, favorites and save for later, onboarding, meal prep with parallel
   cooking and smart prep, swap, grocery advice, first cloud deploy). Built in fourteen steps, one step per session,
   in the order 2b.1, 2b.2, 2b.3a, 2b.4, 2b.3b, 2b.5, 2b.9, 2b.10, 2b.7, 2b.13 (deploy), 2b.11, 2b.12, 2b.6, 2b.8;
   each step ends like a phase."

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
| E13 | Rate limits | When a call would exceed Groq's per-minute limit (e.g. More ideas tapped twice quickly), show a friendly wait state with a short countdown, never an error. Built in 2b.3b (backend, every LLM path) and 2b.4 / 2b.7 (screens). |
| E14 | Approvals | All 18 flagged changes (FLOW_SPEC §16) approved, F3 with E11's cap. All 10 questions answered with the defaults, including Pottle as the mascot (FLOW_SPEC §18). Phase 2 approved. CLAUDE.md updated with the proposed wording (§11 item 7). |

**Two-stage generation (2026-10-10, later the same day).** Your addition for step 2b.3 (now 2b.3a and 2b.3b), then your review of it:

| # | Topic | Decision |
|---|---|---|
| E15 | Two-stage generation | To fit Groq's 8K tokens a minute (FLOW_SPEC §13.5, §14, §15; changes F19–F21):<br>1. **Ideas pass:** one call returns 5–8 ideas (name, ingredients with amounts, method, equipment, rough time; no steps). Code computes nutrition and cost, checks and ranks them, and the cards show at once.<br>2. **Steps pass:** steps are written only when a recipe is first opened, then saved with it. Seed and saved recipes never need one.<br>3. **Compact prompts:** short canonical names, never product descriptions.<br>4. **Background batch:** while results show, the same stream writes the next batch when the rate limit allows, so More ideas is usually instant (tightened in E17: only after the first More ideas tap).<br>5. **Estimates:** the call and token estimates for meal now, meal prep and swap are updated (FLOW_SPEC §15, §7.6). |
| E16 | Protein cap with no target | Approved: with a protein target of 0, the High protein tile rewards protein up to 1.5 × the 100 g default (FLOW_SPEC §13.3). |
| E17 | Review of two-stage generation | F19 and F20 approved as written. Changes:<br>1. **F21 tightened:** the background ideas batch starts only after your first More ideas tap in a search. The first tap waits normally; later taps are instant when the held batch is ready. A search never starts one. The per-flow and per-day estimates are updated (FLOW_SPEC §15.2, §7.6).<br>2. **Reasoning effort:** ideas, steps and idea-revision calls use the lowest effort the configured model supports, if it has the setting (`LLM_REASONING_EFFORT`, `low` for `openai/gpt-oss-*`). The 2b.3b live test records tokens with it.<br>3. **Overhead check:** the 2b.3b live test checks whether the unexplained ≈ 3.5K prompt tokens shrink with the smaller ideas schema (ideas messages with and without the schema, against the full and steps schemas). The finding goes in FLOW_SPEC §15.1.<br>4. **Step split:** 2b.3 becomes 2b.3a (ranking and cards; no LLM calls) and 2b.3b (ideas, steps, background batch, rate-limit waits, live test). Phase 2b now has nine steps; CLAUDE.md's phase outline is updated to match. |

**Step 2b.2 approval (2026-10-10).** You approved 2b.2, then:

| # | Topic | Decision |
|---|---|---|
| H1 | 2b.2 | Approved, including D54–D64. |
| H2 | Footer fix (first) | The fixed Continue button overlapped content on question screens (it covered the hands-on minutes stepper on "When do you cook?"). Bottom padding equal to the footer's height on every question screen, with a test or layout check. Done before 2b.3a (2b.2 approval note, §9). |
| H3 | Build order | To feel the new flow sooner: **2b.3a now, then 2b.4** (the meal-now screens) with seed and saved recipes only, **then 2b.3b** (LLM ideas, steps, background batch), then 2b.5–2b.8. Where a screen would show LLM ideas, More ideas is shown disabled with "coming soon" until 2b.3b. 2b.4 includes Cook home's two big buttons; Meal prep opens the existing plan flow until 2b.7. BUILD_PLAN and CLAUDE.md updated. Consequence (mine): the screen work that needs ideas (New badges, countdown wait states, the held `prefetched` list, the C8 steps state) moves from 2b.4 into 2b.3b. |
| H4 | New plan view (2b.5, 2b.7) | It starts with Today. Freeze and spoil warnings never appear as a block above the days; they collapse into one tappable "Prep notes" row (e.g. "3 to freeze · 4 may spoil"), and freeze steps also appear on the shopping day itself. Days with nothing to cook use "Nothing to cook, eating prepped meals". FLOW_SPEC C6. |
| H5 | "How do you want to cook?" (2b.5, 2b.7) | A meal-prep step with four options: **One big cook day** (pick the day and that day's hands-on minutes, which can go well above the usual; everything is cooked that day); **A few sessions** (pick cook days, like the cook-day settings); **Same dish, many portions** (one recipe scaled to any number of portions; overrides the 5-portions-per-recipe weekly cap, F22); **Mix it up** (today's variety behavior). Rules: portions within the fridge window stay in the fridge, later ones go to the freezer with a plain thaw-in-the-fridge-the-night-before instruction, stated per day; a "freezes well" flag on recipes (seeds set by hand: rice dishes and curry gravies yes, yogurt sauces and fresh salads no or with a freeze-the-base note; ideas include it and the validator checks it), and portions past the fridge window only use recipes that freeze well; a big cook day's total hands-on time is estimated and checked against that day's time; the cook day shows a simple prep order where the recipes allow it. The 2b.5 and 2b.7 criteria and tests cover all four options, including a whole week cooked on one day and one dish for 8 portions. FLOW_SPEC C1b, C6, §16 F22. |
| H6 | Pre-deploy | The login rate limit must key on the real client address (X-Forwarded-For read only from the trusted proxy), so devices and visitors don't share one lockout counter. Added to the pre-deploy list (§12.4). |

**Step 2b.3a approval (2026-10-10).** You approved 2b.3a, then:

| # | Topic | Decision |
|---|---|---|
| J1 | 2b.3a | Approved, including D65–D76. |
| J2 | Substitute groups (D66 follow-up) | Vegetable swaps use culinary role groups instead of the broad "vegetable" category: groups drafted in seed data (aromatics, leafy greens, sturdy vegetables, and so on) covering every vegetable and herb in the ingredient table. Swaps happen only inside a group; an ingredient in no group gets no substitute. Tests include "yellow onion never becomes spinach". The full group list goes in the step summary. |
| J3 | Mark cooked fix | Mark cooked on a one-meal plan never takes from the items you turned off for that search. With a test. |
| J4 | Held items with versions (in 2b.4) | Ask which version when adding, toggling or planning with one, with "Check the label" guidance. Pepperoni and salami: pork + beef (excluded), pork only (allowed, counts toward the pork cap), turkey (allowed, no pork cap), chicken (allowed, no pork cap), not sure (stays held). Bouillon cubes or powder: chicken, no beef listed (allowed); contains beef or beef fat (excluded); not sure (stays held). Each allowed version is its own ingredient with its own tags and nutrition (estimated and flagged where USDA has no exact entry). Choosing a version never releases the generic held item. Same choices in Settings under held items. Tests: turkey pepperoni never counts toward the pork cap; pork + beef pepperoni is always excluded. |
| J5 | Amount presets (in 2b.4) | Adding to Pantry or "What do you have?": step 1 the form (fresh, frozen, canned, dried, or that ingredient's forms), mapped to the right ingredient entry; step 2 common package sizes for that form as buttons, plus Custom, plus Not sure (the most common size, the lot marked estimated, correctable from Pantry). Presets in seed data per ingredient and form, realistic US sizes, flagged as estimates; listed in the step summary. |
| J6 | Recipe amounts in your terms (in 2b.4) | For each ingredient you have, the recipe page shows how much the recipe uses relative to what you have ("uses 4 oz, about half your bag · 4 oz left after"). Mark cooked subtracts exactly that; the leftover stays in Pantry for later plans and searches. |

**Step 2b.4 approval (2026-10-10).** You tested and approved 2b.4, then:

| # | Topic | Decision |
|---|---|---|
| M1 | 2b.4 | Approved, including D77–D88. Fixes M2–M13 first, then step 2b.3b (with M14). If both don't fit one session, the fixes are finished and committed first, and the step stops with what's left of 2b.3b. |
| M2 | Correct amount (D88 follow-up, decision #1) | Pantry's **Correct amount** works on any lot, not only estimated ones, with quick taps for ¾, ½ and ¼ of the package plus Custom. |
| M3 | Usual version (decision #5) | Your usual version of a held item is saved in your settings on the server, not on one device. |
| M4 | Chicken cuts | Chicken is protein-critical, so it must be exact. Catalog ingredients with forms and package sizes for chicken thigh and breast bone-in skin-on, drumsticks, wings and whole chicken, each mapped to the best USDA entry. |
| M5 | Bone-in refuse | Bone-in cuts use USDA refuse (bone) percentages, so a package's weight becomes edible weight for nutrition, portions and leftovers. With tests. |
| M6 | Strict chicken | Chicken search is strict: bone-in vs boneless and skin-on vs skinless must match exactly ("chicken thighs bone in" never leads with boneless). Never substitute between these forms anywhere (search, swaps, substitutes). With tests. |
| M7 | Close matches, labeled | Everything else can use a close match as long as it's labeled: "garlic paste" maps to minced garlic, "canned peas" to frozen peas; search shows "Closest match: frozen peas". Added as aliases where they make sense. |
| M8 | USDA fallback | "Can't find it? Add from USDA" is deferred to a later phase (§12.5, DF1). |
| M9 | Meal choice | The small "Dinner for 1 ▸" line becomes a visible choice: Breakfast, Lunch, Dinner, Snack, Dessert. No default by time of day, nothing preselected (Same as last time covers repeats). Results match the chosen meal. |
| M10 | Mood is soft | Mood is a preference, not a hard filter: recipes matching the mood first, then "A bit more effort" or "Simpler options" with the rest that pass the hard filters. |
| M11 | Card wording | A substitute you have reads "Swap: X instead of Y (you have it)", not "Missing"; only things you'd buy are "Missing". The duplicated "Uses …" line at the bottom of cards goes. |
| M12 | Card cost | Cards show "$X a portion" and "$Y to buy today" (whole packages of what's missing). With Cheap on, ranking accounts for the buy-today total, not just the per-portion cost. |
| M13 | Seed library | 30–40 new draft recipes in your style (chicken, Indian-style gravies, tortillas as chapati, eggs, rice bowls; no beef, pork rare) across breakfast, lunch, dinner, snacks and protein desserts, and simple, medium and fancy. Nutrition and cost computed by code. Listed in the step summary. **Conflict flagged:** CLAUDE.md says "Seed recipes use no pork component", which wins over "pork rare", so the new seeds have no pork component. |
| M14 | Gap rule (2b.3b) | A meal-now search calls the ideas pass when fewer than **6** recipes fit well (was 3), so every search aims for 6–8 options. The token estimates are updated for this. |
| M15 | Portion vs batch (A1, now) | Every recipe page and plan view shows amounts per portion and, for batches, the batch total ("1 scoop per portion · 4 scoops for the batch of 4"). Scoop-based items always show scoops, not just grams. Done with the fixes. |
| M16 | Daily amount cap (A2, 2b.5) | A per-day amount cap setting for an ingredient (like frequency caps, but amount per day). Protein powder: usually 1 scoop (31 g) a day, hard maximum 2 scoops. The solver penalizes days above the usual amount and never exceeds the maximum, counting every meal that day; meal-now ranking never suggests a single portion above the maximum; Settings shows the cap. Tests: oats and pudding on one day never exceed 2 scoops, and 1 is preferred when protein targets are still met. Didn't fit with the fixes, so it is built in 2b.5 (deliverable 13). |
| M17 | "No plan fits" (B: 2b.7, plus a fix now) | Never CLI wording like "--topup", never repeated, action buttons instead of a paragraph: "Allow a $X top-up" (rounded up) and "Switch to shopping", the items behind "See what it would buy". Fixed now on `/plan/new/`; the meal-prep screens follow in 2b.7. |
| M18 | Custom items from labels (C, backlog) | Add an item that isn't in USDA (granola bought abroad) by entering label values per serving. Scheduled together with DF1 (§12.5, DF3). |
| M19 | Daily habit items (C, backlog) | A recurring item counted every day toward calories and protein, with a one-tap "had an extra today". Placed with Phase 4 (daily tracking and rebalancing). |
| M20 | Solver shortlist (asked during the fixes) | With the 47 seed recipes the weekly MILP stopped proving its best plan in time (slower plans that could differ between identical requests; planning tests timed out). Your choice: before each solve, code shortlists the best 3 candidates per meal (your nutrition priority per kcal, closeness to the meal's calories, favorites, pantry use, price; never-favored and disliked last), preferring recipes that share ingredients, since solve time grows with the number of different ingredients. When the shortlist can't make a plan it widens to 6 per meal, and a library of 16 or fewer is solved whole. The solver still does all the fitting. A default week now solves in about 6 s (the 10 Phase 0 seeds took about 10 s). `app/planning/shortlist.py`. |

**Step 2b.4 fixes approval (2026-10-10).** You approved the fixes, then:

| # | Topic | Decision |
|---|---|---|
| N1 | 2b.4 fixes | Approved: M2–M13, M15, M17 and M20, including every decision and deviation in the fixes outcome note (§9). |
| N2 | Ground vs whole cuts | Ground meat swaps only with ground meat (ground turkey and ground chicken are fine for each other); a whole cut swaps only with a whole cut of the same form (bone and skin, as M6). Never between ground and whole cuts. Tests include "ground turkey never becomes chicken thigh". Built at the start of 2b.3b: `meat_forms` in the pantry catalog, `domain/meat_forms.py`, checked in every substitute step (accepted pairs and pantry). As built, the rule is symmetric: neither kind stands in for, or is replaced by, something that is neither (eggs, tofu, beans, fish, sausage), so chicken thighs no longer stand in for salmon, shrimp or eggs on a card. |
| N3 | Mapping review (13 ingredients new to the top 25) | Ground turkey: 93% lean (FDC 172850). Salmon: farmed Atlantic, raw (FDC 175167). Canned chickpeas: drained solids (173800). Red lentils (174284) and quinoa (168874): dry, uncooked. Approved as-is: the five chicken cuts, ground chicken, pita, russet potato. Bone-in thigh keeps the raw leg's 27% refuse for now, noted in the seed as replaceable with a measured value. All 13 are marked reviewed (`nutrition_reviewed_on` 2026-10-10, already in the seed; no mapping changed). |

**Step 2b.3b approval (2026-10-11).** You approved 2b.3b, then (worked through overnight without waiting, per
your instruction; real design decisions stop and wait):

| # | Topic | Decision |
|---|---|---|
| P1 | 2b.3b | Approved, including D89–D101. |
| P2 | Fish and shellfish swaps | Fish fillets get their own group and swap only with other fish fillets; shrimp and other shellfish get their own group. Eggs and tofu never stand in for fish or shellfish; fish never swaps with chicken. With tests. |
| P3 | Regression (first) | A shop-mode week with no budget and the current settings (45 hands-on minutes per cook day, medium mood) returns "No plan fits" (Monday needs 50 min vs 45; 6 fancy recipes left out), though it planned before the 2b.4 fixes. Likely the shortlist picking recipes before the time and mood limits: apply every hard filter (equipment, the day's allowed mood, hands-on time that can fit) before the shortlist, and widen to every eligible recipe before declaring no plan. Test: default settings + the seed library always plan a shop-mode week with no budget. |
| P4 | Time/mood "no plan fits" message | One message, never repeated, no stray punctuation, plain wording ("Monday needs 50 minutes of hands-on cooking; you set 45", "6 recipes are fancy and your cook days are set to medium"), with action buttons "Allow X min on <day>" and "Use simpler recipes" (or "Allow fancy recipes" where that's the blocker). Same rules as the top-up fix (M17). |
| P5 | Model speed | An opt-in live comparison of the ideas pass on two gpt-oss sizes (same prompt, 2 runs each): latency, tokens, ideas passing. If the smaller is clearly faster with a similar pass rate, a separate ideas model setting (`LLM_IDEAS_MODEL`) defaulting to it; steps stay on the main model. Under 40K tokens. |
| P6 | Test speed | Profile the slowest tests; run the suite in parallel (**pytest-xdist approved** as a dev dependency); mark the heaviest solver tests `slow` so the default local run skips them while the fresh-clone check runs everything. Before/after times. |
| P7 | Ideas pass rate | Ideas kept vs asked recorded in the LLM call log. |
| P8 | Next | Then step 2b.5 (meal prep engine), with C1b's four cooking options, the freezes-well rules and A2 (M16: the daily amount cap for protein powder, usually 1 scoop, at most 2). If the pre-work plus 2b.5 doesn't fit one session, the pre-work is committed first and the step stops with what's left. |

**2b.3b pre-work approval (2026-10-11).** You approved the pre-work, then:

| # | Topic | Decision |
|---|---|---|
| T1 | Pre-work | Approved, including D102 and D105. |
| T2 | D102 follow-up (done first) | With a budget or top-up, each meal's shortlist always keeps its cheapest eligible recipe, by cost per portion and by buy-today total, alongside the quickest ones, before widening. Test: the only plan that fits the budget uses a recipe ranked below the top 6. |
| T3 | Freeze note | The nullable `recipe_version.freeze_note` column (migration), so your own recipe versions and generated recipes can carry it too. |
| T4 | Protein powder per portion (fix now) | Chocolate protein overnight oats: 1 scoop, the other ingredients rebalanced to keep a reasonable breakfast. Every seed: no single portion uses more than 1 scoop by default. |
| T5 | Meal slots | Snack recipes filling breakfast is fine, as long as the day stays within your calorie and protein targets. No change. |
| T6 | Batch view (record now, build in 2b.7) | Each cook day lists every batch with its portion count and where each portion goes; each meal row shows its source ("cooked Mon" / "from freezer, cooked Mon, thaw Fri night"); "Left out" and freeze notes only behind Prep notes or "About this plan". FLOW_SPEC C6, F23. |
| T7 | Not for me (record now, build in 2b.6/2b.7) | On recipe pages and meal rows, separate from Swap: hides the recipe from all future suggestions and plans, logs a feedback event, undone from "Hidden recipes" in Settings. Swap still replaces one meal. FLOW_SPEC C6, F24. |
| T8 | Next | Step 2b.5 per this plan, with C1b's four options, the freezes-well rules and freeze notes, and A2 (the daily cap counting every meal that day), plus a test that oats and protein pudding on the same day respect the cap. |

**Step 2b.5 approval (2026-10-11).** You approved 2b.5, then:

| # | Topic | Decision |
|---|---|---|
| U1 | 2b.5 | Approved, including D107–D126. |
| U2 | Freeze note in ideas (built now) | The ideas pass includes an optional freeze note alongside freezes-well, validated like the other fields, so generated recipes follow the same freezer rules as seeds; with a test. Done: D127 (2b.5 approval note, §9). |
| U3 | Smart prep (design only) | "Cook basics, mix and match", a fifth meal-prep option: free-form prep items (no fixed main or side), prep stages that can stop at raw, marinated, partly cooked or cooked with a finish task on the eating day, storage per item and state from the FoodSafety.gov chart in the repo (never guessed), assemblies built from prep items, and a solver that minimizes effort (cook sessions and hands-on time) with each item in 2–3+ meals, zero planned spoilage and every day meeting calories, protein, goals and caps, with variety. Written as FLOW_SPEC §19; proposed steps 2b.10–2b.12 (§9). |
| U4 | Parallel cooking (design only) | Each task's time split into hands-on and hands-off on a piece of equipment; hands-on grows with batch size; capacity per equipment with extra rounds; each cook day a schedule (equipment one at a time, hands one task at a time, hands-off overlapping), with the cook-day check on its elapsed time; eating-day finish tasks on their own days; a timeline. Written as FLOW_SPEC §20; proposed step 2b.9 (§9). |
| U5 | Next | Stop for your review of both designs: the build order, the token impact and the open questions V1–V17 (FLOW_SPEC §21). No other code this session. |

**Design approval (2026-10-11).** You approved both designs, then:

| # | Topic | Decision |
|---|---|---|
| X1 | Designs | Smart prep (FLOW_SPEC §19) and parallel cooking (FLOW_SPEC §20) approved, including D127; so are the changes F25–F32 (FLOW_SPEC §16) and the migrations `0008_step_timing` and `0009_smart_prep` (§4.5; later phases' migrations move up by two). |
| X2 | V1: storage rows the chart doesn't have | The USDA FSIS **FoodKeeper** data is the second official storage source. You save `foodkeeper.json` (English) into `docs/sources/`. In 2b.10 I transcribe the rows needed (cooked rice and grains, cooked vegetables, cut fresh vegetables, salads, sauces, and any other gaps) into the storage table, citing FoodKeeper per row. If the file isn't in `docs/sources/` when 2b.10 starts, cooked items keep today's 3-day rule and fresh items are made on the day, and I tell you. |
| X3 | V2: partly cooked protein | Approved: partly cooked meat, poultry, fish or eggs is never stored. |
| X4 | V11: cook-day time | Approved: a cook day's minutes mean start to finish, checked against the day's schedule. Default 90 minutes; your saved cook days are converted (doubled, at most 600). This replaces C1's hands-on reading. |
| X5 | V7: weeknight time | Approved: a per-day weeknight time for finish tasks, default 30 minutes, editable per day (in Settings next to the cook days). |
| X6 | V16: CLAUDE.md | Approved: CLAUDE.md's phase outline is updated (§11 item 7). |
| X7 | Other questions | V3–V6, V8–V10, V12–V15 and V17: the recommended defaults (FLOW_SPEC §21.3). V13's per-appliance size and V17 go to the backlog (§12.5 DF5, DF4). |
| X8 | Build order | New screens and a live link sooner: **2b.9** cook-day schedule → **2b.10** smart prep data model (including meals that draw from several prep batches) → **2b.7** the new plan screens, built to show both single-recipe meals and assemblies (batch view, sources per meal, Prep notes row, cook-day timeline) → **2b.13** a deploy step (Vercel + Neon per `docs/deploy.md`, with the pre-deploy list, PD1 first) → **2b.11** smart prep solver → **2b.12** smart prep ideas → **2b.6** swap (with Not for me) → **2b.8** What should I buy?. Consequences (mine, in §9 "How the steps run"): 2b.7 takes the read side of 2b.11's plan view data; the swap screens and Not for me move to 2b.6; the fifth tile shows "coming soon" until 2b.11. |
| X9 | Next | Step 2b.9 per this plan. |

**Step 2b.9 approval (2026-10-11).** You approved 2b.9, then:

| # | Topic | Decision |
|---|---|---|
| Y1 | 2b.9 | Approved, including D128–D142 and D135 (pairs kept apart before the first solve). |
| Y2 | Time guard (first) | Every plan request (meal prep, plan a week, the top-up and budget explanations) finishes inside its time budget (Vercel's slower single CPU, 180 s) and returns the best plan found so far, clearly marked as not proven best, instead of timing out. Solve time and re-solves per run are logged in the run record. A test: a request with a deliberately tiny time budget returns a valid plan or a clear "ran out of time", never a hang. Built as D143–D147 (2b.9 approval note, §9). |
| Y3 | Next | Step 2b.10 per this plan, with the FoodKeeper rows from `docs/sources/foodkeeper.json` (or the 3-day rule and same-day fresh items if it's missing). |

**Step 2b.10 approval (2026-10-12).** You approved 2b.10, then:

| # | Topic | Decision |
|---|---|---|
| Z1 | 2b.10 | Approved, including D148–D156. |
| Z2 | Y4: a big week inside 180 s (first) | Option a, as recommended: when a cook day runs over, re-solve only that day with the rest of the week fixed, instead of re-solving the whole week. A test: a 7-day, 4-meals-a-day week with your dev settings finishes well inside the 180 s budget (the time reported) and the time guard never has to cut it off. Built as D157–D160 (2b.10 approval note, §9). |
| Z3 | Flaky frontend test | Vitest's per-test timeout raised to 15 s, so the fresh-clone check stops tripping on a loaded machine. |
| Z4 | Next | Step 2b.7 (the new plan screens) per this plan, including: Today first, then the following days; the batch view ("cook once, eat many": each cook day's batches with portions and where each portion goes, each meal row's source); meals that are assemblies of several prep items; the cook-day timeline; freeze, spoil and "left out" notes behind one Prep notes row, never a block above the days; "Nothing to cook, eating prepped meals"; the "no plan fits" messages with action buttons, no CLI wording, no repeats; and **the screen side of Not for me (F24) with a Hidden recipes list in Settings** (X8 had moved Not for me to 2b.6). |
| Z5 | Not for me's storage (asked during 2b.7) | A new table like ♥ and 🔖: migration `0010_recipe_hidden` (user, recipe, when). A hidden recipe leaves meal-now results, plans and ideas; the recipe_hidden / recipe_unhidden events are logged; Settings → Hidden recipes lists them with Undo; Phase 3–6 migrations move up by one (0011–0014). Built as D166. |

**Step 2b.7 approval (2026-10-12).** You approved 2b.7, then:

| # | Topic | Decision |
|---|---|---|
| AA1 | 2b.7 | Approved, including D161–D167 and Z5. |
| AA2 | C1's freezer extras (first) | "Extra portions to freeze" becomes **"Cook extra for the freezer (future weeks)"** with a one-line explanation, so it's clear these portions aren't part of this plan. It defaults to 0. |
| AA3 | Next, before the deploy | **Step 2b.6 now, expanded** (A–D below); the deploy (2b.13) comes after it. If it is too much for one session: commit A and AA2 first, stop, and say what's left. |
| AA4 | A. Meal swap | As planned (§9 2b.6), with a list: **Swap** on any meal row shows **3–5 alternatives** that fit the same slot, day, fridge/freezer and time rules, sorted by cost and protein; one tap replaces just that meal and keeps the rest of the plan valid. |
| AA5 | B. Ingredient options | On recipe pages and plan meals, each ingredient gets a ⋯ with: **Swap it** (substitutes from the culinary role groups, chicken exact by form, with the change in kcal, protein and cost); **Leave it out** (non-essential lines only: garnish, optional, minor aromatics or spices; nutrition recomputed, a warning when protein or calories drop a lot); **I'm out of this** (swap it, or add it to the shopping list); **Never use this** (a **Foods I don't eat** list in Settings, like beef; future plans, searches and ideas avoid it; "Allow again"). Edits save as your own version of the recipe (the existing versioning). |
| AA6 | C. Budget tiers | Three cards replace the budget number as the main control, in the meal-prep shopping step (and in What should I buy?, 2b.8): **Cheapest**, **A bit better**, **Fancy**, each with its estimated total and protein per day for this week. Tiers differ by the ingredients they may use and by variety (Cheapest: cheap staples such as chicken thighs, eggs, lentils, rice, frozen veg, tortillas; A bit better adds chicken breast, more Greek yogurt, ground turkey, more fresh veg; Fancy adds premium items such as salmon and shrimp, and more variety). A price tier per ingredient in the seed data (from protein per dollar where possible; estimates flagged). The cards use a fast estimate; only the tapped tier gets the full solve. A custom limit stays under **Set my own limit**. |
| AA7 | D. Cooking order | Every cook-day timeline follows a systematic kitchen order: all chopping and marinating first, the longest-cooking items next, the rest while they cook, then portioning and storing. With a test. |
| AA8 | Asked at the start of 2b.6 | **Tier cards:** a quick solve per tier (the planner on saved recipes, no LLM, a short time limit), shown as "about $X". **Tier rules:** a tier limits what gets bought; what you have, Always-have items, seasonings and oils work in every tier; at most 5 portions of one recipe a week in Cheapest, 4 in A bit better, 3 in Fancy. **Plan edits:** an ingredient edit saves your version and leaves the current plan unchanged; after the edit an **Also update this week's plan** button switches the batch (every meal it feeds) to your version, recomputes nutrition, cost and the shopping list, validates, and re-solves that batch's portions if a limit breaks (or says why it can't); only batches not yet cooked can change. **Step text:** code edits the names (no LLM call) and adds a "Your version" line; a left-out ingredient is marked in the steps that mention it ("(skipped: spinach)"); a swap that changes cooking time, temperature or method (chicken breast for thighs, frozen for fresh vegetables) flags the affected steps with a short note and offers **Rewrite steps for this change**, one LLM steps call made only when you tap it. |

### 12.2 Remaining questions (from applying your answers)

- **Y4: answered 2026-10-12 (Z2), option a; built as D157–D160.** The question as asked: **Planning a big week inside 180 s (from the time guard, 2026-10-11).** With your settings (7 cook days, 4
  meals a day) a seed week needs 8 weekly solves at their full 30 s, 245 s in all; the guard now stops it at 180 s,
  where it may or may not have a plan that fits (171 s with one locally). The waste: solves on the narrow shortlist
  whose plans keep running over a cook day, each followed by a whole re-solve. Options (not built; your call):
  - **a. Repair before re-solving (my recommendation):** when a cook day runs over, re-solve only that day's
    batches with everything else fixed (seconds, not 30 s), keeping the whole re-solve for when time allows;
  - **b. Shorter cut rounds:** give the cut re-solves 10–12 s each (their plans arrive by then on the narrow
    shortlist) and keep 30 s for the first solve;
  - **c. Start big weeks on the wider shortlist:** it found far better plans here (objective about −10 against
    −0.1) but needs 15–25 s for its first plan, which a slower CPU may not reach in 30 s;
  - **d. Tighter linear time limits in the model,** so fewer plans run over at all (a design change to 2b.9's
    limits).

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

### 12.4 Pre-deploy list (fix before the first cloud deploy)

Started 2026-10-10 (H6). Each item is done before `docs/deploy.md` is followed for real, in step 2b.13 (X8).

- **PD1. Login rate limit keyed on the real client address.** Today `client_address()` (`api/routes/auth.py`) trusts `X-Real-IP` / `X-Forwarded-For` whenever it runs on Vercel and otherwise uses the socket's peer, which behind the Next dev proxy is the proxy itself, so every device shares one lockout counter. Fix: read `X-Forwarded-For` only when the request comes from the trusted proxy (a configured proxy address or Vercel's own header), take the client entry that proxy appended, and fall back to the peer address otherwise. Test: two clients behind the proxy get separate counters, and a client can't pick its own key by sending the header directly.

### 12.5 Deferred features (no phase yet)

Recorded so they aren't lost; each gets a phase when you schedule it.

- **DF1. "Can't find it? Add from USDA"** (M8, 2026-10-10). When an ingredient search has no match, offer a
  lookup in the local USDA cache and add the chosen food as a new canonical ingredient (with its mapping
  reviewed like the seed ones). Until then a search with no match says so, and close matches are labeled
  "Closest match: …" (M7).
- **DF2. Variety caps as a setting** (E9): "max servings of one recipe per week"; the built-in Q14 rule stays.
- **DF3. Custom items from labels** (M18, 2026-10-10): add an item that isn't in USDA (granola bought abroad) by
  entering its label values per serving, like the protein powder's label entry (package-label nutrition, values per
  serving, USDA filling nothing). Scheduled together with DF1, since both are "Can't find it?" in the add flow.
- **Daily habit items** (M19) are placed with Phase 4 (see its section).
- **DF4. Smart prep in What should I buy?** (V17, X7, 2026-10-11): grocery advice plans dishes in 2b.8; planning it
  with prep items and assemblies comes later.
- **DF5. Appliance sizes** (V13, X7, 2026-10-11): a size choice per appliance in Settings → Equipment (a bigger air
  fryer basket, a second oven rack), replacing the capacity constants of FLOW_SPEC §20.2 for that appliance.

---

## 13. Seed recipe library (DRAFTS: quantities for you to adjust)

**Step 2b.5:** every seed's "freezes well" value was reviewed by hand (H5) and 18 carry a freeze note
("Freeze the chicken and rice; make the garlic yogurt sauce and the salad fresh"); the coconut shrimp curry now
freezes well (a curry gravy). A changed seed file becomes a new draft version (D107). No seed portion uses more
than 1 scoop of protein powder (T4, tested).

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

- **5a. Chocolate protein overnight oats.** Simple · no-cook · base 1 (one jar; revised 2026-10-11, T4) · ≈ 5 min + refrigerate overnight.
  - *Ingredients:* old-fashioned rolled oats 35 g · protein powder, double chocolate 1 scoop · milk (2%) 120 ml · Greek yogurt, plain nonfat 60 g · chia seeds 5 g (USDA has no spoon measure for chia, so it's authored in grams) · banana ½ (optional, for topping). Computed by code: 374 kcal, 39.6 g protein a jar (was 408 kcal and 40.5 g, also 1 scoop a jar, as a 2-jar recipe).
  - *Outline:* whisk powder into the milk until smooth; stir in yogurt, oats and chia; spoon into the jar; refrigerate overnight; top with sliced banana when serving.
  - *Note:* nutrition complete from your package label (L1); cost pending until you give the powder's price.
