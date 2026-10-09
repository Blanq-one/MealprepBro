"""Diet-rule resolution (BUILD_PLAN §7.4, R2). Pure: callers pass tags, decisions and caps.

Order:
  1. EXCLUDED: a diet tag in `excluded_tags` (default {"beef"}), an explicit `exclude` decision, or
     membership in a frequency cap set to 0. An `allow` decision never overrides a hard tag exclusion.
  2. HELD: tagged `possible_beef` with no `allow` decision. Held = excluded by default, listed for review.
  3. ALLOWED otherwise. Pork components (`pork`) are allowed and carry their frequency cap;
     trace pork (`pork_trace`) is allowed with no limit.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

DEFAULT_EXCLUDED_TAGS = frozenset({"beef"})
HELD_TAG = "possible_beef"
PORK_COMPONENT_TAG = "pork"
PORK_TRACE_TAG = "pork_trace"
KNOWN_DIET_TAGS = frozenset(
    {
        "poultry",
        "fish",
        "shellfish",
        "egg",
        "dairy",
        "lamb",
        "beef",
        HELD_TAG,
        PORK_COMPONENT_TAG,
        PORK_TRACE_TAG,
    }
)


class ExclusionStatus(StrEnum):
    ALLOWED = "allowed"
    EXCLUDED = "excluded"
    HELD = "held"


class Preference(StrEnum):
    EXCLUDE = "exclude"
    DISLIKE = "dislike"
    LIKE = "like"
    ALLOW = "allow"


@dataclass(frozen=True)
class TaggedIngredient:
    id: int
    name: str
    diet_tags: frozenset[str]
    review_note: str | None = None


@dataclass(frozen=True)
class ExclusionResult:
    status: ExclusionStatus
    reasons: tuple[str, ...] = ()

    @property
    def usable(self) -> bool:
        return self.status is ExclusionStatus.ALLOWED


def resolve_one(
    ingredient: TaggedIngredient,
    excluded_tags: frozenset[str],
    preference: Preference | None = None,
    zero_cap_label: str | None = None,
) -> ExclusionResult:
    reasons: list[str] = []
    hard_tags = sorted(ingredient.diet_tags & excluded_tags)
    if hard_tags:
        reasons.append(f"tagged {', '.join(hard_tags)} (always excluded)")
    if preference is Preference.EXCLUDE:
        reasons.append("you excluded it")
    if zero_cap_label is not None:
        reasons.append(f"frequency cap '{zero_cap_label}' is 0")
    if reasons:
        return ExclusionResult(ExclusionStatus.EXCLUDED, tuple(reasons))
    if HELD_TAG in ingredient.diet_tags and preference is not Preference.ALLOW:
        note = ingredient.review_note or "may be beef-derived; source not stated"
        return ExclusionResult(ExclusionStatus.HELD, (f"held for review: {note}",))
    return ExclusionResult(ExclusionStatus.ALLOWED)


def resolve(
    ingredients: Iterable[TaggedIngredient],
    excluded_tags: frozenset[str] = DEFAULT_EXCLUDED_TAGS,
    preferences: Mapping[int, Preference] | None = None,
    zero_cap_exclusions: Mapping[int, str] | None = None,
) -> dict[int, ExclusionResult]:
    preferences = preferences or {}
    zero_cap_exclusions = zero_cap_exclusions or {}
    return {
        i.id: resolve_one(i, excluded_tags, preferences.get(i.id), zero_cap_exclusions.get(i.id))
        for i in ingredients
    }


def unusable_ids(results: Mapping[int, ExclusionResult]) -> frozenset[int]:
    return frozenset(i for i, result in results.items() if not result.usable)
