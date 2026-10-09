"""Database → PlanningProblem: hard filters keep their reasons; offers and needs share one unit per
ingredient."""

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.db.models import Ingredient
from app.domain.enums import Equipment, PlanningMode, StorageLocation
from app.domain.exclusions import Preference
from app.planning.inputs import constraints_for
from app.planning.loader import build_problem
from app.schemas.plans import PlanRequest
from app.services.inventory import LotInput, add_lot
from app.services.settings import current_user, set_preference

WEEK = date(2026, 10, 12)


def problem(session, **request):
    user = current_user(session)
    c = constraints_for(session, user.id, PlanRequest(week_start=WEEK, **request))
    return build_problem(session, user.id, c)


def slug_id(session, slug):
    return session.scalars(select(Ingredient.id).where(Ingredient.slug == slug)).one()


def test_all_ten_seed_recipes_are_candidates_by_default(seeded_db):
    p = problem(seeded_db)
    assert len(p.candidates) == 10 and p.excluded == ()
    assert all(c.is_draft and c.origin == "seed" for c in p.candidates)


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


def test_a_budget_excludes_unpriced_recipes_and_says_why(seeded_db):
    p = problem(seeded_db, budget_cents=10000)
    left_out = {e.title: e for e in p.excluded}
    for title in POWDER_RECIPES:
        assert left_out[title].unpriced_ingredients == ("protein powder, double chocolate",)
        assert "your budget can't be checked" in " ".join(left_out[title].reasons)
    assert len(p.candidates) == 7


def test_inventory_mode_excludes_unpriced_items_you_dont_have(seeded_db):
    p = problem(seeded_db, mode=PlanningMode.INVENTORY, topup_cents=2000)
    left_out = {e.title: e for e in p.excluded}
    for title in POWDER_RECIPES:
        assert "isn't in your inventory and has no price" in " ".join(left_out[title].reasons)


def test_no_budget_keeps_unpriced_recipes(seeded_db):
    p = problem(seeded_db)
    assert len(p.candidates) == 10 and p.excluded == ()


def test_raw_protein_carries_its_chart_fridge_life(seeded_db):
    p = problem(seeded_db)
    thigh = p.ingredients[slug_id(seeded_db, "chicken-thigh-boneless-skinless")]
    assert thigh.fridge_life is not None and thigh.fridge_life.days == 1 and thigh.fridge_life.freeze_raw
    assert thigh.location == "fridge"
    rice = p.ingredients[slug_id(seeded_db, "rice-long-grain-white")]
    assert rice.fridge_life is None


def test_inventory_lets_a_budget_use_an_unpriced_item(seeded_db):
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
    p = problem(seeded_db, budget_cents=10000)
    assert len(p.candidates) == 10  # the powder comes from what you have, so no price is needed
    p = problem(seeded_db, mode=PlanningMode.INVENTORY)
    assert len(p.candidates) == 10
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
    by_store = {o.store_id: o for o in chicken.offers}
    assert {o.package_cents for o in by_store.values()} == {1347, 1047}  # 3 lb at $4.49 / $3.49 per lb
    onion = p.ingredients[slug_id(seeded_db, "onion-red")]
    sheet_pan = next(c for c in p.candidates if c.title.startswith("Sheet-pan"))
    assert onion.planning_unit == "g"  # priced per pound…
    assert sheet_pan.need_per_portion[onion.id] == onion.units.count_unit_weight_g / 4  # …authored as 1 onion
    salt = p.ingredients[slug_id(seeded_db, "salt")]
    assert salt.staple and salt.id not in sheet_pan.need_per_portion
