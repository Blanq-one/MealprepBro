"""Idempotent seed loader: nutrients, stores, ingredients (nutrition from the USDA cache or your labels),
named units, aliases, accepted substitutions, products and estimated prices, default settings and the
draft seed recipe library. Run after `usda-import`. The caller commits."""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

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
    UsdaFoodNutrient,
    UsdaFoodPortion,
    UserSettingsRow,
)
from app.domain.enums import NutritionSource, RecipeOrigin
from app.domain.exclusions import HELD_TAG, PORK_COMPONENT_TAG
from app.domain.food_state import line_state_error
from app.domain.frequency_caps import CapTarget
from app.domain.nutrition import energy_from_usda, label_per_100g
from app.domain.quantities import parse_quantity
from app.domain.units import (
    COUNT_UNITS,
    GRAMS_PER_UNIT,
    ML_PER_UNIT,
    normalize_named_unit,
    normalize_unit,
    to_base,
)
from app.schemas.seed import LabelRef, PortionRef, SeedAmount, SeedIngredient, SeedNutrient, SeedRecipe
from app.seed.files import DATA_DIR, SeedFiles, load_seed_files, normalize_name
from app.services.ingredient_data import load_by_slug

SEED_USER_NAME = "Me"
_Q3 = Decimal("0.001")
_Q4 = Decimal("0.0001")
_MEASURE_WORDS = {
    "tsp": ("tsp", "teaspoon"),
    "tbsp": ("tbsp", "tablespoon"),
    "cup": ("cup",),
    "fl_oz": ("fl oz",),
}
SEED_FORBIDDEN_TAGS = frozenset({"beef", HELD_TAG, PORK_COMPONENT_TAG})  # R2: seeds use none of these


class SeedError(ValueError):
    pass


@dataclass
class SeedReport:
    counts: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _q3(value: Decimal) -> Decimal:
    return value.quantize(_Q3, rounding=ROUND_HALF_UP)


def _base_amount(amount: SeedAmount) -> tuple[Decimal, str]:
    unit = normalize_unit(amount.unit)
    if unit in GRAMS_PER_UNIT:
        return _q3(amount.amount * GRAMS_PER_UNIT[unit]), "g"
    if unit in ML_PER_UNIT:
        return _q3(amount.amount * ML_PER_UNIT[unit]), "ml"
    if unit in COUNT_UNITS:
        return _q3(amount.amount), "count"
    raise SeedError(f"unit '{amount.unit}' can't be used for a package or price")


def ensure_user(session: Session) -> AppUser:
    user = session.scalars(select(AppUser).order_by(AppUser.id)).first()
    if user is None:
        user = AppUser(display_name=SEED_USER_NAME)
        session.add(user)
        session.flush()
    return user


def _nutrients(session: Session, files: SeedFiles) -> None:
    for n in files.nutrients.nutrients:
        row = session.get(Nutrient, n.id) or Nutrient(id=n.id)
        row.code, row.display_name, row.unit = n.code, n.display_name, n.unit
        row.fdc_number, row.is_core, row.daily_value, row.sort_order = (
            n.fdc_number,
            n.is_core,
            n.daily_value,
            n.id,
        )
        session.add(row)
    session.flush()


def _stores(session: Session, files: SeedFiles) -> dict[str, Store]:
    stores: dict[str, Store] = {}
    for s in files.stores.stores:
        row = session.scalars(select(Store).where(Store.name == s.name)).first() or Store(name=s.name)
        row.priority, row.region_code, row.notes, row.kind = s.priority, s.region_code, s.notes, s.kind
        session.add(row)
        stores[s.name] = row
    session.flush()
    return stores


