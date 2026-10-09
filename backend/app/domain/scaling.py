"""Exact and practical scaling of recipe lines (BUILD_PLAN §7.1).

Practical quantities are the single source of truth after scaling: nutrition, cost and validation all
run on the rounded values. Rounding happens in the display unit, so what you read is what was computed.
Scale = 1 keeps the authored quantity untouched.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.domain.units import COUNT_UNITS, GRAMS_PER_UNIT, ML_PER_UNIT, US_VOLUME_UNITS

MAX_SCALE_FACTOR = Decimal(10)
PORTION_MULTIPLIERS = {
    "small": Decimal("0.75"),
    "normal": Decimal("1.00"),
    "large": Decimal("1.25"),
    "extra_large": Decimal("1.50"),
}

_TSP = ML_PER_UNIT["tsp"]
_TBSP = ML_PER_UNIT["tbsp"]
_CUP = ML_PER_UNIT["cup"]
_QUARTER_CUP = _CUP / 4
_EIGHTH = Decimal("0.125")
_HALF = Decimal("0.5")
_CUP_FRACTIONS = (
    Decimal(0),
    Decimal(1) / 4,
    Decimal(1) / 3,
    Decimal(1) / 2,
    Decimal(2) / 3,
    Decimal(3) / 4,
    Decimal(1),
)


class ScalingError(ValueError):
    pass


@dataclass(frozen=True)
class ScaledLine:
    """A recipe line after scaling. `amount`/`unit` are what the cook measures."""

    amount: Decimal
    unit: str
    exact_amount: Decimal  # unrounded, in the authored unit
    authored_amount: Decimal
    authored_unit: str
    was_rounded: bool


def scale_factor(base_servings: int, portions: int, portion_multiplier: Decimal = Decimal(1)) -> Decimal:
    """portions × multiplier / base_servings, e.g. base 4 → 5 portions = 1.25."""
    if base_servings < 1:
        raise ScalingError("base servings must be at least 1")
    if portions < 1:
        raise ScalingError("portions must be at least 1")
    if portion_multiplier <= 0:
        raise ScalingError("portion multiplier must be positive")
    factor = Decimal(portions) * portion_multiplier / Decimal(base_servings)
    if factor > MAX_SCALE_FACTOR:
        raise ScalingError(f"scale factor {factor:.2f} is above the maximum of {MAX_SCALE_FACTOR}")
    return factor


def round_to_step(value: Decimal, step: Decimal) -> Decimal:
    """Half-up rounding to a multiple of `step`."""
    return (value / step).quantize(Decimal(1), rounding=ROUND_HALF_UP) * step


def _at_least(value: Decimal, step: Decimal) -> Decimal:
    rounded = round_to_step(value, step)
    return rounded if rounded >= step else step


def practical_mass_grams(grams: Decimal) -> Decimal:
    """< 10 g → 1 g steps; 10–250 g → 5 g; > 250 g → 10 g."""
    if grams < 10:
        return _at_least(grams, Decimal(1))
    if grams <= 250:
        return round_to_step(grams, Decimal(5))
    return round_to_step(grams, Decimal(10))


def practical_metric_volume_ml(ml: Decimal) -> Decimal:
    """Same steps as mass: < 10 ml → 1 ml; 10–250 ml → 5 ml; > 250 ml → 10 ml."""
    return practical_mass_grams(ml)


def practical_us_volume(ml: Decimal) -> tuple[Decimal, str]:
    """< 1 tbsp → ⅛ tsp steps; < ¼ cup → ½ tbsp steps; otherwise the nearest standard cup measure."""
    if ml < _TBSP:
        tsp = _at_least(ml / _TSP, _EIGHTH)
        return (Decimal(1), "tbsp") if tsp == 3 else (tsp, "tsp")
    if ml < _QUARTER_CUP:
        tbsp = round_to_step(ml / _TBSP, _HALF)
        return (Decimal("0.25"), "cup") if tbsp >= 4 else (tbsp, "tbsp")
    cups = ml / _CUP
    whole = int(cups)
    rest = cups - whole
    best = min(_CUP_FRACTIONS, key=lambda f: (abs(rest - f), -f))  # ties go up
    return Decimal(whole) + best, "cup"


def practical_count(count: Decimal, step: Decimal) -> Decimal:
    """Half-up to the ingredient's count step (eggs 1, onions ½), never below one step."""
    return _at_least(count, step)


def practical_named(amount: Decimal) -> Decimal:
    """Named units (clove, scoop, slice, can): whole units, or ½ when the amount is below one."""
    if amount < 1:
        return _at_least(amount, _HALF)
    return round_to_step(amount, Decimal(1))


def practical_round(amount: Decimal, unit: str, count_step: Decimal = Decimal(1)) -> tuple[Decimal, str]:
    """Round an exact scaled amount to something you can measure, in the display unit."""
    if unit in GRAMS_PER_UNIT:
        if unit == "g":
            return practical_mass_grams(amount), "g"
        if unit == "kg":
            return practical_mass_grams(amount * 1000), "g"
        step = Decimal("0.25") if unit == "oz" else Decimal("0.05")
        return _at_least(amount, step), unit
    if unit in US_VOLUME_UNITS:
        return practical_us_volume(amount * ML_PER_UNIT[unit])
    if unit in ML_PER_UNIT:
        return practical_metric_volume_ml(amount * ML_PER_UNIT[unit]), "ml"
    if unit in COUNT_UNITS:
        return practical_count(amount, count_step), "count"
    return practical_named(amount), unit


def scale_line(
    authored_amount: Decimal, authored_unit: str, factor: Decimal, count_step: Decimal = Decimal(1)
) -> ScaledLine:
    if factor <= 0:
        raise ScalingError("scale factor must be positive")
    if factor == 1:
        return ScaledLine(
            amount=authored_amount,
            unit=authored_unit,
            exact_amount=authored_amount,
            authored_amount=authored_amount,
            authored_unit=authored_unit,
            was_rounded=False,
        )
    exact = authored_amount * factor
    amount, unit = practical_round(exact, authored_unit, count_step)
    return ScaledLine(
        amount=amount,
        unit=unit,
        exact_amount=exact,
        authored_amount=authored_amount,
        authored_unit=authored_unit,
        was_rounded=True,
    )
