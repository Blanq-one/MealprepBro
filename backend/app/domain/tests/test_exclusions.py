import pytest

from app.domain.exclusions import (
    ExclusionStatus,
    Preference,
    TaggedIngredient,
    resolve,
    resolve_one,
    unusable_ids,
)
from app.domain.frequency_caps import (
    CapIngredient,
    CapTarget,
    FrequencyCap,
    resolve_caps,
    zero_cap_exclusions,
)

BEEF = frozenset({"beef"})


def ing(i: int, name: str, *tags: str) -> TaggedIngredient:
    return TaggedIngredient(i, name, frozenset(tags))


GROUND_BEEF = ing(1, "ground beef", "beef")
BEEF_BROTH = ing(2, "beef broth", "beef")
BEEF_TALLOW = ing(3, "beef tallow", "beef")
BOVINE_GELATIN = ing(4, "gelatin, bovine", "beef")
BEEF_BOUILLON = ing(5, "beef bouillon cube", "beef")
GELATIN = ing(6, "gelatin, unflavored", "possible_beef")
MARSHMALLOW = ing(7, "marshmallows", "possible_beef")
COLLAGEN = ing(8, "collagen peptides", "possible_beef")
BACON = ing(9, "bacon", "pork")
HAM = ing(10, "ham", "pork")
PORK_SAUSAGE = ing(11, "pork sausage", "pork")
PORK_CHOP = ing(12, "pork chop", "pork")
LARD = ing(13, "lard", "pork_trace")
PORK_GELATIN = ing(14, "gelatin, pork-derived", "pork_trace")
TORTILLA = ing(15, "flour tortilla, small")
GREEK_YOGURT = ing(16, "Greek yogurt, plain nonfat", "dairy")
CHICKEN = ing(17, "chicken thigh", "poultry")
PEPPERONI = ing(18, "pepperoni", "pork", "possible_beef")


@pytest.mark.parametrize("item", [GROUND_BEEF, BEEF_BROTH, BEEF_TALLOW, BOVINE_GELATIN, BEEF_BOUILLON])
def test_beef_and_beef_derived_are_excluded(item):
    result = resolve_one(item, BEEF)
    assert result.status is ExclusionStatus.EXCLUDED
    assert "tagged beef" in result.reasons[0]


def test_allow_never_releases_beef():
    assert resolve_one(GROUND_BEEF, BEEF, Preference.ALLOW).status is ExclusionStatus.EXCLUDED


@pytest.mark.parametrize("item", [GELATIN, MARSHMALLOW, COLLAGEN])
def test_possible_beef_items_are_held(item):
    result = resolve_one(item, BEEF)
    assert result.status is ExclusionStatus.HELD
    assert not result.usable


def test_allow_releases_a_held_item_and_exclude_excludes_any_item():
    assert resolve_one(GELATIN, BEEF, Preference.ALLOW).status is ExclusionStatus.ALLOWED
    assert resolve_one(GELATIN, BEEF, Preference.EXCLUDE).status is ExclusionStatus.EXCLUDED
    assert resolve_one(CHICKEN, BEEF, Preference.EXCLUDE).reasons == ("you excluded it",)
    assert resolve_one(CHICKEN, BEEF, Preference.DISLIKE).status is ExclusionStatus.ALLOWED


def test_held_reason_uses_the_review_note():
    noted = TaggedIngredient(6, "gelatin", frozenset({"possible_beef"}), "gelatin source not stated")
    assert resolve_one(noted, BEEF).reasons == ("held for review: gelatin source not stated",)


@pytest.mark.parametrize("item", [BACON, HAM, PORK_SAUSAGE, PORK_CHOP, LARD, PORK_GELATIN])
def test_pork_components_and_trace_pork_are_allowed(item):
    assert resolve_one(item, BEEF).status is ExclusionStatus.ALLOWED


@pytest.mark.parametrize("item", [TORTILLA, GREEK_YOGURT, CHICKEN])
def test_everyday_items_are_allowed(item):
    assert resolve_one(item, BEEF).usable


def test_pepperoni_is_held_until_allowed_then_allowed():
    assert resolve_one(PEPPERONI, BEEF).status is ExclusionStatus.HELD
    assert resolve_one(PEPPERONI, BEEF, Preference.ALLOW).status is ExclusionStatus.ALLOWED


def test_empty_excluded_tags_leave_only_held_and_explicit_exclusions():
    results = resolve([GROUND_BEEF, GELATIN, CHICKEN], frozenset(), {17: Preference.EXCLUDE})
    assert results[1].status is ExclusionStatus.ALLOWED
    assert results[6].status is ExclusionStatus.HELD
    assert results[17].status is ExclusionStatus.EXCLUDED


def test_pork_cap_zero_excludes_components_but_not_trace_pork():
    everything = [BACON, HAM, PORK_SAUSAGE, PORK_CHOP, LARD, PORK_GELATIN, TORTILLA, CHICKEN]
    caps = resolve_caps(
        [FrequencyCap("Pork as a meal component", CapTarget.TAG, "pork", 0)],
        [CapIngredient(i.id, i.name, i.diet_tags) for i in everything],
    )
    results = resolve(everything, BEEF, zero_cap_exclusions=zero_cap_exclusions(caps))
    for item in (BACON, HAM, PORK_SAUSAGE, PORK_CHOP):
        assert results[item.id].status is ExclusionStatus.EXCLUDED
        assert results[item.id].reasons == ("frequency cap 'Pork as a meal component' is 0",)
    for item in (LARD, PORK_GELATIN, TORTILLA, CHICKEN):
        assert results[item.id].usable
    assert unusable_ids(results) == frozenset({9, 10, 11, 12})


def test_default_resolve_uses_beef_exclusion():
    results = resolve([GROUND_BEEF, BACON])
    assert results[1].status is ExclusionStatus.EXCLUDED
    assert results[9].status is ExclusionStatus.ALLOWED
