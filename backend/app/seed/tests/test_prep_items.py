"""The draft prep items and assemblies (step 2b.10, FLOW_SPEC §19.6, AC 1-4): each item split from a seed
along its components, its steps staged and tagged; every item's storage per stage as the §19.4 table says;
every seed assembly named, with its instruction; an assembly's numbers its items' portions plus its add-ons,
to the kcal and the cent; every dish a one-item assembly; and dish plans and meal-now untouched (they never
see items or assemblies)."""

import json
from decimal import ROUND_HALF_UP, Decimal

import pytest
from sqlalchemy import select

from app.db.models import AssemblyComponent, Recipe, RecipeStep, RecipeVersion
from app.domain.cook_schedule import StepTiming, dish_alone, timing_from_steps
from app.domain.enums import PrepState, RecipeKind
from app.domain.prep_storage import StorageLine, prep_storage
from app.planning.assemblies import default_item, item_portion, load_assembly, one_item_assembly
from app.planning.loader import candidate_versions
from app.schemas.seed import SeedPrepItem
from app.seed.files import DATA_DIR, load_seed_files
from app.services.calculations import calculate
from app.services.pricing import active_stores
from app.services.recipes import version_lines
from app.services.settings import current_user

FILES = load_seed_files()
ITEMS = FILES.prep_items
ASSEMBLIES = FILES.assemblies
SEEDS = {name.split("_")[0]: seed for name, seed in FILES.recipes}
TOLERANCE = 5
FRESH = "fresh"

# FLOW_SPEC §19.4, per item and stage (your 3-day leftover setting): days in the fridge (FRESH = made on the
# eating day), and whether it may go to the freezer
STORAGE = {
    "Spiced seared chicken thighs": [(1, True), (3, True)],
    "Broth rice": [(3, True)],
    "Plain rice": [(3, True)],
    "Air-fryer chicken breast": [(1, True), (3, True)],
    "Air-fryer broccoli": [(3, True)],
    "Sheet-pan chicken and peppers": [(1, True), (3, True)],
    "Chicken curry": [(3, True)],
    "Chicken and spinach curry": [(3, True)],
    "Chicken tikka": [(1, True), (3, True)],
    "Tandoori drumsticks": [(1, True), (3, True)],
    "Chicken, broccoli and pepper stir-fry": [(3, True)],
    "Roast bone-in chicken breasts": [(1, True), (3, True)],
    "Quinoa": [(3, True)],
    "Roasted asparagus": [(3, False)],  # doesn't freeze well
    "Roasted root vegetables": [(3, True)],
    "Dal tadka": [(3, True)],
    "Black beans and corn": [(3, True)],
    "Garlic yogurt sauce": [(FRESH, False)],
    "Cucumber raita": [(FRESH, False)],
    "Chopped salad": [(FRESH, False)],
}
NAMES = {  # the composed names (an assembly with its own title keeps it)
    "a01_spiced_chicken_broth_rice.json": "Spiced chicken over broth rice with garlic yogurt sauce",
    "a02_spiced_chicken_wrap.json": "Spiced chicken wrap with chopped salad and garlic yogurt sauce",
    "a03_chicken_curry_rice.json": "Chicken curry with rice",
    "a04_chicken_curry_tortillas.json": "Chicken curry with flour tortillas",
    "a05_chicken_tikka_rice_raita.json": "Chicken tikka over rice with raita",
    "a06_tandoori_drumsticks_rice_raita.json": "Tandoori drumsticks over rice with raita",
    "a07_dal_rice.json": "Dal with rice",
    "a08_air_fryer_chicken_quinoa_broccoli.json": "Air-fryer chicken over quinoa with roasted broccoli",
    "a09_chicken_burrito_bowl.json": "Chicken burrito bowl",
    "a10_chicken_peppers_wrap.json": "Roasted chicken and peppers wrap with salsa and romaine lettuce",
    "a11_roast_chicken_root_vegetables.json": "Roast chicken breast with roasted root vegetables",
    "a12_chicken_stir_fry_rice.json": "Chicken stir-fry with rice",
}


def _timing(item: SeedPrepItem):
    return timing_from_steps(
        [
            StepTiming(
                s.section.value,
                s.duration_minutes,
                s.appliance_temp_f,
                s.component,
                s.equipment.value if s.equipment else None,
                s.hands_on_minutes,
                s.hands_off_minutes,
            )
            for s in item.steps
        ],
        active_minutes=item.active_minutes,
        total_minutes=item.total_minutes,
        equipment=[e.value for e in item.equipment],
    )


def test_16_to_20_prep_items_and_about_10_assemblies():
    assert 16 <= len(ITEMS) <= 20
    assert 8 <= len(ASSEMBLIES) <= 14
    assert set(STORAGE) == {item.title for _, item in ITEMS}
    assert set(NAMES) == {name for name, _ in ASSEMBLIES}


