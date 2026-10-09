"""General per-ingredient / per-tag frequency caps (BUILD_PLAN §7.4, R2+).

The default cap is "pork as a meal component ≤ 1 meal per week", but nothing here is pork-specific:
a cap targets one ingredient (by slug) or one tag. A tag stands in for a "category" because the
culinary category column can't single out pork (sausage and chicken are both `protein`).

A meal counts once toward a cap if any ingredient of its batch is a member. A cap of 0 turns into an
exclusion of its members; ingredients outside the cap (e.g. `pork_trace`) are unaffected.
`never_favor` tells the Phase 1 solver to give members no nutrition, price or inventory-use bonus.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum


class CapTarget(StrEnum):
    INGREDIENT = "ingredient"
    TAG = "tag"


class FrequencyCapError(ValueError):
    pass


@dataclass(frozen=True)
class FrequencyCap:
    label: str
    target_type: CapTarget
    target: str  # ingredient slug or tag
    max_meals_per_week: int
    never_favor: bool = True

    def __post_init__(self) -> None:
        if self.max_meals_per_week < 0:
            raise FrequencyCapError(f"{self.label}: max meals per week must not be negative")


@dataclass(frozen=True)
class CapIngredient:
    id: int
    slug: str
    diet_tags: frozenset[str]


@dataclass(frozen=True)
class ResolvedCap:
    label: str
    member_ids: frozenset[int]
    max_meals_per_week: int
    never_favor: bool


@dataclass(frozen=True)
class Meal:
    """One eaten meal and the ingredient ids of the batch it comes from."""

    ref: str  # e.g. "2026-10-14 dinner"
    ingredient_ids: frozenset[int]


@dataclass(frozen=True)
class CapViolation:
    label: str
    max_meals_per_week: int
    meals: tuple[str, ...]

    @property
    def message(self) -> str:
        return (
            f"{self.label}: {len(self.meals)} meals this week, the limit is {self.max_meals_per_week} "
            f"({', '.join(self.meals)})"
        )


def cap_members(cap: FrequencyCap, ingredients: Iterable[CapIngredient]) -> frozenset[int]:
    ingredients = list(ingredients)
    if cap.target_type is CapTarget.INGREDIENT:
        members = frozenset(i.id for i in ingredients if i.slug == cap.target)
        if not members:
            raise FrequencyCapError(f"{cap.label}: no ingredient with slug '{cap.target}'")
        return members
    return frozenset(i.id for i in ingredients if cap.target in i.diet_tags)


def resolve_caps(
    caps: Sequence[FrequencyCap], ingredients: Iterable[CapIngredient]
) -> tuple[ResolvedCap, ...]:
    ingredients = list(ingredients)
    return tuple(
        ResolvedCap(
            label=cap.label,
            member_ids=cap_members(cap, ingredients),
            max_meals_per_week=cap.max_meals_per_week,
            never_favor=cap.never_favor,
        )
        for cap in caps
    )


def zero_cap_exclusions(resolved: Iterable[ResolvedCap]) -> dict[int, str]:
    """Members of any cap set to 0 → excluded, with the cap's label as the reason."""
    excluded: dict[int, str] = {}
    for cap in resolved:
        if cap.max_meals_per_week == 0:
            for ingredient_id in cap.member_ids:
                excluded.setdefault(ingredient_id, cap.label)
    return excluded


def never_favored_ids(resolved: Iterable[ResolvedCap]) -> frozenset[int]:
    return frozenset(i for cap in resolved if cap.never_favor for i in cap.member_ids)


def capped_meals(cap: ResolvedCap, meals: Iterable[Meal]) -> tuple[str, ...]:
    """Meals that count toward this cap: each meal at most once, however many member lines it has."""
    return tuple(meal.ref for meal in meals if meal.ingredient_ids & cap.member_ids)


def cap_violations(resolved: Iterable[ResolvedCap], meals: Sequence[Meal]) -> tuple[CapViolation, ...]:
    violations = []
    for cap in resolved:
        counted = capped_meals(cap, meals)
        if len(counted) > cap.max_meals_per_week:
            violations.append(CapViolation(cap.label, cap.max_meals_per_week, counted))
    return tuple(violations)
