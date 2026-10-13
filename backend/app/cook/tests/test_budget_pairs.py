"""Classic and budget ingredients (the 2b.6 approval, item 4): the seed pairs, which side each tier cooks with
by your stores' real stored prices, a plan that cooks with a budget side (its batch page and its check), and
fixing a line to one side for a recipe (your own version)."""

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cook.tests.test_meal_prep_api import meal_prep, plan_of
from app.db.models import Ingredient, MealPlan, PlanBatchIngredient, Recipe, RecipeIngredient, RecipeVersion
from app.domain.price_tiers import PriceTier
from app.planning.budget_lines import BETTER_KEEPS_CLASSIC, line_cents
from app.planning.inputs import constraints_for
from app.planning.loader import build_problem
from app.planning.problem import PlanningProblem, RecipeLine
from app.schemas.plans import PlanRequest
from app.schemas.recipes import BudgetLine
from app.seed.files import load_seed_files
from app.services.settings import current_user

CURRY = "Everyday chicken curry gravy"  # 3 fresh tomatoes; canned diced tomatoes as its budget equivalent
SHAKSHUKA = "Shakshuka with warm tortillas"  # canned tomatoes; fresh as its "budget" one (it isn't cheaper)


def slugs(session: Session) -> dict[int, str]:
    return dict(session.execute(select(Ingredient.id, Ingredient.slug)).tuples().all())


def problem(session: Session, tier: PriceTier | None) -> PlanningProblem:
    user = current_user(session)
    request = PlanRequest(week_start="2026-10-14", days=3, price_tier=tier, allow_llm=False)
    return build_problem(session, user.id, constraints_for(session, user.id, request))


def tomato_line(p: PlanningProblem, title: str, classic: str, session: Session) -> RecipeLine:
    by_slug = {v: k for k, v in slugs(session).items()}
    recipe = next(r for r in p.candidates if r.title == title)
    return next(ln for ln in recipe.lines if by_slug[classic] in (ln.ingredient_id, ln.classic_ingredient_id))


def test_every_seed_pair_is_one_role_never_a_protein_and_priced_on_both_sides(seeded_db: Session) -> None:
    rows = {i.slug: i for i in seeded_db.scalars(select(Ingredient))}
    p = problem(seeded_db, None)
    pairs = 0
    for _, seed in load_seed_files().recipes:
        for line in seed.ingredients:
            if line.budget is None:
                continue
            pairs += 1
            classic, budget = rows[line.ingredient], rows[line.budget.ingredient]
            assert classic.category == budget.category != "protein", (seed.title, line.ingredient)
            for side in (classic, budget):
                plan = p.ingredients.get(side.id)
                if plan is not None:  # in a candidate this week
                    assert plan.offers, (seed.title, side.slug)  # compared on real stored prices
    assert pairs >= 15


def test_each_tier_cooks_the_side_its_rule_picks_by_your_stores_prices(seeded_db: Session) -> None:
    names = slugs(seeded_db)
    picked: dict[PriceTier | None, str | None] = {}
    for tier in (None, *PriceTier):
        p = problem(seeded_db, tier)
        if not any(r.title == CURRY for r in p.candidates):
            picked[tier] = None  # the tier can't make it at all
            continue
        line = tomato_line(p, CURRY, "tomato", seeded_db)
        picked[tier] = names[line.ingredient_id]
    # no tier and Fancy: the classic; Broke: canned (fresh tomatoes aren't a staple); Cheapest: the cheaper
    # one
    assert picked[None] == picked[PriceTier.FANCY] == "tomato"
    assert picked[PriceTier.BROKE] == picked[PriceTier.CHEAPEST] == "tomatoes-canned"
    # A bit better keeps the classic unless the budget one saves more than 25 cents a portion
    p = problem(seeded_db, PriceTier.BETTER)
    classic = next(r for r in p.candidates if r.title == CURRY)
    raw = seeded_db.scalars(  # its one line with a pair
        select(RecipeIngredient).where(
            RecipeIngredient.recipe_version_id == classic.version_id, RecipeIngredient.budget.is_not(None)
        )
    ).one()
    alt = BudgetLine.model_validate(raw.budget)
    fresh = line_cents(p.ingredients, raw.ingredient_id, raw.quantity, raw.unit)
    canned = line_cents(p.ingredients, alt.ingredient_id, alt.quantity, alt.unit)
    assert fresh is not None and canned is not None  # both priced at your stores
    saving = (fresh - canned) / classic.base_servings
    assert picked[PriceTier.BETTER] == ("tomatoes-canned" if saving > BETTER_KEEPS_CLASSIC else "tomato")
    # whichever is actually cheaper: the shakshuka's canned tomatoes are, so even Broke keeps them
    for tier in (PriceTier.BROKE, PriceTier.CHEAPEST):
        p = problem(seeded_db, tier)
        if any(r.title == SHAKSHUKA for r in p.candidates):
            assert (
                names[tomato_line(p, SHAKSHUKA, "tomatoes-canned", seeded_db).ingredient_id]
                == "tomatoes-canned"
            )