@pytest.mark.parametrize(("name", "item"), ITEMS, ids=[n for n, _ in ITEMS])
def test_each_item_is_split_from_its_seed(name, item):
    seed = SEEDS[item.split_from]
    assert item.family == seed.family
    assert item.split_from in item.draft_note and seed.title in item.draft_note
    assert seed.ingredients, name
    # its protein is the seed's own (no cut swapped on the way)
    seed_slugs = {line.ingredient for line in seed.ingredients}
    assert {ln.ingredient for ln in item.ingredients if ln.role.value == "protein"} <= seed_slugs


@pytest.mark.parametrize(("name", "item"), ITEMS, ids=[n for n, _ in ITEMS])
def test_each_items_steps_are_tagged_and_its_times_are_its_own_schedule(name, item):
    timing = _timing(item)
    assert not timing.estimated
    assert abs(timing.hands_on - item.active_minutes) <= TOLERANCE
    schedule = dish_alone(timing, item.base_servings, item.base_servings)
    assert abs(schedule.ready - item.total_minutes) <= TOLERANCE


def test_no_item_or_add_on_uses_beef_held_items_or_a_pork_component():
    data = json.loads((DATA_DIR / "ingredients.json").read_text(encoding="utf-8"))
    tags = {i["slug"]: set(i.get("diet_tags", [])) for i in data["ingredients"]}
    forbidden = {"beef", "possible_beef", "pork"}
    for name, item in ITEMS:
        assert not any(tags[ln.ingredient] & forbidden for ln in item.ingredients), name
    for name, assembly in ASSEMBLIES:
        assert not any(tags[ln.ingredient] & forbidden for ln in assembly.add_ons), name


# ---------------- loaded ----------------
def _versions(session, kind: RecipeKind) -> list[tuple[RecipeVersion, Recipe]]:
    user = current_user(session)
    return [
        (v, r)
        for v, r in session.execute(
            select(RecipeVersion, Recipe)
            .join(Recipe, Recipe.default_version_id == RecipeVersion.id)
            .where(Recipe.user_id == user.id, Recipe.origin == "seed", RecipeVersion.kind == kind.value)
            .order_by(Recipe.id)
        ).tuples()
    ]


def test_the_loader_stores_kind_stages_label_and_each_steps_stage(seeded_db):
    versions = _versions(seeded_db, RecipeKind.PREP_ITEM)
    assert len(versions) == len(ITEMS)
    by_title = {item.title: item for _, item in ITEMS}
    for version, _ in versions:
        seed = by_title[version.title]
        assert version.is_draft and version.label == seed.label
        assert version.pairs_with == [p.value for p in seed.pairs_with]
        assert version.stages == [
            {"n": n, "state": s.state.value} for n, s in enumerate(seed.stages, start=1)
        ]
        stages = list(
            seeded_db.scalars(
                select(RecipeStep.stage)
                .where(RecipeStep.recipe_version_id == version.id)
                .order_by(RecipeStep.position)
            )
        )
        assert stages == [s.stage for s in seed.steps]


def test_every_items_storage_per_stage_matches_the_table(seeded_db):
    for version, recipe in _versions(seeded_db, RecipeKind.PREP_ITEM):
        item = item_portion(seeded_db, version, recipe, leftover_fridge_days=3)
        got = [(FRESH if s.made_on_the_day else s.fridge_days, s.freezer) for s in item.storage]
        assert got == STORAGE[version.title], version.title
        for s in item.storage:
            assert s.made_on_the_day or s.sources, version.title  # every stored window cites its row


def test_no_partly_cooked_protein_can_be_stored(seeded_db):
    for version, recipe in _versions(seeded_db, RecipeKind.PREP_ITEM):
        item = item_portion(seeded_db, version, recipe, leftover_fridge_days=3)
        protein = any(ln.ingredient.safety_category is not None for ln in item.lines)
        for state, storage in zip(item.states, item.storage, strict=True):
            if state is PrepState.PARTLY_COOKED and protein:
                assert not storage.stored
        # and in the rules themselves, for every item with meat, poultry, fish or eggs
        if protein:
            lines = [
                StorageLine(
                    ln.ingredient.slug,
                    ln.ingredient.safety_category.value if ln.ingredient.safety_category else None,
                    frozenset(ln.ingredient.tagged.diet_tags),
                    ln.role,
                )
                for ln in item.lines
            ]
            assert not prep_storage(
                lines, PrepState.PARTLY_COOKED, freezes_well=True, leftover_fridge_days=3
            ).stored


def test_every_seed_assembly_has_its_name_and_instruction(seeded_db):
    user = current_user(seeded_db)
    versions = _versions(seeded_db, RecipeKind.ASSEMBLY)
    assert {v.title for v, _ in versions} == set(NAMES.values())
    for version, _ in versions:
        assembly = load_assembly(seeded_db, user.id, version, leftover_fridge_days=3)
        assert assembly.name == version.title
        assert assembly.instruction
        for part in assembly.parts:
            assert part.item.label in assembly.instruction
            if part.item.fresh:
                assert f"Make the {part.item.label} fresh" in assembly.instruction
        if any(not p.item.fresh and not p.item.served_cold for p in assembly.parts):
            assert "to 165°F" in assembly.instruction  # every reheat says to 165°F
        components = seeded_db.scalars(
            select(AssemblyComponent).where(AssemblyComponent.assembly_version_id == version.id)
        ).all()
        assert len(components) == len(assembly.parts)


