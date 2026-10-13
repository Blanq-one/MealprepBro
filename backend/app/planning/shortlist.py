"""The solver's shortlist (decided at the 2b.4 approval, after the M13 seed library). Pure: no database.

With dozens of recipes per meal the weekly MILP stops proving its best plan within the time limit, so plans
got slow and could differ between identical requests (the solve time grows with every candidate: the 10
Phase 0 seeds solve in about 10 s, 15 candidates take 20–60 s). Before each solve, code keeps the best
SHORTLIST_PER_SLOT candidates for each of the week's meals; the solver still does all the fitting. If they
can't make a plan, the orchestrator widens the shortlist once (SHORTLIST_WIDER), then tries every eligible
recipe before it says no plan fits (2b.3b approval, P3; not with a money limit, whose proof over every recipe
outlasts any time limit: see Orchestrator._solve). The candidates are already eligible: build_problem
applies every hard filter first (diet rules, equipment, mood and hands-on time that fit some cook day).

Each meal's shortlist always starts with its quickest recipe, and the quickest one your strictest cook day's
mood allows (P3): the first day of a week cooks every one of its meals itself, so a shortlist of slow recipes
could miss a short cook day that the library fits easily. With a money limit (a budget, or inventory mode's
top-up) it also keeps the meal's cheapest recipe by cost per portion and the cheapest by what it costs to buy
today (whole packages of what your pantry doesn't cover), since the planner stops at the wider shortlist then
(D102 follow-up, approved 2026-10-11); so does a cost-first tier (Broke mode, Cheapest). A tier that
includes upgrades (A bit better, Fancy; 2b.6 approval, item 2) keeps enough of the meal's best upgraded
recipes, and premium-protein ones, to reach its counts.

Each candidate is scored within its meal, every term scaled 0–1 across that meal's pool, ties by version id:
  nutrition   your priority per kcal (protein, carbs, or iron with heme counted twice; none for balanced)
  calories    how close one portion is to the meal's calorie target
  favorite    a recipe you ♥ (the solver's favorite bonus, here too)
  pantry      the share of its lines your inventory already covers (Always-have and staples count)
  cost        cheaper per portion is better (unknown cost: never an advantage); double weight when cheapest
Candidates are picked one at a time, and each pick pays W_NEW_INGREDIENT for every ingredient it would add
that the picks so far don't use (Always-have and staples are free): the solve time grows fast with the number
of different ingredients, and shared ingredients make a shorter shopping list with less left over.
Never favored (pork components, CLAUDE.md) and disliked recipes rank last: they can still be shortlisted when
a meal has fewer recipes than the limit, and the frequency caps still apply in the solver.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import replace
from decimal import Decimal

from app.domain.cook_time import MOOD_ORDER
from app.domain.enums import GroceryMode, MealSlot, NutritionPriority
from app.domain.price_tiers import COST_FIRST, RANK, IngredientTier, PriceTier, upgrade_slots
from app.planning.problem import CandidateRecipe, IngredientPlan, PlanningProblem
from app.schemas.constraints import VARIETY_CAPPED_SLOTS

SHORTLIST_PER_SLOT = 3  # lunch and dinner share most recipes, so a week shortlists about 8–12
SHORTLIST_WIDER = 6  # the second try when the shortlist can't make a plan
FULL_SOLVE_MAX = 16  # a library this small is solved whole from the start
W_NUTRITION = Decimal(1)
W_CALORIES = Decimal(1)
W_FAVORITE = Decimal(1)
W_PANTRY = Decimal(1)
W_COST = Decimal("0.5")
W_COST_CHEAPEST = Decimal(1)
W_NEW_INGREDIENT = Decimal("0.15")
_ZERO = Decimal(0)


def _density(c: CandidateRecipe, priority: NutritionPriority) -> Decimal:
    kcal = c.kcal
    if kcal <= 0:
        return _ZERO
    if priority is NutritionPriority.PROTEIN:
        return c.protein_g / kcal
    if priority is NutritionPriority.CARB:
        return c.per_portion.get("carbohydrate_g", _ZERO) / kcal
    if priority is NutritionPriority.IRON:
        return (c.per_portion.get("iron_mg", _ZERO) + c.heme_iron_mg) / kcal
    return _ZERO


def _pantry(c: CandidateRecipe, ingredients: Mapping[int, IngredientPlan]) -> Decimal:
    needed = [i for i in c.need_per_portion if i in ingredients]
    if not needed:
        return _ZERO
    covered = sum(1 for i in needed if ingredients[i].unlimited or ingredients[i].lots)
    return Decimal(covered) / len(needed)


def _scaled(values: Sequence[Decimal]) -> list[Decimal]:
    low, high = min(values), max(values)
    return [(v - low) / (high - low) if high > low else _ZERO for v in values]


def score_pool(
    pool: Sequence[CandidateRecipe], problem: PlanningProblem, slot_kcal: int
) -> dict[int, Decimal]:
    """Each candidate's shortlist score within one meal's pool (higher is better)."""
    c = problem.constraints
    nutrition = _scaled([_density(x, c.nutrition_priority) for x in pool])
    calories = _scaled([-abs(x.kcal - slot_kcal) for x in pool])
    pantry = _scaled([_pantry(x, problem.ingredients) for x in pool])
    known = [x.cost_cents_per_portion for x in pool if x.cost_cents_per_portion is not None]
    worst = max(known, default=_ZERO)
    cost = _scaled(
        [-(x.cost_cents_per_portion if x.cost_cents_per_portion is not None else worst) for x in pool]
    )
    w_cost = W_COST_CHEAPEST if c.grocery_mode is GroceryMode.CHEAPEST else W_COST
    out: dict[int, Decimal] = {}
    for n, x in enumerate(pool):
        if x.never_favored or x.has_disliked:
            out[x.version_id] = Decimal(-1)  # last, and nothing it does well moves it up
            continue
        out[x.version_id] = (
            W_NUTRITION * nutrition[n]
            + W_CALORIES * calories[n]
            + (W_FAVORITE if x.is_favorite else _ZERO)
            + W_PANTRY * pantry[n]
            + w_cost * cost[n]
        )
    return out


def quickest(
    pool: Sequence[CandidateRecipe], problem: PlanningProblem, scores: Mapping[int, Decimal]
) -> list[CandidateRecipe]:
    """The meal's quickest recipe, and the quickest one the strictest cook day's mood allows (ties by score):
    start to finish for one meal's batch on its own (step 2b.9, V11). Never-favored and disliked recipes only
    when nothing else is there."""
    usable = [x for x in pool if not (x.never_favored or x.has_disliked)] or list(pool)
    moods = [MOOD_ORDER[d.mood] for d in problem.constraints.days if d.is_cook_day]
    strictest = min(moods, default=max(MOOD_ORDER.values()))
    minutes = {x.version_id: x.minutes_alone(problem.constraints.household_size) for x in usable}

    def key(x: CandidateRecipe) -> tuple[int, Decimal, int]:
        return (minutes[x.version_id], -scores[x.version_id], x.version_id)

    out = [min(usable, key=key)]
    allowed = [x for x in usable if MOOD_ORDER[x.mood] <= strictest]
    if allowed and (fit := min(allowed, key=key)) not in out:
        out.append(fit)
    return out


def meal_portions(problem: PlanningProblem, slot: MealSlot) -> int:
    """The portions one recipe would cook for a meal this plan: every day that has the meal (the weekly
    variety cap for meals), for everyone eating."""
    c = problem.constraints
    days = sum(1 for d in c.days if slot in d.slots)
    if slot in VARIETY_CAPPED_SLOTS:
        days = min(days, c.max_portions_per_recipe)
    return max(days, 1) * c.household_size


def cost_first(problem: PlanningProblem) -> bool:
    """Broke mode and Cheapest plan on cost first (2b.6 approval, item 2), like a money limit."""
    tier = problem.constraints.price_tier
    return tier is not None and PriceTier(tier) in COST_FIRST


def buy_today_cents(x: CandidateRecipe, problem: PlanningProblem, portions: int) -> Decimal | None:
    """What cooking `portions` of a recipe costs to buy today: whole packages (the cheapest way at your
    stores) of what your pantry doesn't cover, counting only what the money limit covers (a cost-first tier:
    the regular groceries). None when something it would buy has no price."""
    c = problem.constraints
    first = cost_first(problem)
    total = Decimal(0)
    for ingredient_id, per_portion in x.need_per_portion.items():
        plan = problem.ingredients.get(ingredient_id)
        covered = (
            c.limit_covers(plan.stock_up) or (first and not plan.stock_up) if plan is not None else False
        )
        if plan is None or plan.unlimited or not covered:
            continue
        rest = per_portion * portions - plan.available
        if rest <= 0:
            continue
        options = [
            Decimal(math.ceil(rest / o.package_amount) * o.package_cents)
            if o.package_amount is not None and o.package_cents is not None
            else rest * o.cents_per_unit
            for o in plan.offers
            if o.store_id in c.store_ids
        ]
        if not options:
            return None
        total += min(options)
    return total


def cheapest(
    pool: Sequence[CandidateRecipe], problem: PlanningProblem, slot: MealSlot, scores: Mapping[int, Decimal]
) -> list[CandidateRecipe]:
    """With a money limit, or in a cost-first tier: the meal's cheapest recipe per portion and the cheapest
    to buy today (ties by score). An unknown cost never counts as cheap. Never-favored and disliked recipes
    only when nothing else is there."""
    if not problem.constraints.has_purchase_limit and not cost_first(problem):
        return []
    usable = [x for x in pool if not (x.never_favored or x.has_disliked)] or list(pool)
    out: list[CandidateRecipe] = []
    per_portion = [x for x in usable if x.cost_cents_per_portion is not None]
    if per_portion:
        out.append(
            min(
                per_portion,
                key=lambda x: (x.cost_cents_per_portion, -scores[x.version_id], x.version_id),
            )
        )
    portions = meal_portions(problem, slot)
    today = [(cents, x) for x in usable if (cents := buy_today_cents(x, problem, portions)) is not None]
    if today:
        best = min(today, key=lambda t: (t[0], -scores[t[1].version_id], t[1].version_id))[1]
        if best not in out:
            out.append(best)
    return out


def tiered(
    pool: Sequence[CandidateRecipe], problem: PlanningProblem, slot: MealSlot, scores: Mapping[int, Decimal]
) -> list[CandidateRecipe]:
    """A tier's upgrades (item 2): the meal's best upgraded recipes, and premium-protein ones, enough to fill
    the tier's counts within the variety rule (one more than that, so the solver still has a choice)."""
    c = problem.constraints
    if slot not in upgrade_slots(s for d in c.days for s in d.slots):
        return []
    usable = [x for x in pool if not (x.never_favored or x.has_disliked)]
    out: list[CandidateRecipe] = []
    better = RANK[IngredientTier.BETTER]
    wants = (
        (c.upgraded_meals_min, [x for x in usable if x.tier_rank >= better]),
        (c.premium_meals_min, [x for x in usable if x.premium_protein]),
    )
    for need, matching in wants:
        if need <= 0:
            continue
        ranked = sorted(matching, key=lambda x: (-scores[x.version_id], x.version_id))
        out += [x for x in ranked[: math.ceil(need / c.max_portions_per_recipe) + 1] if x not in out]
    return out


