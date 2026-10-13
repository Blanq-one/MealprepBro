"""Step text after an ingredient edit (step 2b.6, AA8): names swapped by code, left-out lines marked, and a
note where the new food cooks differently."""

from app.domain.step_text import FoodFacts, cooking_note, flagged, names_in, replace_names, skipped

THIGH = ["chicken thigh, boneless skinless", "chicken thigh", "boneless chicken thighs"]


def facts(name: str, slug: str, **kw: bool) -> FoodFacts:
    base = {"meat": False, "ground": False, "frozen": False, "canned": False, "dried": False}
    return FoodFacts(name=name, slug=slug, **{**base, **kw})


def test_a_swap_puts_the_new_name_in_singular_or_plural_keeping_a_capital() -> None:
    text = "Cut the chicken thighs into strips. Chicken thigh browns in 6 minutes."
    assert replace_names(text, THIGH, "chicken breast") == (
        "Cut the chicken breasts into strips. Chicken breast browns in 6 minutes."
    )
    # the longest name wins, once: no "chicken breast, boneless skinless" left half-replaced
    assert replace_names("Add the chicken thigh, boneless skinless.", THIGH, "chicken breast") == (
        "Add the chicken breast."
    )
    assert (
        replace_names("Stir in the chicken broth.", THIGH, "chicken breast") == "Stir in the chicken broth."
    )


def test_a_left_out_ingredient_is_marked_where_a_step_names_it() -> None:
    step = "Top with the cilantro and serve."
    assert names_in(step, ["cilantro"]) and not names_in("Serve warm.", ["cilantro"])
    assert skipped(step, "cilantro") == "Top with the cilantro and serve. (skipped: cilantro)"


def test_a_note_only_when_the_food_cooks_differently() -> None:
    thigh = facts("chicken thigh", "chicken-thigh-boneless-skinless", meat=True)
    breast = facts("chicken breast", "chicken-breast-boneless-skinless", meat=True)
    assert cooking_note(thigh, breast) is not None and "cooks differently" in cooking_note(thigh, breast)  # type: ignore[operator]
    turkey = facts("ground turkey", "ground-turkey-93", meat=True, ground=True)
    chicken = facts("ground chicken", "ground-chicken", meat=True, ground=True)
    assert cooking_note(turkey, chicken) is None  # ground for ground cooks the same
    spinach = facts("spinach", "spinach")
    frozen = facts("frozen spinach", "spinach-frozen", frozen=True)
    assert "straight from the freezer" in (cooking_note(spinach, frozen) or "")
    assert "less time" in (cooking_note(frozen, spinach) or "")
    assert cooking_note(facts("kale", "kale"), spinach) is None
    steps = [("Chop the onion.", None), ("Sear the chicken breast.", None), ("Simmer until done.", 7)]
    assert flagged(steps, ["chicken breast"], 7) == [1, 2]
