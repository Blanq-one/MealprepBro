import pytest

from app.domain.frequency_caps import (
    CapIngredient,
    CapTarget,
    FrequencyCap,
    FrequencyCapError,
    Meal,
    cap_members,
    cap_violations,
    capped_meals,
    never_favored_ids,
    resolve_caps,
    zero_cap_exclusions,
)

INGREDIENTS = [
    CapIngredient(1, "bacon", frozenset({"pork"})),
    CapIngredient(2, "pork-sausage", frozenset({"pork"})),
    CapIngredient(3, "ham", frozenset({"pork"})),
    CapIngredient(4, "lard", frozenset({"pork_trace"})),
    CapIngredient(5, "flour-tortilla-small", frozenset()),
    CapIngredient(6, "chicken-thigh", frozenset({"poultry"})),
    CapIngredient(7, "salmon", frozenset({"fish"})),
    CapIngredient(8, "gelatin-pork", frozenset({"pork_trace"})),
]
PORK = FrequencyCap("Pork as a meal component", CapTarget.TAG, "pork", 1)


def resolved(*caps: FrequencyCap):
    return resolve_caps(list(caps), INGREDIENTS)


def test_membership_by_tag_and_by_ingredient():
    assert cap_members(PORK, INGREDIENTS) == frozenset({1, 2, 3})
    salmon = FrequencyCap("Salmon", CapTarget.INGREDIENT, "salmon", 2, never_favor=False)
    assert cap_members(salmon, INGREDIENTS) == frozenset({7})


def test_unknown_ingredient_target_is_an_error():
    with pytest.raises(FrequencyCapError, match="no ingredient"):
        cap_members(FrequencyCap("x", CapTarget.INGREDIENT, "nope", 1), INGREDIENTS)


def test_negative_cap_is_an_error():
    with pytest.raises(FrequencyCapError):
        FrequencyCap("x", CapTarget.TAG, "pork", -1)


def test_a_meal_counts_once_even_with_two_pork_lines():
    (cap,) = resolved(PORK)
    meals = [Meal("Mon dinner", frozenset({1, 2, 5}))]
    assert capped_meals(cap, meals) == ("Mon dinner",)


def test_trace_pork_never_counts():
    (cap,) = resolved(PORK)
    meals = [Meal("Mon lunch", frozenset({4, 5, 6})), Meal("Tue dessert", frozenset({8}))]
    assert capped_meals(cap, meals) == ()
    assert cap_violations([cap], meals) == ()


def test_one_pork_meal_under_cap_one_is_ok():
    meals = [Meal("Mon dinner", frozenset({1, 6})), Meal("Tue dinner", frozenset({6, 5}))]
    assert cap_violations(resolved(PORK), meals) == ()


def test_two_pork_meals_violate_cap_one():
    meals = [Meal("Mon dinner", frozenset({1})), Meal("Thu lunch", frozenset({3, 5}))]
    (violation,) = cap_violations(resolved(PORK), meals)
    assert violation.meals == ("Mon dinner", "Thu lunch")
    assert violation.message == (
        "Pork as a meal component: 2 meals this week, the limit is 1 (Mon dinner, Thu lunch)"
    )


def test_cap_zero_turns_into_exclusions():
    zero = FrequencyCap("Pork as a meal component", CapTarget.TAG, "pork", 0)
    exclusions = zero_cap_exclusions(resolved(zero))
    assert exclusions == {1: zero.label, 2: zero.label, 3: zero.label}
    assert zero_cap_exclusions(resolved(PORK)) == {}


def test_ingredient_target_cap_works_the_same_way():
    salmon = FrequencyCap("Salmon", CapTarget.INGREDIENT, "salmon", 2, never_favor=False)
    meals = [Meal(f"day {i}", frozenset({7})) for i in range(3)]
    (violation,) = cap_violations(resolved(salmon), meals)
    assert len(violation.meals) == 3


def test_never_favor_flag_is_carried_through():
    salmon = FrequencyCap("Salmon", CapTarget.INGREDIENT, "salmon", 2, never_favor=False)
    caps = resolved(PORK, salmon)
    assert caps[0].never_favor and not caps[1].never_favor
    assert never_favored_ids(caps) == frozenset({1, 2, 3})