def _kcal(value: Decimal) -> int:
    return int(value.quantize(Decimal(1), ROUND_HALF_UP))


def test_an_assemblys_numbers_are_its_items_portions_plus_its_add_ons(client, seeded_db):
    user = current_user(seeded_db)
    for version, _ in _versions(seeded_db, RecipeKind.ASSEMBLY):
        page = client.get(f"/api/v1/recipe-versions/{version.id}").json()
        assert page["kind"] == "assembly" and page["assembly"]["name"] == version.title
        kcal = Decimal(0)
        cents: dict[int, int] = {}
        for entry in page["assembly"]["items"]:
            item_page = client.get(f"/api/v1/recipe-versions/{entry['version_id']}?portions=1").json()
            item = seeded_db.get(RecipeVersion, entry["version_id"])
            exact = calculate(seeded_db, version_lines(seeded_db, item.id), item.base_servings)
            portions = Decimal(entry["portions"])
            kcal += portions * exact.per_portion.amounts["energy_kcal"]
            for cost in exact.costs:
                cents[cost.store_id] = cents.get(cost.store_id, 0) + _kcal(portions * cost.per_portion_cents)
            assert item_page["kind"] in ("prep_item", "dish")
        add_lines = version_lines(seeded_db, version.id)
        if add_lines:
            add = calculate(seeded_db, add_lines, 1)
            kcal += add.per_portion.amounts["energy_kcal"]
            for cost in add.costs:
                cents[cost.store_id] += cost.per_portion_cents
        assert page["per_portion"]["kcal"] == _kcal(kcal), version.title  # to the kcal
        assert {c["store_id"]: c["per_portion_cents"] for c in page["costs"]} == cents, version.title  # cent
        assert load_assembly(seeded_db, user.id, version, leftover_fridge_days=3).kcal == _kcal(kcal)


def test_a_prep_items_page_shows_its_stages_and_storage(client, seeded_db):
    vid = seeded_db.scalars(
        select(Recipe.default_version_id).where(Recipe.title == "Tandoori drumsticks")
    ).one()
    page = client.get(f"/api/v1/recipe-versions/{vid}").json()
    assert page["kind"] == "prep_item" and page["assembly"] is None
    prep = page["prep"]
    assert (prep["label"], prep["brings"]) == ("tandoori drumsticks", "protein")
    assert [(s["n"], s["state"]) for s in prep["stages"]] == [(1, "marinated"), (2, "cooked")]
    marinated, cooked = (s["storage"] for s in prep["stages"])
    assert (marinated["fridge_days"], marinated["freezer"]) == (1, True)
    assert marinated["sources"] == [
        "FoodSafety.gov Cold Food Storage Chart: Fresh poultry, chicken or turkey, pieces (1 to 2 days; "
        "9 months)"
    ]
    assert (cooked["fridge_days"], cooked["freezer"]) == (3, True)
    assert {s["stage"] for s in page["steps"]} == {1, 2}
    storage_lines = [s["text"] for s in page["steps"] if s["section"] == "storage" and s["added_by_app"]]
    assert storage_lines == [cooked["note"]]  # its own storage text, from the table


def test_a_fresh_items_page_says_it_is_made_on_the_day(client, seeded_db):
    vid = seeded_db.scalars(select(Recipe.default_version_id).where(Recipe.title == "Cucumber raita")).one()
    page = client.get(f"/api/v1/recipe-versions/{vid}").json()
    (stage,) = page["prep"]["stages"]
    assert stage["storage"]["made_on_the_day"] and stage["storage"]["sources"] == []
    assert not any(s["section"] == "reheating" for s in page["steps"])


def test_every_dish_is_a_one_item_assembly(seeded_db):
    user = current_user(seeded_db)
    stores = active_stores(seeded_db, "grocery")
    dishes = _versions(seeded_db, RecipeKind.DISH)
    assert len(dishes) == len(FILES.recipes)
    for version, recipe in dishes:
        item = default_item(seeded_db, user.id, recipe.id, leftover_fridge_days=3)
        assembly = one_item_assembly(item, stores)
        assert assembly.name == version.title
        assert assembly.kcal == _kcal(item.per_portion.amounts["energy_kcal"])
        assert [c.per_portion_cents for c in assembly.costs] == [
            c.per_portion_cents for c in item.calculation.costs
        ]
        # stored as every dish is today: your leftover days, frozen when it freezes well
        (storage,) = item.storage
        assert (storage.fridge_days, storage.freezer) == (3, version.freezer_friendly)
        if item.served_cold:
            assert assembly.instruction.startswith("Serve 1 portion") and "165" not in assembly.instruction
        else:
            assert assembly.instruction == f"Reheat 1 portion {item.label} to 165°F."


def test_dish_plans_and_meal_now_never_see_items_or_assemblies(seeded_db):
    user = current_user(seeded_db)
    kinds = {v.kind for _, v in candidate_versions(seeded_db, user.id)}
    assert kinds == {"dish"}
