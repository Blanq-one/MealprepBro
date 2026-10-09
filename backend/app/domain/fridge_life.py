"""How long a raw ingredient keeps in the fridge, from the FoodSafety.gov Cold Food Storage Chart
(storage_chart.py). Code sets these values, never the LLM (CLAUDE.md food-safety rules).

An ingredient maps to a chart row by its slug, or else by its safety category. The plan uses the SHORT end of
the chart's range ("1 to 2 days" -> 1 day), the same way the leftover default uses the short end of
"3 to 4 days".

Raw meat, poultry and fish that the plan doesn't cook within that time of shopping day (including what is
left of a package) gets a "freeze on shopping day" instruction. Eggs have a chart row but are not frozen
in the shell, so they only count as keeping well.
"""

from dataclasses import dataclass

from app.domain import storage_chart

# safety category -> APP_STORAGE use, for raw proteins without a slug entry below
CATEGORY_USE = {
    "poultry": "raw_poultry_pieces",
    "fish_shellfish": "raw_lean_fish",
    "ground_meat": "raw_ground_meat_or_poultry",
    "whole_cut_meat": "raw_pork_chops_roasts",
}
SLUG_USE = {
    "ground-chicken": "raw_ground_meat_or_poultry",
    "ground-turkey-93": "raw_ground_meat_or_poultry",
    "ground-pork": "raw_ground_meat_or_poultry",
    "chicken-sausage": "raw_sausage",  # USDA's row doesn't say cooked, so treat it as raw
    "pork-sausage-italian": "raw_sausage",
    "salmon": "raw_fatty_fish",
    "tilapia": "raw_lean_fish",
    "cod": "raw_lean_fish",
    "shrimp": "raw_shrimp",
    "bacon": "bacon",
    "egg-large": "raw_eggs_in_shell",
}
NOT_FROZEN_RAW = frozenset({"raw_eggs_in_shell"})


@dataclass(frozen=True)
class FridgeLife:
    use: str  # the APP_STORAGE key
    chart: storage_chart.ChartRow
    days: int  # the short end of the chart's refrigerator range
    freeze_raw: bool  # raw meat, poultry or fish: freeze what isn't cooked in time

    @property
    def label(self) -> str:
        return f"{self.chart.food}, {self.chart.type.lower()}: {self.chart.refrigerator} in the fridge"


def fridge_life(slug: str, safety_category: str | None) -> FridgeLife | None:
    """The chart's fridge life for a raw ingredient, or None when the chart doesn't cover it."""
    use = SLUG_USE.get(slug) or (CATEGORY_USE.get(safety_category) if safety_category else None)
    if use is None:
        return None
    row = storage_chart.chart_row(storage_chart.APP_STORAGE[use])
    days = row.fridge_days
    if days is None:
        return None
    return FridgeLife(use, row, days[0], use not in NOT_FROZEN_RAW)
