"""The plan view's display lines (FLOW_SPEC C6; 2b.5 deliverables 8 and 12): fridge and freezer per portion,
the thaw note the night before, freezing after cooking, and the one Prep notes row."""

from datetime import date
from decimal import Decimal

from app.domain.enums import MealSlot
from app.services import plan_view as view

MON, WED, FRI, SAT = date(2026, 10, 12), date(2026, 10, 14), date(2026, 10, 16), date(2026, 10, 17)


def test_where_each_portion_comes_from():
    assert view.meal_source(MON, MON, False) == ("fresh", "Cooked today")
    assert view.meal_source(WED, MON, False) == ("fridge", "From the fridge, cooked Mon 12")
    assert view.meal_source(SAT, MON, True) == (
        "freezer",
        "From the freezer, cooked Mon 12 · thaw Fri 16 night",
    )


def test_a_batch_splits_into_fridge_and_freezer_portions():
    assert view.portion_split(5, freezer_meals=1, household=1, extras=0) == (4, 1)
    assert view.portion_split(10, freezer_meals=1, household=2, extras=2) == (6, 4)
    assert view.portions_display(5, 4, 1) == "5 portions (4 fridge, 1 freezer)"
    assert view.portions_display(3, 3, 0) == "3 portions"


def test_thaw_and_freeze_lines():
    assert view.thaw_note(MealSlot.LUNCH, "Chicken over rice") == (
        "Thaw tomorrow's lunch (Chicken over rice) in the fridge tonight."
    )
    assert (
        view.freeze_today("Dal tadka with rice", 2) == "Freeze 2 portions of Dal tadka with rice once cooled."
    )
    assert view.freeze_portions_note("Chicken over rice", 1, MON, "Freeze the chicken and rice.") == (
        "Freeze 1 portion of Chicken over rice after cooking on Mon 12. Freeze the chicken and rice."
    )


def test_the_prep_notes_row_counts_its_items_and_disappears_when_empty():
    assert view.prep_notes_display(3, 4) == "3 to freeze · 4 may spoil"
    assert view.prep_notes_display(2, 0) == "2 to freeze"
    assert view.prep_notes_display(0, 1) == "1 may spoil"
    assert view.prep_notes_display(0, 0) is None
    # the plan's own notes (recipes left out, not proven best) sit behind the same row (2b.7, F23)
    assert view.prep_notes_display(3, 0, 2) == "3 to freeze · About this plan"
    assert view.prep_notes_display(0, 0, 1) == "About this plan"


def test_where_each_batchs_portions_go():
    """F23: 'Cook Air-fryer chicken over rice ×4 → Mon lunch, Tue dinner, Wed lunch, Sat dinner (1 to the
    freezer)'."""
    labels = [view.meal_label(MON, MealSlot.LUNCH), view.meal_label(SAT, MealSlot.DINNER)]
    assert labels == ["Mon lunch", "Sat dinner"]
    assert view.meal_label(SAT, MealSlot.PROTEIN_DESSERT, with_date=True) == "Sat 17 dessert"
    assert view.uses_display(labels, Decimal(1)) == "Mon lunch, Sat dinner (1 to the freezer)"
    assert view.uses_display(labels, Decimal(0)) == "Mon lunch, Sat dinner"
    assert view.uses_display([], Decimal(2)) == "2 to the freezer"
    assert view.uses_display(["Mon lunch"], Decimal("1.5")) == "Mon lunch (1½ to the freezer)"


def test_a_prep_batch_its_stop_and_finish_lines():
    assert view.stop_display("marinated") == "marinate only"
    assert view.stop_display("cooked") == "cooked"
    assert view.stop_display(None) is None
    assert view.finish_time_display(5, 25) == "30 min, 5 hands-on"
    assert view.finish_time_display(5, 0) == "5 min hands-on"
    assert view.in_plan_line("marinated", MON, [(WED, "oven"), (FRI, "oven")]) == (
        "In this plan: marinate on Mon 12, roast on Wed 14 and Fri 16."
    )
    assert view.in_plan_line("cooked", MON, []) == "In this plan: cook on Mon 12."


def test_an_assembled_meals_source_line():
    same = [("chicken curry", WED, MON, False), ("rice", WED, MON, False)]
    assert view.assembly_source(same) == ("fridge", "From the fridge, cooked Mon 12")
    mixed = [("chicken curry", SAT, MON, True), ("rice", SAT, WED, False)]
    assert view.assembly_source(mixed) == (
        "freezer",
        "From the fridge: rice cooked Wed 14; "
        "from the freezer: chicken curry cooked Mon 12 · thaw Fri 16 night",
    )
