"""Unit normalization and conversion. Everything is stored as g, ml or count (CLAUDE.md data model rules).

Exact constants: 1 lb = 453.59237 g, 1 oz = 28.349523125 g, US tsp = 4.92892159375 ml,
tbsp = 3 tsp, US cup = 236.5882365 ml, US fl oz = 29.5735295625 ml.
"""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum


class UnitKind(StrEnum):
    MASS = "mass"
    VOLUME = "volume"
    COUNT = "count"


class BaseUnit(StrEnum):
    G = "g"
    ML = "ml"
    COUNT = "count"


BASE_UNIT_FOR_KIND = {UnitKind.MASS: BaseUnit.G, UnitKind.VOLUME: BaseUnit.ML, UnitKind.COUNT: BaseUnit.COUNT}

GRAMS_PER_UNIT: dict[str, Decimal] = {
    "g": Decimal(1),
    "kg": Decimal(1000),
    "oz": Decimal("28.349523125"),
    "lb": Decimal("453.59237"),
}
ML_PER_UNIT: dict[str, Decimal] = {
    "ml": Decimal(1),
    "l": Decimal(1000),
    "tsp": Decimal("4.92892159375"),
    "tbsp": Decimal("14.78676478125"),
    "cup": Decimal("236.5882365"),
    "fl_oz": Decimal("29.5735295625"),
}
COUNT_UNITS = frozenset({"count"})
US_VOLUME_UNITS = frozenset({"tsp", "tbsp", "cup", "fl_oz"})

_ALIASES: dict[str, str] = {
    "g": "g",
    "gram": "g",
    "grams": "g",
    "gr": "g",
    "kg": "kg",
    "kilogram": "kg",
    "kilograms": "kg",
    "kgs": "kg",
    "oz": "oz",
    "ounce": "oz",
    "ounces": "oz",
    "lb": "lb",
    "lbs": "lb",
    "pound": "lb",
    "pounds": "lb",
    "ml": "ml",
    "milliliter": "ml",
    "milliliters": "ml",
    "millilitre": "ml",
    "millilitres": "ml",
    "l": "l",
    "liter": "l",
    "liters": "l",
    "litre": "l",
    "litres": "l",
    "tsp": "tsp",
    "teaspoon": "tsp",
    "teaspoons": "tsp",
    "tsps": "tsp",
    "tbsp": "tbsp",
    "tablespoon": "tbsp",
    "tablespoons": "tbsp",
    "tbsps": "tbsp",
    "tbs": "tbsp",
    "cup": "cup",
    "cups": "cup",
    "fl_oz": "fl_oz",
    "fl oz": "fl_oz",
    "fluid ounce": "fl_oz",
    "fluid ounces": "fl_oz",
    "floz": "fl_oz",
    "count": "count",
    "each": "count",
    "ea": "count",
    "piece": "count",
    "pieces": "count",
    "pc": "count",
    "pcs": "count",
    "whole": "count",
}


class UnitError(ValueError):
    """Base class for unit problems; messages are written for humans (and LLM retry prompts)."""


class AmbiguousUnitError(UnitError):
    pass


class UnknownUnitError(UnitError):
    pass


class ConversionError(UnitError):
    pass


class InvalidQuantityError(ValueError):
    pass


@dataclass(frozen=True)
class IngredientUnits:
    """What the converter needs to know about one ingredient."""

    name: str
    default_unit_kind: UnitKind
    density_g_per_ml: Decimal | None = None
    count_unit_weight_g: Decimal | None = None
    named_units: Mapping[str, Decimal] = field(default_factory=dict)  # unit name -> grams per unit


@dataclass(frozen=True)
class Quantity:
    amount: Decimal
    unit: BaseUnit


def _clean(raw: str) -> str:
    key = re.sub(r"\s+", " ", raw.strip().lower())
    key = key.replace("fl.", "fl").replace(".", "")
    return key.strip()


def normalize_named_unit(raw: str) -> str:
    """Normalize a named unit for storage/lookup: lowercase, underscores, singular."""
    key = _clean(raw).replace(" ", "_").replace("-", "_")
    return key


def normalize_unit(raw: str, named_units: Iterable[str] = ()) -> str:
    """Return the canonical unit code ('g', 'tbsp', 'count', or a named unit such as 'clove').

    'T' and 't' are rejected: tablespoon vs teaspoon is exactly the mistake we must not guess.
    """
    stripped = raw.strip()
    if stripped in {"T", "t"}:
        raise AmbiguousUnitError(f"unit '{raw}' is ambiguous: write 'tbsp' or 'tsp'")
    if not stripped:
        raise UnknownUnitError("unit is empty")
    key = _clean(stripped)
    named = {normalize_named_unit(n) for n in named_units}
    named_key = normalize_named_unit(stripped)
    # Named portions win over generic units (e.g. an ingredient-specific 'cup' weight beats density).
    for candidate in (named_key, named_key.removesuffix("es"), named_key.removesuffix("s")):
        if candidate in named:
            return candidate
    if key in _ALIASES:
        return _ALIASES[key]
    raise UnknownUnitError(f"unknown unit '{raw}'")


