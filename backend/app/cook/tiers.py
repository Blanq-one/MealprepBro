"""Budget tier cards for meal prep's shopping step (step 2b.6, AA6, AA8; four tiers since its approval).

Four cards for this week, Broke mode, Cheapest, A bit better and Fancy, each with its estimated regular
groceries, the stock-up items apart (rice, oil, spices: they last many weeks), and protein. To stay well
inside the request's time, a card's numbers come from a quick solve: the week's MILP on the shortlist (the
best few recipes per meal), saved recipes only (no LLM), one solve with a short time limit and a loose gap,
the cook days held to their linear limits (the exact schedules, rounding, the validator and the saved plan
come only with the full solve of the tier you tap). So a card says "about": its regular total is the solver's
own estimate of the whole-package cash, a stock-up item's the whole packs you'd pay for at the register, and
its protein the planned portions'. A plan of some of your meals says what share of your day's protein it
covers (item 3): "Lunch + dinner: about 76 g of your 100 g daily target".
"""

import math
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

import pulp
from sqlalchemy.orm import Session

from app.cook.answers import SLOT_LABELS
from app.cook.prep import PrepAnswersError, PrepPlan, resolve_prep
from app.domain.cost import money_display
from app.domain.enums import MealSlot
from app.domain.price_tiers import (
    BLURBS,
    LABELS,
    MAX_PORTIONS,
    RANK,
    IngredientTier,
    PriceTier,
    upgrade_slots,
)
from app.llm.pacing import Deadline, SystemClock
from app.planning.constraint_builder import ConstraintError
from app.planning.inputs import constraints_for
from app.planning.loader import build_problem
from app.planning.post_solve import rounding_fit
from app.planning.problem import PlanningProblem, Tightening
from app.planning.shortlist import shortlist
from app.planning.solver import diagnostics
from app.planning.solver.backend import SolveBudget, SolveDeadlineError, solve_budget
from app.planning.solver.model import SolverSolution, _Model, build_model, extract, run_solver
from app.schemas.cook import CookAnswers
from app.schemas.settings import UserSettings
from app.services.settings import load_settings

TIER_SOLVE_LIMIT_S = 15  # each card's solve (A bit better and Fancy need the time on a full week)
TIER_GAP_REL = 0.05  # within 5% is close enough for "about"
# and within one point (about 70 cents at the cost-first weights): the cards' first build stopped within 100
# points, nearly the first plan found, so the tiers came out about the same (2b.6 approval, item 2)
TIER_GAP_ABS = 1.0
ESTIMATE_WIDER = 10  # recipes a meal on the second try
TIERS_BUDGET_S = 90  # all four cards
OUT_OF_TIME = "There wasn't time to price this one; tap it to plan it anyway."
BOUGHT_EPSILON = 1e-6


@dataclass(frozen=True)
class TierCard:
    tier: PriceTier
    label: str  # "Cheapest"
    blurb: str  # what it buys
    status: Literal["estimated", "none_fits", "not_priced"]  # not_priced: ran out of time; still pickable
    total_cents: int | None = None  # regular groceries
    total_display: str | None = None  # "about $54.20"
    protein_per_day_display: str | None = (
        None  # "about 104 g protein a day", "Lunch + dinner: about 76 g of …"
    )
    reason: str | None = None  # why none fits
    stock_up_cents: int | None = None  # stock-up items, apart (what you'd pay for their whole packs)
    stock_up_display: str | None = None  # "+ about $6.98 stock-up: rice, olive oil"
    protein_per_day_g: int | None = None
    includes_display: str | None = None  # "4 meals with an upgrade · up to 4 of one recipe a week"


def _none(tier: PriceTier, reason: str) -> TierCard:
    return TierCard(tier, LABELS[tier], BLURBS[tier], "none_fits", reason=reason)


def _unpriced(tier: PriceTier) -> TierCard:
    """No estimate in time: the card says so and can still be picked (the full plan has its own time)."""
    return TierCard(tier, LABELS[tier], BLURBS[tier], "not_priced", reason=OUT_OF_TIME)


def _value(var: object) -> float:
    v = pulp.value(var)
    return float(v) if v is not None else 0.0


def split_cost(problem: PlanningProblem, model: _Model) -> tuple[int, int, list[str]]:
    """(regular groceries, stock-up items, the stock-up items' names) of a solved model, in cents. Regular
    items are the solver's whole-package cash; a stock-up item is what its whole packs cost at the register
    (the pack that is cheapest per unit, as the grocery list buys it)."""
    regular = Decimal(0)
    stock = Decimal(0)
    names: list[str] = []
    stores = set(problem.constraints.store_ids)
    for ingredient_id, (bought, cost) in sorted(model.purchases.items()):
        amount = _value(bought)
        if amount <= BOUGHT_EPSILON:
            continue
        plan = problem.ingredients[ingredient_id]
        if not plan.stock_up:
            regular += Decimal(str(_value(cost)))
            continue
        offers = [o for o in plan.offers if o.store_id in stores]
        if not offers:
            continue
        best = min(offers, key=lambda o: o.cents_per_unit)
        if best.package_amount is not None and best.package_cents is not None:
            stock += (
                math.ceil(Decimal(str(amount)) / best.package_amount - Decimal("1e-9")) * best.package_cents
            )
        else:
            stock += Decimal(str(amount)) * best.cents_per_unit
        names.append(plan.name)
    cents = int(regular.quantize(Decimal(1), ROUND_HALF_UP)), int(stock.quantize(Decimal(1), ROUND_HALF_UP))
    return cents[0], cents[1], names


