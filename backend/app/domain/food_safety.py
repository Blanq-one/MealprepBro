"""Hardcoded food-safety table (CLAUDE.md food safety rules). The LLM never sets these values.

Safe internal temperatures: the USDA baseline listed in CLAUDE.md.

Storage durations: to be transcribed from the FoodSafety.gov Cold Food Storage Chart,
    https://www.foodsafety.gov/food-safety-charts/cold-food-storage-charts
The page returned HTTP 403 to automated fetches on 2026-10-08 (planning and the Phase 0 retry), so
every chart-derived value below is PENDING (no number) until the chart is saved into docs/sources/
(BUILD_PLAN action item A1). Values are never taken from secondary sources.

Fixed by the user (BUILD_PLAN Q4), live now: cooked leftovers 3 days in the fridge; reheat to 165 F.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

FOODSAFETY_GOV_CHART_URL = "https://www.foodsafety.gov/food-safety-charts/cold-food-storage-charts"
CHART_ACCESS_NOTE = "HTTP 403 on 2026-10-08 (planning and Phase 0 retry); awaiting a saved copy (A1)"

REHEAT_TEMP_F = 165
LEFTOVER_FRIDGE_DAYS_DEFAULT = 3


class SafetyCategory(StrEnum):
    POULTRY = "poultry"
    GROUND_MEAT = "ground_meat"
    WHOLE_CUT_MEAT = "whole_cut_meat"
    FISH_SHELLFISH = "fish_shellfish"
    EGG = "egg"


@dataclass(frozen=True)
class SafeTemperature:
    key: str
    applies_to: str
    temp_f: int
    rest_minutes: int = 0


SAFE_INTERNAL_TEMPS: dict[SafetyCategory, SafeTemperature] = {
    SafetyCategory.POULTRY: SafeTemperature("poultry", "chicken, turkey, duck: whole, parts, ground", 165),
    SafetyCategory.GROUND_MEAT: SafeTemperature("ground_meat", "ground beef, pork, lamb, veal", 160),
    SafetyCategory.WHOLE_CUT_MEAT: SafeTemperature(
        "whole_cut_meat", "steaks, chops, roasts of beef, pork, lamb, veal", 145, rest_minutes=3
    ),
    SafetyCategory.FISH_SHELLFISH: SafeTemperature("fish_shellfish", "fish and shellfish", 145),
    SafetyCategory.EGG: SafeTemperature("egg_dish", "dishes where eggs are a primary component", 160),
}
LEFTOVERS_REHEAT = SafeTemperature("leftovers_reheat", "any reheated leftovers", REHEAT_TEMP_F)


class ChartStatus(StrEnum):
    PENDING = "pending"  # not yet transcribed from the chart
    VERIFIED = "verified"


@dataclass(frozen=True)
class StorageEntry:
    key: str
    food: str
    fridge_days_min: int | None
    fridge_days_max: int | None
    freezer_text: str | None  # the chart's own wording
    status: ChartStatus


# Rows to transcribe from the chart (A1). Until then: no numbers.
STORAGE_CHART: tuple[StorageEntry, ...] = (
    StorageEntry(
        "leftovers_cooked",
        "Leftovers: cooked meat, poultry, and dishes",
        None,
        None,
        None,
        ChartStatus.PENDING,
    ),
    StorageEntry("leftovers_soups_stews", "Soups and stews", None, None, None, ChartStatus.PENDING),
    StorageEntry("poultry_raw_pieces", "Fresh poultry pieces", None, None, None, ChartStatus.PENDING),
    StorageEntry("poultry_raw_ground", "Ground poultry", None, None, None, ChartStatus.PENDING),
    StorageEntry("fish_raw", "Fresh fish", None, None, None, ChartStatus.PENDING),
    StorageEntry("shellfish_raw", "Fresh shellfish", None, None, None, ChartStatus.PENDING),
    StorageEntry("eggs_raw_shell", "Raw eggs in shell", None, None, None, ChartStatus.PENDING),
    StorageEntry(
        "egg_dishes_cooked", "Egg casseroles and cooked egg dishes", None, None, None, ChartStatus.PENDING
    ),
    StorageEntry("pork_raw_cuts", "Fresh pork chops, roasts", None, None, None, ChartStatus.PENDING),
    StorageEntry("pork_bacon_sausage", "Bacon and raw sausage", None, None, None, ChartStatus.PENDING),
    StorageEntry("ham", "Ham", None, None, None, ChartStatus.PENDING),
    StorageEntry("lunch_meats", "Lunch meats and hot dogs", None, None, None, ChartStatus.PENDING),
)


class FoodSafetyError(ValueError):
    pass


def storage_entry(key: str) -> StorageEntry:
    for entry in STORAGE_CHART:
        if entry.key == key:
            return entry
    raise KeyError(key)


def leftover_fridge_days_upper_bound() -> int:
    """The chart's upper bound for cooked leftovers once verified; until then, your fixed 3 days."""
    entry = storage_entry("leftovers_cooked")
    if entry.status is ChartStatus.VERIFIED and entry.fridge_days_max is not None:
        return entry.fridge_days_max
    return LEFTOVER_FRIDGE_DAYS_DEFAULT


def validate_leftover_fridge_days(days: int) -> int:
    if days < 0:
        raise FoodSafetyError("leftover fridge days must not be negative")
    upper = leftover_fridge_days_upper_bound()
    if days > upper:
        raise FoodSafetyError(
            f"leftover fridge days {days} is above the allowed maximum of {upper} "
            f"(FoodSafety.gov chart value; pending transcription)"
            if storage_entry("leftovers_cooked").status is ChartStatus.PENDING
            else f"leftover fridge days {days} is above the FoodSafety.gov chart maximum of {upper}"
        )
    return days


@dataclass(frozen=True)
class IngredientSafety:
    """One recipe line, as the safety table sees it."""

    name: str
    safety_category: SafetyCategory | None
    role: str  # recipe role; an egg counts as an egg dish only when it's the protein


def doneness_requirement(lines: Iterable[IngredientSafety]) -> SafeTemperature | None:
    """Strictest safe internal temperature among the recipe's lines (mixed ground meats → strictest).
    Eggs only count when they are a primary component (role 'protein'): pancakes get no egg note."""
    temps: list[SafeTemperature] = []
    for line in lines:
        if line.safety_category is None:
            continue
        if line.safety_category is SafetyCategory.EGG and line.role != "protein":
            continue
        temps.append(SAFE_INTERNAL_TEMPS[line.safety_category])
    if not temps:
        return None
    return max(temps, key=lambda t: (t.temp_f, t.rest_minutes))


def doneness_text(ingredient_name: str, temp: SafeTemperature) -> str:
    text = f"Check that the {ingredient_name} reaches {temp.temp_f}°F in the thickest part"
    if temp.rest_minutes:
        text += f", then rest {temp.rest_minutes} minutes"
    return text + "."


def reheat_text() -> str:
    return f"Reheat leftovers until they reach {REHEAT_TEMP_F}°F throughout."


def fridge_storage_text(days: int) -> str:
    unit = "day" if days == 1 else "days"
    return f"Refrigerate in airtight containers and eat within {days} {unit} of cooking."
