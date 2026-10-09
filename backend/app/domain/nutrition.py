"""Nutrition math from per-100 g values (CLAUDE.md rule 3: never from the LLM).

A missing value is unknown, never zero: totals list which ingredients lack each nutrient.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

CORE_CODES: tuple[str, ...] = ("energy_kcal", "protein_g", "carbohydrate_g", "fat_g")
ATWATER = {"protein_g": Decimal(4), "carbohydrate_g": Decimal(4), "fat_g": Decimal(9)}
ATWATER_MISMATCH_TOLERANCE = Decimal("0.20")
ATWATER_MIN_KCAL = Decimal(20)  # below this, rounding noise makes the comparison meaningless
GOOD_SOURCE_PCT = Decimal(10)
HIGH_IN_PCT = Decimal(20)

# USDA nutrient numbers for energy, in order of preference (BUILD_PLAN §2 / §9 Phase 0).
ENERGY_NBR_PREFERENCE: tuple[str, ...] = ("208", "958", "957")


@dataclass(frozen=True)
class NutritionProfile:
    """Per-100 g edible-portion values for one ingredient (known values only)."""

    ingredient_id: int
    name: str
    per_100g: Mapping[str, Decimal]
    heme_iron_fraction: Decimal = Decimal(0)
    edible_fraction: Decimal = Decimal(1)


@dataclass(frozen=True)
class NutritionLine:
    profile: NutritionProfile
    grams_as_purchased: Decimal


@dataclass(frozen=True)
class HemeEstimate:
    heme_mg: Decimal
    non_heme_mg: Decimal
    is_estimate: bool = True  # always shown as "estimated" (Q3 + R1)


@dataclass(frozen=True)
class NutritionTotals:
    amounts: dict[str, Decimal]
    missing: dict[str, tuple[str, ...]] = field(default_factory=dict)  # nutrient code -> ingredient names
    heme: HemeEstimate | None = None

    def is_complete(self, code: str) -> bool:
        return code not in self.missing

    @property
    def core_complete(self) -> bool:
        return all(self.is_complete(code) for code in CORE_CODES)

    @property
    def missing_core(self) -> dict[str, tuple[str, ...]]:
        return {code: names for code, names in self.missing.items() if code in CORE_CODES}


@dataclass(frozen=True)
class EnergyValue:
    kcal: Decimal
    source: str  # '208' | '958' | '957' | 'atwater'

    @property
    def is_derived(self) -> bool:
        return self.source == "atwater"


def edible_grams(grams_as_purchased: Decimal, edible_fraction: Decimal) -> Decimal:
    return grams_as_purchased * edible_fraction


def line_amounts(line: NutritionLine) -> dict[str, Decimal]:
    grams = edible_grams(line.grams_as_purchased, line.profile.edible_fraction)
    return {code: value * grams / 100 for code, value in line.profile.per_100g.items()}


def heme_estimate(lines: Iterable[NutritionLine]) -> HemeEstimate | None:
    heme = Decimal(0)
    total = Decimal(0)
    for line in lines:
        iron = line_amounts(line).get("iron_mg")
        if iron is None:
            return None
        heme += iron * line.profile.heme_iron_fraction
        total += iron
    return HemeEstimate(heme_mg=heme, non_heme_mg=total - heme)


def total(lines: Sequence[NutritionLine], codes: Iterable[str]) -> NutritionTotals:
    codes = tuple(codes)
    amounts = dict.fromkeys(codes, Decimal(0))
    missing: dict[str, list[str]] = {}
    for line in lines:
        values = line_amounts(line)
        for code in codes:
            if code in values:
                amounts[code] += values[code]
            else:
                missing.setdefault(code, []).append(line.profile.name)
    heme = heme_estimate(lines) if "iron_mg" in codes else None
    return NutritionTotals(
        amounts=amounts, missing={code: tuple(names) for code, names in missing.items()}, heme=heme
    )


def divide(totals: NutritionTotals, portions: int) -> NutritionTotals:
    if portions < 1:
        raise ValueError("portions must be at least 1")
    n = Decimal(portions)
    heme = (
        HemeEstimate(heme_mg=totals.heme.heme_mg / n, non_heme_mg=totals.heme.non_heme_mg / n)
        if totals.heme
        else None
    )
    return NutritionTotals(
        amounts={code: value / n for code, value in totals.amounts.items()}, missing=totals.missing, heme=heme
    )


FIBER_KCAL_PER_G = Decimal(2)


def atwater_kcal(
    protein_g: Decimal, carbohydrate_g: Decimal, fat_g: Decimal, fiber_g: Decimal | None = None
) -> Decimal:
    """4/4/9 kcal per g. With fiber known, the fiber part of (by-difference) carbohydrate counts 2 kcal/g."""
    carbs = carbohydrate_g * ATWATER["carbohydrate_g"]
    if fiber_g is not None:
        fiber = min(fiber_g, carbohydrate_g)
        carbs = (carbohydrate_g - fiber) * ATWATER["carbohydrate_g"] + fiber * FIBER_KCAL_PER_G
    return protein_g * ATWATER["protein_g"] + carbs + fat_g * ATWATER["fat_g"]


def energy_from_usda(by_nutrient_nbr: Mapping[str, Decimal]) -> EnergyValue | None:
    """Energy fallback chain: 208 → 958 (Atwater specific) → 957 (Atwater general) → 4/4/9 (derived)."""
    for nbr in ENERGY_NBR_PREFERENCE:
        if nbr in by_nutrient_nbr:
            return EnergyValue(kcal=by_nutrient_nbr[nbr], source=nbr)
    try:
        protein, carbs, fat = by_nutrient_nbr["203"], by_nutrient_nbr["205"], by_nutrient_nbr["204"]
    except KeyError:
        return None
    return EnergyValue(kcal=atwater_kcal(protein, carbs, fat), source="atwater")


def atwater_mismatch(
    kcal: Decimal, protein_g: Decimal, carbohydrate_g: Decimal, fat_g: Decimal, fiber_g: Decimal | None = None
) -> bool:
    """True when stated energy and 4/4/9 (fiber at 2) differ by more than 20%: a sign of a bad mapping,
    or of energy from something else (alcohol in extracts, acetic acid in vinegar)."""
    computed = atwater_kcal(protein_g, carbohydrate_g, fat_g, fiber_g)
    if max(kcal, computed) < ATWATER_MIN_KCAL:
        return False
    return abs(kcal - computed) / max(kcal, computed) > ATWATER_MISMATCH_TOLERANCE


def dv_label(amount: Decimal, daily_value: Decimal | None) -> str | None:
    """FDA nutrient-content wording per serving: ≥ 20% DV 'high_in', ≥ 10% 'good_source'."""
    if daily_value is None or daily_value <= 0:
        return None
    pct = amount / daily_value * 100
    if pct >= HIGH_IN_PCT:
        return "high_in"
    if pct >= GOOD_SOURCE_PCT:
        return "good_source"
    return None


@dataclass(frozen=True)
class LabelConversion:
    per_100g: dict[str, Decimal]
    missing: tuple[str, ...]


def label_per_100g(per_serving: Mapping[str, Decimal | None], serving_grams: Decimal) -> LabelConversion:
    """Nutrition-facts label (per serving + serving grams) → per 100 g. None values stay missing."""
    if serving_grams <= 0:
        raise ValueError("serving grams must be positive")
    known = {
        code: (value * 100 / serving_grams).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        for code, value in per_serving.items()
        if value is not None
    }
    missing = tuple(sorted(code for code, value in per_serving.items() if value is None))
    return LabelConversion(per_100g=known, missing=missing)


def kcal_display(kcal: Decimal) -> int:
    """Shown kcal: half-up per meal. Day and week totals are sums of the displayed meal values."""
    return int(kcal.quantize(Decimal(1), rounding=ROUND_HALF_UP))
