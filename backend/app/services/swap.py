"""Swap one meal of a plan (step 2b.6, E5, FLOW_SPEC C6 and §13.3, AA4).

  options  POST /plans/{id}/meals/{meal_id}/swap-options: 3-5 alternatives that fit the same slot, day,
           fridge or freezer and time rules, from the pinned re-solve (planning/pins.py), sorted by what they
           add to the groceries and then by protein. Recipes already swapped away for this meal are left
           out; "Write a new one" (allow_llm) makes one ideas call first, whose ideas join the pool for
           later swaps.
  apply    POST /plans/{id}/meals/{meal_id}/swap: the tapped option, rounded and validated like any plan,
           saved as a new version of the plan that supersedes the old one (same kind and status), with the
           grocery check-offs carried over and cooked batches kept as they were cooked.
  undo     POST /plans/{id}/swap/undo: the previous version back, exactly as it was.

After Done shopping, a swap plans from your pantry (inventory mode, nothing bought) unless you allow buying.
What a cooked batch used is counted back as stock for the re-solve, since Mark cooked already took it from
your pantry. Plans already made keep their meals when you stop eating a food or hide a recipe (D166), so the
batches a swap keeps aren't failed for it; everything new is checked against your rules as they are now.
"""

import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.cook import search as search_service
from app.cook.ideas import ClientFactory, wait_seconds
from app.cook.stream import HEARTBEAT_SECONDS, Emit, access_for, stream_events
from app.db.models import (
    AppUser,
    CookSearch,
    FeedbackEvent,
    GenerationRun,
    GroceryList,
    GroceryListItem,
    MealPlan,
    PlanBatchIngredient,
    PlanCookBatch,
    PlanMeal,
    Recipe,
    RecipeIngredient,
    RecipeVersion,
)
from app.domain.cost import money_display
from app.domain.enums import MealSlot, PlanningMode, PortionSize
from app.domain.exclusions import ExclusionStatus
from app.domain.nutrition import kcal_display
from app.llm.errors import LLMBudgetExceededError, LLMError, LLMWaitTooLongError
from app.llm.pacing import Clock as LLMClock
from app.llm.pacing import Deadline
from app.planning.candidates import Gap
from app.planning.exposure import log_exposures
from app.planning.ideas import IdeaCandidates
from app.planning.inputs import diet_inputs
from app.planning.loader import build_problem, candidate_versions
from app.planning.orchestrator import problem_json, tightening_from
from app.planning.persistence import SINGLE, PlanNotFoundError, save_plan
from app.planning.pins import (
    KeptBatch,
    PinError,
    Pins,
    filled,
    kept_indices,
    solve_pinned,
    swap_options,
)
from app.planning.plan_validator import RESOLVABLE, ValidationReport, validate_plan
from app.planning.post_solve import KeptRounding, build_rounded_plan, exclusion_notes, rounding_fit
from app.planning.problem import PlanningProblem, Tightening, size_multiplier
from app.planning.reference import ReferenceData, load_reference
from app.planning.rounded import ABSORBED, RoundedPlan
from app.planning.rounding import round_batch
from app.planning.solver.model import BatchKey, NearLimits, SolvedBatch, SolverSolution
from app.schemas.constraints import ExtraLot, KcalAllowance, PlanConstraints
from app.schemas.feedback import SWAPPED_PAYLOAD_VERSION, FeedbackEventType, SwappedPayload
from app.schemas.plans import SwapMealOut, SwapOptionOut, SwapOptionsIn, SwapStreamEvent
from app.services import plan_view as view
from app.services.cooking import stock_needs
from app.services.dishes import dish_categories
from app.services.errors import ConflictError

log = logging.getLogger(__name__)

SWAP = "swap"  # generation_run.purpose
MIN_OPTIONS = 3
MAX_OPTIONS = 5
IDEAS_PER_CALL = 5
MAX_RESOLVES = 2
LIVE_STATUSES = ("draft", "active")
NO_LONGER_FITS = "That recipe doesn't fit this meal any more. Pick another one."
PLAN_AGAIN = "This plan's days or rules changed since it was made, so a swap can't keep the rest; plan again."
Slot = tuple[date, MealSlot]


class SwapError(ConflictError):
    """This meal can't be swapped (the message says why): 409."""


@dataclass
class SwapContext:
    plan: MealPlan
    meal: PlanMeal
    slot: Slot
    problem: PlanningProblem
    pins: Pins
    saved: PlanConstraints  # what the new plan stores (without the stock counted back for cooked batches)
    after_shopping: bool
    current_version: int
    current_title: str
    batches: list[PlanCookBatch]
    plan_version_ids: frozenset[int]


# ---------------- loading ----------------
def _plan_and_meal(
    session: Session, user_id: int, plan_id: int, meal_id: int, today: date
) -> tuple[MealPlan, PlanMeal]:
    plan = session.get(MealPlan, plan_id)
    if plan is None or plan.user_id != user_id:
        raise PlanNotFoundError(f"plan {plan_id} not found")
    meal = session.get(PlanMeal, meal_id)
    if meal is None or meal.meal_plan_id != plan.id or meal.status == "replaced":
        raise PlanNotFoundError(f"meal {meal_id} not found in plan {plan_id}")
    if plan.kind == SINGLE:
        raise SwapError("A one-meal plan has nothing else to keep: pick another recipe instead.")
    if plan.status not in LIVE_STATUSES:
        raise SwapError("This version of the plan was replaced. Open your current plan to swap a meal.")
    if meal.assembly_version_id is not None or meal.cook_batch_id is None:
        raise SwapError("Swapping a mix-and-match meal comes with smart prep.")
    if meal.eat_on < today:
        raise SwapError("This meal's day has passed.")
    return plan, meal


def _live_diet(session: Session, user_id: int) -> dict[str, Any]:
    """Your food rules as they are now (the constraint builder's resolution), for what a swap brings in."""
    diet = diet_inputs(session, user_id)
    excluded = frozenset(i for i, s in diet.statuses.items() if s is not ExclusionStatus.ALLOWED)
    held = frozenset(i for i, s in diet.statuses.items() if s is ExclusionStatus.HELD)
    capped_out = (
        frozenset(i for cap in diet.caps if cap.max_meals_per_week == 0 for i in cap.member_ids) & excluded
    )
    return {
        "excluded_ingredient_ids": excluded,
        "held_ingredient_ids": held,
        "capped_out_ingredient_ids": capped_out,
        "disliked_ingredient_ids": diet.disliked_ids - excluded,
        "favorite_recipe_ids": diet.favorite_recipe_ids,
    }


def _grocery_list(session: Session, plan_id: int) -> GroceryList | None:
    return session.scalars(select(GroceryList).where(GroceryList.meal_plan_id == plan_id)).first()


