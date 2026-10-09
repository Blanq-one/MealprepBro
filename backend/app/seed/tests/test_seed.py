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
    """Every ingredient has energy/protein/carbs/fat, except pepperoni (held, and USDA has no proximates
    for it yet)."""
    data = load_by_slug(seeded_db)
    gaps = {slug: [c for c in CORE_CODES if c not in d.profile.per_100g] for slug, d in data.items()}
    gaps = {slug: missing for slug, missing in gaps.items() if missing}
    assert gaps == {"pepperoni": ["energy_kcal", "protein_g", "carbohydrate_g", "fat_g"]}


def _sources(session, slug):
    ingredient = _slug(session, slug)
    rows = session.execute(
        select(Nutrient.code, IngredientNutrient.amount_per_100g, IngredientNutrient.source)
        .join(Nutrient, Nutrient.id == IngredientNutrient.nutrient_id)
        .where(IngredientNutrient.ingredient_id == ingredient.id)
    ).all()
    return {code: (amount, source) for code, amount, source in rows}


def test_protein_powder_comes_from_the_package_label(seeded_db):
    rows = _sources(seeded_db, "protein-powder-double-chocolate")
    per_100g = {code: amount for code, (amount, _) in rows.items()}
    # per scoop / 31 g x 100
    assert per_100g == {
        "energy_kcal": Decimal("387.0970"),
        "protein_g": Decimal("77.4190"),
        "fat_g": Decimal("4.8390"),
        "saturated_fat_g": Decimal("3.2260"),
        "carbohydrate_g": Decimal("9.6770"),
        "fiber_g": Decimal("1.6130"),
        "sugars_g": Decimal("3.2260"),
        "sodium_mg": Decimal("419.3550"),
        "calcium_mg": Decimal("419.3550"),
        "iron_mg": Decimal("2.2580"),
        "potassium_mg": Decimal("645.1610"),
    }
    assert {source for _, source in rows.values()} == {"package_label"}
    powder = _slug(seeded_db, "protein-powder-double-chocolate")
    assert (powder.nutrition_source, powder.fdc_id, powder.heme_iron_fraction) == ("package_label", None, 0)
    assert sorted(powder.diet_tags) == ["dairy", "soy"]  # allergens: milk, soy
    units = load_by_slug(seeded_db)["protein-powder-double-chocolate"].units.named_units
    assert units == {"scoop": Decimal("31.000")}


def test_tortilla_label_overrides_usda_and_usda_fills_the_gaps(seeded_db):
    rows = _sources(seeded_db, "flour-tortilla-small")
    on_label = {
        "energy_kcal",
        "protein_g",
        "fat_g",
        "saturated_fat_g",
        "carbohydrate_g",
        "fiber_g",
        "sugars_g",
        "sodium_mg",
    }
    assert {code for code, (_, source) in rows.items() if source == "package_label"} == on_label
    assert rows["energy_kcal"] == (Decimal("297.2970"), "package_label")  # 110 kcal / 37 g
    assert rows["sodium_mg"] == (Decimal("918.9190"), "package_label")  # 340 mg / 37 g
    assert rows["protein_g"][0] == Decimal("8.1080")
    assert rows["iron_mg"][1] == "usda"  # not among the label values: from USDA FDC 167535
    tortilla = _slug(seeded_db, "flour-tortilla-small")
    assert (tortilla.nutrition_source, tortilla.fdc_id) == ("package_label", 167535)


def test_tortilla_piece_weight_from_the_label(seeded_db):
    tortilla = _slug(seeded_db, "flour-tortilla-small")
    assert tortilla.count_unit_weight_g == Decimal("37.000")  # 740 g / 20
    assert "ESTIMATE" not in (tortilla.notes or "")
    unit = seeded_db.scalars(select(IngredientUnit).where(IngredientUnit.ingredient_id == tortilla.id)).one()
    assert (unit.unit_name, unit.grams, unit.source) == ("tortilla", Decimal("37.000"), "package_label")
    files = load_seed_files()
    package = files.labels.packages["flour-tortilla-small"]
    assert (package.count, package.net_weight_g, package.is_estimate) == (20, Decimal("740"), False)
    assert {label.source for label in files.labels.labels.values()} == {"package label"}


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
        Decimal("20.000"),
        "count",
    )
    assert product.name == "Flour tortillas, 20 ct (740 g)"
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


def test_all_seed_recipes_have_complete_nutrition(seeded_db):
    user = seeded_db.scalars(select(AppUser)).one()
    views = {v.version.title: v.calculation for v in seed_recipes(seeded_db, user.id)}
    assert all(c.nutrition_complete for c in views.values())
    powder_recipes = {"Double chocolate protein pudding", "Chocolate protein overnight oats"}
    for title, calc in views.items():
        if title in powder_recipes:  # protein powder price still pending
            assert all(c.total.unpriced == ("protein powder, double chocolate",) for c in calc.costs), title
        else:
            assert all(c.total.complete for c in calc.costs), title


