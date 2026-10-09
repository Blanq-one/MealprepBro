from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.models import (
    AppUser,
    Ingredient,
    IngredientSubstitution,
    MealPlan,
    PriceObservation,
    Product,
    Recipe,
    RecipeIngredient,
    RecipeVersion,
    Store,
)


def _first(session, model):
    return session.scalars(select(model).order_by(model.id)).first()


def _expect_violation(session, obj):
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(obj)
        session.flush()


def _observation(session, **overrides):
    product, store = _first(session, Product), _first(session, Store)
    values = dict(
        product_id=product.id,
        store_id=store.id,
        observed_on=date(2026, 10, 9),
        price_cents=199,
        priced_quantity=Decimal(1),
        priced_unit="count",
        source="manual",
    )
    values.update(overrides)
    return PriceObservation(**values)


def test_negative_cents_rejected(seeded_db):
    _expect_violation(seeded_db, _observation(seeded_db, price_cents=-1))


def test_invalid_unit_rejected(seeded_db):
    _expect_violation(seeded_db, _observation(seeded_db, priced_unit="lb"))


def test_price_observation_requires_a_store(seeded_db):
    _expect_violation(seeded_db, _observation(seeded_db, store_id=None))


def test_valid_observation_is_accepted(seeded_db):
    seeded_db.add(_observation(seeded_db))
    seeded_db.flush()


def test_recipe_version_number_unique_per_recipe(seeded_db):
    version = _first(seeded_db, RecipeVersion)
    clone = RecipeVersion(
        recipe_id=version.recipe_id,
        version_number=1,
        created_by="user",
        title="x",
        description="x",
        meal_slots=["lunch"],
        mood="simple",
        base_servings=1,
        active_minutes=1,
        total_minutes=1,
        equipment=[],
        freezer_friendly=False,
        content_hash="x",
    )
    _expect_violation(seeded_db, clone)


def test_recipe_ingredient_quantity_must_be_positive(seeded_db):
    version, ingredient = _first(seeded_db, RecipeVersion), _first(seeded_db, Ingredient)
    _expect_violation(
        seeded_db,
        RecipeIngredient(
            recipe_version_id=version.id,
            position=99,
            ingredient_id=ingredient.id,
            quantity=Decimal(0),
            unit="g",
            authored_quantity=Decimal(0),
            authored_unit="g",
            role="other",
        ),
    )


def test_only_one_active_plan_per_week(seeded_db):
    user = _first(seeded_db, AppUser)

    def plan(status):
        return MealPlan(
            user_id=user.id,
            week_start=date(2026, 10, 12),
            status=status,
            constraints={},
            constraints_hash="h",
            solver_status="optimal",
            totals={},
            validation_report={},
        )

    seeded_db.add_all([plan("active"), plan("draft"), plan("superseded")])
    seeded_db.flush()
    _expect_violation(seeded_db, plan("active"))


def test_substitution_from_must_differ_from_to(seeded_db):
    ingredient = _first(seeded_db, Ingredient)
    _expect_violation(
        seeded_db,
        IngredientSubstitution(
            from_ingredient_id=ingredient.id,
            to_ingredient_id=ingredient.id,
            status="accepted",
            source="user",
            quantity_rule={"mode": "same_mass"},
        ),
    )


def test_recipe_default_version_must_exist(seeded_db):
    recipe = _first(seeded_db, Recipe)
    recipe.default_version_id = 10**12
    with pytest.raises(IntegrityError), seeded_db.begin_nested():
        seeded_db.flush()