def _cooked_stock(
    session: Session, batches: list[PlanCookBatch], always_have: frozenset[int]
) -> tuple[ExtraLot, ...]:
    """What the cooked batches took from your pantry (as Mark cooked counted it), as stock for this re-solve
    only: they stay in the plan, so their needs must be met without buying them again."""
    out: list[ExtraLot] = []
    for b in batches:
        if b.status != "cooked":
            continue
        for ingredient_id, (quantity, unit) in sorted(stock_needs(session, b, always_have).items()):
            if quantity > 0:
                out.append(ExtraLot(ingredient_id=ingredient_id, quantity=quantity, unit=unit))
    return tuple(out)


def _constraints(
    session: Session, user_id: int, plan: MealPlan, batches: list[PlanCookBatch], *, allow_buying: bool
) -> tuple[PlanConstraints, PlanConstraints, bool]:
    """(what the new plan stores, what the re-solve uses, whether you've done the shopping)."""
    c = PlanConstraints.model_validate(plan.constraints)
    glist = _grocery_list(session, plan.id)
    after = glist is not None and glist.status == "done"
    update: dict[str, Any] = {
        **_live_diet(session, user_id),
        # the lots you turned off then stay off; what the plan bought since is fine
        "lots_off_ingredient_ids": frozenset(),
        # one meal of "Same dish, many portions" may become another dish: you asked for it
        "portion_requests": tuple(r.model_copy(update={"same_recipe": False}) for r in c.portion_requests),
    }
    if after:
        update |= {"allowed_purchase_ingredient_ids": None, "preferred_ingredient_ids": frozenset()}
        if allow_buying:
            update |= {"planning_mode": PlanningMode.SHOP, "purchase_limit_cents": None}
        else:
            update |= {"planning_mode": PlanningMode.INVENTORY, "purchase_limit_cents": 0}
    saved = c.model_copy(update=update)
    stock = _cooked_stock(session, batches, c.always_have_ingredient_ids)
    return saved, saved.model_copy(update={"extra_lots": (*saved.extra_lots, *stock)}), after


def _problem(
    session: Session,
    user_id: int,
    constraints: PlanConstraints,
    plan_versions: frozenset[int],
    *,
    slot: MealSlot | None,
    extra: frozenset[int] = frozenset(),
    budget_pins: dict[int, frozenset[int]] | None = None,
) -> tuple[PlanningProblem, frozenset[int]]:
    """The plan's own recipes plus every recipe you could have for this meal (your pool as it is now), and
    `extra` versions (your new version of a batch; it must pass your rules like any recipe). `budget_pins`:
    each kept version's lines on their budget side, as its stored batch cooked them (item 4)."""
    pool = (
        [(r, v) for r, v in candidate_versions(session, user_id) if slot.value in v.meal_slots]
        if slot is not None
        else []
    )
    kept = session.execute(
        select(Recipe, RecipeVersion)
        .join(Recipe, Recipe.id == RecipeVersion.recipe_id)
        .where(RecipeVersion.id.in_(plan_versions | extra))
    ).tuples()
    by_id = {v.id: (r, v) for r, v in [*kept, *pool]}
    pairs = [by_id[vid] for vid in sorted(by_id)]
    problem = build_problem(
        session, user_id, constraints, pairs, keep_version_ids=plan_versions, budget_pins=budget_pins
    )
    kcal, protein = rounding_fit(problem), rounding_fit(problem, "protein_g")
    problem = problem.with_tightening(
        Tightening(
            kcal_bias=kcal.bias, protein_bias=protein.bias, kcal_scale=kcal.scale, protein_scale=protein.scale
        )
    )
    return problem, frozenset(v.id for _, v in pool)


def _budget_pins(session: Session, batches: list[PlanCookBatch]) -> dict[int, frozenset[int]]:
    """Per recipe version in the plan: the line ids its stored batch cooked with their budget equivalent
    (the 2b.6 approval, item 4), so a swap keeps every batch as planned whatever the prices say now."""
    if not batches:
        return {}
    version_of = {b.id: b.recipe_version_id for b in batches}
    classic = {
        r.id: r.ingredient_id
        for r in session.scalars(
            select(RecipeIngredient).where(RecipeIngredient.recipe_version_id.in_(set(version_of.values())))
        )
    }
    pins: dict[int, set[int]] = {v: set() for v in version_of.values()}
    for row in session.scalars(
        select(PlanBatchIngredient).where(PlanBatchIngredient.cook_batch_id.in_(list(version_of)))
    ):
        line = row.recipe_ingredient_id
        if line is not None and line in classic and classic[line] != row.ingredient_id:
            pins[version_of[row.cook_batch_id]].add(line)
    return {v: frozenset(lines) for v, lines in pins.items()}


def _absorbed_lines(session: Session, batch_ids: list[int]) -> dict[int, tuple[int, Decimal]]:
    out: dict[int, tuple[int, Decimal]] = {}
    for row in session.scalars(
        select(PlanBatchIngredient).where(
            PlanBatchIngredient.cook_batch_id.in_(batch_ids), PlanBatchIngredient.adjustment == ABSORBED
        )
    ):
        out[row.cook_batch_id] = (row.ingredient_id, row.quantity)
    return out


@dataclass
class _Loaded:
    """A stored plan, read for a re-solve: its batches as kept batches, its meals, and the problem."""

    batches: list[PlanCookBatch]
    meals: list[PlanMeal]
    saved: PlanConstraints
    after_shopping: bool
    problem: PlanningProblem
    pool: frozenset[int]
    kept: dict[BatchKey, KeptBatch]
    key_of: dict[int, BatchKey]
    plan_versions: frozenset[int]


def _load(
    session: Session,
    user_id: int,
    plan: MealPlan,
    *,
    allow_buying: bool,
    slot: MealSlot | None,
    extra: frozenset[int] = frozenset(),
) -> _Loaded:
    batches = list(
        session.scalars(
            select(PlanCookBatch).where(PlanCookBatch.meal_plan_id == plan.id).order_by(PlanCookBatch.id)
        )
    )
    meals = list(
        session.scalars(
            select(PlanMeal).where(PlanMeal.meal_plan_id == plan.id, PlanMeal.status != "replaced")
        )
    )
    if any(m.assembly_version_id is not None for m in meals):
        raise SwapError("Changing a mix-and-match plan comes with smart prep.")
    saved, solving, after = _constraints(session, user_id, plan, batches, allow_buying=allow_buying)
    plan_versions = frozenset(b.recipe_version_id for b in batches)
    problem, pool = _problem(
        session,
        user_id,
        solving,
        plan_versions,
        slot=slot,
        extra=extra,
        budget_pins=_budget_pins(session, batches),
    )
    known = {r.version_id for r in problem.candidates}
    if missing := sorted(plan_versions - known):
        raise SwapError(
            f"Some of this plan's recipes can't be read any more ({missing}); plan the week again."
        )
    absorbed = _absorbed_lines(session, [b.id for b in batches])
    kept: dict[BatchKey, KeptBatch] = {}
    key_of: dict[int, BatchKey] = {}
    for b in batches:
        key = (b.recipe_version_id, b.cook_on, b.portion_size)
        if key in kept:
            raise SwapError(
                "This plan cooks one recipe twice on one day, so a swap can't keep it; plan again."
            )
        recipe = problem.candidate(b.recipe_version_id)
        size = size_multiplier(PortionSize(b.portion_size))
        kept[key] = KeptBatch(
            key=key,
            batch_id=b.id,
            title=recipe.title,
            portions=b.portions,
            portions_to_freeze=b.portions_to_freeze,
            nudge=b.scale_factor * recipe.base_servings / (b.portions * size),
            rounding=KeptRounding(b.scale_factor, absorbed.get(b.id)),
            cooked=b.status == "cooked",
        )
        key_of[b.id] = key
    return _Loaded(batches, meals, saved, after, problem, pool, kept, key_of, plan_versions)


