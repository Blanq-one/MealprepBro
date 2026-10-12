"""Database → PlanningProblem: hard filters keep their reasons; offers and needs share one unit per
ingredient."""

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select, update

from app.db.models import Ingredient, Product, RecipeVersion
from app.domain.enums import Equipment, PlanningMode, StorageLocation
from app.domain.exclusions import Preference
from app.planning.inputs import constraints_for
from app.planning.loader import build_problem
from app.schemas.plans import PlanRequest
from app.services.ingredient_data import load_ingredients
from app.services.inventory import LotInput, add_lot
from app.services.settings import current_user, set_preference

WEEK = date(2026, 10, 12)


def problem(session, **request):
    user = current_user(session)
    c = constraints_for(session, user.id, PlanRequest(week_start=WEEK, **request))
    return build_problem(session, user.id, c)


def slug_id(session, slug):
    return session.scalars(select(Ingredient.id).where(Ingredient.slug == slug)).one()


SEED_RECIPES = 47  # 10, plus the 37 drafts of the step 2b.4 approval (M13)


def test_every_seed_recipe_is_a_candidate_unless_this_weeks_cook_days_are_too_short(seeded_db):
    p = problem(seeded_db)
    week = {t.slot.value for t in p.constraints.slot_targets}
    versions = seeded_db.scalars(select(RecipeVersion).where(RecipeVersion.kind == "dish")).all()
    assert len(versions) == SEED_RECIPES  # prep items and assemblies (step 2b.10) are smart prep's
    for_this_week = [v for v in versions if week & set(v.meal_slots)]  # snack-only recipes have no meal here
    assert len(p.candidates) + len(p.excluded) == len(for_this_week) < SEED_RECIPES
    assert all(c.is_draft and c.origin == "seed" for c in p.candidates)
    # the default cook days have no fancy day, so the fancy drafts wait for one; nothing else is left out
    assert p.excluded and all(e.codes == ("time",) for e in p.excluded)
    assert set(POWDER_RECIPES) | set(YOGURT_RECIPES) <= {c.title for c in p.candidates}


def test_missing_equipment_keeps_its_reason(seeded_db):
    user = current_user(seeded_db)
    c = constraints_for(seeded_db, user.id, PlanRequest(week_start=WEEK))
    c = c.model_copy(update={"equipment": frozenset({Equipment.STOVETOP})})
    p = build_problem(seeded_db, user.id, c)
    reasons = {e.title: e.reasons for e in p.excluded}
    assert "needs equipment you don't have: air_fryer" in reasons["Air-fryer chicken over rice with broccoli"]
    assert "needs equipment you don't have: oven" in reasons["Sheet-pan chicken and peppers over rice"]


POWDER_RECIPES = (
    "Double chocolate protein pudding",
    "Chocolate protein overnight oats",
    "Chocolate protein chia pudding",
)
YOGURT_RECIPES = (
    "Chicken over rice with garlic yogurt sauce",
    "Air-fryer chicken over rice with broccoli",
    "Sheet-pan chicken and peppers over rice",
    "Yogurt chicken gravy",
    "Double chocolate protein pudding",
    "Chocolate protein overnight oats",
)


def unprice(session, slug):
    """No current price at any store: archive the ingredient's products (rolled back with the test)."""
    session.execute(
        update(Product)
        .where(Product.ingredient_id == slug_id(session, slug))
        .values(archived_at=datetime.now(UTC))
    )
    session.flush()


def by_default(session):
    """The default week's candidates and what it leaves out for its cook days."""
    base = problem(session)
    return base.candidates, {e.title for e in base.excluded}


def test_a_budget_excludes_recipes_with_an_unpriced_regular_item_and_says_why(seeded_db):
    candidates, too_long = by_default(seeded_db)
    yogurt = slug_id(seeded_db, "greek-yogurt-nonfat")
    with_yogurt = {c.title for c in candidates if yogurt in c.ingredient_ids}
    unprice(seeded_db, "greek-yogurt-nonfat")
    p = problem(seeded_db, budget_cents=10000)
    left_out = {e.title: e for e in p.excluded if e.title not in too_long}
    assert set(left_out) == with_yogurt and set(YOGURT_RECIPES) <= with_yogurt
    for title in with_yogurt:
        assert left_out[title].unpriced_ingredients == ("Greek yogurt, plain nonfat",)
        assert "your budget can't be checked" in " ".join(left_out[title].reasons)


def test_an_unpriced_stock_up_item_doesnt_block_a_budget(seeded_db):
    candidates, too_long = by_default(seeded_db)
    unprice(seeded_db, "protein-powder-double-chocolate")
    p = problem(seeded_db, budget_cents=10000)  # the budget covers regular groceries only
    assert len(p.candidates) == len(candidates) and {e.title for e in p.excluded} == too_long


def test_inventory_mode_excludes_unpriced_items_you_dont_have(seeded_db):
    unprice(seeded_db, "protein-powder-double-chocolate")
    p = problem(seeded_db, mode=PlanningMode.INVENTORY, topup_cents=2000)  # a top-up covers everything
    left_out = {e.title: e for e in p.excluded}
    for title in POWDER_RECIPES:
        assert "isn't in your inventory and has no price" in " ".join(left_out[title].reasons)


def test_no_budget_keeps_unpriced_recipes(seeded_db):
    candidates, too_long = by_default(seeded_db)
    unprice(seeded_db, "greek-yogurt-nonfat")
    p = problem(seeded_db)
    assert len(p.candidates) == len(candidates) and {e.title for e in p.excluded} == too_long