def kind_of(unit: str) -> UnitKind | None:
    """Kind of a canonical generic unit; None for named units."""
    if unit in GRAMS_PER_UNIT:
        return UnitKind.MASS
    if unit in ML_PER_UNIT:
        return UnitKind.VOLUME
    if unit in COUNT_UNITS:
        return UnitKind.COUNT
    return None


def _require_positive(amount: Decimal) -> None:
    if amount <= 0:
        raise InvalidQuantityError(f"quantity must be greater than 0 (got {amount})")


def grams_of(amount: Decimal, unit: str, iu: IngredientUnits) -> Decimal:
    """Mass in grams of `amount` `unit` of this ingredient."""
    if amount < 0:
        raise InvalidQuantityError(f"quantity must not be negative (got {amount})")
    if unit in iu.named_units:
        return amount * iu.named_units[unit]
    kind = kind_of(unit)
    if kind is UnitKind.MASS:
        return amount * GRAMS_PER_UNIT[unit]
    if kind is UnitKind.VOLUME:
        if iu.density_g_per_ml is None:
            raise ConversionError(f"{iu.name}: no density, so {unit} can't be converted to grams")
        return amount * ML_PER_UNIT[unit] * iu.density_g_per_ml
    if kind is UnitKind.COUNT:
        if iu.count_unit_weight_g is None:
            raise ConversionError(f"{iu.name}: no typical weight per piece, so a count can't become grams")
        return amount * iu.count_unit_weight_g
    raise UnknownUnitError(f"{iu.name}: unit '{unit}' is not defined for this ingredient")


def to_base(amount: Decimal, unit: str, iu: IngredientUnits) -> Quantity:
    """Convert an authored amount to its stored base unit: mass and named units -> g, volume -> ml,
    count -> count."""
    _require_positive(amount)
    canonical = normalize_unit(unit, iu.named_units)
    if canonical in iu.named_units:
        return Quantity(amount * iu.named_units[canonical], BaseUnit.G)
    kind = kind_of(canonical)
    if kind is UnitKind.MASS:
        return Quantity(amount * GRAMS_PER_UNIT[canonical], BaseUnit.G)
    if kind is UnitKind.VOLUME:
        return Quantity(amount * ML_PER_UNIT[canonical], BaseUnit.ML)
    return Quantity(amount, BaseUnit.COUNT)


def convert(amount: Decimal, from_unit: str, to_unit: str, iu: IngredientUnits | None = None) -> Decimal:
    """Convert between any two units. Cross-kind conversions need the ingredient's density / piece
    weight / named units."""
    if amount < 0:
        raise InvalidQuantityError(f"quantity must not be negative (got {amount})")
    if from_unit == to_unit:
        return amount
    from_kind, to_kind = kind_of(from_unit), kind_of(to_unit)
    if from_kind is UnitKind.MASS and to_kind is UnitKind.MASS:
        return amount * GRAMS_PER_UNIT[from_unit] / GRAMS_PER_UNIT[to_unit]
    if from_kind is UnitKind.VOLUME and to_kind is UnitKind.VOLUME:
        return amount * ML_PER_UNIT[from_unit] / ML_PER_UNIT[to_unit]
    if iu is None:
        raise ConversionError(f"converting {from_unit} to {to_unit} needs ingredient data")
    grams = grams_of(amount, from_unit, iu)
    if to_unit in iu.named_units:
        return grams / iu.named_units[to_unit]
    if to_kind is UnitKind.MASS:
        return grams / GRAMS_PER_UNIT[to_unit]
    if to_kind is UnitKind.VOLUME:
        if iu.density_g_per_ml is None:
            raise ConversionError(f"{iu.name}: no density, so grams can't be converted to {to_unit}")
        return grams / iu.density_g_per_ml / ML_PER_UNIT[to_unit]
    if to_kind is UnitKind.COUNT:
        if iu.count_unit_weight_g is None:
            raise ConversionError(f"{iu.name}: no typical weight per piece, so grams can't become a count")
        return grams / iu.count_unit_weight_g
    raise UnknownUnitError(f"{iu.name}: unit '{to_unit}' is not defined for this ingredient")


def to_grams(quantity: Quantity, iu: IngredientUnits) -> Decimal:
    return grams_of(quantity.amount, quantity.unit.value, iu)
