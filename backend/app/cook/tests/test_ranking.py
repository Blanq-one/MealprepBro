"""The meal-now ranking (FLOW_SPEC §14), step 2b.3a: the score components and their weights, the hard filters,
the never-favored rule (AC 2), the per-meal protein cap (E11), the sort and the gap rule (AC 4). Pure tests on
hand-built candidates, then golden orderings, the calendar-week pork cap and more than one person on the seed
library."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select

from app.cook.answers import MealNowQuery, NutritionTerm
from app.cook.caps import meals_this_week, week_of
from app.cook.coverage import LineCoverage, NeedLine, Purchase, Status
from app.cook.ranking import RankInput, Rules, empty_reason, good_matches, ideas_needed, rank, top_filter
from app.cook.substitutes import Substitute
from app.cook.tests.conftest import ZONE, add_recipe, add_stock, final, meal_now, results, titles
from app.db.models import Ingredient, MealPlan, PlanCandidate, PlanCookBatch, PlanMeal, RecipeStep
from app.domain.enums import Equipment, MealSlot, PortionSize, RecipeMood, StorageLocation
from app.domain.frequency_caps import ResolvedCap
from app.schemas.cook import GoalTile
from app.services.settings import current_user

TODAY = date(2026, 10, 14)
STOVE = frozenset({Equipment.STOVETOP, Equipment.OVEN})


def query(**overrides: Any) -> MealNowQuery:
    base: dict[str, Any] = {
        "today": TODAY,
        "slot": MealSlot.DINNER,
        "people": 1,
        "mood": RecipeMood.MEDIUM,
        "portion_size": PortionSize.NORMAL,
        "nutrition": (),
        "cheap": False,
        "quick_minutes": None,
        "low_calorie": False,
        "kcal_target": None,
        "protein_cap_g": Decimal(1000),
        "toggled_off": frozenset(),
        "have": frozenset(),
        "have_amounts": {},
        "could_buy": frozenset(),
        "store_order": ("Stop & Shop",),
        "goals": (),
    }
    return MealNowQuery(**{**base, **overrides})


def need(i: int, role: str = "other", **kwargs: Any) -> NeedLine:
    base: dict[str, Any] = {
        "ingredient_id": i,
        "name": f"item {i}",
        "role": role,
        "category": "vegetable",
        "quantity": Decimal(100),
        "planning_unit": "g",
        "grams": Decimal(100),
        "count": None,
        "protein_g": Decimal(5),
        "kcal": Decimal(50),
    }
    return NeedLine(**{**base, **kwargs})


def have(i: int, role: str = "other", soon: bool = False) -> LineCoverage:
    return LineCoverage(need(i, role), Status.HAVE, uses_soon=soon)


def missing(i: int, role: str = "other", cents: int | None = 100, sub: bool = False) -> LineCoverage:
    substitute = Substitute(900 + i, "stand-in", Decimal(1), "count", "1", "pantry") if sub else None
    buy = Purchase(cents, 1, "Stop & Shop", False) if cents is not None and not sub else None
    return LineCoverage(need(i, role), Status.MISSING, Decimal(100), purchase=buy, substitute=substitute)


def candidate(version_id: int, coverage: tuple[LineCoverage, ...] = (), **kwargs: Any) -> RankInput:
    base: dict[str, Any] = {
        "version_id": version_id,
        "recipe_id": version_id,
        "title": f"recipe {version_id}",
        "mood": RecipeMood.MEDIUM,
        "equipment": frozenset({Equipment.STOVETOP}),
        "total_minutes": 30,
        "ingredient_ids": frozenset(c.line.ingredient_id for c in coverage),
        "nutrition_complete": True,
        "per_portion": {"energy_kcal": Decimal(600), "protein_g": Decimal(40), "carbohydrate_g": Decimal(60)},
        "heme_mg": Decimal(0),
        "cost_per_portion_cents": 250,
        "coverage": coverage,
    }
    return RankInput(**{**base, **kwargs})


def ranked(cands: list[RankInput], q: MealNowQuery | None = None, rules: Rules | None = None, empty=False):
    out, filtered = rank(cands, q or query(), rules or Rules(equipment=STOVE), {}, pantry_empty=empty)
    return out, filtered


# ---------------- components ----------------
def test_pantry_fit_use_up_missing_and_could_buy_components():
    coverage = (
        have(1, "protein", soon=True),
        LineCoverage(
            need(2, "carb"), Status.SHORT, Decimal(50), purchase=Purchase(300, 1, "Stop & Shop", False)
        ),
        missing(3, "vegetable", sub=True),
        missing(4, "sauce", cents=200),
        LineCoverage(
            need(5), Status.COULD_BUY, Decimal(100), purchase=Purchase(129, 1, "Stop & Shop", False)
        ),
        LineCoverage(need(6, owned=True), Status.OWNED),
        LineCoverage(need(7, optional=True), Status.OPTIONAL),
    )
    (r,), _ = ranked([candidate(1, coverage)])
    c = r.components
    assert c["pantry_fit"] == Decimal("0.3000")  # (1 have + ½ short) of 5 counted lines
    assert c["use_up"] == Decimal("0.5000")
    assert c["missing"] == Decimal("-0.8000")  # −0.6 without a substitute, −0.2 with one
    assert c["could_buy"] == Decimal("-0.2000")  # the could-buy line and the top-up
    assert "mood_match" not in c  # the mood is a section now (M10), not a score term
    assert r.score == sum(c.values())
    assert r.cash_cents == 300 + 200 + 129  # what you'd buy now: the top-up, the missing sauce, the could-buy
    assert r.missing_count == 2
    assert r.why == ("Uses up your item 1",)  # the card's Uses line names your items: no chip for it (M11)


def test_the_use_up_bonus_stops_at_one():
    coverage = tuple(have(i, soon=True) for i in range(1, 5))
    (r,), _ = ranked([candidate(1, coverage)])
    assert r.components["use_up"] == Decimal("1.0000")


def test_favorite_disliked_mood_and_the_kcal_band():
    q = query(kcal_target=Decimal(600))
    fav = candidate(1, (have(1),), is_favorite=True, per_portion={"energy_kcal": Decimal(750)})
    disliked = candidate(2, (have(1),), has_disliked=True, mood=RecipeMood.SIMPLE)
    out, _ = ranked([fav, disliked], q)
    by_id = {r.candidate.version_id: r.components for r in out}
    assert by_id[1]["favorite"] == Decimal("0.3000")
    assert by_id[1]["kcal_fit"] == Decimal("-0.2400")  # 150 over 600, beyond the ±90 band: 60 × −0.004
    assert "Your favorite" in next(r.why for r in out if r.candidate.version_id == 1)
    assert by_id[2]["disliked"] == Decimal("-0.3000")
    assert "mood_match" not in by_id[2]  # simple on a medium search: allowed, no exact-match bonus
    assert "kcal_fit" not in by_id[2]  # 600 kcal: on target


def test_nutrition_goals_are_normalized_and_weighted_in_tap_order():
    q = query(
        nutrition=(
            NutritionTerm(GoalTile.HIGH_CARB, Decimal("1.0")),
            NutritionTerm(GoalTile.IRON_RICH, Decimal("0.6")),
        )
    )
    a = candidate(1, per_portion={"carbohydrate_g": Decimal(80), "iron_mg": Decimal(2)}, heme_mg=Decimal(1))
    b = candidate(2, per_portion={"carbohydrate_g": Decimal(40), "iron_mg": Decimal(6)})
    out, _ = ranked([a, b], q)
    by_id = {r.candidate.version_id: r.components for r in out}
    assert by_id[1]["goal:high_carb"] == Decimal("1.0000") and by_id[2]["goal:high_carb"] == Decimal("0.5000")
    # iron counts heme twice: a = 2 + 1 = 3, b = 6 → a gets 0.6 × 3/6
    assert by_id[1]["goal:iron_rich"] == Decimal("0.3000") and by_id[2]["goal:iron_rich"] == Decimal("0.6000")


def test_protein_counts_only_up_to_the_meals_share_of_one_and_a_half_times_the_target():
    q = query(nutrition=(NutritionTerm(GoalTile.HIGH_PROTEIN, Decimal("1.0")),), protein_cap_g=Decimal(45))
    big = candidate(1, per_portion={"protein_g": Decimal(80)})
    bigger = candidate(2, per_portion={"protein_g": Decimal(120)})
    small = candidate(3, per_portion={"protein_g": Decimal(30)})
    out, _ = ranked([big, bigger, small], q)
    goal = {r.candidate.version_id: r.components.get("goal:high_protein", Decimal(0)) for r in out}
    assert goal[1] == goal[2] == Decimal("1.0000")  # both above the cap: no extra reward for 120 g
    assert goal[3] == Decimal("0.6667")  # 30 of 45
    assert [r.candidate.version_id for r in out] == [1, 2, 3]  # the tie goes to the lower version id


def test_quick_low_calorie_and_cheap_terms():
    q = query(quick_minutes=40, low_calorie=True, cheap=True)
    fast_light = candidate(
        1, (missing(1, cents=100),), total_minutes=10, per_portion={"energy_kcal": Decimal(400)}
    )
    slow_heavy = candidate(
        2, (missing(1, cents=500),), total_minutes=40, per_portion={"energy_kcal": Decimal(700)}
    )
    slow_heavy = RankInput(**{**slow_heavy.__dict__, "cost_per_portion_cents": 500})
    out, _ = ranked([fast_light, slow_heavy], q)
    by_id = {r.candidate.version_id: r for r in out}
    assert by_id[1].components["goal:quick"] == Decimal("1.0000") and "goal:quick" not in by_id[2].components
    assert by_id[1].components["goal:low_calorie"] == Decimal("1.0000")
    assert by_id[2].components["goal:cheap"] == Decimal("-1.0000")  # most to buy and the dearest portion
    assert by_id[1].components["goal:cheap"] == Decimal("-0.3500")  # (100/500 + 250/500) / 2
    assert out[0].candidate.version_id == 1 and "Ready in 10 min" in out[0].why


# ---------------- never favored (AC 2) ----------------
def test_a_never_favored_recipe_never_outranks_an_otherwise_equal_one_on_goal_pantry_or_cost():
    q = query(nutrition=(NutritionTerm(GoalTile.HIGH_PROTEIN, Decimal("1.0")),), cheap=True)
    plain = candidate(1, (have(1, "protein"), missing(2, cents=400)))
    # the pork recipe is better on every goal, pantry and cost term: more protein, more of your items (one
    # about to expire), nothing to buy and a cheaper portion
    pork = candidate(
        2,
        (have(1, "protein", soon=True), have(2)),
        never_favored=True,
        per_portion={"energy_kcal": Decimal(600), "protein_g": Decimal(90)},
        cost_per_portion_cents=100,
    )
    out, _ = ranked([pork, plain], q)
    assert [r.candidate.version_id for r in out] == [1, 2]
    parts = next(r.components for r in out if r.candidate.version_id == 2)
    assert "goal:high_protein" not in parts and "pantry_fit" not in parts and "use_up" not in parts
    plain_parts = out[0].components
    assert parts["goal:cheap"] == plain_parts["goal:cheap"]  # the pool's worst cost term, never better
    assert parts["missing"] == plain_parts["missing"]  # the pool's worst, though it misses nothing
    assert parts["never_favored"] == Decimal("-0.0500")
    assert out[1].why == ()


def test_otherwise_equal_recipes_the_capped_one_loses_by_the_tie_break():
    a = candidate(1, (have(1, "protein"),))
    b = candidate(2, (have(1, "protein"),), never_favored=True)
    out, _ = ranked([b, a])
    assert [r.candidate.version_id for r in out] == [1, 2]
    assert out[0].score - out[1].score == Decimal("1.0500")  # its pantry fit (1.0) is zero, plus −0.05


# ---------------- filters ----------------
def test_hard_filters_record_their_reason():
    rules = Rules(
        equipment=frozenset({Equipment.STOVETOP}),
        excluded=frozenset({10, 11, 12}),
        held=frozenset({11}),
        capped_out=frozenset({12}),
        cap_used_up={"Pork as a meal component": frozenset({13})},
    )
    q = query(mood=RecipeMood.SIMPLE, quick_minutes=20)
    cands = [
        candidate(1, ingredient_ids=frozenset({10}), total_minutes=10, mood=RecipeMood.SIMPLE),
        candidate(2, ingredient_ids=frozenset({11}), total_minutes=10, mood=RecipeMood.SIMPLE),
        candidate(3, ingredient_ids=frozenset({12}), total_minutes=10, mood=RecipeMood.SIMPLE),
        candidate(4, ingredient_ids=frozenset({13}), total_minutes=10, mood=RecipeMood.SIMPLE),
        candidate(5, equipment=frozenset({Equipment.AIR_FRYER}), total_minutes=10, mood=RecipeMood.SIMPLE),
        candidate(6, mood=RecipeMood.FANCY, total_minutes=10),
        candidate(7, total_minutes=45, mood=RecipeMood.SIMPLE),
        candidate(8, nutrition_complete=False, total_minutes=10, mood=RecipeMood.SIMPLE),
        candidate(9, total_minutes=10, mood=RecipeMood.SIMPLE),
        candidate(10, ingredient_ids=frozenset({11}), mood=RecipeMood.FANCY, total_minutes=45),
    ]
    out, filtered = ranked(cands, q, rules)
    # mood is a preference (M10): the Fancy recipe is not filtered; it comes after, under "A bit more effort"
    assert [(r.candidate.version_id, r.section) for r in out] == [(9, "match"), (6, "more_effort")]
    reasons = {f.candidate.version_id: f.reason for f in filtered}
    assert reasons == {
        1: "excluded",
        2: "held",
        3: "frequency_cap",
        4: "frequency_cap",
        5: "equipment",
        7: "time",
        8: "nutrition_incomplete",
        10: "held",  # held outranks time
    }
    assert set(next(f for f in filtered if f.candidate.version_id == 10).codes) == {"held", "time"}
    assert top_filter(filtered) == "held"  # held and frequency_cap remove two each: the more important wins


def test_the_empty_state_names_the_filter_that_removed_the_most():
    q = query(quick_minutes=20)
    out, filtered = ranked([candidate(1, total_minutes=45), candidate(2, total_minutes=60)], q)
    assert out == [] and top_filter(filtered) == "time"
    assert empty_reason(filtered, q) == "Nothing fits 20 minutes."


# ---------------- sort and the gap rule ----------------
def test_ties_go_to_fewer_missing_items_then_the_lower_version_id():
    # equal scores: one missing line with a substitute (−0.2) against two could-buy lines (−0.2)
    could = LineCoverage(
        need(2), Status.COULD_BUY, Decimal(100), purchase=Purchase(100, 1, "Stop & Shop", False)
    )
    could2 = LineCoverage(
        need(3), Status.COULD_BUY, Decimal(100), purchase=Purchase(100, 1, "Stop & Shop", False)
    )
    a = candidate(5, (have(1), missing(2, sub=True)))  # fit ½, missing −0.2
    b = candidate(3, (have(1), could, could2))  # fit ⅓, could buy −0.2: a lower score
    c = candidate(4, (have(1), missing(2, sub=True)))
    out, _ = ranked([a, b, c])
    assert [r.candidate.version_id for r in out] == [4, 5, 3]


def test_a_good_match_uses_your_protein_or_carb_with_at_most_two_missing_without_a_substitute():
    ok = candidate(1, (have(1, "protein"), missing(2), missing(3), missing(4, sub=True)))
    too_many = candidate(2, (have(1, "carb"), missing(2), missing(3), missing(4)))
    side_only = candidate(3, (have(1, "vegetable"),))
    out, _ = ranked([ok, too_many, side_only])
    good = {r.candidate.version_id: r.good_match for r in out}
    assert good == {1: True, 2: False, 3: False}
    assert good_matches(out) == 1 and ideas_needed(out)
    # an empty pantry: every recipe is equally missing, so the mood is enough
    out, _ = ranked([ok, too_many, side_only], empty=True)
    assert good_matches(out) == 3 and ideas_needed(out)  # M14: fewer than 6 good matches asks for ideas
    six = [candidate(i, (have(1, "protein"),)) for i in range(1, 7)]
    assert not ideas_needed(ranked(six)[0])
    # a recipe in another mood is shown (under its section) but isn't a good match (M10)
    fancy = candidate(7, (have(1, "protein"),), mood=RecipeMood.FANCY)
    out, _ = ranked([*six[:5], fancy])
    assert [r.section for r in out][-1] == "more_effort" and good_matches(out) == 5 and ideas_needed(out)


# ---------------- on the seed library ----------------
def stock_thighs_spinach_tortillas(session: Any) -> None:
    add_stock(session, "chicken-thigh-boneless-skinless", 1000)
    add_stock(session, "spinach", 300, expires_on=TODAY + timedelta(days=2))
    add_stock(session, "flour-tortilla-small", 20, "count", location=StorageLocation.PANTRY)


def test_golden_ordering_with_a_pantry_of_chicken_thighs_spinach_and_tortillas(api, seeded_db):
    stock_thighs_spinach_tortillas(seeded_db)
    events = meal_now(api, slot="dinner")
    cards = results(events)
    assert len(cards) == 25  # every dinner seed: your mood only orders them (M10)
    assert titles(cards)[:8] == [
        "Chicken and spinach gravy",  # uses all three, and the spinach before it expires
        "Everyday chicken curry gravy",
        "Sheet-pan chicken and peppers over rice",
        # its carb is a swap you have; the salmon is never swapped for your thighs (a whole cut swaps only
        # with a whole cut of the same form, 2b.4 fixes approval)
        "Lemon garlic salmon with rice and broccoli",
        "Yogurt chicken gravy",
        "Air-fryer chicken wings with sweet potato wedges",
        "Roast bone-in chicken breasts with quinoa and asparagus",
        "Chicken and black bean burrito bowls",
    ]
    sections = [
        c["section"] for c in cards
    ]  # Wednesday is medium: those first, then more effort, then simpler
    assert sections == sorted(sections, key=["match", "more_effort", "simpler"].index)
    assert sections.count("match") == 15 and "simpler" in sections
    top = cards[0]
    assert top["uses"] == [
        "chicken thigh, boneless skinless",
        "spinach, fresh",
        "flour tortilla (Price Rite, 37 g)",
    ]
    assert top["why"] == [
        "Uses up your spinach, fresh"
    ]  # no "Uses 3 of your items": the uses line says it (M11)
    air = next(c for c in cards if c["title"] == "Air-fryer chicken over rice with broccoli")
    assert air["uses"] == [] and air["section"] == "simpler"
    assert all(m["substitute"] is None for m in air["missing"])  # a line you can swap is never Missing (M11)
    swaps = {s["name"]: s for s in air["swaps"]}
    # a protein keeps its protein grams: 170 g of breast per portion is matched by about 200 g of thigh
    breast = swaps["chicken breast, boneless skinless"]
    assert breast["substitute"]["name"] == "chicken thigh, boneless skinless"
    assert breast["substitute"]["amount_display"].endswith(" g")
    assert breast["display"] == (
        "Swap: chicken thigh, boneless skinless instead of chicken breast, boneless skinless (you have it)"
    )
    rice = swaps["long-grain white rice (dry)"]["substitute"]
    assert rice["name"] == "flour tortilla (Price Rite, 37 g)"  # a carb, by kcal
    assert all(s["substitute"]["you_have"] for s in swaps.values())
    # an identical search ranks identically (and is served from the cache)
    again = meal_now(api, slot="dinner")
    assert titles(results(again)) == titles(cards) and final(again)["cached"] is True


def test_golden_ordering_quick_and_simple_leaves_the_two_seeds_that_fit(api, seeded_db):
    # step 2b.9: the seeds' totals are their own schedules now, so the air-fryer chicken (the chicken and the
    # broccoli take turns in the basket) takes 40 minutes and the burrito bowls 30
    stock_thighs_spinach_tortillas(seeded_db)
    events = meal_now(api, slot="dinner", goals=["quick"], time_limit_minutes=30, mood="simple")
    assert titles(results(events)) == ["Ground turkey tacos", "Chicken and black bean burrito bowls"]
    assert [c["why"] for c in results(events)] == [["Ready in 25 min"], ["Ready in 30 min"]]
    assert [c["section"] for c in results(events)] == ["match", "more_effort"]  # the bowls are medium (M10)
    nothing = meal_now(api, slot="dinner", goals=["quick"], time_limit_minutes=20, mood="simple")
    assert results(nothing) == []
    # the mood never empties the list (M10): the time limit does
    assert final(nothing)["empty_filter"] == "time"
    assert final(nothing)["empty_reason"] == "Nothing fits 20 minutes."


# ---------------- the pork cap, per calendar week ----------------
PORK = [("pork-chop-boneless", 400, "g", "protein"), ("rice-long-grain-white", 150, "g", "carb")]


def test_the_pork_cap_counts_monday_to_sunday_across_one_meal_plans(api, seeded_db, clock):
    pork = add_recipe(seeded_db, "Pork chop with rice", PORK)
    assert pork.title in titles(results(meal_now(api, slot="dinner")))  # allowed, ranked on neutral grounds
    cooked = api.post("/api/v1/cook/meals", json={"version_id": pork.id, "slot": "dinner"})
    assert cooked.status_code == 201, cooked.text
    events = meal_now(api, slot="dinner")
    assert pork.title not in titles(results(events))  # Wednesday: this week's one pork meal is planned
    run = final(events)["run_id"]
    row = seeded_db.scalars(
        select(PlanCandidate).where(
            PlanCandidate.generation_run_id == run, PlanCandidate.recipe_version_id == pork.id
        )
    ).one()
    assert row.filtered_reason == "frequency_cap"
    assert api.post(f"/api/v1/cook-batches/{cooked.json()['batch_id']}/cooked", json={}).status_code == 200
    clock(datetime(2026, 10, 18, 20, 0, tzinfo=ZONE))  # Sunday, same week: still used up
    assert pork.title not in titles(results(meal_now(api, slot="dinner")))
    clock(datetime(2026, 10, 19, 18, 0, tzinfo=ZONE))  # Monday: a new week, a new allowance
    assert pork.title in titles(results(meal_now(api, slot="dinner")))


def test_an_uncooked_one_meal_plan_from_an_earlier_day_no_longer_counts(api, seeded_db, clock):
    pork = add_recipe(seeded_db, "Pork chop with rice", PORK)
    api.post("/api/v1/cook/meals", json={"version_id": pork.id, "slot": "dinner"})  # Wednesday, never cooked
    clock(datetime(2026, 10, 16, 18, 0, tzinfo=ZONE))  # Friday, same week
    assert pork.title in titles(results(meal_now(api, slot="dinner")))


def test_active_plans_count_toward_the_week_too(seeded_db):
    user = current_user(seeded_db)
    pork = add_recipe(seeded_db, "Pork chop with rice", PORK)
    plan = MealPlan(
        user_id=user.id,
        week_start=date(2026, 10, 11),
        status="active",
        constraints={},
        constraints_hash="x",
        solver_status="optimal",
        totals={},
        validation_report={},
    )
    seeded_db.add(plan)
    seeded_db.flush()
    batch = PlanCookBatch(
        meal_plan_id=plan.id,
        recipe_version_id=pork.id,
        cook_on=date(2026, 10, 11),
        portions=2,
        portion_size="normal",
        portion_multiplier=Decimal(1),
        scale_factor=Decimal(1),
        planned_minutes=20,
    )
    seeded_db.add(batch)
    seeded_db.flush()
    for day in (date(2026, 10, 11), date(2026, 10, 12)):  # Sunday of last week, then this Monday
        seeded_db.add(
            PlanMeal(
                meal_plan_id=plan.id, eat_on=day, slot="dinner", cook_batch_id=batch.id, planned_kcal=600
            )
        )
    seeded_db.flush()
    caps = (ResolvedCap("Pork as a meal component", frozenset(pork_ids(seeded_db)), 1, True),)
    assert week_of(TODAY) == (date(2026, 10, 12), date(2026, 10, 18))
    assert meals_this_week(seeded_db, user.id, caps, TODAY) == {"Pork as a meal component": 1}
    assert meals_this_week(seeded_db, user.id, caps, date(2026, 10, 11)) == {"Pork as a meal component": 1}
    assert meals_this_week(seeded_db, user.id, caps, date(2026, 10, 19)) == {"Pork as a meal component": 0}


def pork_ids(session: Any) -> list[int]:
    return list(session.scalars(select(Ingredient.id).where(Ingredient.diet_tags.contains(["pork"]))))


# ---------------- more than one person ----------------
def test_cards_for_two_people_are_two_portions_with_the_recipe_pages_numbers(api, seeded_db):
    cards = results(meal_now(api, slot="dinner", people=2))
    for card in cards:
        assert card["portions"] == 2 and card["portions_display"] == "for 2 people"
        page = api.get(f"/api/v1/recipe-versions/{card['version_id']}", params={"portions": 2}).json()
        kcal = f"{page['per_portion']['kcal']} kcal"
        assert card["numbers"][0] == kcal


# ---------------- culinary groups on the seed library (J2) ----------------
def test_yellow_onion_never_becomes_spinach_on_a_card(api, seeded_db):
    add_stock(seeded_db, "chicken-thigh-boneless-skinless", 1000)
    add_stock(seeded_db, "spinach", 300)
    curry = next(
        c for c in results(meal_now(api, slot="dinner")) if c["title"] == "Everyday chicken curry gravy"
    )
    onion = next(m for m in curry["missing"] if m["name"] == "yellow onion")
    assert onion["substitute"] is None and onion["buy"] is not None
    add_stock(seeded_db, "onion-red", 2, "count", location=StorageLocation.PANTRY)
    curry = next(
        c for c in results(meal_now(api, slot="dinner")) if c["title"] == "Everyday chicken curry gravy"
    )
    assert all(m["name"] != "yellow onion" for m in curry["missing"])  # a swap now, not Missing (M11)
    onion = next(s for s in curry["swaps"] if s["name"] == "yellow onion")
    assert onion["substitute"]["name"] == "red onion"
    assert onion["display"] == "Swap: red onion instead of yellow onion (you have it)"


# ---------------- ideas rank like any recipe (step 2b.3b) ----------------
def test_an_idea_ranks_exactly_like_the_same_recipe_with_steps(api, seeded_db):
    lines = [
        ("chicken-thigh-boneless-skinless", 600, "g", "protein"),
        ("rice-long-grain-white", 300, "g", "carb"),
        ("spinach", 200, "g", "vegetable"),
    ]
    add_recipe(seeded_db, "Twin with steps", lines, mood="medium")
    idea = add_recipe(seeded_db, "Twin without steps", lines, mood="medium")
    seeded_db.execute(delete(RecipeStep).where(RecipeStep.recipe_version_id == idea.id))
    idea.steps_status = "pending"
    seeded_db.flush()
    add_stock(seeded_db, "chicken-thigh-boneless-skinless", 1000)
    cards = {c["title"]: c for c in results(meal_now(api, slot="dinner"))}
    a, b = cards["Twin with steps"], cards["Twin without steps"]
    assert (a["steps_ready"], b["steps_ready"]) == (True, False)
    same = ("numbers", "uses", "could_buy", "missing", "swaps", "why", "score", "section", "good_match")
    assert {k: a[k] for k in same} == {k: b[k] for k in same}
    order = [c["title"] for c in results(meal_now(api, slot="dinner"))]
    assert (
        abs(order.index("Twin with steps") - order.index("Twin without steps")) == 1
    )  # only the id breaks the tie
