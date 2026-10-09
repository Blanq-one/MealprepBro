"""FoodSafety.gov Cold Food Storage Chart, transcribed row by row (wording as printed).

Source: FoodSafety.gov, "Cold Food Storage Chart",
    https://www.foodsafety.gov/food-safety-charts/cold-food-storage-charts
    "Date Last Reviewed: September 19, 2023".
Saved copy: docs/sources/Cold Food Storage Chart _ FoodSafety.gov.pdf (5 pages, printed from the page
2026-10-08). Transcribed 2026-10-08.

Refrigerator = 40 °F (4 °C) or below; freezer = 0 °F (-18 °C) or below. In the chart's words: "The short time
limits for home-refrigerated foods will help keep them from spoiling or becoming dangerous to eat. The
guidelines for freezer storage are for quality only — frozen foods stored continuously at 0 °F (-18 °C) or
below can be kept indefinitely."

The chart gives no reheating guidance; reheat temperatures come from CLAUDE.md (165 °F).
"""

import re
from dataclasses import dataclass

CHART_URL = "https://www.foodsafety.gov/food-safety-charts/cold-food-storage-charts"
CHART_PDF = "docs/sources/Cold Food Storage Chart _ FoodSafety.gov.pdf"
CHART_LAST_REVIEWED = "September 19, 2023"
CHART_SAVED_ON = "2026-10-08"
FREEZER_NOTE = (
    "Freezer times are for quality only; frozen foods stored continuously at 0 °F (-18 °C) or below "
    "can be kept indefinitely."
)

_RANGE = re.compile(r"(\d+)\s*(?:to|-)\s*(\d+)\s*(day|week)s?\b", re.IGNORECASE)
_SINGLE = re.compile(r"(\d+)\s*(day|week)s?\b", re.IGNORECASE)


def parse_days(refrigerator: str) -> tuple[int, int] | None:
    """Refrigerator time in days: '3 to 4 days' → (3, 4), '1 - 3 Days' → (1, 3), '3 to 5 weeks' → (21, 35).
    Months, years and 'Use immediately' give None (not a day count)."""
    match = _RANGE.search(refrigerator)
    if match:
        low, high, unit = int(match.group(1)), int(match.group(2)), match.group(3).lower()
    else:
        single = _SINGLE.search(refrigerator)
        if not single:
            return None
        low = high = int(single.group(1))
        unit = single.group(2).lower()
    factor = 7 if unit == "week" else 1
    return low * factor, high * factor


@dataclass(frozen=True)
class ChartRow:
    key: str
    food: str  # the chart's "Food" column
    type: str  # the chart's "Type" column
    refrigerator: str  # as printed
    freezer: str  # as printed
    page: int
    note: str | None = None

    @property
    def fridge_days(self) -> tuple[int, int] | None:
        return parse_days(self.refrigerator)


_USE_BY = '"use by" date'

