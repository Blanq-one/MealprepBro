import json
import shutil
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.db.models import (
    AppUser,
    Ingredient,
    IngredientAlias,
    IngredientNutrient,
    IngredientSubstitution,
    IngredientUnit,
    Nutrient,
    PriceObservation,
    Product,
    Recipe,
    RecipeFamily,
    RecipeIngredient,
    RecipeStep,
    RecipeVersion,
    Store,
    UsdaFood,
    UsdaFoodPortion,
    UserSettingsRow,
)
from app.domain.nutrition import CORE_CODES
from app.schemas.settings import UserSettings
from app.seed.files import DATA_DIR, load_seed_files, normalize_name
from app.seed.loader import SEED_FORBIDDEN_TAGS, SeedError, seed_all
from app.seed.report import build_report, format_report
from app.services.ingredient_data import load_by_slug
from app.services.recipes import seed_recipes

TABLES = (
    AppUser,
    Ingredient,
    IngredientAlias,
    IngredientNutrient,
    IngredientUnit,
    IngredientSubstitution,
    Store,
    Product,
    PriceObservation,
    RecipeFamily,
    Recipe,
    RecipeVersion,
    RecipeIngredient,
    RecipeStep,
    UserSettingsRow,
    Nutrient,
)


def _count(session, model):
    return session.scalar(select(func.count()).select_from(model))


def _slug(session, slug):
    return session.scalars(select(Ingredient).where(Ingredient.slug == slug)).one()


def test_seed_is_idempotent(seeded_db):
    before = {m.__tablename__: _count(seeded_db, m) for m in TABLES}
    report = seed_all(seeded_db)
    after = {m.__tablename__: _count(seeded_db, m) for m in TABLES}
    assert after == before
    assert report.counts["recipes_created"] == 0
    assert "settings already exist" in report.warnings[0]


def test_creates_single_user(seeded_db):
    assert _count(seeded_db, AppUser) == 1
    assert seeded_db.scalars(select(AppUser)).one().timezone == "America/New_York"


def test_ingredient_and_alias_counts(seeded_db):
    assert _count(seeded_db, Ingredient) >= 150
    assert _count(seeded_db, IngredientAlias) >= 300


def test_alias_keys_are_unique_and_normalized(seeded_db):
    keys = seeded_db.scalars(select(IngredientAlias.alias_normalized)).all()
    assert len(keys) == len(set(keys))
    assert all(k == normalize_name(k) for k in keys)
    hit = seeded_db.scalars(
        select(IngredientAlias).where(IngredientAlias.alias_normalized == "boneless thighs")
    ).one()
    assert seeded_db.get(Ingredient, hit.ingredient_id).slug == "chicken-thigh-boneless-skinless"


def test_fdc_ids_exist(seeded_db):
    for ingredient in seeded_db.scalars(select(Ingredient).where(Ingredient.fdc_id.is_not(None))):
        assert seeded_db.get(UsdaFood, ingredient.fdc_id) is not None, ingredient.slug


def test_nutrition_complete(seeded_db):
    """Every ingredient has energy/protein/carbs/fat, except label placeholders and pepperoni (held, and
    USDA has no proximates for it yet)."""
    data = load_by_slug(seeded_db)
    gaps = {slug: [c for c in CORE_CODES if c not in d.profile.per_100g] for slug, d in data.items()}
    gaps = {slug: missing for slug, missing in gaps.items() if missing}
    assert gaps == {
        "protein-powder-double-chocolate": ["carbohydrate_g", "fat_g"],
        "pepperoni": ["energy_kcal", "protein_g", "carbohydrate_g", "fat_g"],
    }


def test_label_conversion_for_protein_powder(seeded_db):
    data = load_by_slug(seeded_db)["protein-powder-double-chocolate"]
    assert data.profile.per_100g == {"energy_kcal": Decimal("387.0970"), "protein_g": Decimal("80.6450")}
    assert data.units.named_units == {"scoop": Decimal("31.000")}


def test_tortilla_piece_weight_is_flagged_estimate(seeded_db):
    tortilla = _slug(seeded_db, "flour-tortilla-small")
    assert tortilla.count_unit_weight_g == Decimal("21.733")
    assert "ESTIMATE" in tortilla.notes
    unit = seeded_db.scalars(select(IngredientUnit).where(IngredientUnit.ingredient_id == tortilla.id)).one()
    assert (unit.unit_name, unit.grams, unit.source) == ("tortilla", Decimal("21.733"), "label")


def test_usda_units_link_to_portions(seeded_db):
    units = seeded_db.scalars(select(IngredientUnit).where(IngredientUnit.source == "usda_portion")).all()
    assert len(units) > 50
    for unit in units:
        portion = seeded_db.get(UsdaFoodPortion, unit.usda_portion_id)
        ingredient = seeded_db.get(Ingredient, unit.ingredient_id)
        assert portion.fdc_id == ingredient.fdc_id
        assert unit.grams == (portion.gram_weight / (portion.amount or 1)).quantize(Decimal("0.001"))
    egg = _slug(seeded_db, "egg-large")
    assert egg.count_unit_weight_g == Decimal("50.000")
    garlic = load_by_slug(seeded_db)["garlic"]
    assert garlic.units.named_units["clove"] == Decimal("3.000")
    assert _slug(seeded_db, "olive-oil").density_g_per_ml == Decimal("0.9130")  # 13.5 g per tbsp


