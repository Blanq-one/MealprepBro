from datetime import date
from decimal import Decimal

from app.domain.food_state import FoodState
from app.seed.mapping_review import (
    REVIEW_MARK,
    REVIEW_TOP_N,
    build_rows,
    flag_summary,
    keyword_flags,
    render_markdown,
    state_flags,
)


def test_canned_is_flagged_unless_the_ingredient_says_canned():
    desc = "Soup, chicken broth, low sodium, canned"
    assert keyword_flags(desc, "condiment", "low-sodium chicken broth | 32 fl oz carton") == [
        "description says 'canned'"
    ]
    assert (
        keyword_flags("Fish, tuna, light, canned in water", "protein", "tuna, light, canned in water") == []
    )
    assert keyword_flags("Tomato products, canned, paste", "vegetable", "tomato paste | 6 oz can") == []


def test_cooked_fried_breaded_sweetened_keywords():
    assert keyword_flags("Chicken, breast, meat only, cooked, fried", "protein", "chicken breast") == [
        "description says 'fried'",
        "description says 'cooked'",
    ]
    assert keyword_flags("Fish, cod, breaded", "protein", "cod fillet") == ["description says 'breaded'"]
    assert keyword_flags("Yogurt, vanilla, sweetened", "dairy", "yogurt") == ["description says 'sweetened'"]
    assert keyword_flags("Cocoa, dry powder, unsweetened", "condiment", "cocoa powder") == []
    assert keyword_flags("Onions, fried", "vegetable", "fried onions") == []


def test_with_skin_is_flagged_for_skinless_meat_not_for_apples():
    assert keyword_flags(
        "Chicken, thigh, meat and skin, raw", "protein", "chicken thigh, boneless skinless"
    ) == ["description says 'with skin'"]
    assert keyword_flags("Apples, raw, with skin", "fruit", "apple | apples") == []
    assert keyword_flags("Chicken, thigh, meat and skin, raw", "protein", "skin-on chicken thighs") == []


def test_state_flags():
    assert state_flags("rice", [None], FoodState.DRY) == []
    assert state_flags("rice", [None], FoodState.COOKED) == [
        "state: mapping is cooked, recipes use raw / dry / as-sold weights"
    ]
    assert state_flags("rice", [FoodState.COOKED], FoodState.DRY) == [
        "state: mapping is dry, recipes use cooked weights"
    ]


def test_review_sheet_rows(seeded_db):
    rows = build_rows(seeded_db)
    assert len(rows) == 185
    kcal = [r.seed_kcal for r in rows]
    assert kcal == sorted(kcal, reverse=True)
    assert sum(r.share_pct for r in rows) == Decimal("100.0")
    # you approved the whole top 25 on 2026-10-08, so nothing is left marked for review
    assert all(r.approved_on == date(2026, 10, 8) for r in rows[:REVIEW_TOP_N])
    assert not any(r.review for r in rows)
    assert not any(r.approved_on for r in rows[REVIEW_TOP_N:])
    assert rows[0].ingredient.slug == "chicken-thigh-boneless-skinless"
    by_slug = {r.ingredient.slug: r for r in rows}
    tortilla = by_slug["flour-tortilla-small"]
    assert tortilla.source.startswith("package label")
    assert tortilla.flags == []  # package labels aren't checked for USDA description issues
    powder = by_slug["protein-powder-double-chocolate"]
    assert (powder.source, powder.fdc_id, powder.state) == ("package label", None, FoodState.AS_SOLD)
    assert by_slug["rice-long-grain-white"].state is FoodState.DRY
    assert by_slug["chicken-broth-low-sodium"].flags == ["description says 'canned'"]
    assert not any(f.startswith("state:") for r in rows for f in r.flags)  # every mapping is uncooked
    assert any("approximate" in f for f in by_slug["garam-masala"].flags)


def test_review_sheet_markdown(seeded_db):
    rows = build_rows(seeded_db)
    text = render_markdown(rows, date(2026, 10, 8))
    assert "| # | Ingredient | Nutrition source | USDA description | FDC id | State | kcal per 100 g " in text
    assert text.count(f"**{REVIEW_MARK}**") == 1  # only the legend: the top 25 are approved
    assert text.count("approved 2026-10-08") == REVIEW_TOP_N
    assert "| 1 | chicken thigh, boneless skinless | USDA |" in text
    assert "| 2 | flour tortilla (Price Rite, 37 g) | package label" in text
    summary = flag_summary(rows)
    assert any(line.startswith("description says 'canned': 3") for line in summary)
