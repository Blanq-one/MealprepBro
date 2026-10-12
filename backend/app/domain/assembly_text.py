"""Assembly names and eating-day instructions, composed by code (step 2b.10, FLOW_SPEC §19.5). The LLM writes
none of this text: amounts come from code, appliance temperatures and times from the item's tasks, and the
safety lines from the food-safety table.

What an item brings (protein, a base, vegetables, a sauce, or a whole dish) is worked out from its lines'
roles and weights, and used only to name meals (and, from 2b.11, to suggest combinations).

Names, by the shape of the meal:
- a dish alone: its title;
- a dish + a base: "{dish} with {base}", and "and a side {vegetables}";
- protein + base (+ vegetables): "{protein} over {base}" (+ "with {vegetables}"), or "with {base}" when the
  base isn't a grain (roasted potatoes);
- protein + vegetables: "{protein} with {vegetables}";
- with a flatbread add-on: "{protein} wrap with {the rest}"; a dish and flatbread: "{dish} with tortillas";
- a sauce: "… with {sauce}", or "… and {sauce}" after another "with".
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from app.domain.food_safety import REHEAT_TEMP_F, SafeTemperature

FRESH_MINUTES = 5  # an item made on the eating day (prep_storage.MADE_ON_THE_DAY_MINUTES)
FLATBREADS = frozenset({"flour-tortilla-small", "corn-tortilla", "chapati", "pita"})
COUNTED_ROLES = frozenset({"protein", "carb", "vegetable", "fruit", "sauce", "dairy"})
PROTEIN_SHARE = Decimal("0.25")  # an item brings protein when protein lines are at least this share
DISH_REST_SHARE = Decimal("0.4")  # ... and is a whole dish when vegetables and sauce are at least this
SAUCE_SHARE = Decimal("0.35")
BASE_SHARE = Decimal("0.5")
APPLIANCE_VERBS = {
    "oven": "Roast",
    "air_fryer": "Air fry",
    "stovetop": "Cook",
    "grill": "Grill",
    "microwave": "Microwave",
    "pressure_cooker": "Pressure cook",
    "slow_cooker": "Slow cook",
}


class Brings(StrEnum):
    DISH = "dish"
    PROTEIN = "protein"
    BASE = "base"
    VEGETABLES = "vegetables"
    SAUCE = "sauce"


@dataclass(frozen=True)
class BringsLine:
    role: str
    grams: Decimal  # edible grams, for the item's base servings
    grain: bool = False  # the ingredient's category is grain (rice, quinoa, pasta)


def brings(lines: Sequence[BringsLine]) -> Brings:
    """What an item brings to a meal, from its lines' roles weighed in grams (seasoning, fat, garnish and
    water left out)."""
    counted = [line for line in lines if line.role in COUNTED_ROLES and line.grams > 0]
    whole = sum((line.grams for line in counted), Decimal(0))
    if whole <= 0:
        return Brings.SAUCE

    def share(*roles: str) -> Decimal:
        return sum((line.grams for line in counted if line.role in roles), Decimal(0)) / whole

    protein, carbs = share("protein"), share("carb")
    rest = share("vegetable", "fruit", "sauce", "dairy")
    if protein < PROTEIN_SHARE and share("sauce", "dairy") >= SAUCE_SHARE:
        return Brings.SAUCE
    if protein >= PROTEIN_SHARE:
        return Brings.DISH if rest >= DISH_REST_SHARE else Brings.PROTEIN
    if carbs >= BASE_SHARE:
        return Brings.BASE
    return Brings.VEGETABLES


def is_grain_base(lines: Sequence[BringsLine]) -> bool:
    """A base whose carbohydrate lines are grains: a meal goes "over" it."""
    carbs = [line for line in lines if line.role == "carb" and line.grams > 0]
    return bool(carbs) and all(line.grain for line in carbs)


@dataclass(frozen=True)
class NamePart:
    label: str  # "roasted chicken"
    title: str  # "Roasted chicken thighs": a lone dish is called by its title
    brings: Brings
    grain_base: bool = False


def _join(words: Sequence[str]) -> str:
    if len(words) <= 1:
        return "".join(words)
    return ", ".join(words[:-1]) + " and " + words[-1]


def _capital(text: str) -> str:
    return text[:1].upper() + text[1:]


def assembly_name(
    parts: Sequence[NamePart], add_ons: Sequence[str] = (), *, flatbread: str | None = None
) -> str:
    """The composed name of a meal built from `parts` (in the assembly's order) and its add-ons (short names,
    the flatbread left out of `add_ons` and given as `flatbread`, plural: "tortillas")."""
    dishes = [p for p in parts if p.brings is Brings.DISH]
    proteins = [p for p in parts if p.brings is Brings.PROTEIN]
    bases = [p for p in parts if p.brings is Brings.BASE]
    vegetables = [p.label for p in parts if p.brings is Brings.VEGETABLES]
    sauces = [p.label for p in parts if p.brings is Brings.SAUCE]
    if len(parts) == 1 and not add_ons and flatbread is None:
        return parts[0].title
    mains = [p.label for p in dishes + proteins] or [p.label for p in bases] or vegetables[:1] or sauces[:1]
    if not dishes and not proteins:
        bases = [p for p in bases if p.label not in mains]
        vegetables = [v for v in vegetables if v not in mains]
        sauces = [s for s in sauces if s not in mains]
    main = _join(mains)
    withs: list[str] = []
    if flatbread is not None and not dishes:
        rest = [p.label for p in bases] + vegetables + sauces + list(add_ons)
        name = f"{main} wrap" + (f" with {_join(rest)}" if rest else "")
        return _capital(name)
    name = main
    if flatbread is not None:  # a dish with flatbread on the side: "Chicken curry with tortillas"
        withs.append(flatbread)
    base_text = _join([p.label for p in bases])
    if bases and dishes:
        withs.append(base_text)
    elif bases:
        if all(p.grain_base for p in bases):
            name += f" over {base_text}"
        else:
            withs.append(base_text)
    if vegetables:
        if dishes and bases:
            side = f"a side {_join(vegetables)}"
            name += (" with " + _join(withs) + f" and {side}") if withs else f" and {side}"
            withs = []
        else:
            withs.extend(vegetables)
    if withs:
        name += " with " + _join(withs)
        joined = True
    else:
        joined = " with " in name
    if sauces:
        name += (" and " if joined else " with ") + _join(sauces)
    return _capital(name)


# ---------------- eating-day instructions ----------------
HALF = Decimal("0.5")


def portions_text(portions: Decimal) -> str:
    """'1 portion', '½ portion', '1½ portions'."""
    whole = int(portions)
    half = portions - whole == HALF
    if whole == 0 and half:
        return "½ portion"
    number = f"{whole}½" if half else f"{whole}"
    return f"{number} portion" if portions == 1 else f"{number} portions"


@dataclass(frozen=True)
class FinishStep:
    """The stages left of an item stopped early, as one appliance step on the eating day."""

    equipment: str | None  # oven, air_fryer, stovetop, ...
    appliance_temp_f: int | None
    minutes: int
    safe_temp: SafeTemperature | None  # the stage cooks a protein: the safe internal temperature


@dataclass(frozen=True)
class MealItem:
    """One item of a meal on its eating day."""

    label: str
    portions: Decimal  # per person
    state_label: str = ""  # "marinated" for a finish stage: "Roast the marinated chicken"
    from_freezer: bool = False
    fresh: bool = False  # made on the eating day (no storage row)
    cold: bool = False  # nothing in it is cooked: eaten cold from the fridge, never reheated
    finish: FinishStep | None = None  # stages left (stopped before its last stage)


def _amount(item: MealItem) -> str:
    return f"{portions_text(item.portions)} {item.label}"


def _finish_sentence(item: MealItem) -> str:
    assert item.finish is not None
    f = item.finish
    verb = APPLIANCE_VERBS.get(f.equipment or "", "Cook")
    what = (
        f"the {item.state_label} {item.label}".replace("  ", " ") if item.state_label else f"the {item.label}"
    )
    setting = f"{f.appliance_temp_f}°F for {f.minutes} min" if f.appliance_temp_f else f"{f.minutes} min"
    text = f"{verb} {what} ({portions_text(item.portions)}): {setting}"
    if f.safe_temp is not None:
        text += f", until it reaches {f.safe_temp.temp_f}°F"
        if f.safe_temp.rest_minutes:
            text += f", then rest {f.safe_temp.rest_minutes} minutes"
    return text + "."


def finish_task_text(kind: str, item: MealItem, *, meal: str | None = None, minutes: int = 0) -> str:
    """A finish task's line at the top of its eating day (step 2b.7, FLOW_SPEC §19.10): the stages left
    ("Roast the marinated chicken (2 portions): 425°F for 25 min, until it reaches 165°F."), a reheat, or
    putting a meal together."""
    if kind == "stage" and item.finish is not None:
        sentence = _finish_sentence(item)
        return (
            f"From the freezer, thawed overnight in the fridge: {sentence}" if item.from_freezer else sentence
        )
    if kind == "reheat":
        return (
            f"Serve {_amount(item)} cold." if item.cold else f"Reheat {_amount(item)} to {REHEAT_TEMP_F}°F."
        )
    return f"Put together {meal or 'the meal'} ({minutes} min)."


def meal_instruction(
    items: Sequence[MealItem],
    add_ons: Sequence[str] = (),
    *,
    flatbread: str | None = None,
    wrap: bool = True,
) -> str:
    """The short eating-day instruction for one meal. `add_ons`: display amounts with names ("¼ cup sliced
    bell pepper", "1 tbsp hot sauce"); `flatbread`: the flatbread's ("1 flour tortilla"), or None; `wrap`:
    filled with the rest, or (a dish with flatbread, like chapati) eaten with it."""
    sentences: list[str] = []
    finishing = [i for i in items if i.finish is not None]
    for item in finishing:
        if item.from_freezer:
            sentences.append(f"From the freezer, thawed overnight in the fridge: {_finish_sentence(item)}")
        else:
            sentences.append(_finish_sentence(item))
    fridge = [i for i in items if i.finish is None and not i.fresh and not i.cold and not i.from_freezer]
    frozen = [i for i in items if i.finish is None and not i.fresh and not i.cold and i.from_freezer]
    cold = [i for i in items if i.finish is None and not i.fresh and i.cold]
    if fridge:
        sentences.append(f"Reheat {_join([_amount(i) for i in fridge])} to {REHEAT_TEMP_F}°F.")
    if frozen:
        sentences.append(
            f"From the freezer, thawed overnight in the fridge: reheat {_join([_amount(i) for i in frozen])} "
            f"to {REHEAT_TEMP_F}°F."
        )
    if cold:
        thawed = (
            " (from the freezer, thawed overnight in the fridge)" if any(i.from_freezer for i in cold) else ""
        )
        sentences.append(f"Serve {_join([_amount(i) for i in cold])} cold{thawed}.")
    for item in (i for i in items if i.fresh):
        sentences.append(f"Make the {item.label} fresh ({FRESH_MINUTES} min) and add it cold.")
    if flatbread is not None and wrap:
        filling = (
            [i.label for i in items if not i.fresh] + [i.label for i in items if i.fresh] + list(add_ons)
        )
        sentences.append(
            f"Warm {flatbread}; fill with the {_join(filling)}." if filling else f"Warm {flatbread}."
        )
    elif flatbread is not None:
        sentences.append(f"Warm {flatbread} to eat with it.")
        if add_ons:
            sentences.append(f"Top with {_join(list(add_ons))}.")
    elif add_ons:
        sentences.append(f"Top with {_join(list(add_ons))}.")
    return " ".join(sentences)
