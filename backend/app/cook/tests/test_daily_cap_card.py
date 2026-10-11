"""A meal-now card is never above a daily amount cap's maximum (M16, 2b.5 deliverable 13): a recipe whose
single portion has more protein powder than 2 scoops is filtered, whatever else it does well."""

from typing import Any

from sqlalchemy.orm import Session

from app.cook.tests.conftest import add_recipe, meal_now, results


def test_a_meal_now_card_is_never_above_the_daily_maximum(api: Any, seeded_db: Session) -> None:
    for title, grams in (("Triple scoop shake", "93"), ("One scoop shake", "31")):
        add_recipe(
            seeded_db,
            title,
            [("protein-powder-double-chocolate", grams, "g", "protein"), ("milk-2", "240", "ml", "dairy")],
            slots=("protein_dessert",),
            equipment=(),
            servings=1,
        )
    events = meal_now(api, slot="protein_dessert", allow_llm=False)
    shown = {c["title"] for c in results(events)}
    assert "One scoop shake" in shown
    assert "Triple scoop shake" not in shown