def test_a_broke_plan_cooks_with_budget_sides_and_its_batch_page_says_the_classic(
    api: Any, seeded_db: Session
) -> None:
    prep = {
        "shape": "days",
        "day_count": 3,
        "slots": ["lunch", "dinner"],
        "start": "today",
        "cook_style": "mix",
    }
    plan = plan_of(meal_prep(api, prep=prep, shopping="make_a_list", price_tier="broke"))
    row = seeded_db.get(MealPlan, plan["id"])
    assert row is not None and row.validation_report["ok"] is True  # either side of a pair passes the check
    lines = {r.id: r for r in seeded_db.scalars(select(RecipeIngredient))}
    names = slugs(seeded_db)
    swapped = []
    for batch in plan["batches"]:
        for item in seeded_db.scalars(
            select(PlanBatchIngredient).where(PlanBatchIngredient.cook_batch_id == batch["id"])
        ):
            source = lines.get(item.recipe_ingredient_id or 0)
            if source is not None and source.ingredient_id != item.ingredient_id:
                assert source.budget is not None and source.budget["ingredient_id"] == item.ingredient_id
                swapped.append((batch["id"], names[source.ingredient_id], names[item.ingredient_id]))
    assert swapped, "Broke's week cooks at least one line with its budget equivalent"
    batch_id, classic, _budget = swapped[0]
    page = api.get(f"/api/v1/cook-batches/{batch_id}").json()
    classic_name = seeded_db.scalars(select(Ingredient.name).where(Ingredient.slug == classic)).one()
    shown = [ln["name"] for ln in page["lines"]]
    assert any(name.endswith(f"(classic: {classic_name})") for name in shown), shown


def test_fixing_a_line_to_one_side_is_your_version_and_every_tier_keeps_it(
    api: Any, seeded_db: Session
) -> None:
    version = seeded_db.scalars(
        select(RecipeVersion)
        .join(Recipe, Recipe.default_version_id == RecipeVersion.id)
        .where(Recipe.title == CURRY, RecipeVersion.kind == "dish")
    ).one()
    line = seeded_db.scalars(
        select(RecipeIngredient).where(
            RecipeIngredient.recipe_version_id == version.id, RecipeIngredient.budget.is_not(None)
        )
    ).one()
    options = api.get(f"/api/v1/recipe-versions/{version.id}/lines/{line.id}/options").json()
    assert options["pair"]["classic"] == "tomato" and options["pair"]["budget_display"].startswith("360 ml")
    reply = api.post(
        f"/api/v1/recipe-versions/{version.id}/edits", json={"line_id": line.id, "action": "use_budget"}
    )
    assert reply.status_code == 200, reply.text
    mine = reply.json()["version"]
    assert mine["your_version"] is True and "always" in reply.json()["note"]
    fixed = seeded_db.scalars(
        select(RecipeIngredient).where(
            RecipeIngredient.recipe_version_id == mine["version_id"],
            RecipeIngredient.position == line.position,
        )
    ).one()
    canned = seeded_db.scalars(select(Ingredient.id).where(Ingredient.slug == "tomatoes-canned")).one()
    assert fixed.ingredient_id == canned and fixed.budget is None and fixed.quantity == Decimal("360.000")
    # every tier cooks your version with canned tomatoes now, Fancy included
    p = problem(seeded_db, PriceTier.FANCY)
    recipe = next(r for r in p.candidates if r.title == CURRY)
    assert recipe.version_id == mine["version_id"]
    assert canned in {ln.ingredient_id for ln in recipe.lines}
    again = api.post(
        f"/api/v1/recipe-versions/{mine['version_id']}/edits",
        json={"line_id": fixed.id, "action": "use_classic"},
    )
    assert again.status_code == 422  # a fixed line has no pair left to choose from
