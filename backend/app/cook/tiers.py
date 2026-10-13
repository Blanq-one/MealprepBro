"""Budget tier cards for meal prep's shopping step (step 2b.6, AA6, AA8).

Three cards for this week, Cheapest, A bit better and Fancy, each with its estimated total and protein per
day. To stay well inside the request's time, a card's numbers come from a quick solve: the week's MILP on
the shortlist (the best few recipes per meal), saved recipes only (no LLM), one solve with a short time limit
and a loose gap, the cook days held to their linear limits (the exact schedules, rounding, the validator and
the saved plan come only with the full solve of the tier you tap). So a card says "about": its total is the
solver's own estimate of the whole-package cash, and its protein the planned portions'.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

import pulp
from sqlalchemy.orm import Session

from app.cook.prep import PrepAnswersError, resolve_prep
from app.domain.cost import money_display
from app.domain.price_tiers import BLURBS, LABELS, PriceTier
from app.llm.pacing import Deadline, SystemClock
from app.planning.constraint_builder import ConstraintError
from app.planning.inputs import constraints_for
from app.planning.loader import build_problem
from app.planning.post_solve import rounding_fit
from app.planning.problem import Tightening
from app.planning.shortlist import SHORTLIST_PER_SLOT, shortlist
from app.planning.solver import diagnostics
from app.planning.solver.backend import SolveBudget, SolveDeadlineError, solve_budget
from app.planning.solver.model import build_model, extract, run_solver
from app.schemas.cook import CookAnswers
from app.services.settings import load_settings

TIER_SOLVE_LIMIT_S = 6  # each card's one solve
TIER_GAP_REL = 0.05  # within 5% is close enough for "about"
ESTIMATE_WIDER = 10  # recipes a meal on the second try
TIERS_BUDGET_S = 45  # all three cards
OUT_OF_TIME = "There wasn't time to price this one; tap it to plan it anyway."


@dataclass(frozen=True)
class TierCard:
    tier: PriceTier
    label: str  # "Cheapest"
    blurb: str  # what it buys
    status: Literal["estimated", "none_fits"]
    total_cents: int | None = None
    total_display: str | None = None  # "about $54.20"
    protein_per_day_display: str | None = None  # "about 132 g protein a day"
    reason: str | None = None  # why none fits


def _none(tier: PriceTier, reason: str) -> TierCard:
    return TierCard(tier, LABELS[tier], BLURBS[tier], "none_fits", reason=reason)


def estimate(
    session: Session, user_id: int, answers: CookAnswers, tier: PriceTier, *, today: date
) -> TierCard:
    """One card: the tier's quick solve for this week."""
    answers = answers.model_copy(
        update={"price_tier": tier, "shopping": "make_a_list", "budget_cents": None, "allow_llm": False}
    )
    try:
        plan = resolve_prep(answers, load_settings(session, user_id), today)
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
    # the narrow shortlist first, then a wide one: Fancy's variety (3 portions of a recipe a week) can need
    # more recipes than the narrow one holds; on a real week 10 a meal found a plan in 3 s where 6 took 10
    for per_slot in (SHORTLIST_PER_SLOT, ESTIMATE_WIDER):
        short = shortlist(problem, per_slot)
        model = build_model(short)
        status = run_solver(model, TIER_SOLVE_LIMIT_S, TIER_GAP_REL, 100.0)
        if status in (pulp.LpSolutionOptimal, pulp.LpSolutionIntegerFeasible):
            solution = extract(short, model, status)
            problem = short
            break
    if solution is None:
        return _none(tier, f"No week fits your limits with the {LABELS[tier]} tier's groceries.")
    total = solution.estimated_purchase_cents
    eaten = sum(
        (
            problem.candidate(solution.batches[m.batch_index].version_id).protein_g
            * solution.batches[m.batch_index].multiplier
            for m in solution.meals
        ),
        Decimal(0),
    )
    per_day = (eaten / len(problem.constraints.days)).quantize(Decimal(1), ROUND_HALF_UP)
    return TierCard(
        tier,
        LABELS[tier],
        BLURBS[tier],
        "estimated",
        total_cents=total,
        total_display=f"about {money_display(total)}",
        protein_per_day_display=f"about {per_day} g protein a day",
    )


def tier_cards(session: Session, user_id: int, answers: CookAnswers, *, today: date) -> list[TierCard]:
    """All three cards, inside one time budget (the time guard cuts each solve to what's left)."""
    budget = SolveBudget(Deadline.after(SystemClock(), TIERS_BUDGET_S), reserve_s=0)
    cards = []
    with solve_budget(budget):
        for tier in PriceTier:
            try:
                cards.append(estimate(session, user_id, answers, tier, today=today))
            except SolveDeadlineError:
                cards.append(_none(tier, OUT_OF_TIME))
    return cards