def test_raw_protein_carries_its_chart_fridge_life(seeded_db):
    p = problem(seeded_db)
    thigh = p.ingredients[slug_id(seeded_db, "chicken-thigh-boneless-skinless")]
    assert thigh.fridge_life is not None and thigh.fridge_life.days == 1 and thigh.fridge_life.freeze_raw
    assert thigh.location == "fridge"
    rice = p.ingredients[slug_id(seeded_db, "rice-long-grain-white")]
    assert rice.fridge_life is None


def test_inventory_lets_a_top_up_use_an_unpriced_item(seeded_db):
    unprice(seeded_db, "protein-powder-double-chocolate")
    user = current_user(seeded_db)
    add_lot(
        seeded_db,
        user.id,
        LotInput(
            slug_id(seeded_db, "protein-powder-double-chocolate"),
            Decimal(10),
            "scoop",
            StorageLocation.PANTRY,
        ),
    )
    p = problem(seeded_db, mode=PlanningMode.INVENTORY)
    # the powder comes from what you have, so no price is needed
    assert set(POWDER_RECIPES) <= {c.title for c in p.candidates}
    lot = p.ingredients[slug_id(seeded_db, "protein-powder-double-chocolate")].lots[0]
    assert lot.location == "pantry"


def test_allowing_a_held_item_is_reflected_in_reasons(seeded_db):
    user = current_user(seeded_db)
    gelatin = slug_id(seeded_db, "gelatin-unflavored")
    p = problem(seeded_db)
    assert gelatin in p.constraints.held_ingredient_ids
    set_preference(seeded_db, user.id, gelatin, Preference.ALLOW)
    assert gelatin not in problem(seeded_db).constraints.held_ingredient_ids


def test_offers_and_needs_share_one_unit(seeded_db):
    p = problem(seeded_db)
    chicken = p.ingredients[slug_id(seeded_db, "chicken-thigh-boneless-skinless")]
    assert chicken.planning_unit == "g"
    family = {o.package_cents for o in chicken.offers if o.package_amount and o.package_amount > 1000}
    assert family == {1347, 1047}  # 3 lb at $4.49 / $3.49 per lb
    onion = p.ingredients[slug_id(seeded_db, "onion-red")]
    sheet_pan = next(c for c in p.candidates if c.title.startswith("Sheet-pan"))
    assert onion.planning_unit == "g"  # priced per pound…
    assert sheet_pan.need_per_portion[onion.id] == onion.units.count_unit_weight_g / 4  # …authored as 1 onion
    salt = p.ingredients[slug_id(seeded_db, "salt")]
    assert salt.staple and salt.id not in sheet_pan.need_per_portion


def test_other_stores_come_after_your_store_order(seeded_db):
    p = problem(seeded_db)
    assert [p.store_names[i] for i in p.constraints.store_ids] == ["Stop & Shop", "Price Rite", "Other"]


def test_protein_powder_is_priced_at_other_as_estimates_and_is_stock_up(seeded_db):
    p = problem(seeded_db)
    powder = p.ingredients[slug_id(seeded_db, "protein-powder-double-chocolate")]
    assert powder.stock_up and not powder.perishable
    assert {p.store_names[o.store_id] for o in powder.offers} == {"Other"}
    assert all(o.is_estimate for o in powder.offers)
    tubs = sorted((o.package_amount, o.package_cents) for o in powder.offers)
    assert tubs == [(Decimal("682.000"), 2631), (Decimal("2268.000"), 6250)]  # small tub: +40% per gram
    big = max(powder.offers, key=lambda o: o.package_amount or 0)
    assert (big.cents_per_unit * 31).quantize(Decimal("0.1")) == Decimal("85.4")  # about $0.85 a scoop


def test_chicken_comes_in_family_and_regular_packs_at_both_stores(seeded_db):
    p = problem(seeded_db)
    for slug in ("chicken-thigh-boneless-skinless", "chicken-breast-boneless-skinless"):
        chicken = p.ingredients[slug_id(seeded_db, slug)]
        for store_id in (1, 2):
            packs = sorted(
                (o for o in chicken.offers if o.store_id == store_id), key=lambda o: o.package_amount or 0
            )
            regular, family = packs
            assert regular.package_amount.quantize(Decimal(1)) == 567  # 1.25 lb
            assert family.package_amount.quantize(Decimal(1)) == 1361  # 3 lb
            premium = regular.cents_per_unit / family.cents_per_unit
            assert Decimal("1.19") < premium < Decimal("1.21") and regular.is_estimate


def test_shelf_life_fixes_for_bottled_and_frozen_items(seeded_db):
    p = problem(seeded_db)
    data = {d.slug: d for d in load_ingredients(seeded_db).values()}
    for slug in ("lemon-juice", "lime-juice", "spinach-frozen", "peas-frozen", "corn-frozen", "edamame"):
        assert not data[slug].is_perishable, slug
    assert data["lemon"].is_perishable  # fresh lemons stay perishable
    assert data["lemon-juice"].stock_up and data["rice-long-grain-white"].stock_up
    assert data["cumin-ground"].stock_up and data["cumin-ground"].assume_in_stock  # still "check you have"
    assert not data["chicken-thigh-boneless-skinless"].stock_up
    assert p.candidates  # the week still plans
