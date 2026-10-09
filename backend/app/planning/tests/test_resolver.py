"""Ingredient names from the LLM → canonical ingredients (deliverable 7) and accepted substitutions (8)."""

import pytest

from app.planning.resolver import IngredientResolver
from app.services.settings import current_user


@pytest.fixture
def resolver(seeded_db):
    return IngredientResolver(seeded_db, current_user(seeded_db).id)


@pytest.mark.parametrize(
    ("written", "canonical", "via"),
    [
        ("chicken thigh, boneless skinless", "chicken thigh, boneless skinless", "exact"),
        ("boneless thighs", "chicken thigh, boneless skinless", "exact"),
        ("Greek Yogurt", "Greek yogurt, plain nonfat", "exact"),
        ("garlic cloves (minced)", "garlic", "normalized"),
        ("bell peppers", "bell pepper", "exact"),
    ],
)
def test_canonical_matches(resolver, written, canonical, via):
    res = resolver.resolve(written)
    assert res.ok and res.canonical_name == canonical and res.via == via


def test_typo_resolves_by_trigram_with_a_margin(resolver):
    res = resolver.resolve("brocoli florets")
    assert res.ok and res.canonical_name == "broccoli florets" and res.via == "trigram"


def test_unknown_name_gets_suggestions_and_is_logged(resolver):
    res = resolver.resolve("saffron threads")
    assert not res.ok
    assert "'saffron threads' is not in the ingredient list" in (res.error or "")
    assert resolver.unresolved == {"saffron threads": 1}


def test_ambiguous_name_lists_suggestions(resolver):
    res = resolver.resolve("chicken")
    if not res.ok:  # several chicken cuts: the retry message names the closest ones
        assert res.suggestions and "Closest names" in (res.error or "")
        assert any("chicken" in s for s in res.suggestions)


def test_beef_broth_is_an_excluded_ingredient_error(resolver):
    res = resolver.resolve("beef broth")
    assert not res.ok and res.ingredient_id is not None
    assert "is excluded" in (res.error or "") and "beef" in (res.error or "")


def test_unspecified_gelatin_is_a_held_ingredient_error(resolver):
    res = resolver.resolve("gelatin")
    assert not res.ok
    assert "is held" in (res.error or "") and "allow" in (res.error or "")


def test_bacon_resolves_as_a_capped_pork_component(resolver):
    res = resolver.resolve("bacon")
    assert res.ok and res.canonical_name == "bacon"


def test_chapati_resolves_then_becomes_the_tortilla(resolver):
    res = resolver.resolve("chapati")
    assert res.ok
    assert res.substituted_from == "chapati (roti)"
    assert res.canonical_name == "flour tortilla (Price Rite, 37 g)"
    assert res.quantity_rule == {"mode": "count_for_count"}