def test_powder_product_has_no_price_yet(seeded_db):
    powder = _slug(seeded_db, "protein-powder-double-chocolate")
    product = seeded_db.scalars(select(Product).where(Product.ingredient_id == powder.id)).one()
    assert (product.package_amount, product.package_unit) == (Decimal("682.000"), "g")
    observations = seeded_db.scalars(
        select(PriceObservation).where(PriceObservation.product_id == product.id)
    )
    assert observations.all() == []


def _copy_data(tmp_path):
    data_dir = tmp_path / "data"
    shutil.copytree(DATA_DIR, data_dir)
    return data_dir


def _base_recipe(data_dir):
    return json.loads((data_dir / "recipes" / "1b_air_fryer_chicken_rice_broccoli.json").read_text("utf-8"))


def test_a_missing_label_value_makes_recipes_incomplete(seeded_db, tmp_path):
    data_dir = _copy_data(tmp_path)
    labels = json.loads((data_dir / "label_inputs.json").read_text(encoding="utf-8"))
    powder = labels["labels"]["protein-powder-double-chocolate"]
    powder["per_serving"]["fat_g"] = None
    powder["placeholders"] = ["fat_g"]
    (data_dir / "label_inputs.json").write_text(json.dumps(labels), encoding="utf-8")
    seed_all(seeded_db, data_dir)
    user = seeded_db.scalars(select(AppUser)).one()
    views = {v.version.title: v.calculation for v in seed_recipes(seeded_db, user.id)}
    assert views["Double chocolate protein pudding"].incomplete_reasons == (
        "incomplete: protein powder, double chocolate label values missing (fat_g)",
    )


def test_untracked_label_values_are_rejected(seeded_db, tmp_path):
    data_dir = _copy_data(tmp_path)
    labels = json.loads((data_dir / "label_inputs.json").read_text(encoding="utf-8"))
    labels["labels"]["flour-tortilla-small"]["per_serving"]["cholesterol_mg"] = "0"
    (data_dir / "label_inputs.json").write_text(json.dumps(labels), encoding="utf-8")
    with pytest.raises(SeedError, match="other_values"):
        seed_all(seeded_db, data_dir)


def test_line_marked_cooked_with_a_dry_mapping_fails(seeded_db, tmp_path):
    data_dir = _copy_data(tmp_path)
    recipe = _base_recipe(data_dir)
    recipe["title"] = "Cooked-rice bowl"
    recipe["ingredients"] = [
        dict(line, state="cooked") if line["ingredient"] == "rice-long-grain-white" else line
        for line in recipe["ingredients"]
    ]
    (data_dir / "recipes" / "9y_cooked_rice.json").write_text(json.dumps(recipe), encoding="utf-8")
    with pytest.raises(SeedError, match="the line says cooked, but its nutrition is for dry food"):
        seed_all(seeded_db, data_dir)


def test_raw_weight_line_with_a_cooked_mapping_fails(seeded_db, tmp_path):
    # remap pasta (dry) to a cooked USDA food, then use it with the default raw / dry quantity
    seeded_db.add(
        UsdaFood(
            fdc_id=9990001,
            data_type="sr_legacy_food",
            source_release="test",
            description="Pasta, cooked, enriched, without added salt",
        )
    )
    seeded_db.flush()
    data_dir = _copy_data(tmp_path)
    ingredients = json.loads((data_dir / "ingredients.json").read_text(encoding="utf-8"))
    for item in ingredients["ingredients"]:
        if item["slug"] == "pasta-dry":
            item["fdc_id"] = 9990001
    (data_dir / "ingredients.json").write_text(json.dumps(ingredients), encoding="utf-8")
    recipe = _base_recipe(data_dir)
    recipe["title"] = "Chicken pasta"
    recipe["ingredients"] = [
        dict(line, ingredient="pasta-dry") if line["ingredient"] == "rice-long-grain-white" else line
        for line in recipe["ingredients"]
    ]
    (data_dir / "recipes" / "9x_pasta.json").write_text(json.dumps(recipe), encoding="utf-8")
    with pytest.raises(SeedError, match="its nutrition is for cooked food, but recipe quantities are raw"):
        seed_all(seeded_db, data_dir)


def test_seed_lines_match_their_mappings(seeded_db):
    data = {d.id: d for d in load_by_slug(seeded_db).values()}
    for line in seeded_db.scalars(select(RecipeIngredient)):
        assert data[line.ingredient_id].mapping_state.value != "cooked"


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
    assert "not filled yet" not in text
    assert "ESTIMATE" not in text
    assert report.placeholders == ["food-safety storage chart: 12 rows pending transcription (A1)"]
    held = " ".join(report.held)
    assert "gelatin, unflavored" in held and "pepperoni" in held
    assert any("ground beef" in e for e in report.excluded)
    assert "bacon" in report.pork_capped and "lard" in report.pork_trace
