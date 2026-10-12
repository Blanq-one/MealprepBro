"""USDA FSIS FoodKeeper data: the rows smart prep needs that the FoodSafety.gov chart doesn't have,
transcribed row by row (step 2b.10, BUILD_PLAN X2: the second official storage source). Code sets these
values, never the LLM.

Source: USDA Food Safety and Inspection Service, FoodKeeper data (English), file "FMA-Data-v128.xlsx",
data version 128 (the current version), modified 09-06-2018. Saved copy: docs/sources/foodkeeper.json (the
workbook as JSON: sheets Version, Category, Product, CookingTips, CookingMethods, Data Dictionary).
Transcribed 2026-10-11.

Each row is the Product sheet's row with that ID, worded as printed (the subtitle's "vegitables" too).
"Refrigerate" is the time in the refrigerator after cooking (Refrigerate_Min, _Max, _Metric); a cooked
shellfish's freezer time is printed as from the date of purchase (DOP_Freeze). As in the FoodSafety.gov
chart, freezer times are for quality.

What FoodKeeper doesn't have, checked against every Product row: cut fresh vegetables (only commercial cut
fruit, by its package date), green salads (only mayonnaise deli salads, as in the chart's "Salads" row) and
homemade sauces (only commercial bottled or jarred sauces and dips, after opening). Those stay made on the
eating day (V1).
"""

from dataclasses import dataclass

from app.domain.storage_chart import parse_days

FOODKEEPER_FILE = "docs/sources/foodkeeper.json"
FOODKEEPER_WORKBOOK = "FMA-Data-v128.xlsx"
FOODKEEPER_DATA_VERSION = 128
FOODKEEPER_MODIFIED = "09-06-2018"
FOODKEEPER_TRANSCRIBED_ON = "2026-10-11"
DELI = "Deli & Prepared Foods"


@dataclass(frozen=True)
class FoodKeeperRow:
    key: str
    product_id: int  # the Product sheet's ID
    name: str  # Name, as printed
    subtitle: str | None  # Name_subtitle, as printed
    category: str  # the Category sheet's name (and subcategory) for the row's Category_ID
    refrigerator: str  # "3 to 4 days", from Refrigerate_Min, _Max and _Metric
    freezer: str  # "1 to 2 months", from Freeze_* (or DOP_Freeze_*, and then it says so)

    @property
    def fridge_days(self) -> tuple[int, int] | None:
        return parse_days(self.refrigerator)

    @property
    def food(self) -> str:
        return f"{self.name}, {self.subtitle}" if self.subtitle else self.name

    @property
    def citation(self) -> str:
        return f"USDA FoodKeeper (data version {FOODKEEPER_DATA_VERSION}), product {self.product_id}"


FOODKEEPER_ROWS: tuple[FoodKeeperRow, ...] = (
    FoodKeeperRow(
        "leftovers_without_meat",
        174,
        "Leftovers",
        "without meat, fish, poultry, or egg (such as cooked vegitables, rice, or potatoes)",
        DELI,
        "3 to 4 days",
        "1 to 2 months",
    ),
    FoodKeeperRow("cooked_rice", 178, "Cooked rice", None, DELI, "4 to 6 days", "6 months"),
    FoodKeeperRow("cooked_pasta", 177, "Cooked pasta", None, DELI, "3 to 5 days", "1 to 2 months"),
    FoodKeeperRow(
        "cooked_quinoa", 426, "Quinoa", "cooked", "Grains, Beans & Pasta", "6 to 7 days", "6 to 12 months"
    ),
    FoodKeeperRow("cooked_fish", 148, "Cooked fish", "all", "Seafood, Fresh", "3 to 4 days", "1 to 2 months"),
    FoodKeeperRow(
        "cooked_shellfish",
        162,
        "Cooked shellfish",
        "all",
        "Seafood, Shellfish",
        "3 to 4 days",
        "1 to 3 months from the date of purchase",
    ),
)


def foodkeeper_row(key: str) -> FoodKeeperRow:
    for row in FOODKEEPER_ROWS:
        if row.key == key:
            return row
    raise KeyError(key)
