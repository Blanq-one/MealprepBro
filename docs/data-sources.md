# Data sources

Everything the app treats as fact comes from one of these sources. Nothing nutritional, food-safety or
price-related is ever taken from the LLM.

## USDA FoodData Central (nutrition)

| Release | File | Size (zipped) | Used for |
|---|---|---|---|
| Foundation Foods, April 2026 | `FoodData_Central_foundation_food_csv_2026-04-30.zip` | 3.7 MB | a few ingredients (red onion, cheddar, pepperoni) |
| SR Legacy, April 2018 | `FoodData_Central_sr_legacy_food_csv_2018-04.zip` | 6.7 MB | most ingredients (complete nutrient profiles) |

- Download page: <https://fdc.nal.usda.gov/download-datasets/>. Direct links:
  `https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_foundation_food_csv_2026-04-30.zip` and
  `https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_sr_legacy_food_csv_2018-04.zip`.
- Put the zips in `data/raw/usda/` (gitignored), then run `python -m app.cli usda-import`.
- USDA FoodData Central data is in the public domain (CC0 1.0).
- Only `foundation_food` and `sr_legacy_food` rows are imported. All values are per 100 g of edible portion.
- Energy: nutrient 208 (Energy) → 958 (Atwater specific) → 957 (Atwater general) → 4/4/9 from protein, carbs
  and fat (stored with source `derived`). Foundation Foods often have only 957/958.
- Densities and piece weights come from USDA household portions (`food_portion.csv`), referenced by portion
  id in `backend/app/seed/data/ingredients.json`. The loader checks that each portion belongs to the
  ingredient's FDC food and really is the stated measure.
- **Test fixture:** `backend/app/testing/fixtures/usda_subset/` holds only the ~180 foods the seed references
  (rebuild with `python -m app.cli usda-subset`). Tests and a fresh clone seed from it without the download.
- **Mappings to review:** every USDA mapping starts unreviewed (`nutrition_reviewed_at` is empty).
  `garam masala` has no USDA entry and is approximated by curry powder (flagged in `ingredient-report`).

## Your labels (`backend/app/seed/data/label_inputs.json`)

- Protein powder, double chocolate: scoop 31 g, 120 kcal, 25 g protein (your values, 2026-10-08).
  **Carbs and fat per scoop are still empty**, so recipes using the powder are reported as incomplete.
- Price Rite small flour tortillas, 30 count: net weight ≈ 23 oz (652 g), **an estimate** from a 20–26 oz
  range; piece weight = 652 / 30 = 21.733 g, computed by the loader. Replace with the exact label values.

## Food safety

- Safe internal temperatures: the USDA baseline in `CLAUDE.md`, hardcoded in
  `backend/app/domain/food_safety.py`.
- Storage durations: to be transcribed from the FoodSafety.gov Cold Food Storage Chart,
  <https://www.foodsafety.gov/food-safety-charts/cold-food-storage-charts>. The page returned HTTP 403 to
  automated fetches on 2026-10-08 (twice). Until a saved copy is in `docs/sources/`, every chart value is
  **pending** and unused. Values are never taken from secondary sources.
- Your fixed values (live now): cooked leftovers 3 days in the fridge; reheat to 165 °F.

## Prices (`backend/app/seed/data/products_prices.json`)

- Stores: Stop & Shop (primary), Price Rite (secondary).
- One real price: Price Rite small flour tortillas, 30 count, $1.99 (`source = manual`).
- Every other price is an **estimate** (`source = estimate`, observed 2026-10-08), with Price Rite chicken
  set below Stop & Shop. Estimates are shown as "est." and never produce "cheap" or "deal" labels. Real
  entries supersede them per store.
- Protein powder has no price yet.