@dataclass
class _UsdaCache:
    """Everything the ingredient pass needs from the USDA tables, loaded in a few bulk queries."""

    foods: set[int]
    portions: dict[int, UsdaFoodPortion]
    values: dict[int, dict[int, Decimal]]  # fdc_id -> usda_nutrient_id -> amount

    @classmethod
    def load(cls, session: Session, files: SeedFiles) -> "_UsdaCache":
        fdc_ids = {i.fdc_id for i in files.ingredients.ingredients if i.fdc_id is not None}
        portion_ids: set[int] = set()
        for i in files.ingredients.ingredients:
            for ref in (i.density, i.count_unit_weight):
                if isinstance(ref, PortionRef):
                    portion_ids.add(ref.usda_portion_id)
            portion_ids.update(u.usda_portion_id for u in i.units if u.usda_portion_id is not None)
        foods = set(session.scalars(select(UsdaFood.fdc_id).where(UsdaFood.fdc_id.in_(fdc_ids))))
        portions = {
            p.id: p
            for p in session.scalars(select(UsdaFoodPortion).where(UsdaFoodPortion.id.in_(portion_ids)))
        }
        values: dict[int, dict[int, Decimal]] = {}
        for fdc_id, nutrient_id, amount in session.execute(
            select(UsdaFoodNutrient.fdc_id, UsdaFoodNutrient.usda_nutrient_id, UsdaFoodNutrient.amount).where(
                UsdaFoodNutrient.fdc_id.in_(fdc_ids)
            )
        ):
            values.setdefault(fdc_id, {})[nutrient_id] = amount
        return cls(foods, portions, values)

    def portion(self, portion_id: int, ingredient: SeedIngredient) -> UsdaFoodPortion:
        portion = self.portions.get(portion_id)
        if portion is None:
            raise SeedError(f"{ingredient.slug}: USDA portion {portion_id} not found (run usda-import)")
        if portion.fdc_id != ingredient.fdc_id:
            raise SeedError(
                f"{ingredient.slug}: portion {portion.id} belongs to FDC {portion.fdc_id}, "
                f"not {ingredient.fdc_id}"
            )
        return portion


def _grams_per_portion(portion: UsdaFoodPortion) -> Decimal:
    return portion.gram_weight / (portion.amount or Decimal(1))


def _density(cache: _UsdaCache, ingredient: SeedIngredient) -> Decimal | None:
    ref = ingredient.density
    if ref is None:
        return None
    portion = cache.portion(ref.usda_portion_id, ingredient)
    assert ref.measure is not None  # enforced by the schema
    text = f"{portion.modifier or ''} {portion.measure_unit or ''}".lower()
    if not any(word in text for word in _MEASURE_WORDS[ref.measure]):
        raise SeedError(
            f"{ingredient.slug}: portion {portion.id} ('{portion.modifier}') is not a {ref.measure}"
        )
    ml = (portion.amount or Decimal(1)) * ML_PER_UNIT[ref.measure]
    return (portion.gram_weight / ml).quantize(_Q4, rounding=ROUND_HALF_UP)


def _label_piece_grams(files: SeedFiles, key: str) -> Decimal:
    if key in files.labels.packages:
        package = files.labels.packages[key]
        return _q3(package.net_weight_g / package.count)
    if key in files.labels.labels:
        return _q3(files.labels.labels[key].serving_grams)
    raise SeedError(f"label '{key}' is not in label_inputs.json")


NutritionRow = tuple[int, Decimal, str, int | None]  # (nutrient_id, amount_per_100g, source, fdc_id)


def _nutrition_rows(
    files: SeedFiles, cache: _UsdaCache, seed: SeedIngredient, nutrients: list[SeedNutrient]
) -> list[NutritionRow]:
    if seed.nutrition_source is not NutritionSource.PACKAGE_LABEL:
        assert seed.fdc_id is not None  # enforced by the schema
        return _usda_rows(seed.fdc_id, cache.values.get(seed.fdc_id, {}), nutrients)
    label = files.labels.labels.get(seed.slug)
    if label is None:
        raise SeedError(f"{seed.slug}: package-label ingredient missing from label_inputs.json")
    by_code = {n.code: n.id for n in nutrients}
    if unknown := sorted(set(label.per_serving) - set(by_code)):
        raise SeedError(
            f"{seed.slug}: label values for untracked nutrients {unknown}; put them in other_values"
        )
    conversion = label_per_100g(label.per_serving, label.serving_grams)
    source = NutritionSource.PACKAGE_LABEL.value
    rows: list[NutritionRow] = [
        (by_code[code], value, source, None) for code, value in conversion.per_100g.items()
    ]
    if seed.fdc_id is not None:
        # The label overrides the USDA mapping; USDA fills only nutrients the label doesn't list.
        on_label = {nutrient_id for nutrient_id, *_ in rows} | {by_code[c] for c in label.placeholders}
        usda = _usda_rows(seed.fdc_id, cache.values.get(seed.fdc_id, {}), nutrients)
        rows += [row for row in usda if row[0] not in on_label]
    return rows


