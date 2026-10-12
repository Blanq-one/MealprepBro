"""Display lines for the meal-prep plan view (FLOW_SPEC C6, H4/H5, step 2b.5): where each portion comes from,
what to thaw the night before, what to freeze after cooking, and the one Prep notes row. Step 2b.7 (F23,
§19.10): where each batch's portions go, a prep batch's stop state, an assembled meal's sources and the finish
tasks' times. Strings only, from numbers code already computed; the app shows them as they are."""

from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from app.domain.cook_schedule import minutes_text
from app.domain.enums import MealSlot, PrepState

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


ABOUT_THIS_PLAN = "About this plan"


def prep_notes_display(to_freeze: int, may_spoil: int, about: int = 0) -> str | None:
    """'3 to freeze · 4 may spoil · About this plan'; None when there's nothing to note (no row). `about`: the
    plan's own notes and warnings (recipes left out, not proven best), behind the same row (F23)."""
    parts = []
    if to_freeze:
        parts.append(f"{to_freeze} to freeze")
    if may_spoil:
        parts.append(f"{may_spoil} may spoil")
    if about:
        parts.append(ABOUT_THIS_PLAN)
    return " · ".join(parts) or None


# ---------------- step 2b.7: the batch view and assembled meals ----------------
def meal_label(eat_on: date, slot: MealSlot, *, with_date: bool = False) -> str:
    """'Mon lunch', or 'Mon 12 lunch' in a plan longer than a week."""
    day = short_day(eat_on) if with_date else f"{eat_on:%a}"
    return f"{day} {SLOT_WORDS[slot]}"


def amount_text(portions: Decimal) -> str:
    """'1', '½', '1½' (portions come in halves, V3)."""
    whole = int(portions)
    half = portions - whole == Decimal("0.5")
    if whole == 0 and half:
        return "½"
    return f"{whole}½" if half else str(whole)


def uses_display(labels: Sequence[str], freezer: Decimal) -> str:
    """Where a batch's portions go: 'Mon lunch, Tue dinner, Sat dinner (1 to the freezer)', or '2 to the
    freezer' for portions frozen for later weeks only."""
    text = ", ".join(labels)
    if freezer <= 0:
        return text
    frozen = f"{amount_text(freezer)} to the freezer"
    return f"{text} ({frozen})" if text else frozen


STOP_DISPLAY = {
    PrepState.RAW: "prep only",
    PrepState.MARINATED: "marinate only",
    PrepState.PARTLY_COOKED: "partly cooked",
    PrepState.COOKED: "cooked",
}


def stop_display(state: str | None) -> str | None:
    """A prep batch's stop state as the cook day says it: 'Tandoori chicken ×2, marinate only'."""
    return STOP_DISPLAY.get(PrepState(state)) if state else None


PREP_VERBS = {
    PrepState.RAW: "prep",
    PrepState.MARINATED: "marinate",
    PrepState.PARTLY_COOKED: "part-cook",
    PrepState.COOKED: "cook",
}
FINISH_VERBS = {"oven": "roast", "air_fryer": "air fry", "grill": "grill", "microwave": "microwave"}


def in_plan_line(stop_state: str, cook_on: date, finishes: Sequence[tuple[date, str | None]]) -> str:
    """A prep item's page in a plan (FLOW_SPEC §19.10): 'In this plan: marinate on Sun 11, roast on Wed 14 and
    Thu 15.'"""
    text = f"In this plan: {PREP_VERBS[PrepState(stop_state)]} on {short_day(cook_on)}"
    days = sorted({day for day, _ in finishes})
    if days:
        verb = next((FINISH_VERBS.get(e or "", "cook") for _, e in finishes if e), "cook")
        names = [short_day(d) for d in days]
        joined = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
        text += f", {verb} on {joined}"
    return text + "."


def finish_time_display(hands_on: int, hands_off: int) -> str:
    """'25 min, 5 hands-on', or '5 min hands-on' when it's all hands-on."""
    if not hands_off:
        return f"{minutes_text(hands_on)} hands-on"
    return f"{minutes_text(hands_on + hands_off)}, {hands_on} hands-on"


def assembly_source(sources: Sequence[tuple[str, date, date, bool]]) -> tuple[str, str]:
    """(storage, the meal row's line) of an assembled meal from its components' (label, eat on, cook on, from
    the freezer): one line when they all come the same way, else each named ('From the fridge: chicken cooked
    Sun 11, rice cooked Mon 12')."""
    ways = {(cook_on, from_freezer) for _, _, cook_on, from_freezer in sources}
    if len(ways) == 1:
        _, eat_on, cook_on, from_freezer = sources[0]
        return meal_source(eat_on, cook_on, from_freezer)
    frozen = [s for s in sources if s[3]]
    fridge = [s for s in sources if not s[3]]
    parts = []
    if fridge:
        parts.append(
            "From the fridge: "
            + ", ".join(f"{label} cooked {short_day(cook_on)}" for label, _, cook_on, _ in fridge)
        )
    if frozen:
        thaw = date.fromordinal(frozen[0][1].toordinal() - 1)
        parts.append(
            "from the freezer: "
            + ", ".join(f"{label} cooked {short_day(cook_on)}" for label, _, cook_on, _ in frozen)
            + f" · thaw {short_day(thaw)} night"
        )
    text = "; ".join(parts)
    return ("freezer" if frozen else "fridge"), text[:1].upper() + text[1:]