def test_every_price_has_a_store(seeded_db):
    assert _count(seeded_db, PriceObservation) == 52
    stores = {s.name: s for s in seeded_db.scalars(select(Store))}
    assert {(s.name, s.priority) for s in stores.values()} == {("Stop & Shop", 1), ("Price Rite", 2)}
    observations = seeded_db.scalars(select(PriceObservation)).all()
    assert all(o.store_id in {s.id for s in stores.values()} for o in observations)


def test_price_rite_tortilla_price_is_exact_and_manual(seeded_db):
    tortilla = _slug(seeded_db, "flour-tortilla-small")
    price_rite = seeded_db.scalars(select(Store).where(Store.name == "Price Rite")).one()
    obs = seeded_db.execute(
        select(PriceObservation, Product)
        .join(Product, Product.id == PriceObservation.product_id)
        .where(Product.ingredient_id == tortilla.id, PriceObservation.store_id == price_rite.id)
    ).one()
    observation, product = obs
    assert (observation.price_cents, observation.priced_quantity, observation.priced_unit) == (
        199,
        Decimal("30.000"),
        "count",
    )
    assert observation.source == "manual"
    assert product.store_id == price_rite.id  # store brand
    others = seeded_db.scalars(select(PriceObservation).where(PriceObservation.id != observation.id)).all()
    assert {o.source for o in others} == {"estimate"}


def test_price_rite_chicken_estimate_below_stop_and_shop(seeded_db):
    for slug in ("chicken-thigh-boneless-skinless", "chicken-breast-boneless-skinless"):
        rows = seeded_db.execute(
            select(Store.name, PriceObservation.price_cents)
            .join(Product, Product.id == PriceObservation.product_id)
            .join(Store, Store.id == PriceObservation.store_id)
            .where(Product.ingredient_id == _slug(seeded_db, slug).id)
        ).all()
        prices = dict(rows)
        assert prices["Price Rite"] < prices["Stop & Shop"]


def test_seed_recipes(seeded_db):
    versions = seeded_db.scalars(select(RecipeVersion)).all()
    assert len(versions) == 9
    assert all(v.is_draft and v.version_number == 1 and v.created_by == "system" for v in versions)
    families = seeded_db.scalars(select(RecipeFamily.name)).all()
    assert sorted(families) == sorted(
        [
            "Chicken over rice",
            "Chicken gravy with flour tortillas used as chapati",
            "Protein pudding",
            "Egg breakfast",
            "Protein oats",
        ]
    )
    for recipe in seeded_db.scalars(select(Recipe)):
        assert recipe.origin == "seed"
        assert recipe.default_version_id is not None
        assert seeded_db.get(RecipeVersion, recipe.default_version_id).recipe_id == recipe.id


def test_seed_recipes_use_no_beef_held_or_pork_component(seeded_db):
    data = {d.id: d for d in load_by_slug(seeded_db).values()}
    for line in seeded_db.scalars(select(RecipeIngredient)):
        assert not data[line.ingredient_id].tagged.diet_tags & SEED_FORBIDDEN_TAGS


def test_seed_steps(seeded_db):
    for version in seeded_db.scalars(select(RecipeVersion)):
        steps = seeded_db.scalars(select(RecipeStep).where(RecipeStep.recipe_version_id == version.id)).all()
        sections = {s.section for s in steps}
        assert {"prep", "portioning"} <= sections, version.title
        for step in steps:
            if step.section in {"oven", "air_fryer"}:
                assert step.appliance_temp_f is not None
    air_fry = seeded_db.scalars(select(RecipeStep).where(RecipeStep.section == "air_fryer")).first()
    assert "400F for 18 minutes, flip" in air_fry.text
    checks = seeded_db.scalars(
        select(RecipeStep).where(RecipeStep.doneness_check_ingredient_id.is_not(None))
    ).all()
    assert len(checks) == 7  # every chicken and egg dish names what to check


def test_seed_quantities_in_base_units(seeded_db):
    version = seeded_db.scalars(
        select(RecipeVersion).where(RecipeVersion.title == "Chicken over rice with garlic yogurt sauce")
    ).one()
    lines = {
        seeded_db.get(Ingredient, r.ingredient_id).slug: r
        for r in seeded_db.scalars(
            select(RecipeIngredient).where(RecipeIngredient.recipe_version_id == version.id)
        )
    }
    assert (lines["garlic"].quantity, lines["garlic"].unit) == (Decimal("15.000"), "g")  # 5 cloves × 3 g
    assert (lines["garlic"].authored_quantity, lines["garlic"].authored_unit) == (Decimal("5.000"), "clove")
    assert (lines["salt"].quantity, lines["salt"].unit) == (Decimal("6.161"), "ml")  # 1¼ tsp
    assert (lines["tomato"].quantity, lines["tomato"].unit) == (Decimal("2.000"), "count")


