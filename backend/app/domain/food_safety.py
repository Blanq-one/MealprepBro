"""Hardcoded food-safety table (CLAUDE.md food safety rules). The LLM never sets these values.

Safe internal temperatures and the reheat temperature: the USDA baseline listed in CLAUDE.md.

Storage durations: the FoodSafety.gov Cold Food Storage Chart, transcribed in app/domain/storage_chart.py
    https://www.foodsafety.gov/food-safety-charts/cold-food-storage-charts
    Date Last Reviewed: September 19, 2023
    saved copy: docs/sources/Cold Food Storage Chart _ FoodSafety.gov.pdf (printed 2026-10-08)

Your fixed defaults (BUILD_PLAN Q4): cooked leftovers 3 days in the fridge, never above the chart's upper
bound (3 to 4 days); reheat to 165 F.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from app.domain import storage_chart

FOODSAFETY_GOV_CHART_URL = storage_chart.CHART_URL

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


class FoodSafetyError(ValueError):
    pass


def storage_for(use: str) -> storage_chart.ChartRow:
    """The chart row for an app use, e.g. 'cooked_leftovers' or 'raw_poultry_pieces'."""
    return storage_chart.chart_row(storage_chart.APP_STORAGE[use])


def leftover_fridge_days_upper_bound() -> int:
    """The chart's upper bound for cooked leftovers (cooked meat or poultry: 3 to 4 days)."""
    days = storage_for("cooked_leftovers").fridge_days
    assert days is not None  # the leftovers row is a day range
    return days[1]


def validate_leftover_fridge_days(days: int) -> int:
    if days < 0:
        raise FoodSafetyError("leftover fridge days must not be negative")
    upper = leftover_fridge_days_upper_bound()
    if days > upper:
        raise FoodSafetyError(
            f"leftover fridge days {days} is above the FoodSafety.gov chart maximum of {upper} "
            f"(cooked meat or poultry: {storage_for('cooked_leftovers').refrigerator})"
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


def freezer_storage_text(use: str = "cooked_leftovers") -> str:
    row = storage_for(use)
    return f"Freezer: {row.freezer} for best quality (FoodSafety.gov). {storage_chart.FREEZER_NOTE}"