def swap_context(
    session: Session,
    user_id: int,
    plan_id: int,
    meal_id: int,
    *,
    today: date,
    exclude: frozenset[int] = frozenset(),
    allow_buying: bool = False,
) -> SwapContext:
    plan, meal = _plan_and_meal(session, user_id, plan_id, meal_id, today)
    slot = MealSlot(meal.slot)
    loaded = _load(session, user_id, plan, allow_buying=allow_buying, slot=slot)
    problem, key_of = loaded.problem, loaded.key_of
    assert meal.cook_batch_id is not None
    current = loaded.kept[key_of[meal.cook_batch_id]]
    offer = frozenset(
        r.version_id
        for r in problem.candidates
        if slot in r.meal_slots and r.version_id in loaded.pool and r.version_id not in exclude
    ) - {current.key[0]}
    pins = Pins(
        slot=(meal.eat_on, slot),
        fed_by=current.key,
        meals={
            (m.eat_on, MealSlot(m.slot)): key_of[m.cook_batch_id]
            for m in loaded.meals
            if m.id != meal.id and m.cook_batch_id is not None
        },
        batches=loaded.kept,
        offer=offer,
        earliest=today,
    )
    return SwapContext(
        plan=plan,
        meal=meal,
        slot=(meal.eat_on, slot),
        problem=problem,
        pins=pins,
        saved=loaded.saved,
        after_shopping=loaded.after_shopping,
        current_version=current.key[0],
        current_title=current.title,
        batches=loaded.batches,
        plan_version_ids=loaded.plan_versions,
    )


# ---------------- options ----------------
def current_meal(ctx: SwapContext) -> SwapMealOut:
    m = ctx.meal
    return SwapMealOut(
        plan_meal_id=m.id,
        eat_on=m.eat_on,
        slot=MealSlot(m.slot),
        version_id=ctx.current_version,
        title=ctx.current_title,
        kcal=m.planned_kcal,
        protein_g=_meal_protein(ctx),
        label=view.meal_label(m.eat_on, MealSlot(m.slot), with_date=True),
    )


def _meal_protein(ctx: SwapContext) -> Decimal:
    assert ctx.pins.fed_by is not None
    kept = ctx.pins.batches[ctx.pins.fed_by]
    batch = SolvedBatch(kept.key[0], kept.key[1], PortionSize(kept.key[2]), kept.nudge, kept.portions)
    rounded = round_batch(
        ctx.problem, batch, factor=kept.rounding.scale_factor, absorbed=kept.rounding.absorbed
    )
    return rounded.per_portion.get("protein_g", Decimal(0)).quantize(Decimal("0.1"), ROUND_HALF_UP)


def _restore_cooked(solution: SolverSolution, pins: Pins) -> SolverSolution:
    """A cooked batch keeps its food: the portion the swap freed stays in its batch (and the batch stays in
    the plan when it fed nothing else), so it rounds exactly as it was cooked."""
    batches = list(solution.batches)
    present = {(b.version_id, b.cook_on, b.portion_size.value): i for i, b in enumerate(batches)}
    for key, kept in pins.batches.items():
        if not kept.cooked:
            continue
        restored = SolvedBatch(
            key[0], key[1], PortionSize(key[2]), kept.nudge, kept.portions, kept.portions_to_freeze
        )
        if key in present:
            batches[present[key]] = restored
        else:
            batches.append(restored)
    return replace(solution, batches=tuple(batches))