def usda_nutrition_rows(session: Session, fdc_id: int, nutrients: list[SeedNutrient]) -> list[NutritionRow]:
    """Per-100 g rows for one food from the USDA cache (see _usda_rows)."""
    values = dict(
        session.execute(
            select(UsdaFoodNutrient.usda_nutrient_id, UsdaFoodNutrient.amount).where(
                UsdaFoodNutrient.fdc_id == fdc_id
            )
        )
        .tuples()
        .all()
    )
    return _usda_rows(fdc_id, values, nutrients)


def _usda_rows(fdc_id: int, values: dict[int, Decimal], nutrients: list[SeedNutrient]) -> list[NutritionRow]:
    """Each nutrient takes the first USDA id present in its preference list; energy falls back
    208 → 958 → 957 → 4/4/9 (stored as 'derived')."""
    rows: list[NutritionRow] = []
    resolved: dict[str, Decimal] = {}
    for n in nutrients:
        if n.code == "energy_kcal":
            continue
        for usda_id in n.usda_nutrient_ids:
            if usda_id in values:
                resolved[n.code] = values[usda_id]
                rows.append((n.id, values[usda_id], "usda", fdc_id))
                break
    energy_def = next(n for n in nutrients if n.code == "energy_kcal")
    by_nbr = {
        nbr: values[uid]
        for uid, nbr in zip(energy_def.usda_nutrient_ids, ("208", "958", "957"), strict=True)
        if uid in values
    }
    for code, nbr in (("protein_g", "203"), ("carbohydrate_g", "205"), ("fat_g", "204")):
        if code in resolved:
            by_nbr[nbr] = resolved[code]
    energy = energy_from_usda(by_nbr)
    if energy is not None:
        source = NutritionSource.DERIVED.value if energy.is_derived else "usda"
        rows.append((energy_def.id, energy.kcal, source, fdc_id))
    return rows


def _apply_ingredient(row: Ingredient, seed: SeedIngredient, files: SeedFiles, cache: _UsdaCache) -> None:
    row.name, row.category, row.default_unit_kind = (
        seed.name,
        seed.category.value,
        seed.default_unit_kind.value,
    )
    row.density_g_per_ml = _density(cache, seed)
    if isinstance(seed.count_unit_weight, PortionRef):
        row.count_unit_weight_g = _q3(
            _grams_per_portion(cache.portion(seed.count_unit_weight.usda_portion_id, seed))
        )
    elif isinstance(seed.count_unit_weight, LabelRef):
        row.count_unit_weight_g = _label_piece_grams(files, seed.count_unit_weight.label)
    else:
        row.count_unit_weight_g = None
    row.count_rounding_step = seed.count_rounding_step
    row.heme_iron_fraction = seed.heme_iron_fraction
    row.diet_tags = sorted(seed.diet_tags)
    row.diet_review_note = seed.diet_review_note
    row.safety_category = seed.safety_category.value if seed.safety_category else None
    row.is_perishable, row.typical_location = seed.is_perishable, seed.typical_location.value
    row.assume_in_stock, row.nutrition_source = seed.assume_in_stock, seed.nutrition_source.value
    row.stock_up = seed.stock_up
    row.fdc_id, row.notes = seed.fdc_id, seed.notes
    if seed.nutrition_reviewed_on is not None:  # never clears a review recorded elsewhere
        row.nutrition_reviewed_at = datetime.combine(seed.nutrition_reviewed_on, time(), tzinfo=UTC)


