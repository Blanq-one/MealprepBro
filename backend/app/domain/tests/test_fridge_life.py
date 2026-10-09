"""Raw fridge life comes from the FoodSafety.gov chart, short end of its range (item 3 of the fix-up)."""

import pytest

from app.domain import storage_chart
from app.domain.fridge_life import CATEGORY_USE, SLUG_USE, fridge_life


@pytest.mark.parametrize(
    ("slug", "category", "days", "freeze"),
    [
        ("chicken-thigh-boneless-skinless", "poultry", 1, True),  # "1 to 2 days"
        ("turkey-breast", "poultry", 1, True),
        ("ground-turkey-93", "poultry", 1, True),  # ground meats: "1 to 2 days"
        ("salmon", "fish_shellfish", 1, True),  # fin fish: "1 - 3 days"
        ("shrimp", "fish_shellfish", 3, True),  # "3 - 5 days"
        ("pork-chop-boneless", "whole_cut_meat", 3, True),  # chops: "3 to 5 days"
        ("bacon", None, 7, True),  # "1 week"
        ("egg-large", "egg", 21, False),  # "3 to 5 weeks"; eggs aren't frozen in the shell
    ],
)
def test_chart_rows_by_slug_or_category(slug, category, days, freeze):
    life = fridge_life(slug, category)
    assert life is not None and (life.days, life.freeze_raw) == (days, freeze)
    assert life.chart.refrigerator in life.label


def test_an_unknown_raw_protein_falls_back_on_its_safety_category():
    life = fridge_life("rabbit-legs", "poultry")
    assert life is not None and life.chart.key == "poultry_pieces"


@pytest.mark.parametrize(("slug", "category"), [("ham-deli", None), ("tofu-firm", None), ("milk-2", None)])
def test_cured_ready_to_eat_and_non_meat_items_have_no_raw_fridge_life(slug, category):
    assert fridge_life(slug, category) is None


def test_every_mapping_points_at_a_chart_row():
    for use in {*SLUG_USE.values(), *CATEGORY_USE.values()}:
        assert storage_chart.chart_row(storage_chart.APP_STORAGE[use]).fridge_days is not None