def also_changed(ctx: SwapContext, solution: SolverSolution) -> list[str]:
    """What else the option changes: the batch that gives up the meal, one that grows, or a new one."""
    now = {(b.version_id, b.cook_on, b.portion_size.value): b for b in solution.batches}
    lines: list[str] = []
    for key, kept in sorted(ctx.pins.batches.items(), key=lambda kv: (kv[0][1], kv[1].title)):
        after = now[key].portions if key in now else 0
        if kept.cooked and key == ctx.pins.fed_by:
            lines.append(
                view.batch_change(
                    key[1], kept.title, kept.portions, kept.portions - _people(ctx), cooked=True
                )
            )
        elif after != kept.portions and not kept.cooked:
            lines.append(view.batch_change(key[1], kept.title, kept.portions, after))
    for key, b in sorted(now.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        if key not in ctx.pins.batches:
            title = ctx.problem.candidate(key[0]).title
            lines.append(view.batch_change(key[1], title, 0, b.portions))
    return lines


def _people(ctx: SwapContext) -> int:
    return ctx.problem.constraints.household_size


@dataclass
class _Fit:
    """One option as the plan it would make, rounded and checked like any plan (step 2b.6 approval, A), so a
    tap never fails on what the sheet showed. A close fit (B) moved other portions a little or goes past a
    calorie limit or a cook day's minutes: `changes` says how, and its plan's constraints carry what it
    needs past your limits (kept with the plan when you pick it)."""

    solution: SolverSolution
    pins: Pins
    plan: RoundedPlan
    report: ValidationReport
    close: bool = False
    changes: tuple[str, ...] = ()
    distance: int = 0  # kcal past your limits + NEAR_MINUTE_KCAL × minutes past (close fits, closest first)


def _option_out(
    ctx: SwapContext,
    fit: _Fit,
    *,
    baseline_cents: int,
    versions: dict[int, RecipeVersion],
    categories: dict[int, str],
    new_ids: frozenset[int],
) -> SwapOptionOut:
    solution = fit.solution
    pins = fit.pins
    fill = filled(solution, pins)
    batch = solution.batches[fill.batch_index]
    recipe = ctx.problem.candidate(fill.version_id)
    meal = next(m for m in fit.plan.meals if (m.eat_on, m.slot) == ctx.slot)  # the rounded meal
    numbers = [f"{meal.kcal:,} kcal", f"{meal.protein_g} g protein"]
    if recipe.cost_cents_per_portion is not None:
        cents = int(
            (recipe.cost_cents_per_portion * size_multiplier(batch.portion_size) * batch.nudge).quantize(
                Decimal(1), ROUND_HALF_UP
            )
        )
        numbers.append(f"about {money_display(cents)} a portion")
    delta = solution.estimated_purchase_cents - baseline_cents
    version = versions[fill.version_id]
    return SwapOptionOut(
        version_id=fill.version_id,
        recipe_id=recipe.recipe_id,
        title=recipe.title,
        dish_category=categories.get(fill.version_id, "other"),
        kcal=meal.kcal,
        protein_g=meal.protein_g,
        numbers=numbers,
        cost_delta_cents=delta,
        cost_delta_display=view.swap_cost_display(delta, money_display(abs(delta))),
        source_display=view.swap_source(
            batch.cook_on, ctx.slot[0], fill.from_freezer, new=fill.new, title=recipe.title
        ),
        also_changed=also_changed(ctx, solution),
        buys=list(_bought(ctx, fit.plan)),
        is_new=fill.version_id in new_ids,
        steps_ready=version.steps_status is None,
        is_draft=version.is_draft,
        fit="close" if fit.close else "exact",
        changes=list(fit.changes),
    )


@dataclass
class OptionsResult:
    options: list[SwapOptionOut]
    no_fit: str | None


def find_options(
    session: Session, ctx: SwapContext, *, new_ids: frozenset[int] = frozenset()
) -> OptionsResult:
    """3-5 alternatives, sorted by what they add to the groceries, then by protein (new ideas first after
    Write a new one). Each is checked as the plan it would make, exactly as a tap applies it (A). When fewer
    than 3 fit exactly, the closest fits come after them (B), closest first; "no other fits" only when there
    is neither."""
    base = solve_pinned(ctx.problem, replace(ctx.pins, offer=frozenset({ctx.current_version})))
    baseline = base[0].estimated_purchase_cents if base is not None else 0
    solutions: list[SolverSolution] = []
    fresh = ctx.pins.offer & new_ids
    for offer in (fresh, ctx.pins.offer - fresh) if fresh else (ctx.pins.offer,):
        if len(solutions) >= MAX_OPTIONS or not offer:
            continue
        found, pins = swap_options(
            ctx.problem, replace(ctx.pins, offer=offer), count=MAX_OPTIONS - len(solutions)
        )
        ctx.pins = replace(ctx.pins, cuts=pins.cuts)
        solutions += found
    exact: list[_Fit] = []
    for version in dict.fromkeys(filled(s, ctx.pins).version_id for s in solutions):
        if (fit := exact_fit(session, ctx, version)) is not None:
            exact.append(fit)
    close: list[_Fit] = []
    if len(exact) < MIN_OPTIONS:
        close = _close_fits(
            session,
            ctx,
            skip={filled(f.solution, f.pins).version_id for f in exact},
            count=MIN_OPTIONS - len(exact),
        )
    fits = [*exact, *close]
    ids = {filled(f.solution, f.pins).version_id for f in fits}
    versions = {v.id: v for v in session.scalars(select(RecipeVersion).where(RecipeVersion.id.in_(ids)))}
    categories = {vid: c.value for vid, c in dish_categories(session, ids).items()}
    out = [
        _option_out(
            ctx, fit, baseline_cents=baseline, versions=versions, categories=categories, new_ids=new_ids
        )
        for fit in fits
    ]
    distance = {filled(f.solution, f.pins).version_id: f.distance for f in fits}
    out.sort(  # new ideas first (D168), then the exact fits, then the close ones, closest first
        key=lambda o: (
            not o.is_new,
            o.fit == "close",
            distance[o.version_id] if o.fit == "close" else 0,
            o.cost_delta_cents,
            -o.protein_g,
            o.title,
        )
    )
    no_fit = view.no_fit_text(ctx.slot[1], ctx.slot[0]) if not out else None
    return OptionsResult(out, no_fit)


def _bought(ctx: SwapContext, plan: RoundedPlan) -> tuple[str, ...]:
    """After shopping with buying allowed: what the option needs that your pantry doesn't have."""
    if not ctx.after_shopping or ctx.problem.constraints.planning_mode is PlanningMode.INVENTORY:
        return ()
    return tuple(
        f"{item.name} ({money_display(item.cost_cents)})" if item.cost_cents is not None else item.name
        for item in plan.grocery.items
        if item.kind == "buy" and (item.bought or item.to_buy) > 0
    )


# ---------------- checking an option (A) and close fits (B) ----------------
NEAR = NearLimits()
NEAR_MINUTE_KCAL = 4  # a minute past a cook day's time counts like 4 kcal past a limit (sorting)
# what a close fit may go past (with an allowance kept with the plan); every other limit stays as it is
ALLOWABLE = frozenset(
    {
        "KCAL_DAY_OVER_CEILING",
        "KCAL_DAY_UNDER_FLOOR",
        "KCAL_WEEK_OVER_CEILING",
        "KCAL_WEEK_UNDER_FLOOR",
        "COOK_TIME_OVER",
    }
)
SHIFT_SHOWN = Decimal("0.001")  # a rebalanced batch says so when its portions moved at all
MAX_COOK_MINUTES = 600  # DaySpec's limit


def _rounded(
    session: Session, user_id: int, problem: PlanningProblem, pins: Pins, solution: SolverSolution
) -> tuple[SolverSolution, RoundedPlan, ValidationReport, ReferenceData, frozenset[int]]:
    """The re-solve rounded as the saved plan would be (cooked batches as cooked), and its check."""
    solution = _restore_cooked(solution, pins)
    exact, nudge_only = kept_indices(solution, pins)
    plan = build_rounded_plan(problem, solution, kept=exact, keep_nudge=nudge_only)
    reference = load_reference(session, user_id, problem.constraints, [b.version_id for b in plan.batches])
    kept = frozenset(exact)
    return solution, plan, validate_plan(plan, reference, kept=kept), reference, kept


def exact_fit(session: Session, ctx: SwapContext, version_id: int) -> _Fit | None:
    """The version in the meal's place with everything else exactly as it is, rounded and checked (with up to
    MAX_RESOLVES re-solves when rounding pushed a limit); None when it doesn't fit once rounded."""
    pins = replace(ctx.pins, offer=frozenset({version_id}))
    found = solve_pinned(ctx.problem, pins)
    if found is None:
        return None
    solution, pins = found
    user_id = ctx.plan.user_id
    try:
        plan, report, solution = _round_and_check(session, user_id, ctx.problem, pins, solution, failed="")
    except SwapError:
        return None
    return _Fit(solution, pins, plan, report)


def close_fit(session: Session, ctx: SwapContext, version_id: int) -> _Fit | None:
    """The version as a close fit: the other batches' portions may move a little, and the calorie limits and
    the cook day's minutes may give by up to NEAR (each kcal and minute at a steep price). Rounded and
    checked: re-solved with a bound tightened while that can help, and what is still past a limit becomes the
    plan's allowance. None when even that doesn't fit."""
    pins = replace(ctx.pins, offer=frozenset({version_id}), rebalance=True)
    found = solve_pinned(ctx.problem, pins, near=NEAR)
    if found is None:
        return None
    solution, pins = found
    problem = ctx.problem
    user_id = ctx.plan.user_id
    fallback: _Fit | None = None
    for resolves in range(MAX_RESOLVES + 1):
        solution, plan, report, reference, kept = _rounded(session, user_id, problem, pins, solution)
        if report.ok:
            return _Fit(solution, pins, plan, report, close=True, changes=tuple(_rebalanced(ctx, plan)))
        if fallback is None and all(e.code in ALLOWABLE for e in report.errors):
            fallback = _allowing(
                ctx, solution=solution, pins=pins, plan=plan, report=report, reference=reference, kept=kept
            )
        movable = tuple(e for e in report.errors if e.code != "COOK_TIME_OVER")
        if resolves == MAX_RESOLVES or not movable or not all(e.code in RESOLVABLE for e in movable):
            break
        tightened = replace(report, errors=movable)
        problem = problem.with_tightening(tightening_from(tightened, problem, solution, plan))
        found = solve_pinned(problem, pins, near=NEAR)
        if found is None:
            break
        solution, pins = found
    return fallback


def _close_fits(session: Session, ctx: SwapContext, *, skip: set[int], count: int) -> list[_Fit]:
    """Up to `count` close fits, each a different recipe, closest first."""
    out: list[_Fit] = []
    offer = set(ctx.pins.offer) - skip
    pins = replace(ctx.pins, rebalance=True)
    while len(out) < count and offer:
        found = solve_pinned(ctx.problem, replace(pins, offer=frozenset(offer)), near=NEAR)
        if found is None:
            break
        solution, pins = found
        version = filled(solution, pins).version_id
        offer.discard(version)
        if (fit := close_fit(session, ctx, version)) is not None:
            out.append(fit)
    return out


def _allowing(
    ctx: SwapContext,
    *,
    solution: SolverSolution,
    pins: Pins,
    plan: RoundedPlan,
    report: ValidationReport,
    reference: ReferenceData,
    kept: frozenset[int],
) -> _Fit | None:
    """The plan with what it goes past allowed: calories as the plan's allowances, a cook day's minutes added
    to that day. None when any of it is past NEAR, or the plan still fails its check."""
    c = plan.constraints
    allowances = list(c.kcal_allowances)
    minutes: dict[date, int] = {}
    lines: list[str] = []
    distance = 0
    for e in report.errors:
        amount = e.amount or 0
        if amount > (NEAR.minutes if e.code == "COOK_TIME_OVER" else NEAR.kcal):
            return None
        day = f"{e.day:%A}'s" if e.day is not None else "the plan's"
        if e.code == "COOK_TIME_OVER" and e.day is not None:
            minutes[e.day] = minutes.get(e.day, 0) + amount
            lines.append(f"+{amount} min cook time on {e.day:%A}")
            distance += NEAR_MINUTE_KCAL * amount
            continue
        over = e.code in ("KCAL_DAY_OVER_CEILING", "KCAL_WEEK_OVER_CEILING")
        allowances.append(KcalAllowance(day=e.day, over=amount if over else 0, under=0 if over else amount))
        lines.append(f"+{amount} kcal over {day} calories" if over else f"{amount} kcal under {day} calories")
        distance += amount
    days = []
    for d in c.days:
        extra = minutes.get(d.day, 0)
        if d.cook_minutes_available + extra > MAX_COOK_MINUTES:
            return None
        days.append(d.model_copy(update={"cook_minutes_available": d.cook_minutes_available + extra}))
    allowed = c.model_copy(update={"kcal_allowances": tuple(allowances), "days": tuple(days)})
    plan = replace(plan, constraints=allowed)
    checked = validate_plan(plan, reference, kept=kept)
    if not checked.ok:
        return None
    changes = (*lines, *_rebalanced(ctx, plan))
    return _Fit(solution, pins, plan, checked, close=True, changes=changes, distance=distance)


def close_fit_note(ctx: SwapContext, fit: _Fit) -> str:
    """The plan's note for a close fit you picked: 'You swapped Thu 15 dinner for a close fit: +80 kcal over
    Thursday's calories.'"""
    label = view.meal_label(ctx.slot[0], ctx.slot[1], with_date=True)
    return f"You swapped {label} for a close fit: {'; '.join(fit.changes)}."


def _rebalanced(ctx: SwapContext, plan: RoundedPlan) -> list[str]:
    """A close fit's other batches whose portions moved: 'Fri 16's Chicken curry: portions 4% smaller, to
    balance the calories'."""
    lines = []
    for b in plan.batches:
        kept = ctx.pins.batches.get((b.version_id, b.cook_on, b.portion_size.value))
        if kept is None or kept.cooked or abs(b.nudge - kept.nudge) < SHIFT_SHOWN:
            continue
        pct = int((abs(b.nudge - kept.nudge) / kept.nudge * 100).quantize(Decimal(1), ROUND_HALF_UP)) or 1
        way = "smaller" if b.nudge < kept.nudge else "larger"
        lines.append(
            f"{view.short_day(b.cook_on)}'s {b.title}: portions {pct}% {way}, to balance the calories"
        )
    return lines


# ---------------- Write a new one ----------------
def write_new(ctx: SwapContext, generator: IdeaCandidates) -> list[int]:
    """One ideas call for this meal (F20); every passing idea is saved and joins your pool. Raises the LLM's
    errors (a wait too long, the daily allowance) for the stream to report."""
    generator.generate(ctx.problem, [Gap(ctx.slot[1], IDEAS_PER_CALL, "swap")])
    return list(generator.created)


# ---------------- apply ----------------
@dataclass
class SwapResult:
    plan: MealPlan
    undo_plan_id: int
    plan_meal_id: int
    also_changed: list[str]


def _round_and_check(
    session: Session,
    user_id: int,
    problem: PlanningProblem,
    pins: Pins,
    solution: SolverSolution,
    *,
    failed: str,
) -> tuple[RoundedPlan, Any, SolverSolution]:
    """Round, validate and, when rounding pushed a day past a limit, re-solve with the bound tightened (as the
    planner does), keeping the pins. `failed` starts the message when it can't fit."""
    for resolves in range(MAX_RESOLVES + 1):
        solution = _restore_cooked(solution, pins)
        exact, nudge_only = kept_indices(solution, pins)
        plan = build_rounded_plan(problem, solution, kept=exact, keep_nudge=nudge_only)
        reference = load_reference(
            session, user_id, problem.constraints, [b.version_id for b in plan.batches]
        )
        report = validate_plan(plan, reference, kept=frozenset(exact))
        if report.ok:
            return plan, report, solution
        if not report.resolvable or resolves == MAX_RESOLVES:
            raise SwapError(f"{failed}: " + "; ".join(e.message for e in report.errors[:3]))
        problem = problem.with_tightening(tightening_from(report, problem, solution, plan))
        found = solve_pinned(problem, pins)
        if found is None:
            raise SwapError(f"{failed}.")
        solution, pins = found
    raise AssertionError("unreachable")


def _carry_check_offs(session: Session, old_plan_id: int, new_plan_id: int) -> None:
    """The new list keeps the old one's state and check-offs, item by item (same ingredient)."""
    old = _grocery_list(session, old_plan_id)
    new = _grocery_list(session, new_plan_id)
    if old is None or new is None:
        return
    old_items = list(
        session.scalars(select(GroceryListItem).where(GroceryListItem.grocery_list_id == old.id))
    )
    by_ingredient: dict[int, GroceryListItem] = {}
    for item in old_items:
        by_ingredient.setdefault(item.ingredient_id, item)
    new_items = list(
        session.scalars(select(GroceryListItem).where(GroceryListItem.grocery_list_id == new.id))
    )
    for item in new_items:
        before = by_ingredient.get(item.ingredient_id)
        if before is None:
            continue
        item.checked_at = before.checked_at
        item.purchased_quantity = before.purchased_quantity
        item.actual_price_cents = before.actual_price_cents
    buying = any(
        (i.reason or {}).get("kind") == "buy" and i.to_buy_quantity > 0 and i.checked_at is None
        for i in new_items
    )
    new.status = "open" if old.status == "done" and buying else old.status
    session.flush()


def _copy_statuses(session: Session, batches: list[PlanCookBatch], new_plan_id: int) -> None:
    """Cooked batches stay cooked in the new version."""
    status = {
        (b.recipe_version_id, b.cook_on, b.portion_size): b.status for b in batches if b.status != "planned"
    }
    for b in session.scalars(select(PlanCookBatch).where(PlanCookBatch.meal_plan_id == new_plan_id)):
        b.status = status.get((b.recipe_version_id, b.cook_on, b.portion_size), b.status)
    session.flush()


def _replace_plan(session: Session, old: MealPlan, new: MealPlan) -> None:
    """The new version takes the old one's place: its status, acceptance and search."""
    status = old.status
    old.status = "superseded"
    session.flush()  # one active plan per week at a time
    new.status = status
    new.accepted_at = old.accepted_at
    new.supersedes_plan_id = old.id
    for search in session.scalars(select(CookSearch).where(CookSearch.meal_plan_id == old.id)):
        search.meal_plan_id = new.id
    session.flush()


def _save_version(
    session: Session,
    user_id: int,
    old: MealPlan,
    batches: list[PlanCookBatch],
    plan: RoundedPlan,
    *,
    report: Any,
    problem: PlanningProblem,
    saved: PlanConstraints,
    marker: dict[str, Any],
    extra_notes: tuple[str, ...] = (),
) -> MealPlan:
    """Save the re-solved plan as the new version of `old`: the old one's notes (plus a package a new batch
    absorbs, and `extra_notes`), status, acceptance and search; cooked batches stay cooked and check-offs
    carry over; exposures under a swap run. `marker` (totals["swap"]) is what Undo reads."""
    old_notes = list((old.validation_report or {}).get("notes", []))
    dropped = set(exclusion_notes(problem))
    absorbed = [n for n in plan.notes if n not in dropped and n not in old_notes and "scaled up" in n]
    notes = (*old_notes, *absorbed, *extra_notes)
    plan = replace(plan, constraints=saved, notes=notes, solver_status=old.solver_status)
    run = GenerationRun(user_id=user_id, purpose=SWAP, status="succeeded", started_at=datetime.now(UTC))
    session.add(run)
    session.flush()
    new = save_plan(session, user_id, plan, report, run.id, kind=old.kind)
    run.finished_at = datetime.now(UTC)
    _replace_plan(session, old, new)
    _copy_statuses(session, batches, new.id)
    _carry_check_offs(session, old.id, new.id)
    new.totals = {**new.totals, "swap": marker}
    log_exposures(session, run.id, new.id, problem, plan)
    session.flush()
    return new


def apply_swap(
    session: Session,
    user_id: int,
    plan_id: int,
    meal_id: int,
    version_id: int,
    *,
    today: date,
    allow_buying: bool = False,
    offered: list[int] | None = None,
    swapped_away: list[int] | None = None,
    close: bool = False,
) -> SwapResult:
    """`offered`: the options the sheet showed, in order; `swapped_away`: recipes already swapped away for
    this meal (both for the meal_swapped event). `close`: the option was a close fit (B); the new plan keeps
    what it goes past (its calorie allowance or the cook day's minutes) and says so in its notes. The fit is
    found and checked exactly as the sheet did, so an option it showed applies."""
    try:
        ctx = swap_context(session, user_id, plan_id, meal_id, today=today, allow_buying=allow_buying)
        if version_id not in ctx.pins.offer:
            raise SwapError(NO_LONGER_FITS)
        fit = close_fit(session, ctx, version_id) if close else exact_fit(session, ctx, version_id)
    except PinError as exc:
        raise SwapError(PLAN_AGAIN) from exc
    if fit is None:
        raise SwapError(NO_LONGER_FITS)
    plan, solution = fit.plan, fit.solution
    lines = [*also_changed(ctx, solution), *fit.changes]
    saved = ctx.saved
    if close:  # what the close fit goes past stays with the plan, so its later checks and swaps keep it
        allowed = plan.constraints
        saved = saved.model_copy(update={"kcal_allowances": allowed.kcal_allowances, "days": allowed.days})
    marker = {
        "kind": "meal",
        "from_plan_id": ctx.plan.id,
        "plan_meal": [ctx.slot[0].isoformat(), ctx.slot[1].value],
    }
    new = _save_version(
        session,
        user_id,
        ctx.plan,
        ctx.batches,
        plan,
        report=fit.report,
        problem=ctx.problem,
        saved=saved,
        marker=marker,
        extra_notes=(close_fit_note(ctx, fit),) if close and fit.changes else (),
    )
    meal_row = session.scalars(
        select(PlanMeal).where(
            PlanMeal.meal_plan_id == new.id,
            PlanMeal.eat_on == ctx.slot[0],
            PlanMeal.slot == ctx.slot[1].value,
        )
    ).one()
    recipe_id = ctx.problem.candidate(version_id).recipe_id
    session.add(
        FeedbackEvent(
            user_id=user_id,
            event_type=FeedbackEventType.MEAL_SWAPPED.value,
            occurred_at=datetime.now(UTC),
            recipe_id=recipe_id,
            recipe_version_id=version_id,
            plan_meal_id=meal_row.id,
            payload=SwappedPayload(
                from_plan_id=ctx.plan.id,
                to_plan_id=new.id,
                eat_on=ctx.slot[0].isoformat(),
                slot=ctx.slot[1].value,
                from_version_id=ctx.current_version,
                to_version_id=version_id,
                offered_version_ids=list(offered or [version_id]),
                swapped_away_version_ids=sorted(swapped_away or []),
                also_changed=lines,
                after_shopping=ctx.after_shopping,
            ).model_dump(mode="json"),
            payload_version=SWAPPED_PAYLOAD_VERSION,
        )
    )
    session.flush()
    return SwapResult(new, ctx.plan.id, meal_row.id, lines)


# ---------------- Also update this week's plan (AA8) ----------------
@dataclass
class VersionResult:
    plan: MealPlan
    undo_plan_id: int
    message: str
    also_changed: list[str]


def batch_for_update(
    session: Session, user_id: int, batch_id: int, *, today: date
) -> tuple[PlanCookBatch, MealPlan, str | None]:
    """A plan batch, its plan, and why it can't switch to another version (None: it can)."""
    batch = session.get(PlanCookBatch, batch_id)
    plan = session.get(MealPlan, batch.meal_plan_id) if batch is not None else None
    if batch is None or plan is None or plan.user_id != user_id:
        raise PlanNotFoundError(f"cook batch {batch_id} not found")
    when = view.short_day(batch.cook_on)
    if batch.status != "planned":
        return batch, plan, f"{when}'s batch is already cooked, so it keeps the recipe it was cooked with."
    if plan.status not in LIVE_STATUSES or plan.kind == SINGLE:
        return batch, plan, "This plan was replaced, so it keeps its recipes."
    if batch.cook_on < today:
        return batch, plan, f"{when}'s cooking day has passed, so this plan keeps its recipe."
    return batch, plan, None


def use_version(
    session: Session, user_id: int, batch_id: int, version_id: int, *, today: date
) -> VersionResult:
    """Switch one batch of a plan (and every meal it feeds) to another version of its recipe: your edited
    version (AA8). The batch's portion size may be re-solved within the plan's ±nudge so the days it feeds
    stay inside your limits; every other batch and meal stays exactly as it was. Saved as a new version of the
    plan, which Undo brings back. Raises SwapError saying why when it can't fit."""
    batch, plan, why_not = batch_for_update(session, user_id, batch_id, today=today)
    if why_not is not None:
        raise SwapError(why_not)
    old_version = session.get(RecipeVersion, batch.recipe_version_id)
    new_version = session.get(RecipeVersion, version_id)
    if new_version is None or old_version is None or new_version.recipe_id != old_version.recipe_id:
        raise PlanNotFoundError(f"recipe version {version_id} not found for this batch")
    if version_id == batch.recipe_version_id:
        raise SwapError("This batch already uses that version.")
    try:
        loaded = _load(session, user_id, plan, allow_buying=True, slot=None, extra=frozenset({version_id}))
    except PinError as exc:
        raise SwapError(PLAN_AGAIN) from exc
    if version_id not in {r.version_id for r in loaded.problem.candidates}:
        reasons = next((e.reasons for e in loaded.problem.excluded if e.version_id == version_id), ())
        raise SwapError(
            "Your version can't be planned: " + "; ".join(reasons or ("it breaks one of your rules",))
        )
    old_key = loaded.key_of[batch.id]
    new_key = (version_id, batch.cook_on, batch.portion_size)
    kept = {k: b for k, b in loaded.kept.items() if k != old_key}
    meals = {
        (m.eat_on, MealSlot(m.slot)): new_key
        if m.cook_batch_id == batch.id
        else loaded.key_of[m.cook_batch_id]
        for m in loaded.meals
        if m.cook_batch_id is not None
    }
    pins = Pins(None, None, meals, kept, frozenset(), today, added=frozenset({new_key}))
    title = new_version.title
    failed = f"With your version, {view.short_day(batch.cook_on)}'s {title} doesn't fit this week's limits"
    try:
        found = solve_pinned(loaded.problem, pins)
        if found is None:
            raise SwapError(_why_version_cant(loaded.problem, batch, version_id, failed))
        solution, pins = found
        rounded, report, solution = _round_and_check(
            session, user_id, loaded.problem, pins, solution, failed=failed
        )
    except PinError as exc:
        raise SwapError(PLAN_AGAIN) from exc
    marker = {"kind": "version", "from_plan_id": plan.id, "batch_id": batch.id, "version_id": version_id}
    new = _save_version(
        session,
        user_id,
        plan,
        loaded.batches,
        rounded,
        report=report,
        problem=loaded.problem,
        saved=loaded.saved,
        marker=marker,
    )
    after = next(b for b in solution.batches if (b.version_id, b.cook_on, b.portion_size.value) == new_key)
    line = f"{view.short_day(batch.cook_on)}'s {title} uses your version"
    if after.nudge != loaded.kept[old_key].nudge:
        line += ", its portions adjusted to keep your calories in range"
    return VersionResult(new, plan.id, f"Updated this week's plan: {line}.", [line])


def _why_version_cant(problem: PlanningProblem, batch: PlanCookBatch, version_id: int, failed: str) -> str:
    """What the new version does to a portion, so the message says why no portion size fits."""
    recipe = problem.candidate(version_id)
    size = size_multiplier(PortionSize(batch.portion_size))
    kcal = kcal_display(recipe.kcal * size)
    protein = (recipe.protein_g * size).quantize(Decimal("0.1"), ROUND_HALF_UP)
    nudge = problem.constraints.portion_nudge_pct
    return (
        f"{failed}: a portion would be about {kcal} kcal and {protein} g protein, and no portion size within "
        f"{nudge:g}% keeps the days it feeds inside your calorie and protein limits. This plan keeps the "
        "recipe as it was; your version is used from your next plan."
    )


# ---------------- undo ----------------
def undo_swap(session: Session, user_id: int, plan_id: int) -> MealPlan:
    """The version before the swap, back exactly as it was. Refused once you've cooked or shopped since."""
    new = session.get(MealPlan, plan_id)
    if new is None or new.user_id != user_id:
        raise PlanNotFoundError(f"plan {plan_id} not found")
    swap = (new.totals or {}).get("swap")
    if not swap or new.supersedes_plan_id is None or new.status not in LIVE_STATUSES:
        raise SwapError("There's no swap to undo on this plan.")
    old = session.get(MealPlan, new.supersedes_plan_id)
    if old is None or old.status != "superseded":
        raise SwapError("The plan before this swap isn't there to bring back.")
    old_cooked = {
        (b.recipe_version_id, b.cook_on, b.portion_size)
        for b in session.scalars(select(PlanCookBatch).where(PlanCookBatch.meal_plan_id == old.id))
        if b.status != "planned"
    }
    new_cooked = {
        (b.recipe_version_id, b.cook_on, b.portion_size)
        for b in session.scalars(select(PlanCookBatch).where(PlanCookBatch.meal_plan_id == new.id))
        if b.status != "planned"
    }
    new_list, old_list = _grocery_list(session, new.id), _grocery_list(session, old.id)
    if new_cooked - old_cooked or (
        new_list is not None
        and old_list is not None
        and new_list.status == "done"
        and old_list.status != "done"
    ):
        raise SwapError(
            "You've cooked or shopped since this swap, so it can't be undone. Swap the meal again."
        )
    status = new.status
    new.status = "superseded"
    session.flush()
    old.status = status
    for search in session.scalars(select(CookSearch).where(CookSearch.meal_plan_id == new.id)):
        search.meal_plan_id = old.id
    _carry_check_offs(session, new.id, old.id)
    event = session.scalars(
        select(FeedbackEvent)
        .where(
            FeedbackEvent.user_id == user_id,
            FeedbackEvent.event_type == FeedbackEventType.MEAL_SWAPPED.value,
            FeedbackEvent.payload["to_plan_id"].as_integer() == new.id,
        )
        .order_by(FeedbackEvent.id.desc())
    ).first()
    if event is not None:
        payload = SwappedPayload.model_validate({**event.payload, "undone": True})
        session.add(
            FeedbackEvent(
                user_id=user_id,
                event_type=FeedbackEventType.MEAL_SWAPPED.value,
                occurred_at=datetime.now(UTC),
                recipe_id=event.recipe_id,
                recipe_version_id=event.recipe_version_id,
                plan_meal_id=event.plan_meal_id,
                payload=payload.model_dump(mode="json"),
                payload_version=SWAPPED_PAYLOAD_VERSION,
            )
        )
    session.flush()
    return old


# ---------------- the options stream (NDJSON) ----------------
NOTE_NOT_SET_UP = "Writing new recipes isn't set up ({reason}), so these come from your saved ones."
NOTE_FAILED = "I couldn't write a new one just now. These are from your saved recipes."
NOTE_DAILY = "That's today's new-recipe allowance; back tomorrow."
STAGES = {
    "finding": "Finding meals that fit",
    "generating": "Writing a new one",
    "waiting": "The recipe service needs a short breather",
    "checking": "Checking calories, cook time and groceries",
}


def swap_option_events(
    session_factory: Callable[[], Session],
    user_id: int,
    plan_id: int,
    meal_id: int,
    body: SwapOptionsIn,
    *,
    client_factory: ClientFactory | None,
    clock: LLMClock | None = None,
    settings: Settings | None = None,
    heartbeat_s: float = HEARTBEAT_SECONDS,
) -> Iterator[str]:
    access = access_for(client_factory, clock, settings)

    def work(session: Session, user: AppUser, emit: Emit, checkpoint: Callable[[], None]) -> dict[str, Any]:
        emit({"event": "started", "plan_id": plan_id, "meal_id": meal_id, "run_id": None})

        def stage(name: str, **extra: Any) -> None:
            emit({"event": "progress", "stage": name, "message": STAGES[name], **extra})

        stage("finding")
        today = search_service.local_now(user).date()  # the Cook flow's clock, as meal prep
        exclude = frozenset(body.exclude_version_ids)

        def context() -> SwapContext:
            return swap_context(
                session,
                user.id,
                plan_id,
                meal_id,
                today=today,
                exclude=exclude,
                allow_buying=body.allow_buying,
            )

        try:
            ctx = context()
        except (SwapError, PinError, PlanNotFoundError) as exc:
            return _failed(exc)
        client, reason = access.client() if access is not None else (None, "no LLM client is configured")
        common: dict[str, Any] = {"can_write_new": client is not None, "llm_call_count": 0, "total_tokens": 0}
        notes: list[str] = []
        new_ids: list[int] = []
        if body.allow_llm:
            if client is None or access is None:
                notes.append(NOTE_NOT_SET_UP.format(reason=reason))
            else:
                run = GenerationRun(
                    user_id=user.id, purpose=SWAP, status="running", started_at=datetime.now(UTC)
                )
                session.add(run)
                session.flush()
                common["run_id"] = run.id
                stage("generating")
                deadline = Deadline.after(access.clock, access.settings.plan_time_budget_seconds)
                llm = access.context(
                    session,
                    client,
                    run.id,
                    deadline=deadline,
                    on_wait=lambda seconds: stage("waiting", wait_s=wait_seconds(seconds)),
                )
                try:
                    new_ids = write_new(ctx, IdeaCandidates(session, user.id, llm))
                    run.status = "succeeded"
                except LLMWaitTooLongError as exc:
                    run.status = "failed"
                    common |= {"status": "waiting", "retry_after_s": wait_seconds(exc.retry_after_s)}
                except LLMBudgetExceededError:
                    run.status = "failed"
                    notes.append(NOTE_DAILY)
                    common["can_write_new"] = False
                except LLMError as exc:
                    log.info("swap's ideas call failed: %s", exc)
                    run.status = "failed"
                    notes.append(NOTE_FAILED)
                run.finished_at = datetime.now(UTC)
                common |= {"llm_call_count": run.llm_call_count, "total_tokens": run.total_tokens}
                checkpoint()  # the new ideas are saved whatever happens next
                if common.get("status") == "waiting":
                    return {**common, "current": current_meal(ctx), "notes": notes}
                if new_ids:
                    ctx = context()  # the pool now holds the new ideas
        stage("checking")
        try:
            result = find_options(session, ctx, new_ids=frozenset(new_ids))
        except PinError as exc:
            return _failed(exc)
        return {
            **common,
            "status": "succeeded" if result.options else "none_fit",
            "current": current_meal(ctx),
            "options": result.options,
            "no_fit": result.no_fit,
            "after_shopping": ctx.after_shopping,
            "new_version_ids": new_ids,
            "notes": notes,
        }

    def on_crash(
        session: Session, user: AppUser, known: dict[str, int], problem: dict[str, Any]
    ) -> dict[str, Any]:
        return {}

    return stream_events(
        session_factory,
        user_id,
        work,
        on_crash,
        SwapStreamEvent,
        ids={"plan_id": plan_id, "meal_id": meal_id, "run_id": None},
        heartbeat_s=heartbeat_s,
        name="swap-options",
        crash_title="I couldn't find other meals just now",
    )


def _failed(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, PinError):
        return {"status": "failed", "problem": problem_json("Can't swap this meal", PLAN_AGAIN, status=409)}
    status = 404 if isinstance(exc, PlanNotFoundError) else 409
    return {"status": "failed", "problem": problem_json("Can't swap this meal", str(exc), status=status)}
