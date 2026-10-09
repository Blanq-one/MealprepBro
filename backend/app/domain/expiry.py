"""Estimated "use by" dates for new inventory lots (Phase 2: "Done shopping" and "Mark cooked"). Pure.

Raw meat, poultry, fish and eggs in the fridge use the FoodSafety.gov chart (fridge_life.py, short end of its
range). Other food uses the ingredient's own shelf life for where it is stored. Frozen food has no date: the
chart notes that food kept frozen at 0 °F stays safe indefinitely (its freezer times are for quality). Every
date is an estimate, and the lot says so."""

from dataclasses import dataclass
from datetime import date, timedelta

from app.domain.fridge_life import fridge_life


@dataclass(frozen=True)
class ShelfLife:
    slug: str
    safety_category: str | None
    pantry_days: int | None
    fridge_days: int | None
    freezer_days: int | None


def estimate_expiry(life: ShelfLife, location: str, start: date) -> date | None:
    """When a lot stored at `location` from `start` should be used by, or None when unknown or frozen."""
    if location == "freezer":
        return start + timedelta(days=life.freezer_days) if life.freezer_days else None
    if location == "fridge":
        chart = fridge_life(life.slug, life.safety_category)
        days = chart.days if chart is not None else life.fridge_days
    else:
        days = life.pantry_days
    return start + timedelta(days=days) if days else None
