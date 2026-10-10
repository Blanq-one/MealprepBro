"""Quick-add amounts (FLOW_SPEC P1): Full, ¾, ½ or ¼ of an item's usual amount, and custom amounts in its
natural units. Pure: every amount and display string is computed here; the server converts what you send.

The usual ("full") amount is a product's package, or one piece of a count item sold loose.
- Mass and volume: the fraction of the package, exactly ("¾ · 1.5 lb (680 g)").
- A pack of pieces (12 eggs, 20 tortillas): the fraction rounded half-up to whole pieces (the item's count
  step if that's bigger), at least one ("½ · 6 eggs").
- One piece (a head of cabbage): the fraction itself ("¼ head").
An option whose amount equals a bigger option's is left out (a 2-pack has no separate ¾).
"""

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from app.domain.units import GRAMS_PER_UNIT, ML_PER_UNIT, IngredientUnits, convert

OptionKey = Literal["full", "three_quarters", "half", "quarter"]
FRACTIONS: tuple[tuple[OptionKey, Decimal, str], ...] = (
    ("full", Decimal(1), "Full"),
    ("three_quarters", Decimal("0.75"), "¾"),
    ("half", Decimal("0.5"), "½"),
    ("quarter", Decimal("0.25"), "¼"),
)
GLYPHS = {Decimal("0.25"): "¼", Decimal("0.5"): "½", Decimal("0.75"): "¾"}
WHOLE_ITEM_UNITS = ("head", "bunch", "loaf")  # named units that mean "one whole piece"
Q3 = Decimal("0.001")

# custom-amount units: (unit to send, label, stepper step)
US_MASS = (("lb", "lb", "0.25"), ("oz", "oz", "1"), ("g", "g", "25"))
METRIC_MASS = (("g", "g", "25"), ("kg", "kg", "0.1"))
US_VOLUME = (("cup", "cups", "0.25"), ("fl_oz", "fl oz", "1"), ("ml", "ml", "50"))
METRIC_VOLUME = (("ml", "ml", "50"), ("l", "l", "0.1"))


class AmountError(ValueError):
    pass


@dataclass(frozen=True)
class AmountChoice:
    key: OptionKey
    quantity: Decimal  # in the base unit, as stored
    unit: str  # g | ml | count
    display: str


@dataclass(frozen=True)
class CustomUnit:
    unit: str  # what to send as custom_unit
    label: str  # "lb", "eggs", "heads"
    step: Decimal
    start: Decimal  # the full amount in this unit, to the step


def _trim(value: Decimal, places: str) -> str:
    text = f"{value.quantize(Decimal(places), ROUND_HALF_UP):,f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def noun(name: str, named_units: dict[str, Decimal] | None = None) -> str:
    """What one piece is called: a whole-item unit ("head"), else the name's first part ("egg, large" → egg;
    "flour tortilla (Price Rite, 37 g)" → flour tortilla)."""
    for unit in WHOLE_ITEM_UNITS:
        if named_units and unit in named_units:
            return unit
    base = re.sub(r"\([^)]*\)", "", name).split(",")[0]
    return " ".join(base.split()).lower()


def plural(word: str) -> str:
    if word.endswith(("s", "x", "ch", "sh", "tomato", "potato")):
        return word + "es"
    if word.endswith("y") and word[-2:-1] not in ("a", "e", "i", "o", "u"):
        return word[:-1] + "ies"
    if word.endswith("loaf"):
        return word[:-1] + "ves"
    return word + "s"


def mass_display(grams: Decimal, us: bool = True) -> str:
    grams_text = f"{grams.quantize(Decimal(1), ROUND_HALF_UP):,} g"
    if not us:
        return grams_text
    pounds = grams / GRAMS_PER_UNIT["lb"]
    if pounds >= 1:
        return f"{_trim(pounds, '0.01')} lb ({grams_text})"
    return f"{_trim(grams / GRAMS_PER_UNIT['oz'], '0.1')} oz ({grams_text})"


def volume_display(ml: Decimal, us: bool = True) -> str:
    ml_text = f"{ml.quantize(Decimal(1), ROUND_HALF_UP):,} ml"
    if not us:
        return ml_text
    cups = ml / ML_PER_UNIT["cup"]
    if cups >= Decimal("0.25"):
        text = _trim(cups, "0.01")
        return f"{text} {'cup' if text == '1' else 'cups'} ({ml_text})"
    return f"{_trim(ml / ML_PER_UNIT['tbsp'], '0.1')} tbsp ({ml_text})"


def count_display(quantity: Decimal, piece: str) -> str:
    whole, part = divmod(quantity, 1)
    if part == 0:
        return f"{whole:f} {piece if whole == 1 else plural(piece)}"
    glyph = GLYPHS.get(part)
    if glyph is None:
        return f"{_trim(quantity, '0.01')} {plural(piece)}"
    return f"{glyph} {piece}" if whole == 0 else f"{whole:f}{glyph} {plural(piece)}"


def amount_display(quantity: Decimal, unit: str, piece: str, us: bool = True) -> str:
    if unit == "g":
        return mass_display(quantity, us)
    if unit == "ml":
        return volume_display(quantity, us)
    return count_display(quantity, piece)


def _round_to(value: Decimal, step: Decimal) -> Decimal:
    steps = (value / step).quantize(Decimal(1), ROUND_HALF_UP)
    return (max(steps, Decimal(1)) * step).quantize(step)


def option_quantity(key: OptionKey, full: Decimal, unit: str, count_step: Decimal = Decimal(1)) -> Decimal:
    """The base-unit amount of one option (see the module docstring)."""
    fraction = next(f for k, f, _ in FRACTIONS if k == key)
    if unit != "count":
        return (full * fraction).quantize(Q3, ROUND_HALF_UP)
    if full == 1:
        return fraction
    return _round_to(full * fraction, max(count_step, Decimal(1)))


def amount_options(
    full: Decimal, unit: str, piece: str, count_step: Decimal = Decimal(1), us: bool = True
) -> tuple[AmountChoice, ...]:
    if full <= 0:
        raise AmountError("the usual amount must be positive")
    single_piece = unit == "count" and full == 1
    out: list[AmountChoice] = []
    seen: set[Decimal] = set()
    for key, _, label in FRACTIONS:
        quantity = option_quantity(key, full, unit, count_step)
        if quantity in seen:
            continue
        seen.add(quantity)
        amount = amount_display(quantity, unit, piece, us)
        out.append(AmountChoice(key, quantity, unit, amount if single_piece else f"{label} · {amount}"))
    return tuple(out)


def custom_units(
    full: Decimal,
    unit: str,
    iu: IngredientUnits,
    piece: str,
    *,
    count_step: Decimal = Decimal(1),
    us: bool = True,
) -> tuple[CustomUnit, ...]:
    """The units a custom amount can be typed in, the natural one first, each with a stepper step and a
    starting value (the full amount)."""
    mass = US_MASS if us else METRIC_MASS
    if unit == "g":
        options: tuple[tuple[str, str, str], ...] = mass
    elif unit == "ml":
        options = US_VOLUME if us else METRIC_VOLUME
    else:
        piece_step = "0.5" if full == 1 else str(max(count_step, Decimal(1)))
        options = (("count", plural(piece), piece_step),)
        if iu.count_unit_weight_g is not None:  # loose produce is often weighed: "2 lb of tomatoes"
            options += mass
    out = []
    for code, label, step_text in options:
        step = Decimal(step_text)
        out.append(CustomUnit(code, label, step, _round_to(convert(full, unit, code, iu), step)))
    return tuple(out)