def test_chapati_pair(seeded_db):
    sub = seeded_db.scalars(select(IngredientSubstitution)).one()
    assert seeded_db.get(Ingredient, sub.from_ingredient_id).slug == "chapati"
    assert seeded_db.get(Ingredient, sub.to_ingredient_id).slug == "flour-tortilla-small"
    assert (sub.status, sub.source, sub.quantity_rule) == ("accepted", "seed", {"mode": "count_for_count"})


def test_default_settings(seeded_db):
    row = seeded_db.scalars(select(UserSettingsRow)).one()
    settings = UserSettings.model_validate(row.settings)
    cook_days = [d.weekday.value for d in settings.cook_schedule if d.is_cook_day]
    assert cook_days == ["mon", "wed", "thu", "sat", "sun"]
    assert all(d.cook_minutes == 0 for d in settings.cook_schedule if not d.is_cook_day)
    assert settings.excluded_diet_tags == ["beef"]
    (cap,) = settings.frequency_caps
    assert (cap.target_type.value, cap.target, cap.max_meals_per_week, cap.never_favor) == (
        "tag",
        "pork",
        1,
        True,
    )
    assert settings.store_split_min_savings_cents == 500
    assert settings.store_order == ["Stop & Shop", "Price Rite"]
    assert settings.leftover_fridge_days == 3
    assert (settings.calorie_mode.value, settings.daily_band_kcal, settings.daily_kcal_target) == (
        "weekly",
        150,
        1800,
    )


def test_seven_recipes_complete_and_powder_recipes_incomplete(seeded_db):
    user = seeded_db.scalars(select(AppUser)).one()
    views = {v.version.title: v.calculation for v in seed_recipes(seeded_db, user.id)}
    incomplete = {t for t, c in views.items() if not c.nutrition_complete}
    assert incomplete == {"Double chocolate protein pudding", "Chocolate protein overnight oats"}
    for title in incomplete:
        assert views[title].incomplete_reasons == (
            "incomplete: protein powder, double chocolate label values missing (carbohydrate_g, fat_g)",
        )
    for title, calc in views.items():
        if title not in incomplete:
            assert all(c.total.complete for c in calc.costs), title


def test_powder_recipes_complete_once_label_values_are_filled(seeded_db, tmp_path, fixtures_dir):
    data_dir = tmp_path / "data"
    shutil.copytree(DATA_DIR, data_dir)
    labels = json.loads((data_dir / "label_inputs.json").read_text(encoding="utf-8"))
    fixture = json.loads((fixtures_dir / "label_values.json").read_text(encoding="utf-8"))
    powder = labels["labels"]["protein-powder-double-chocolate"]
    powder["per_serving"].update(fixture["protein-powder-double-chocolate"])
    powder["placeholders"] = []
    (data_dir / "label_inputs.json").write_text(json.dumps(labels), encoding="utf-8")

    seed_all(seeded_db, data_dir)
    user = seeded_db.scalars(select(AppUser)).one()
    views = {v.version.title: v.calculation for v in seed_recipes(seeded_db, user.id)}
    assert views["Double chocolate protein pudding"].nutrition_complete
    assert views["Chocolate protein overnight oats"].nutrition_complete


def test_seed_rejects_a_recipe_with_a_pork_component(seeded_db, tmp_path):
    data_dir = tmp_path / "data"
    shutil.copytree(DATA_DIR, data_dir)
    recipe = json.loads(
        (data_dir / "recipes" / "4a_egg_spinach_pepper_breakfast_wraps.json").read_text("utf-8")
    )
    recipe["title"] = "Bacon breakfast wraps"
    recipe["ingredients"].append({"ingredient": "bacon", "quantity": "4", "unit": "slice", "role": "protein"})
    (data_dir / "recipes" / "9z_bacon.json").write_text(json.dumps(recipe), encoding="utf-8")
    with pytest.raises(SeedError, match="pork"):
        seed_all(seeded_db, data_dir)


def test_seed_files_validate():
    files = load_seed_files()
    assert len(files.recipes) == 9
    assert len(files.ingredients.ingredients) >= 150


def test_ingredient_report_has_zero_errors(seeded_db):
    report = build_report(seeded_db)
    assert report.errors == []
    text = format_report(report)
    assert "carbohydrate_g, fat_g per scoop not filled yet" in text
    assert "ESTIMATE" in text
    held = " ".join(report.held)
    assert "gelatin, unflavored" in held and "pepperoni" in held
    assert any("ground beef" in e for e in report.excluded)
    assert "bacon" in report.pork_capped and "lard" in report.pork_trace