def shortlist(problem: PlanningProblem, per_slot: int = SHORTLIST_PER_SLOT) -> PlanningProblem:
    """The problem with each meal's best `per_slot` candidates (a recipe kept for any meal is kept for all its
    meals). The same problem when nothing needs cutting."""
    slot_kcal: dict[MealSlot, int] = {t.slot: t.kcal for t in problem.constraints.slot_targets}
    keep: set[int] = set()
    used: set[int] = set()  # ingredients the picks so far need
    bought = {i for i, plan in problem.ingredients.items() if not plan.unlimited}

    def adds(x: CandidateRecipe) -> int:
        return len((set(x.need_per_portion) & bought) - used)

    for slot, kcal in slot_kcal.items():
        pool = [x for x in problem.candidates if slot in x.meal_slots]
        if len(pool) <= per_slot:
            keep |= {x.version_id for x in pool}
            used |= {i for x in pool for i in x.need_per_portion}
            continue
        scores = score_pool(pool, problem, kcal)
        picked = [x for x in pool if x.version_id in keep][:per_slot]  # already kept for another meal
        # the shortest cook day can always be met, a money limit always has the cheap options, and a tier its
        # upgrades
        musts = [*quickest(pool, problem, scores), *cheapest(pool, problem, slot, scores)]
        for must in [*musts, *tiered(pool, problem, slot, scores)]:
            if must not in picked:
                picked.append(must)
                keep.add(must.version_id)
                used |= set(must.need_per_portion)
        while len(picked) < per_slot:
            rest = [x for x in pool if x not in picked]
            best = min(
                rest, key=lambda x: (-(scores[x.version_id] - W_NEW_INGREDIENT * adds(x)), x.version_id)
            )
            picked.append(best)
            keep.add(best.version_id)
            used |= set(best.need_per_portion)
    if len(keep) == len(problem.candidates):
        return problem
    return replace(problem, candidates=tuple(x for x in problem.candidates if x.version_id in keep))
