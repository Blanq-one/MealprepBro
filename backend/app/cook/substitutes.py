"""Deterministic substitutes for a missing recipe line (FLOW_SPEC §14 step 4, change F11). Pure, no LLM.

In order:
  1. an accepted pair (ingredient_substitution, e.g. chapati → flour tortilla) whose substitute you have,
     with the pair's own quantity rule;
  2. else, for a vegetable or herb, something you have from the same culinary group (J2: onions and
     scallions, leafy cooking greens, sturdy green vegetables, …; app/seed/data/pantry_catalog.json): yellow
     onion can become red onion, never spinach. A vegetable in no group (or alone in its group) gets none.
  3. else, for anything else, something you have with the same role and category, allowed and not disliked.
     "Same role" means
     your recipes use it in that role (spinach is a vegetable in them, never a sauce), so tomato paste
     never becomes spinach. Seasonings, garnishes and "other" lines (broth, water) get no pantry
     substitute: they carry the flavor or the structure. The amount keeps the line's protein grams for a
     protein, its kcal for a carb, and its mass otherwise.
Chicken cuts are exact (M6): a cut never stands in for, or is replaced by, a cut of another bone or skin form
(bone-in thighs never become boneless ones), in any of the three steps.
Each thing you have stands in for at most one line of a recipe (the caller passes what is already taken).
Amounts are code-computed and rounded to something you can measure. Nothing is stored; the recipe's numbers
stay those of the recipe as written.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from app.domain.chicken_cuts import CutForm, same_form
from app.domain.nutrition import NutritionLine, NutritionProfile, line_amounts
from app.domain.quantities import format_quantity
from app.domain.scaling import (
    practical_count,
    practical_mass_grams,
    practical_metric_volume_ml,
    practical_us_volume,
)
from app.domain.units import ConversionError, IngredientUnits, UnitError, UnitKind, convert

PANTRY_ROLES = frozenset({"protein", "carb", "vegetable", "fat", "dairy", "sauce", "fruit"})
ROLE_RULES: dict[str, dict[str, str]] = {
    "protein": {"mode": "match_nutrient", "nutrient": "protein_g"},
    "carb": {"mode": "match_nutrient", "nutrient": "energy_kcal"},
}
SAME_MASS = {"mode": "same_mass"}
_HUNDRED = Decimal(100)


@dataclass(frozen=True)
class Have:
    """Something you have that could stand in: a toggled-on pantry item, a "have it" extra or an Always-have
    item."""

    ingredient_id: int
    name: str
    category: str
    profile: NutritionProfile
    units: IngredientUnits
    count_rounding_step: Decimal
    planning_unit: str
    stock: Decimal | None  # in the planning unit; None = enough (a "have it" extra, an Always-have item)
    opened: bool = False
    expires_on: date | None = None
    roles: frozenset[str] = frozenset()  # the roles your recipes use it in
    group: str | None = None  # its culinary group (vegetables and herbs, J2)
    cut: CutForm | None = None  # a chicken cut's bone and skin (M6)


@dataclass(frozen=True)
class AcceptedPair:
    from_id: int
    to_id: int
    rule: Mapping[str, Any]  # {"mode": count_for_count | same_mass | match_nutrient | ratio, ...}
    note: str | None = None


@dataclass(frozen=True)
class MissingLine:
    ingredient_id: int
    name: str
    role: str
    category: str
    grams: Decimal  # as purchased, at the card's practical amount
    count: Decimal | None  # the amount when the line is counted (pieces), else None
    protein_g: Decimal
    kcal: Decimal
    group: str | None = None  # its culinary group (vegetables and herbs, J2)
    cut: CutForm | None = None  # a chicken cut's bone and skin (M6)

    @property
    def grouped(self) -> bool:
        """Vegetables and herbs swap only inside their culinary group (J2)."""
        return self.group is not None or self.category == "vegetable"


@dataclass(frozen=True)
class Substitute:
    ingredient_id: int
    name: str
    amount: Decimal  # in `unit`, rounded to something you can measure
    unit: str
    display: str  # "2 tbsp", "150 g", "3"
    via: str  # pair | pantry
    note: str | None = None


def per_gram(profile: NutritionProfile, code: str) -> Decimal:
    """Nutrient per gram as purchased (edible fraction applied)."""
    return line_amounts(NutritionLine(profile, _HUNDRED)).get(code, Decimal(0)) / _HUNDRED


def _measurable(grams: Decimal, have: Have, units: str) -> tuple[Decimal, str]:
    """Grams of the substitute → a practical amount in its natural unit (pieces, cups or spoons, grams)."""
    kind = have.units.default_unit_kind
    if kind is UnitKind.COUNT and have.units.count_unit_weight_g:
        return practical_count(grams / have.units.count_unit_weight_g, have.count_rounding_step), "count"
    if kind is UnitKind.VOLUME and have.units.density_g_per_ml:
        ml = grams / have.units.density_g_per_ml
        return (practical_metric_volume_ml(ml), "ml") if units == "metric" else practical_us_volume(ml)
    return practical_mass_grams(grams), "g"


def _fits(amount: Decimal, unit: str, have: Have) -> bool:
    if have.stock is None:
        return True
    try:
        return convert(amount, unit, have.planning_unit, have.units) <= have.stock
    except (ConversionError, UnitError):
        return False


def _grams_for(line: MissingLine, have: Have, rule: Mapping[str, Any]) -> Decimal | None:
    mode = rule.get("mode")
    if mode == "same_mass":
        return line.grams
    if mode == "ratio":
        return line.grams * Decimal(str(rule.get("ratio", "1")))
    if mode == "match_nutrient":
        code = str(rule.get("nutrient", "protein_g"))
        density = per_gram(have.profile, code)
        wanted = line.protein_g if code == "protein_g" else line.kcal if code == "energy_kcal" else None
        if wanted is None or density <= 0:
            return None
        return wanted / density
    return None


def _make(have: Have, grams: Decimal, *, via: str, units: str, note: str | None) -> Substitute | None:
    if grams <= 0:
        return None
    amount, unit = _measurable(grams, have, units)
    if not _fits(amount, unit, have):
        return None
    return Substitute(have.ingredient_id, have.name, amount, unit, format_quantity(amount, unit), via, note)


def _pair_substitute(line: MissingLine, pair: AcceptedPair, have: Have, units: str) -> Substitute | None:
    if pair.rule.get("mode") == "count_for_count":
        if line.count is None:
            return None
        amount = practical_count(line.count, have.count_rounding_step)
        if not _fits(amount, "count", have):
            return None
        return Substitute(
            have.ingredient_id,
            have.name,
            amount,
            "count",
            format_quantity(amount, "count"),
            "pair",
            pair.note,
        )
    grams = _grams_for(line, have, pair.rule)
    return _make(have, grams, via="pair", units=units, note=pair.note) if grams is not None else None


def _order(have: Have) -> tuple[bool, date, str, int]:
    return (not have.opened, have.expires_on or date.max, have.name, have.ingredient_id)


def find_substitute(
    line: MissingLine,
    haves: Sequence[Have],
    pairs: Sequence[AcceptedPair],
    *,
    unusable: frozenset[int] = frozenset(),  # excluded, held or disliked
    recipe_ingredient_ids: frozenset[int] = frozenset(),
    taken: frozenset[int] = frozenset(),  # already standing in for another line of this recipe
    units: str = "us",
) -> Substitute | None:
    by_id = {h.ingredient_id: h for h in haves if h.ingredient_id not in unusable | taken}
    for pair in sorted(pairs, key=lambda p: p.to_id):
        if pair.from_id != line.ingredient_id or pair.to_id not in by_id:
            continue
        if not same_form(line.cut, by_id[pair.to_id].cut):  # M6: never another bone or skin form
            continue
        if (found := _pair_substitute(line, pair, by_id[pair.to_id], units)) is not None:
            return found
    if not line.grouped and line.role not in PANTRY_ROLES:
        return None
    rule = ROLE_RULES.get(line.role, SAME_MASS)
    for have in sorted(by_id.values(), key=_order):
        if have.ingredient_id == line.ingredient_id or have.ingredient_id in recipe_ingredient_ids:
            continue
        if not same_form(line.cut, have.cut):  # M6: never another bone or skin form
            continue
        if line.grouped:
            if line.group is None or have.group != line.group:  # the group decides, whatever the role
                continue
        elif have.category != line.category or line.role not in have.roles:
            continue
        grams = _grams_for(line, have, rule)
        if (
            grams is not None
            and (found := _make(have, grams, via="pantry", units=units, note=None)) is not None
        ):
            return found
    return None