def protein_line(grams: int, plan: PrepPlan, settings: UserSettings) -> str:
    """'about 104 g protein a day'; for some of your meals, the share of your day's target they carry:
    'Lunch + dinner: about 76 g of your 100 g daily target' (item 3)."""
    planned = {a.slot for a in settings.slot_allocations}
    if set(plan.slots) >= planned or not settings.daily_protein_target_g:
        return f"about {grams} g protein a day"
    order = list(MealSlot)
    labels = [SLOT_LABELS[s] for s in sorted(plan.slots, key=order.index)]
    meals = " + ".join([labels[0], *(label.lower() for label in labels[1:])])
    return f"{meals}: about {grams} g of your {settings.daily_protein_target_g} g daily target"


def includes_line(tier: PriceTier, problem: PlanningProblem, solution: SolverSolution) -> str:
    """What the tier's week includes besides its price: its upgrades as planned, and its variety rule."""
    c = problem.constraints
    counted = upgrade_slots(s for d in c.days for s in d.slots)
    meals = [
        problem.candidate(solution.batches[m.batch_index].version_id)
        for m in solution.meals
        if m.slot in counted
    ]
    better = RANK[IngredientTier.BETTER]
    variety = f"up to {MAX_PORTIONS[tier]} of one recipe a week"
    if tier is PriceTier.BROKE:
        return f"Repeats are fine ({variety}) · stock-up only when needed"
    if tier is PriceTier.CHEAPEST:
        return variety[0].upper() + variety[1:]
    if tier is PriceTier.BETTER:
        n = sum(1 for r in meals if r.tier_rank >= better)
        return f"{n} meal{'s' if n != 1 else ''} with an upgrade · {variety}"
    n = sum(1 for r in meals if r.premium_protein)
    return f"{n} meal{'s' if n != 1 else ''} with salmon, shrimp or similar · {variety}"


def stock_up_line(cents: int, names: list[str]) -> str | None:
    """'+ about $6.98 stock-up: rice, olive oil' (None when the week buys none)."""
    if cents <= 0:
        return None
    shown = ", ".join(names[:3]) + (f" and {len(names) - 3} more" if len(names) > 3 else "")
    return f"+ about {money_display(cents)} stock-up: {shown}"


def estimate(
    session: Session, user_id: int, answers: CookAnswers, tier: PriceTier, *, today: date
) -> TierCard:
    """One card: the tier's quick solve for this week."""
    answers = answers.model_copy(
        update={"price_tier": tier, "shopping": "make_a_list", "budget_cents": None, "allow_llm": False}
    )
    settings = load_settings(session, user_id)
    try:
        plan = resolve_prep(answers, settings, today)
        constraints = constraints_for(session, user_id, plan.request, today=today)
    except (PrepAnswersError, ConstraintError) as exc:
        return _none(tier, str(exc))
    problem = build_problem(session, user_id, constraints)
    if not problem.candidates:
        return _none(tier, f"None of your recipes fit the {LABELS[tier]} tier with what you have.")
    if pre := diagnostics.precheck(problem):
        return _none(tier, pre[0].message)
    kcal, protein = rounding_fit(problem), rounding_fit(problem, "protein_g")
    problem = problem.with_tightening(
        Tightening(
            kcal_bias=kcal.bias, protein_bias=protein.bias, kcal_scale=kcal.scale, protein_scale=protein.scale
        )
    )
    solution = None
    model = None
    timed_out = False
    # the wide shortlist (10 recipes a meal: the narrow one left Cheapest pricier than A bit better), then
    # every eligible recipe, as the planner does before it says no plan fits (a tier's upgrades can need
    # recipes the shortlist doesn't rank high)
    for per_slot in (ESTIMATE_WIDER, None):
        short = shortlist(problem, per_slot) if per_slot is not None else problem
        model = build_model(short)
        status = run_solver(model, TIER_SOLVE_LIMIT_S, TIER_GAP_REL, TIER_GAP_ABS)
        if status in (pulp.LpSolutionOptimal, pulp.LpSolutionIntegerFeasible):
            solution = extract(short, model, status)
            problem = short
            break
        timed_out = timed_out or status != pulp.LpSolutionInfeasible  # stopped before it found one
    if solution is None or model is None:
        if timed_out:
            return _unpriced(tier)
        return _none(tier, f"No week fits your limits with the {LABELS[tier]} tier's groceries.")
    regular, stock, names = split_cost(problem, model)
    eaten = sum(
        (
            problem.candidate(solution.batches[m.batch_index].version_id).protein_g
            * solution.batches[m.batch_index].multiplier
            for m in solution.meals
        ),
        Decimal(0),
    )
    per_day = int((eaten / len(problem.constraints.days)).quantize(Decimal(1), ROUND_HALF_UP))
    return TierCard(
        tier,
        LABELS[tier],
        BLURBS[tier],
        "estimated",
        total_cents=regular,
        total_display=f"about {money_display(regular)}",
        protein_per_day_display=protein_line(per_day, plan, settings),
        stock_up_cents=stock,
        stock_up_display=stock_up_line(stock, names),
        protein_per_day_g=per_day,
        includes_display=includes_line(tier, problem, solution),
    )


def tier_cards(session: Session, user_id: int, answers: CookAnswers, *, today: date) -> list[TierCard]:
    """All four cards, inside one time budget (the time guard cuts each solve to what's left)."""
    budget = SolveBudget(Deadline.after(SystemClock(), TIERS_BUDGET_S), reserve_s=0)
    cards = []
    with solve_budget(budget):
        for tier in PriceTier:
            try:
                cards.append(estimate(session, user_id, answers, tier, today=today))
            except SolveDeadlineError:
                cards.append(_unpriced(tier))
    return cards