STORAGE_CHART: tuple[ChartRow, ...] = (
    # page 1
    ChartRow(
        "salads",
        "Salads",
        "Egg, chicken, ham, tuna, and macaroni salads",
        "3 to 4 days",
        "Does not freeze well",
        1,
    ),
    ChartRow("hot_dogs_opened", "Hot dogs", "Opened package", "1 week", "1 to 2 months", 1),
    ChartRow("hot_dogs_unopened", "Hot dogs", "Unopened package", "2 weeks", "1 to 2 months", 1),
    ChartRow(
        "luncheon_meat_opened",
        "Luncheon meat",
        "Opened package or deli sliced",
        "3 to 5 days",
        "1 to 2 months",
        1,
    ),
    ChartRow("luncheon_meat_unopened", "Luncheon meat", "Unopened package", "2 weeks", "1 to 2 months", 1),
    ChartRow("bacon", "Bacon and sausage", "Bacon", "1 week", "1 month", 1),
    ChartRow(
        "sausage_raw",
        "Bacon and sausage",
        "Sausage, raw, from chicken, turkey, pork, or beef",
        "1 to 2 days",
        "1 to 2 months",
        1,
    ),
    # page 2
    ChartRow(
        "sausage_fully_cooked",
        "Bacon and sausage",
        "Sausage, fully cooked, from chicken, turkey, pork, or beef",
        "1 week",
        "1 to 2 months",
        2,
    ),
    ChartRow(
        "sausage_purchased_frozen",
        "Bacon and sausage",
        "Sausage, purchased frozen",
        "After cooking, 3-4 days",
        "1-2 months from date of purchase",
        2,
    ),
    ChartRow(
        "ground_meats",
        "Hamburger, ground meats and ground poultry",
        "Hamburger, ground beef, turkey, chicken, other poultry, veal, pork, lamb, and mixtures of them",
        "1 to 2 days",
        "3 to 4 months",
        2,
    ),
    ChartRow(
        "fresh_meat_steaks", "Fresh beef, veal, lamb, and pork", "Steaks", "3 to 5 days", "4 to 12 months", 2
    ),
    ChartRow(
        "fresh_meat_chops", "Fresh beef, veal, lamb, and pork", "Chops", "3 to 5 days", "4 to 12 months", 2
    ),
    ChartRow(
        "fresh_meat_roasts", "Fresh beef, veal, lamb, and pork", "Roasts", "3 to 5 days", "4 to 12 months", 2
    ),
    ChartRow("ham_fresh_uncured_uncooked", "Ham", "Fresh, uncured, uncooked", "3 to 5 days", "6 months", 2),
    ChartRow("ham_fresh_uncured_cooked", "Ham", "Fresh, uncured, cooked", "3 to 4 days", "3 to 4 months", 2),
    ChartRow(
        "ham_cured_uncooked",
        "Ham",
        "Cured, cook-before-eating, uncooked",
        f"5 to 7 days or {_USE_BY}",
        "3 to 4 months",
        2,
    ),
    ChartRow(
        "ham_vacuum_sealed_unopened",
        "Ham",
        "Fully-cooked, vacuum-sealed at plant, unopened",
        f"2 weeks or {_USE_BY}",
        "1 to 2 months",
        2,
    ),
    ChartRow("ham_store_wrapped_whole", "Ham", "Cooked, store-wrapped, whole", "1 week", "1 to 2 months", 2),
    ChartRow(
        "ham_store_wrapped_sliced",
        "Ham",
        "Cooked, store-wrapped, slices, half, or spiral cut",
        "3 to 5 days",
        "1 to 2 months",
        2,
    ),
    ChartRow("ham_country_cooked", "Ham", "Country ham, cooked", "1 week", "1 month", 2),
    # page 3
    ChartRow(
        "ham_canned_keep_refrigerated",
        "Ham",
        'Canned, labeled "Keep Refrigerated," unopened',
        "6 to 9 months",
        "Do not freeze",
        3,
    ),
    ChartRow(
        "ham_canned_shelf_stable_opened",
        "Ham",
        "Canned, shelf-stable, opened",
        "3 to 4 days",
        "1 to 2 months",
        3,
        note="An unopened, shelf-stable, canned ham can be stored at room temperature for 2 years.",
    ),
    ChartRow(
        "ham_prosciutto",
        "Ham",
        "Prosciutto, Parma or Serrano ham, dry Italian or Spanish type, cut",
        "2 to 3 months",
        "1 month",
        3,
    ),
    ChartRow("poultry_whole", "Fresh poultry", "Chicken or turkey, whole", "1 to 2 days", "1 year", 3),
    ChartRow("poultry_pieces", "Fresh poultry", "Chicken or turkey, pieces", "1 to 2 days", "9 months", 3),
    # The chart's refrigerator cell for fin fish is one merged cell ("1 - 3 Days") spanning all three rows.
    ChartRow(
        "fin_fish_fatty",
        "Fin fish",
        "Fatty fish (bluefish, catfish, mackerel, mullet, salmon, tuna, etc.)",
        "1 - 3 days",
        "2 - 3 months",
        3,
    ),
    ChartRow(
        "fin_fish_lean",
        "Fin fish",
        "Lean fish (cod, flounder, haddock, halibut, sole, etc.)",
        "1 - 3 days",
        "6 - 8 months",
        3,
    ),
    ChartRow(
        "fin_fish_lean_pollock",
        "Fin fish",
        "Lean fish (pollock, ocean perch, rockfish, sea trout)",
        "1 - 3 days",
        "4 - 8 months",
        3,
    ),
    ChartRow("shellfish_crab_meat", "Shellfish", "Fresh crab meat", "2 - 4 days", "2 - 4 months", 3),
    ChartRow("shellfish_lobster", "Shellfish", "Fresh lobster", "2 - 4 days", "2 - 4 months", 3),
    # page 4
    ChartRow("shellfish_live_crab_lobster", "Shellfish", "Live crab, lobster", "1 day", "Not recommended", 4),
    ChartRow(
        "shellfish_live_clams",
        "Shellfish",
        "Live clams, mussels, oysters, and scallops",
        "5 - 10 days",
        "Not recommended",
        4,
    ),
    ChartRow("shellfish_shrimp", "Shellfish", "Shrimp, crayfish", "3 - 5 days", "6 - 18 months", 4),
    ChartRow(
        "shellfish_shucked",
        "Shellfish",
        "Shucked clams, mussels, oysters, and scallops",
        "3 - 10 days",
        "3 - 4 months",
        4,
    ),
    ChartRow("shellfish_squid", "Shellfish", "Squid", "1 - 3 days", "6 - 18 months", 4),
    ChartRow(
        "eggs_raw_in_shell",
        "Eggs",
        "Raw eggs in shell",
        "3 to 5 weeks",
        "Do not freeze in shell. Beat yolks and whites together, then freeze.",
        4,
    ),
    ChartRow(
        "eggs_raw_whites_yolks",
        "Eggs",
        "Raw egg whites and yolks",
        "2 to 4 days",
        "12 months",
        4,
        note="Yolks do not freeze well.",
    ),
    ChartRow(
        "eggs_frozen_in_shell",
        "Eggs",
        "Raw egg accidentally frozen in shell",
        "Use immediately after thawing",
        "Keep frozen, then refrigerate to thaw",
        4,
        note="Toss any frozen eggs with a broken shell.",
    ),
    ChartRow("eggs_hard_cooked", "Eggs", "Hard-cooked eggs", "1 week", "Do not freeze", 4),
    ChartRow(
        "egg_substitutes_liquid_unopened",
        "Eggs",
        "Egg substitutes, liquid, unopened",
        "1 week",
        "Do not freeze",
        4,
    ),
    ChartRow(
        "egg_substitutes_liquid_opened",
        "Eggs",
        "Egg substitutes, liquid, opened",
        "3 days",
        "Do not freeze",
        4,
    ),
    # page 5
    ChartRow(
        "egg_substitutes_frozen_unopened",
        "Eggs",
        "Egg substitutes, frozen, unopened",
        f"After thawing, 1 week or refer to {_USE_BY}",
        "12 months",
        5,
    ),
    ChartRow(
        "egg_substitutes_frozen_opened",
        "Eggs",
        "Egg substitutes, frozen, opened",
        f"After thawing, 3 to 4 days or refer to {_USE_BY}",
        "Do not freeze",
        5,
    ),
    ChartRow(
        "eggs_casseroles",
        "Eggs",
        "Casseroles with eggs",
        "After baking, 3 to 4 days",
        "After baking, 2 to 3 months",
        5,
    ),
    ChartRow("eggnog_commercial", "Eggs", "Eggnog, commercial", "3 to 5 days", "6 months", 5),
    ChartRow("eggnog_homemade", "Eggs", "Eggnog, homemade", "2 to 4 days", "Do not freeze", 5),
    ChartRow(
        "pies_pumpkin_pecan",
        "Eggs",
        "Pies: Pumpkin or pecan",
        "After baking, 3 to 4 days",
        "After baking, 1 to 2 months",
        5,
    ),
    ChartRow(
        "pies_custard_chiffon",
        "Eggs",
        "Pies: Custard and chiffon",
        "After baking, 3 to 4 days",
        "Do not freeze",
        5,
    ),
    ChartRow(
        "quiche", "Eggs", "Quiche with filling", "After baking, 3 to 5 days", "After baking, 2 to 3 months", 5
    ),
    ChartRow("soups_stews", "Soups and stews", "Vegetable or meat added", "3 to 4 days", "2 to 3 months", 5),
    ChartRow(
        "leftovers_cooked_meat_poultry",
        "Leftovers",
        "Cooked meat or poultry",
        "3 to 4 days",
        "2 to 6 months",
        5,
    ),
    ChartRow(
        "leftovers_nuggets_patties",
        "Leftovers",
        "Chicken nuggets or patties",
        "3 to 4 days",
        "1 to 3 months",
        5,
    ),
    ChartRow("leftovers_pizza", "Leftovers", "Pizza", "3 to 4 days", "1 to 2 months", 5),
)

# The rows the app uses for meal-prep storage and inventory expiry estimates.
APP_STORAGE: dict[str, str] = {
    "cooked_leftovers": "leftovers_cooked_meat_poultry",
    "soups_stews": "soups_stews",
    "cooked_egg_dishes": "eggs_casseroles",
    "hard_cooked_eggs": "eggs_hard_cooked",
    "raw_eggs_in_shell": "eggs_raw_in_shell",
    "raw_poultry_pieces": "poultry_pieces",
    "raw_poultry_whole": "poultry_whole",
    "raw_ground_meat_or_poultry": "ground_meats",
    "raw_pork_chops_roasts": "fresh_meat_chops",
    "raw_fatty_fish": "fin_fish_fatty",
    "raw_lean_fish": "fin_fish_lean",
    "raw_shrimp": "shellfish_shrimp",
    "bacon": "bacon",
    "raw_sausage": "sausage_raw",
    "deli_meat_opened": "luncheon_meat_opened",
    "hot_dogs_opened": "hot_dogs_opened",
}


def chart_row(key: str) -> ChartRow:
    for row in STORAGE_CHART:
        if row.key == key:
            return row
    raise KeyError(key)