def _wanted_units(
    seed: SeedIngredient, files: SeedFiles, cache: _UsdaCache
) -> dict[str, tuple[Decimal, str, int | None]]:
    wanted: dict[str, tuple[Decimal, str, int | None]] = {}
    for unit in seed.units:
        name = normalize_named_unit(unit.name)
        if unit.usda_portion_id is not None:
            portion = cache.portion(unit.usda_portion_id, seed)
            wanted[name] = (_q3(_grams_per_portion(portion)), "usda_portion", portion.id)
        else:
            assert unit.label is not None
            wanted[name] = (_label_piece_grams(files, unit.label), NutritionSource.PACKAGE_LABEL.value, None)
    return wanted


def _ingredients(session: Session, files: SeedFiles, report: SeedReport) -> dict[str, Ingredient]:
    cache = _UsdaCache.load(session, files)
    nutrients = files.nutrients.nutrients
    existing = {i.slug: i for i in session.scalars(select(Ingredient))}
    result: dict[str, Ingredient] = {}
    with session.no_autoflush:
        for seed in files.ingredients.ingredients:
            if seed.fdc_id is not None and seed.fdc_id not in cache.foods:
                raise SeedError(
                    f"{seed.slug}: FDC {seed.fdc_id} is not in the USDA cache (run usda-import first)"
                )
            row = existing.get(seed.slug) or Ingredient(slug=seed.slug)
            _apply_ingredient(row, seed, files, cache)
            session.add(row)
            result[seed.slug] = row
    session.flush()
    ids = [row.id for row in result.values()]

    # nutrition: replace the seeded ingredients' rows wholesale (idempotent)
    session.execute(delete(IngredientNutrient).where(IngredientNutrient.ingredient_id.in_(ids)))
    session.add_all(
        IngredientNutrient(
            ingredient_id=result[seed.slug].id,
            nutrient_id=nutrient_id,
            amount_per_100g=amount,
            source=source,
            fdc_id=fdc_id,
        )
        for seed in files.ingredients.ingredients
        for nutrient_id, amount, source, fdc_id in _nutrition_rows(files, cache, seed, nutrients)
    )

    # named units
    units: dict[int, dict[str, IngredientUnit]] = {}
    for unit_row in session.scalars(select(IngredientUnit).where(IngredientUnit.ingredient_id.in_(ids))):
        units.setdefault(unit_row.ingredient_id, {})[unit_row.unit_name] = unit_row
    for seed in files.ingredients.ingredients:
        row = result[seed.slug]
        wanted = _wanted_units(seed, files, cache)
        current = units.get(row.id, {})
        for name, stale in current.items():
            if name not in wanted:
                session.delete(stale)
        for name, (grams, source, portion_id) in wanted.items():
            unit_row = current.get(name) or IngredientUnit(ingredient_id=row.id, unit_name=name)
            unit_row.grams, unit_row.source, unit_row.usda_portion_id = grams, source, portion_id
            session.add(unit_row)

    # aliases (the canonical name is always one of them)
    aliases = {a.alias_normalized: a for a in session.scalars(select(IngredientAlias))}
    seen: dict[str, str] = {}
    for seed in files.ingredients.ingredients:
        row = result[seed.slug]
        for alias in [seed.name, *seed.aliases]:
            key = normalize_name(alias)
            owner = seen.setdefault(key, seed.slug)
            if owner != seed.slug:
                raise SeedError(f"alias '{alias}' is used by both {owner} and {seed.slug}")
            alias_row = aliases.get(key)
            if alias_row is None:
                alias_row = IngredientAlias(
                    ingredient_id=row.id, alias=alias, alias_normalized=key, source="seed"
                )
                aliases[key] = alias_row
                session.add(alias_row)
            elif alias_row.ingredient_id != row.id:
                raise SeedError(f"alias '{alias}' already belongs to another ingredient")
    session.flush()
    report.counts["ingredients"] = len(result)
    report.counts["aliases"] = len(seen)
    return result


def _substitutions(session: Session, files: SeedFiles, ingredients: dict[str, Ingredient]) -> int:
    for sub in files.substitutions.substitutions:
        try:
            src, dst = ingredients[sub.from_ingredient], ingredients[sub.to_ingredient]
        except KeyError as exc:
            raise SeedError(f"substitution references unknown ingredient {exc}") from exc
        row = session.scalars(
            select(IngredientSubstitution).where(
                IngredientSubstitution.from_ingredient_id == src.id,
                IngredientSubstitution.to_ingredient_id == dst.id,
                IngredientSubstitution.context_key == sub.context_key,
            )
        ).first() or IngredientSubstitution(
            from_ingredient_id=src.id, to_ingredient_id=dst.id, context_key=sub.context_key
        )
        row.status, row.source, row.quantity_rule = sub.status, "seed", dict(sub.quantity_rule)
        row.culinary_note, row.preparation_changes = sub.culinary_note, sub.preparation_changes
        session.add(row)
    session.flush()
    return len(files.substitutions.substitutions)


