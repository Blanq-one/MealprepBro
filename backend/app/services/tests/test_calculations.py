from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db.models import AppUser
from app.services.calculations import CalculationError, LineInput, calculate, calculate_scaled
from app.services.ingredient_data import load_by_slug
from app.services.recipes import seed_recipes, version_lines


def _ids(session):
    return {slug: d.id for slug, d in load_by_slug(session).items()}


def test_chicken_and_rice_numbers(seeded_db):
    ids = _ids(seeded_db)
    calc = calculate(
        seeded_db,
        [
            LineInput(ids["chicken-thigh-boneless-skinless"], Decimal(680), "g"),
            LineInput(ids["rice-long-grain-white"], Decimal(300), "g"),
        ],
        4,
    )
    # SR Legacy: thigh 121 kcal / 19.66 g protein per 100 g; rice 365 kcal / 7.13 g protein
    assert calc.totals.amounts["energy_kcal"] == Decimal("121") * Decimal("6.8") + Decimal("365") * 3
    assert (
        calc.per_portion.amounts["protein_g"] == (Decimal("19.66") * Decimal("6.8") + Decimal("7.13") * 3) / 4
    )
    assert calc.nutrition_complete
    by_store = {c.store_name: c for c in calc.costs}
    lb = Decimal("453.592")
    assert by_store["Stop & Shop"].total.cents == round(680 * 449 / lb + 300 * 499 / (5 * lb))
    assert by_store["Price Rite"].total.cents < by_store["Stop & Shop"].total.cents
    assert by_store["Stop & Shop"].uses_estimates


def test_heme_estimate_on_a_seed_recipe(seeded_db):
    user = seeded_db.scalars(select(AppUser)).one()
    views = {v.version.title: v.calculation for v in seed_recipes(seeded_db, user.id)}
    gravy = views["Everyday chicken curry gravy"].per_portion
    assert gravy.heme is not None and gravy.heme.is_estimate
    assert gravy.heme.heme_mg == Decimal("0.81") * Decimal("6.8") * Decimal("0.40") / 4  # thigh iron × 40%
    wraps = views["Egg, spinach and pepper breakfast wraps"].per_portion
    assert wraps.heme.heme_mg == 0  # eggs and plants: 0% heme


def test_optional_lines_are_listed_not_counted(seeded_db):
    ids = _ids(seeded_db)
    calc = calculate(
        seeded_db,
        [
            LineInput(ids["greek-yogurt-nonfat"], Decimal(340), "g"),
            LineInput(ids["vanilla-extract"], Decimal("0.5"), "tsp", optional=True),
        ],
        2,
    )
    assert calc.optional_not_counted == ("vanilla extract",)
    assert all(c.total.complete for c in calc.costs)


def test_scaled_calculation_uses_practical_quantities(seeded_db):
    user = seeded_db.scalars(select(AppUser)).one()
    view = next(v for v in seed_recipes(seeded_db, user.id) if v.version.title.startswith("Egg, spinach"))
    scaled = calculate_scaled(seeded_db, version_lines(seeded_db, view.version.id), 4, 5)
    eggs = next(
        s
        for s, r in zip(scaled.scaled, scaled.calculation.lines, strict=True)
        if r.ingredient.slug == "egg-large"
    )
    assert scaled.factor == Decimal("1.25")
    assert (eggs.exact_amount, eggs.amount) == (Decimal("10.000"), Decimal(10))
    onion = next(
        s
        for s, r in zip(scaled.scaled, scaled.calculation.lines, strict=True)
        if r.ingredient.slug == "onion-yellow"
    )
    assert onion.amount == Decimal("0.5")  # 0.625 → ½ (count step ½)
    egg_line = next(r for r in scaled.calculation.lines if r.ingredient.slug == "egg-large")
    assert egg_line.grams == Decimal(500)


def test_errors(seeded_db):
    ids = _ids(seeded_db)
    with pytest.raises(CalculationError):
        calculate(seeded_db, [], 1)
    with pytest.raises(CalculationError):
        calculate(seeded_db, [LineInput(ids["salt"], Decimal(1), "tsp")], 0)
    with pytest.raises(CalculationError):
        calculate(seeded_db, [LineInput(10**9, Decimal(1), "g")], 1)
    with pytest.raises(CalculationError):
        calculate_scaled(seeded_db, [LineInput(10**9, Decimal(1), "g")], 1, 2)
