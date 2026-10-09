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
- **Mappings to review:** every USDA mapping starts unreviewed (`nutrition_reviewed_at` is empty). The
  review sheet is [`docs/review/usda_mappings.md`](review/usda_mappings.md) (regenerate with
  `python -m app.cli mapping-review`). `garam masala` has no USDA entry and is approximated by curry powder.
- **States:** recipe quantities are raw / dry / as-sold weights unless a line says otherwise, and each
  mapping's state is read from its USDA description (BUILD_PLAN §7.8).

## Package labels (`backend/app/seed/data/label_inputs.json`, source "package label")

Package-label values override the USDA mapping. Per-serving values are converted to per 100 g by code.

- **Price Rite flour tortillas** (ingredient "flour tortilla (Price Rite, 37 g)", $1.99/bag): 20 per bag, 1 tortilla = 37 g, net weight 740 g. Per tortilla:
  110 kcal, fat 2 g (sat 1 g, trans 0 g), cholesterol 0 mg, sodium 340 mg, carbs 19 g, fiber 2 g, total sugars
  1 g (0 g added), protein 3 g. The values given don't include iron, calcium, potassium or vitamins; those
  come from the USDA mapping (FDC 167535), and each nutrient row records its own source.
- **Double chocolate whey protein powder**: 1 scoop = 31 g, 22 servings per container (682 g). Per scoop:
  120 kcal, fat 1.5 g (sat 1 g), cholesterol 55 mg, sodium 130 mg, carbs 3 g, fiber <1 g (stored as 0.5 g),
  total sugars 1 g, protein 24 g, calcium 130 mg, iron 0.7 mg (non-heme), potassium 200 mg. Allergens: milk,
  soy. No USDA mapping.
- Trans fat, cholesterol and added sugars are recorded in the label file but aren't tracked nutrients yet.

## Food safety

- Safe internal temperatures: the USDA baseline in `CLAUDE.md`, hardcoded in
  `backend/app/domain/food_safety.py`.
- Storage durations: the FoodSafety.gov Cold Food Storage Chart,
  <https://www.foodsafety.gov/food-safety-charts/cold-food-storage-charts> ("Date Last Reviewed: September 19,
  2023"). The page blocks automated fetches, so you saved it as a PDF:
  [`docs/sources/Cold Food Storage Chart _ FoodSafety.gov.pdf`](sources/) (printed 2026-10-08). All 53 rows are
  transcribed in `backend/app/domain/storage_chart.py`, worded as printed; day ranges are parsed by code.
  Values are never taken from secondary sources.
- Your fixed values: cooked leftovers 3 days in the fridge (the chart allows 3 to 4); reheat to 165 °F
  (CLAUDE.md; the chart has no reheating guidance).

## Prices (`backend/app/seed/data/products_prices.json`)

- Stores: Stop & Shop (primary), Price Rite (secondary).
- One real price: Price Rite flour tortillas, 20 per bag, $1.99 (`source = manual`).
- Every other price is an **estimate** (`source = estimate`, observed 2026-10-08), with Price Rite chicken
  set below Stop & Shop. Estimates are shown as "est." and never produce "cheap" or "deal" labels. Real
  entries supersede them per store.
- Protein powder has no price yet (product: 682 g tub, 22 scoops).