def _products(
    session: Session, files: SeedFiles, ingredients: dict[str, Ingredient], stores: dict[str, Store]
) -> tuple[int, int]:
    observed_on = date.fromisoformat(files.products.observed_on)
    observations = 0
    for p in files.products.products:
        ingredient = ingredients.get(p.ingredient)
        if ingredient is None:
            raise SeedError(f"product '{p.name}' references unknown ingredient '{p.ingredient}'")
        store_id = stores[p.store_brand_of].id if p.store_brand_of else None
        row = session.scalars(
            select(Product).where(Product.ingredient_id == ingredient.id, Product.name == p.name)
        ).first()
        row = row or Product(ingredient_id=ingredient.id, name=p.name)
        if p.package is not None:
            row.package_amount, row.package_unit = _base_amount(p.package)
        else:
            row.package_amount = None
            row.package_unit = (
                {"mass": "g", "volume": "ml", "count": "count"}[ingredient.default_unit_kind]
                if p.price_basis.value != "per_weight"
                else "g"
            )
        row.store_id, row.brand, row.is_variable_weight = store_id, p.brand, p.is_variable_weight
        row.price_basis, row.display_unit, row.is_default = p.price_basis.value, p.display_unit, p.is_default
        session.add(row)
        session.flush()
        for price in p.prices:
            store = stores.get(price.store)
            if store is None:
                raise SeedError(f"price for '{p.name}' references unknown store '{price.store}'")
            quantity, unit = _base_amount(price.per)
            exists = session.scalars(
                select(PriceObservation).where(
                    PriceObservation.product_id == row.id,
                    PriceObservation.store_id == store.id,
                    PriceObservation.observed_on == observed_on,
                    PriceObservation.price_cents == price.price_cents,
                    PriceObservation.source == price.source.value,
                )
            ).first()
            if exists is None:
                session.add(
                    PriceObservation(
                        product_id=row.id,
                        store_id=store.id,
                        observed_on=observed_on,
                        price_cents=price.price_cents,
                        priced_quantity=quantity,
                        priced_unit=unit,
                        source=price.source.value,
                        note=price.note,
                    )
                )
            observations += 1
    session.flush()
    return len(files.products.products), observations


def _settings(
    session: Session,
    files: SeedFiles,
    *,
    user: AppUser,
    stores: dict[str, Store],
    ingredients: dict[str, Ingredient],
    report: SeedReport,
) -> None:
    settings = files.settings
    if unknown := [s for s in settings.store_order if s not in stores]:
        raise SeedError(f"settings reference unknown stores: {unknown}")
    for cap in settings.frequency_caps:
        if cap.target_type is CapTarget.INGREDIENT and cap.target not in ingredients:
            raise SeedError(f"frequency cap '{cap.label}' targets unknown ingredient '{cap.target}'")
    if session.get(UserSettingsRow, user.id) is None:
        session.add(
            UserSettingsRow(
                user_id=user.id,
                settings=settings.model_dump(mode="json"),
                schema_version=settings.schema_version,
            )
        )
    else:
        report.warnings.append("settings already exist; defaults not re-applied (your edits are kept)")
    session.flush()


