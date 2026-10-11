"""Display lines for the meal-prep plan view (FLOW_SPEC C6, H4/H5, step 2b.5): where each portion comes from,
what to thaw the night before, what to freeze after cooking, and the one Prep notes row. Strings only, from
numbers code already computed; the app shows them as they are."""

from datetime import date

from app.domain.enums import MealSlot

SLOT_WORDS = {
    MealSlot.BREAKFAST: "breakfast",
    MealSlot.LUNCH: "lunch",
    MealSlot.DINNER: "dinner",
    MealSlot.SNACK: "snack",
    MealSlot.PROTEIN_DESSERT: "dessert",
    MealSlot.DRINK: "drink",
}


def short_day(day: date) -> str:
    """'Mon 12'."""
    return f"{day:%a} {day.day}"


def portion_split(portions: int, freezer_meals: int, household: int, extras: int) -> tuple[int, int]:
    """(fridge, freezer) portions of a batch: meals past the fridge window and extra portions go in the
    freezer, everything else stays in the fridge (or is eaten the day it's cooked)."""
    freezer = min(portions, freezer_meals * household + extras)
    return portions - freezer, freezer


def portions_display(portions: int, fridge: int, freezer: int) -> str:
    """'5 portions (3 fridge, 2 freezer)', or '5 portions' when nothing is frozen."""
    text = f"{portions} portion{'s' if portions != 1 else ''}"
    return f"{text} ({fridge} fridge, {freezer} freezer)" if freezer else text


def meal_source(eat_on: date, cook_on: date, from_freezer: bool) -> tuple[str, str]:
    """(storage, the meal row's line): fresh 'Cooked today', fridge 'From the fridge, cooked Mon 12', freezer
    'From the freezer, cooked Mon 12 · thaw Fri 16 night'."""
    if from_freezer:
        thaw = date.fromordinal(eat_on.toordinal() - 1)
        return "freezer", f"From the freezer, cooked {short_day(cook_on)} · thaw {short_day(thaw)} night"
    if eat_on == cook_on:
        return "fresh", "Cooked today"
    return "fridge", f"From the fridge, cooked {short_day(cook_on)}"


def thaw_note(slot: MealSlot, title: str) -> str:
    """On the day before a freezer meal: 'Thaw tomorrow's lunch (Chicken over rice) in the fridge tonight.'"""
    return f"Thaw tomorrow's {SLOT_WORDS[slot]} ({title}) in the fridge tonight."


def freeze_today(title: str, freezer: int) -> str:
    """On a cook day: 'Freeze 2 portions of Chicken over rice once cooled.'"""
    return f"Freeze {freezer} portion{'s' if freezer != 1 else ''} of {title} once cooled."


def freeze_portions_note(title: str, freezer: int, cook_on: date, note: str | None) -> str:
    """A Prep notes item: 'Freeze 2 portions of Chicken over rice after cooking on Mon 12. Freeze the chicken
    and rice; make the yogurt sauce fresh.'"""
    portions = f"{freezer} portion{'s' if freezer != 1 else ''}"
    text = f"Freeze {portions} of {title} after cooking on {short_day(cook_on)}."
    return f"{text} {note}" if note else text


def spoil_note(name: str, amount: str) -> str:
    return f"{name}: about {amount} left with no use planned, so it may spoil."


def prep_notes_display(to_freeze: int, may_spoil: int) -> str | None:
    """'3 to freeze · 4 may spoil'; None when there's nothing to note (no row)."""
    parts = []
    if to_freeze:
        parts.append(f"{to_freeze} to freeze")
    if may_spoil:
        parts.append(f"{may_spoil} may spoil")
    return " · ".join(parts) or None
