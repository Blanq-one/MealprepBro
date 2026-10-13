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

Since the deploy (AC3–AC6):
  order      the cards are priced in order, Broke mode first, and each one after it starts from the card
             below: its meals eat at least the regular groceries the card below's do, at unit prices (the
             solver's floor, on the food eaten so a surplus bag of rice can't meet it, with a steep price a
             dollar short, so it never stops a week from planning). So a higher tier costs the same or more;
             where package sizes still bring its number under (or within 50 cents of) the number shown below
             it, the card says "Same as Cheapest this week" instead of a lower price. The plan you tap is held
             to the same floor.
  honesty    A bit better and Fancy count the meals that really have an upgrade or a premium protein; short of
             what the tier aims for, the card says why in plain words ("the recipes with them are fancy to
             cook, and none of your cook days allows fancy recipes"), with the fix as a button when there is
             one ("Allow fancy recipes on Saturday"). It never claims meals it doesn't have.
  dead ends  a week no plan can fill says why ("Tue 13's dinner comes before your first cook day (Wed 14)",
             with "Cook on Tuesday too"); "No week fits" only when the solver proves it.
  slow       a card with no estimate in time is "Taking longer than usual", with Try again, never "No week
             fits". The run record (generation_run, purpose tier_cards) says what each card took and which
             happened: a cold start (a database connection that was slow or retried, a function that had just
             started) or the time budget.
  speed      the cards stream one by one, and a card already worked out for the same week, answers, settings
             and data (its inputs' fingerprint) comes from an earlier run record at once.
"""

import hashlib
import json
import logging
import os
import time
from collections import Counter
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, fields, is_dataclass, replace
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from math import ceil
from typing import Any, Literal

import pulp
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cook import search as search_service
from app.cook.answers import SLOT_LABELS
from app.cook.prep import PrepAnswersError, PrepPlan, resolve_prep
from app.cook.stream import HEARTBEAT_SECONDS, SessionFactory, stream_events
from app.db.models import AppUser, GenerationRun
from app.db.session import ConnectLog, count_connects_into
from app.domain.cook_schedule import minutes_text, round_up_5
from app.domain.cook_time import MOOD_ORDER, mood_allows
from app.domain.cost import money_display
from app.domain.enums import MealSlot, RecipeMood
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
from app.planning.problem import CandidateRecipe, ExcludedRecipe, PlanningProblem, Tightening
from app.planning.shortlist import shortlist
from app.planning.solver import diagnostics
from app.planning.solver.backend import SolveBudget, SolveDeadlineError, solve_budget
from app.planning.solver.model import (
    SolverSolution,
    _Model,
    build_model,
    eaten_value,
    extract,
    run_solver,
)
from app.schemas.constraints import PlanConstraints
from app.schemas.cook import CookAnswers, TierCardOut, TierFixOut, TierStreamEvent
from app.schemas.settings import UserSettings
from app.services.settings import load_settings

log = logging.getLogger(__name__)

TIER_SOLVE_LIMIT_S = 15  # each card's solve (A bit better and Fancy need the time on a full week)
TIER_GAP_REL = 0.05  # within 5% is close enough for "about"
# and within one point (about 70 cents at the cost-first weights): the cards' first build stopped within 100
# points, nearly the first plan found, so the tiers came out about the same (2b.6 approval, item 2)
TIER_GAP_ABS = 1.0
ESTIMATE_WIDER = 10  # recipes a meal on the second try
TIERS_BUDGET_S = 90  # all four cards
BOUGHT_EPSILON = 1e-6
TIER_CARDS = "tier_cards"  # generation_run.purpose
SLOW = "Taking longer than usual."  # AC5: a card with no estimate in time
SAME_WITHIN_CENTS = 50  # AC3: a card this close to the one below is "the same" (they're "about" numbers)
# AC6: a card's inputs' fingerprint covers the problem it solved, your settings and answers, and this version
# of the code (bump it when the cards' logic changes); a run record older than this is never reused
ESTIMATE_VERSION = 3
CACHE_HOURS = 12
CACHE_RUNS = 30  # the run records looked at
# AC5: a cold start: a database connection this slow, or retried (Neon waking from scale-to-zero), or a
# function this young when the request came
COLD_CONNECT_S = 2.0
COLD_PROCESS_S = 30.0
Outcome = Literal["estimated", "none_fits", "timed_out"]


@dataclass(frozen=True)
class TierFix:
    """A card's fix (AC4, AC5): a cook day's mood, or its minutes."""

    kind: Literal["mood", "minutes"]
    label: str
    day: date
    mood: RecipeMood | None = None
    minutes: int | None = None


@dataclass(frozen=True)
class TierCard:
    tier: PriceTier
    label: str  # "Cheapest"
    blurb: str  # what it buys
    status: Outcome  # timed_out: no estimate in time; still pickable
    total_cents: int | None = None  # regular groceries
    total_display: str | None = None  # "about $54.20"
    protein_per_day_display: str | None = (
        None  # "about 104 g protein a day", "Lunch + dinner: about 76 g of …"
    )
    reason: str | None = None  # why none fits, or SLOW
    stock_up_cents: int | None = None  # stock-up items, apart (what you'd pay for their whole packs)
    stock_up_display: str | None = None  # "+ about $6.98 stock-up: rice, olive oil"
    protein_per_day_g: int | None = None
    includes_display: str | None = None  # "4 meals with an upgrade · up to 4 of one recipe a week"
    same_as: str | None = None  # AC3: the label of the card it costs the same as ("Cheapest")
    shortfall_display: str | None = None  # AC4: why its upgrades fall short
    fix: TierFix | None = None
    # AC3: the regular groceries its meals were held to eat (the card below's), and what they eat (the next
    # card's floor), in cents at unit prices
    floor_cents: int | None = None
    eaten_cents: int | None = None
    cached: bool = False  # AC6: from an earlier run record

    @property
    def same_as_display(self) -> str | None:
        return f"Same as {self.same_as} this week" if self.same_as else None


@dataclass(frozen=True)
class Priced:
    """One card and what it took, for the run record (which is also the cache)."""

    card: TierCard
    key: str  # its inputs' fingerprint ("" when its answers couldn't form a plan)
    outcome: Outcome
    # none_fits: answers | no_candidates | precheck | uncovered | infeasible; timed_out: solver_limit (a solve
    # stopped on its limit before any plan) | budget (no time left in the request's budget)
    why: str | None = None
    load_s: float = 0.0  # settings, constraints and the problem, from the database
    solves: tuple[dict[str, Any], ...] = ()
    cached_from: int | None = None  # the run record it came from


def _none(tier: PriceTier, reason: str, fix: TierFix | None = None) -> TierCard:
    return TierCard(tier, LABELS[tier], BLURBS[tier], "none_fits", reason=reason, fix=fix)


def _slow(tier: PriceTier) -> TierCard:
    """No estimate in time: "Taking longer than usual" (AC5), with Try again; still pickable."""
    return TierCard(tier, LABELS[tier], BLURBS[tier], "timed_out", reason=SLOW)


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
            stock += ceil(Decimal(str(amount)) / best.package_amount - Decimal("1e-9")) * best.package_cents
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


# ---------------- what a tier includes, honestly (AC4) ----------------


@dataclass(frozen=True)
class Aim:
    """What A bit better or Fancy aims for: meals with an upgraded item, or with a premium protein."""

    wanted: int
    noun: str  # "an upgrade", "salmon, shrimp or similar"
    recipes: str  # "the recipes with one", "the recipes with them"
    none_have: str  # "uses an upgraded item", "has salmon, shrimp or similar"
    counts: Callable[[CandidateRecipe | ExcludedRecipe], bool]


def aim(tier: PriceTier, c: PlanConstraints) -> Aim | None:
    better = RANK[IngredientTier.BETTER]
    if tier is PriceTier.BETTER:
        return Aim(
            c.upgraded_meals_min,
            "an upgrade",
            "the recipes with one",
            "uses an upgraded item",
            lambda r: r.tier_rank >= better,
        )
    if tier is PriceTier.FANCY:
        return Aim(
            c.premium_meals_min,
            "salmon, shrimp or similar",
            "the recipes with them",
            "has salmon, shrimp or similar",
            lambda r: r.premium_protein,
        )
    return None


def _meals(n: int) -> str:
    return f"{n} meal{'s' if n != 1 else ''}"


def counted_meals(problem: PlanningProblem, solution: SolverSolution, target: Aim) -> int:
    """The planned meals (in the tier's counted slots) that have what it aims for."""
    c = problem.constraints
    counted = upgrade_slots(s for d in c.days for s in d.slots)
    return sum(
        1
        for m in solution.meals
        if m.slot in counted and target.counts(problem.candidate(solution.batches[m.batch_index].version_id))
    )


def includes_line(tier: PriceTier, problem: PlanningProblem, solution: SolverSolution) -> str:
    """What the tier's week includes besides its price: its upgrades as planned (never "0 meals with …":
    the shortfall line says why instead, AC4), and its variety rule."""
    variety = f"up to {MAX_PORTIONS[tier]} of one recipe a week"
    if tier is PriceTier.BROKE:
        return f"Repeats are fine ({variety}) · stock-up only when needed"
    target = aim(tier, problem.constraints)
    n = counted_meals(problem, solution, target) if target is not None else 0
    if target is None or n == 0:
        return variety[0].upper() + variety[1:]
    return f"{_meals(n)} with {target.noun} · {variety}"


_OTHER_REASONS = {  # why the recipes a tier aims for were left out, in plain words (AC4)
    "equipment": "need equipment you don't have",
    "excluded": "use a food you don't eat",
    "held": "use an item on hold (it may be beef-derived)",
    "frequency_cap": "use a food whose weekly cap is 0",
    "unpriced": "use an item with no price at your stores",
    "tier": "need items this tier doesn't buy",
    "nutrition_incomplete": "use an item with incomplete nutrition data",
    "conversion": "use an item I can't measure for buying",
}


def _pick_day(c: PlanConstraints, mood: RecipeMood | None, minutes: int | None) -> tuple[date, int] | None:
    """The cook day a fix goes on: one whose mood allows `mood` (any day for None) and whose minutes fit,
    else the longest such day; the most minutes first, a weekend day on a tie, then the earliest."""
    days = [d for d in c.days if d.is_cook_day and (mood is None or mood_allows(d.mood, mood))]
    if not days:
        return None
    fits = [d for d in days if minutes is None or d.cook_minutes_available >= minutes] or days
    best = max(fits, key=lambda d: (d.cook_minutes_available, d.day.weekday() >= 5, -d.day.toordinal()))
    return best.day, best.cook_minutes_available


def shortfall(
    tier: PriceTier, full: PlanningProblem, problem: PlanningProblem, solution: SolverSolution
) -> tuple[str | None, TierFix | None]:
    """Why A bit better or Fancy has fewer of its upgrades than it aims for, and the fix (AC4): the recipes
    that have them are left out only by a cook day's mood ("Allow fancy recipes on Saturday") or minutes
    ("Allow 55 min on Saturday"), by something else, or don't exist for these meals; or they exist but
    more don't fit the week. `full` is the tier's problem before the shortlist."""
    c = full.constraints
    target = aim(tier, c)
    if target is None or target.wanted <= 0:
        return None, None
    got = counted_meals(problem, solution, target)
    if got >= target.wanted:
        return None, None
    lead = (
        f"No meals with {target.noun} this week"
        if got == 0
        else f"Only {got} of the {_meals(target.wanted)} with {target.noun} that {LABELS[tier]} aims for"
    )
    counted = upgrade_slots(s for d in c.days for s in d.slots)
    blocked = [
        e for e in full.excluded if e.meal_slots & counted and target.counts(e) and "tier" not in e.codes
    ]
    by_time = [e for e in blocked if set(e.codes) == {"time"}]
    mood_blocked = [e for e in by_time if e.blocker == "mood" and e.mood is not None]
    if mood_blocked:
        mood = min((e.mood for e in mood_blocked if e.mood is not None), key=MOOD_ORDER.__getitem__)
        need = min((e.minutes_needed or 0) for e in mood_blocked if e.mood == mood)
        picked = _pick_day(c, None, need)
        why = (
            f"{target.recipes} are {mood.value} to cook, and none of your cook days allows {mood.value} "
            "recipes"
        )
        if picked is None:
            return f"{lead}: {why}.", None
        day, _ = picked
        label = f"Allow {mood.value} recipes on {diagnostics.weekday(c, day)}"
        return f"{lead}: {why}.", TierFix("mood", label, day, mood=mood)
    slow = [e for e in by_time if e.blocker == "minutes" and e.minutes_needed]
    if slow:
        quickest = min(slow, key=lambda e: (e.minutes_needed or 0, e.version_id))
        need = quickest.minutes_needed or 0
        picked = _pick_day(c, quickest.mood, None)
        if picked is not None:
            day, has = picked
            minutes = round_up_5(need)
            why = (
                f"{target.recipes} take about {minutes_text(need)} start to finish; your longest cook day "
                f"for them allows {minutes_text(has)}"
            )
            label = f"Allow {minutes} min on {diagnostics.weekday(c, day)}"
            return f"{lead}: {why}.", TierFix("minutes", label, day, minutes=minutes)
    pool = [r for r in full.candidates if r.meal_slots & counted and target.counts(r) and not r.never_favored]
    if not pool and blocked:
        codes = Counter(code for e in blocked for code in e.codes if code in _OTHER_REASONS)
        if codes:
            return f"{lead}: {target.recipes} {_OTHER_REASONS[codes.most_common(1)[0][0]]}.", None
    if not pool:
        order = list(MealSlot)
        meals = " or ".join(SLOT_LABELS[s].lower() for s in sorted(counted, key=order.index))
        return f"{lead}: none of your {meals} recipes {target.none_have}.", None
    return (
        f"{lead}: more don't fit this week's other limits (calories, cook-day time, the fridge window, "
        "variety).",
        None,
    )


def stock_up_line(cents: int, names: list[str]) -> str | None:
    """'+ about $6.98 stock-up: rice, olive oil' (None when the week buys none)."""
    if cents <= 0:
        return None
    shown = ", ".join(names[:3]) + (f" and {len(names) - 3} more" if len(names) > 3 else "")
    return f"+ about {money_display(cents)} stock-up: {shown}"


# ---------------- a card's inputs' fingerprint (AC6) ----------------


def _canonical(value: Any) -> Any:
    """A JSON-ready form of the inputs with every set and mapping in a fixed order, so the same inputs give
    the same fingerprint in any process (str hashes differ between processes, and with them set order)."""
    if isinstance(value, BaseModel):
        return _canonical(value.model_dump(mode="python"))
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: _canonical(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Mapping):
        pairs = [[_canonical(k), _canonical(v)] for k, v in value.items()]
        return sorted(pairs, key=lambda kv: json.dumps(kv[0], sort_keys=True))
    if isinstance(value, set | frozenset):
        return sorted((_canonical(v) for v in value), key=lambda v: json.dumps(v, sort_keys=True))
    if isinstance(value, list | tuple):
        return [_canonical(v) for v in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal | date | datetime | timedelta):
        return str(value)
    return value


def fingerprint(problem: PlanningProblem, settings: UserSettings, answers: CookAnswers) -> str:
    """Everything a card is worked out from: the problem it solves (constraints, floor included; recipes;
    ingredients, prices and pantry lots), your settings, the answers, and this code's version."""
    payload = {
        "version": ESTIMATE_VERSION,
        "deploy": os.environ.get("VERCEL_GIT_COMMIT_SHA", ""),
        "problem": _canonical(problem),
        "settings": _canonical(settings),
        "answers": _canonical(answers),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def normalized(answers: CookAnswers) -> CookAnswers:
    """The answers the cards price: a shopping list with no tier or limit of its own, saved recipes only."""
    return answers.model_copy(
        update={"price_tier": None, "shopping": "make_a_list", "budget_cents": None, "allow_llm": False}
    )


def answers_key(answers: CookAnswers, today: date) -> str:
    """The cards' request, for the plan you tap to find its card's floor (AC3)."""
    payload = {"answers": normalized(answers).model_dump(mode="json"), "today": today.isoformat()}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


# ---------------- one card ----------------


def price(
    session: Session,
    user_id: int,
    answers: CookAnswers,
    tier: PriceTier,
    *,
    today: date,
    settings: UserSettings,
    floor_cents: int | None,
    cached: Mapping[tuple[str, str], Priced],
) -> Priced:
    """One card: the tier's quick solve for this week, held to `floor_cents` of regular groceries (the card
    below's, AC3), or the same card from an earlier run record when its inputs are the same (AC6)."""
    started = time.monotonic()
    answers = normalized(answers).model_copy(update={"price_tier": tier})
    try:
        plan = resolve_prep(answers, settings, today)
        request = plan.request.model_copy(update={"regular_floor_cents": floor_cents})
        constraints = constraints_for(session, user_id, request, today=today)
    except (PrepAnswersError, ConstraintError) as exc:
        return Priced(_none(tier, str(exc)), "", "none_fits", "answers", time.monotonic() - started)
    problem = build_problem(session, user_id, constraints)
    key = fingerprint(problem, settings, answers)
    load_s = time.monotonic() - started
    if (hit := cached.get((tier.value, key))) is not None:
        return replace(hit, card=replace(hit.card, cached=True), load_s=load_s, solves=())

    def none(reason: str, why: str, fix: TierFix | None = None) -> Priced:
        return Priced(
            replace(_none(tier, reason, fix), floor_cents=floor_cents), key, "none_fits", why, load_s
        )

    if not problem.candidates:
        return none(f"None of your recipes fit the {LABELS[tier]} tier with what you have.", "no_candidates")
    if pre := diagnostics.precheck(problem):
        return none(pre[0].message, "precheck")
    if (gap := diagnostics.uncovered(problem)) is not None:
        fix = None
        if gap.code == "MEAL_BEFORE_COOK_DAY" and gap.day is not None and gap.suggested_minutes:
            fix = TierFix(
                "minutes",
                f"Cook on {diagnostics.weekday(problem.constraints, gap.day)} too",
                gap.day,
                minutes=gap.suggested_minutes,
            )
        return none(gap.message, "uncovered", fix)
    full = problem
    kcal, protein = rounding_fit(problem), rounding_fit(problem, "protein_g")
    problem = problem.with_tightening(
        Tightening(
            kcal_bias=kcal.bias, protein_bias=protein.bias, kcal_scale=kcal.scale, protein_scale=protein.scale
        )
    )
    solution = None
    model = None
    stopped = False
    solves: list[dict[str, Any]] = []
    # the wide shortlist (10 recipes a meal: the narrow one left Cheapest pricier than A bit better), then
    # every eligible recipe, as the planner does before it says no plan fits (a tier's upgrades can need
    # recipes the shortlist doesn't rank high)
    for per_slot in (ESTIMATE_WIDER, None):
        short = shortlist(problem, per_slot) if per_slot is not None else problem
        model = build_model(short)
        solve_started = time.monotonic()
        try:
            status = run_solver(model, TIER_SOLVE_LIMIT_S, TIER_GAP_REL, TIER_GAP_ABS)
        except SolveDeadlineError:
            solves.append({"recipes_a_meal": per_slot, "status": "no_time_left"})
            return Priced(
                replace(_slow(tier), floor_cents=floor_cents),
                key,
                "timed_out",
                "budget",
                load_s,
                tuple(solves),
            )
        solves.append(
            {
                "recipes_a_meal": per_slot,
                "status": pulp.LpSolution[status],
                "seconds": round(time.monotonic() - solve_started, 2),
            }
        )
        if status in (pulp.LpSolutionOptimal, pulp.LpSolutionIntegerFeasible):
            solution = extract(short, model, status)
            problem = short
            break
        # only a proven infeasible model is a week that doesn't fit; anything else stopped before a plan
        stopped = stopped or status != pulp.LpSolutionInfeasible
    if solution is None or model is None:
        if stopped:
            return Priced(
                replace(_slow(tier), floor_cents=floor_cents),
                key,
                "timed_out",
                "solver_limit",
                load_s,
                tuple(solves),
            )
        return replace(
            none(f"No week fits your limits with the {LABELS[tier]} tier's groceries.", "infeasible"),
            solves=tuple(solves),
        )
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
    why_short, fix = shortfall(tier, full, problem, solution)
    card = TierCard(
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
        shortfall_display=why_short,
        fix=fix,
        floor_cents=floor_cents,
        eaten_cents=eaten_value(problem, solution),
    )
    return Priced(card, key, "estimated", None, load_s, tuple(solves))


@dataclass(frozen=True)
class Shown:
    """The price the cards below show so far: its cents and the card that shows it."""

    cents: int
    label: str


def same_as(card: TierCard, shown: Shown | None) -> tuple[TierCard, Shown | None]:
    """AC3: a priced card never shows a lower number than the card below: at or under the price shown below,
    or within 50 cents over it, it says "Same as Cheapest this week" (naming the card whose number shows).
    Returns the card and the price shown after it."""
    if card.status != "estimated" or card.total_cents is None:
        return replace(card, same_as=None), shown
    if shown is not None and card.total_cents - shown.cents <= SAME_WITHIN_CENTS:
        return replace(card, same_as=shown.label), shown
    return replace(card, same_as=None), Shown(card.total_cents, card.label)


def price_all(
    session: Session,
    user_id: int,
    answers: CookAnswers,
    *,
    today: date,
    cached: Mapping[tuple[str, str], Priced],
    on_card: Callable[[Priced], None] = lambda _: None,
) -> list[Priced]:
    """All four cards in order, inside one time budget (the time guard cuts each solve to what's left); each
    one after Broke mode starts from the last priced card: its meals eat at least that card's regular
    groceries (AC3)."""
    settings = load_settings(session, user_id)
    budget = SolveBudget(Deadline.after(SystemClock(), TIERS_BUDGET_S), reserve_s=0)
    out: list[Priced] = []
    floor: int | None = None
    shown: Shown | None = None
    with solve_budget(budget):
        for tier in PriceTier:
            try:
                priced = price(
                    session,
                    user_id,
                    answers,
                    tier,
                    today=today,
                    settings=settings,
                    floor_cents=floor,
                    cached=cached,
                )
            except SolveDeadlineError:  # out of time before the solve itself
                priced = Priced(replace(_slow(tier), floor_cents=floor), "", "timed_out", "budget")
            card, shown = same_as(priced.card, shown)
            priced = replace(priced, card=card)
            on_card(priced)
            out.append(priced)
            if card.status == "estimated" and card.eaten_cents is not None:
                floor = max(card.eaten_cents, floor or 0)
    return out


# ---------------- run records: what happened, and the cache (AC5, AC6) ----------------


def fix_json(fix: TierFix | None) -> dict[str, Any] | None:
    if fix is None:
        return None
    return {
        "kind": fix.kind,
        "label": fix.label,
        "day": fix.day.isoformat(),
        "mood": fix.mood.value if fix.mood else None,
        "minutes": fix.minutes,
    }


def card_json(card: TierCard) -> dict[str, Any]:
    out: dict[str, Any] = {f.name: getattr(card, f.name) for f in fields(card)}
    out["tier"] = card.tier.value
    out["fix"] = fix_json(card.fix)
    return out


def card_from_json(data: Mapping[str, Any]) -> TierCard:
    names = {f.name for f in fields(TierCard)}
    values = {k: v for k, v in data.items() if k in names}
    fix = data.get("fix")
    values["tier"] = PriceTier(data["tier"])
    values["fix"] = (
        TierFix(
            fix["kind"],
            fix["label"],
            date.fromisoformat(fix["day"]),
            mood=RecipeMood(fix["mood"]) if fix.get("mood") else None,
            minutes=fix.get("minutes"),
        )
        if fix
        else None
    )
    return TierCard(**values)


def priced_json(priced: Priced) -> dict[str, Any]:
    return {
        "tier": priced.card.tier.value,
        "key": priced.key,
        "outcome": priced.outcome,
        "why": priced.why,
        "floor_cents": priced.card.floor_cents,
        "load_s": round(priced.load_s, 2),
        "solves": list(priced.solves),
        "cached_from": priced.cached_from,
        "card": card_json(priced.card),
    }


def recent_runs(session: Session, user_id: int) -> list[GenerationRun]:
    since = datetime.now(UTC) - timedelta(hours=CACHE_HOURS)
    return list(
        session.scalars(
            select(GenerationRun)
            .where(
                GenerationRun.user_id == user_id,
                GenerationRun.purpose == TIER_CARDS,
                GenerationRun.created_at >= since,
                GenerationRun.status.in_(("succeeded", "partial")),
            )
            .order_by(GenerationRun.id.desc())
            .limit(CACHE_RUNS)
        )
    )


def cached_cards(runs: list[GenerationRun]) -> dict[tuple[str, str], Priced]:
    """The cards earlier runs worked out to the end (an estimate, or a week that can't be planned), by tier
    and fingerprint, newest first. A card that ran out of time is never reused: Try again works it out."""
    out: dict[tuple[str, str], Priced] = {}
    for run in runs:
        for item in (run.progress or {}).get("cards", []):
            if not item.get("key") or item.get("outcome") not in ("estimated", "none_fits"):
                continue
            try:
                card = card_from_json(item["card"])
            except (KeyError, TypeError, ValueError):
                continue
            origin = item.get("cached_from") or run.id
            out.setdefault(
                (item["tier"], item["key"]),
                Priced(card, item["key"], item["outcome"], item.get("why"), cached_from=origin),
            )
    return out


def tier_floor(session: Session, user_id: int, answers: CookAnswers, today: date) -> int | None:
    """AC3: the floor the card of the tier you tapped was priced with, from this week's cards for the same
    answers, so its plan costs the same or more than the tier below too (None: no card, or no floor)."""
    if answers.price_tier is None:
        return None
    key = answers_key(answers, today)
    for run in recent_runs(session, user_id):
        if (run.constraints or {}).get("answers_key") != key:
            continue
        for item in (run.progress or {}).get("cards", []):
            if item.get("tier") == answers.price_tier.value:
                floor = item.get("floor_cents")
                return int(floor) if isinstance(floor, int) else None
    return None


def slow_start(connects: list[ConnectLog], process_age_s: float | None) -> dict[str, Any]:
    """AC5: the facts of a cold start: database connections (count, retries, seconds) and the function's
    age when the request came."""
    seconds = sum(c.seconds for c in connects)
    retries = sum(c.retries for c in connects)
    cold = (
        retries > 0
        or seconds >= COLD_CONNECT_S
        or (process_age_s is not None and process_age_s < COLD_PROCESS_S)
    )
    return {
        "cold_start": cold,
        "db_connects": sum(c.connects for c in connects),
        "db_connect_retries": retries,
        "db_connect_s": round(seconds, 2),
        "db_connect_failed": sum(c.failed for c in connects),
        "process_age_s": round(process_age_s, 1) if process_age_s is not None else None,
    }


def card_out(card: TierCard) -> TierCardOut:
    fix = card.fix
    return TierCardOut(
        tier=card.tier,
        label=card.label,
        blurb=card.blurb,
        status=card.status,
        total_cents=card.total_cents,
        total_display=card.total_display,
        same_as_display=card.same_as_display,
        protein_per_day_display=card.protein_per_day_display,
        reason=card.reason,
        stock_up_cents=card.stock_up_cents,
        stock_up_display=card.stock_up_display,
        includes_display=card.includes_display,
        shortfall_display=card.shortfall_display,
        fix=TierFixOut(kind=fix.kind, label=fix.label, day=fix.day, mood=fix.mood, minutes=fix.minutes)
        if fix
        else None,
        cached=card.cached,
    )


def tier_events(
    session_factory: SessionFactory,
    user_id: int,
    answers: CookAnswers,
    *,
    request_connects: ConnectLog | None = None,
    process_age_s: float | None = None,
    heartbeat_s: float = HEARTBEAT_SECONDS,
) -> Iterator[str]:
    """POST /cook/meal-prep/tiers as NDJSON (AC6): `started`, a `card` line per tier as soon as it's ready,
    heartbeats, then the `result` with all four; the run record says what each card took (AC5)."""
    worker_connects = ConnectLog()

    def factory() -> Session:  # runs in the stream's worker thread, before its first query
        count_connects_into(worker_connects)
        return session_factory()

    def work(
        session: Session,
        user: AppUser,
        emit: Callable[[dict[str, Any]], None],
        checkpoint: Callable[[], None],
    ) -> dict[str, Any]:
        started = time.monotonic()
        today = search_service.local_now(user).date()
        run = GenerationRun(
            user_id=user.id,
            purpose=TIER_CARDS,
            status="running",
            started_at=datetime.now(UTC),
            constraints={
                "answers_key": answers_key(answers, today),
                "today": today.isoformat(),
                "answers": normalized(answers).model_dump(mode="json"),
            },
        )
        session.add(run)
        session.flush()
        cached = cached_cards(recent_runs(session, user.id))
        checkpoint()  # the run record exists from the start: a crash marks it failed
        emit({"event": "started", "run_id": run.id})
        priced = price_all(
            session,
            user.id,
            answers,
            today=today,
            cached=cached,
            on_card=lambda p: emit({"event": "card", "card": card_out(p.card)}),
        )
        timed_out = any(p.outcome == "timed_out" for p in priced)
        start = slow_start([c for c in (request_connects, worker_connects) if c is not None], process_age_s)
        run.status = "partial" if timed_out else "succeeded"
        run.finished_at = datetime.now(UTC)
        run.progress = {
            "cards": [priced_json(p) for p in priced],
            # which happened (AC5): a card ran out of time after a cold start, or on the time budget alone
            "slow": ("cold_start" if start["cold_start"] else "time_budget") if timed_out else None,
            "timed_out": [p.card.tier.value for p in priced if p.outcome == "timed_out"],
            "start": start,
            "budget_s": TIERS_BUDGET_S,
            "elapsed_s": round(time.monotonic() - started, 2),
            "cached": [p.card.tier.value for p in priced if p.cached_from is not None],
        }
        if timed_out:
            log.info(
                "tier cards %s: %s timed out (%s)", run.id, run.progress["timed_out"], run.progress["slow"]
            )
        return {
            "run_id": run.id,
            "status": run.status,
            "cards": [card_out(p.card) for p in priced],
        }

    def on_crash(
        session: Session, user: AppUser, known: dict[str, int], problem: dict[str, Any]
    ) -> dict[str, Any]:
        """The run record keeps the failure (a database that didn't answer is a cold start, AC5)."""
        start = slow_start([c for c in (request_connects, worker_connects) if c is not None], process_age_s)
        run_id = known.get("run_id")
        run = session.get(GenerationRun, run_id) if run_id else None
        if run is None:
            run = GenerationRun(user_id=user.id, purpose=TIER_CARDS, started_at=datetime.now(UTC))
            session.add(run)
        run.status, run.finished_at = "failed", datetime.now(UTC)
        run.error = problem
        run.progress = {
            "slow": "cold_start" if problem.get("code") == "db_unavailable" else None,
            "start": start,
        }
        session.flush()
        return {"run_id": run.id}

    return stream_events(
        factory,
        user_id,
        work,
        on_crash,
        TierStreamEvent,
        ids={"run_id": None},
        heartbeat_s=heartbeat_s,
        name="tier-cards",
        crash_title="The tier cards failed",
    )
