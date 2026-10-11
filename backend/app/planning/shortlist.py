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
could miss a short cook day that the library fits easily.

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

from collections.abc import Mapping, Sequence
from dataclasses import replace
from decimal import Decimal

from app.domain.cook_time import MOOD_ORDER
from app.domain.enums import GroceryMode, MealSlot, NutritionPriority
from app.planning.problem import CandidateRecipe, IngredientPlan, PlanningProblem

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
    """The meal's quickest recipe, and the quickest one the strictest cook day's mood allows (ties by score).
    Never-favored and disliked recipes only when nothing else is there."""
    usable = [x for x in pool if not (x.never_favored or x.has_disliked)] or list(pool)
    moods = [MOOD_ORDER[d.mood] for d in problem.constraints.days if d.is_cook_day]
    strictest = min(moods, default=max(MOOD_ORDER.values()))

    def key(x: CandidateRecipe) -> tuple[int, Decimal, int]:
        return (x.active_minutes, -scores[x.version_id], x.version_id)

    out = [min(usable, key=key)]
    allowed = [x for x in usable if MOOD_ORDER[x.mood] <= strictest]
    if allowed and (fit := min(allowed, key=key)) not in out:
        out.append(fit)
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
        for fast in quickest(pool, problem, scores):  # so the shortest cook day can always be met
            if fast not in picked:
                picked.append(fast)
                keep.add(fast.version_id)
                used |= set(fast.need_per_portion)
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