def content_hash(recipe: SeedRecipe) -> str:
    payload = json.dumps(recipe.model_dump(mode="json", exclude={"family", "draft_note"}), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _recipes(session: Session, files: SeedFiles, user: AppUser, report: SeedReport) -> int:
    data = load_by_slug(session)
    created = 0
    for file_name, seed in files.recipes:
        for line in seed.ingredients:
            if line.ingredient not in data:
                raise SeedError(f"{file_name}: unknown ingredient '{line.ingredient}'")
            if forbidden := data[line.ingredient].tagged.diet_tags & SEED_FORBIDDEN_TAGS:
                raise SeedError(
                    f"{file_name}: '{line.ingredient}' is tagged {sorted(forbidden)}; "
                    "seed recipes may not use beef, held items or pork components"
                )
            ingredient = data[line.ingredient]
            if problem := line_state_error(ingredient.name, line.state, ingredient.mapping_state):
                raise SeedError(f"{file_name}: {problem}")
        family = session.scalars(
            select(RecipeFamily).where(RecipeFamily.user_id == user.id, RecipeFamily.name == seed.family)
        ).first()
        if family is None:
            family = RecipeFamily(user_id=user.id, name=seed.family)
            session.add(family)
            session.flush()
        digest = content_hash(seed)
        recipe = session.scalars(
            select(Recipe).where(
                Recipe.user_id == user.id,
                Recipe.title == seed.title,
                Recipe.origin == RecipeOrigin.SEED.value,
            )
        ).first()
        if recipe is not None:
            first = session.scalars(
                select(RecipeVersion).where(
                    RecipeVersion.recipe_id == recipe.id, RecipeVersion.version_number == 1
                )
            ).one()
            if first.content_hash != digest:
                report.warnings.append(
                    f"{file_name}: seed file changed since it was loaded; versions are "
                    "immutable, so the stored draft was not updated"
                )
            continue
        recipe = Recipe(
            user_id=user.id, family_id=family.id, title=seed.title, origin=RecipeOrigin.SEED.value
        )
        session.add(recipe)
        session.flush()
        version = RecipeVersion(
            recipe_id=recipe.id,
            version_number=1,
            created_by="system",
            is_draft=True,
            change_summary=f"Seed draft. {seed.draft_note}",
            title=seed.title,
            description=seed.description,
            meal_slots=[s.value for s in seed.meal_slots],
            mood=seed.mood.value,
            cuisine=seed.cuisine,
            flavor_tags=list(seed.flavor_tags),
            base_servings=seed.base_servings,
            active_minutes=seed.active_minutes,
            total_minutes=seed.total_minutes,
            equipment=[e.value for e in seed.equipment],
            freezer_friendly=seed.freezer_friendly,
            content_hash=digest,
        )
        session.add(version)
        session.flush()
        for position, line in enumerate(seed.ingredients, start=1):
            ingredient = data[line.ingredient]
            amount = parse_quantity(line.quantity)
            base = to_base(amount, line.unit, ingredient.units)
            session.add(
                RecipeIngredient(
                    recipe_version_id=version.id,
                    position=position,
                    ingredient_id=ingredient.id,
                    quantity=_q3(base.amount),
                    unit=base.unit.value,
                    authored_quantity=_q3(amount),
                    authored_unit=normalize_unit(line.unit, ingredient.units.named_units),
                    preparation=line.preparation,
                    role=line.role.value,
                    component=line.component,
                    is_optional=line.optional,
                )
            )
        for position, step in enumerate(seed.steps, start=1):
            session.add(
                RecipeStep(
                    recipe_version_id=version.id,
                    position=position,
                    section=step.section.value,
                    text=step.text,
                    duration_minutes=step.duration_minutes,
                    appliance_temp_f=step.appliance_temp_f,
                    doneness_check_ingredient_id=data[step.doneness_check_for].id
                    if step.doneness_check_for
                    else None,
                )
            )
        session.flush()
        recipe.default_version_id = version.id
        created += 1
    session.flush()
    return created


def seed_all(session: Session, data_dir: Path = DATA_DIR) -> SeedReport:
    files = load_seed_files(data_dir)
    report = SeedReport()
    user = ensure_user(session)
    _nutrients(session, files)
    stores = _stores(session, files)
    ingredients = _ingredients(session, files, report)
    report.counts["substitutions"] = _substitutions(session, files, ingredients)
    report.counts["products"], report.counts["price_observations"] = _products(
        session, files, ingredients, stores
    )
    _settings(session, files, user=user, stores=stores, ingredients=ingredients, report=report)
    report.counts["recipes_created"] = _recipes(session, files, user, report)
    report.counts["stores"] = len(stores)
    return report
