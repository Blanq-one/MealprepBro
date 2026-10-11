"""One planning run, start to finish (deliverable 17), with the generation_run lifecycle:

  constraints → candidate pool (seeds + saved first; the LLM only for uncovered slots) → solve
  → infeasible: targeted generation for the slots the diagnostics name (≤ 2 rounds) or a clear `infeasible`
  → pricing: round + absorb, packages, stores and costs → validate the RoundedPlan → calorie / protein /
    purchase-limit / daily-amount errors: re-solve with the observed rounding bias and the bound tightened
    (≤ 2) → still failing: a clear error
  → persist the plan and its grocery list.

Meal prep (step 2b.5) fills gaps with the ideas pass (`recipe_ideas/2`, F20) and saves the plan with its
kind; POST /plans keeps the Phase 1 complete-recipe calls.

LLM failures end the run as `failed` with a problem+json error; nothing from the failing call and no plan is
persisted (validated recipes from earlier, completed calls stay saved for reuse, per CLAUDE.md rule 7).

A run finishes inside one request (Phase 2: serverless hosting stops a function at 300 s). Every LLM call,
rate-limit wait and solve is checked against the request's time budget (PLAN_TIME_BUDGET_SECONDS). When the
budget runs out during recipe generation, the run keeps the recipes made so far and plans with them; when it
runs out before a solve, the run fails with a clear "out of time" error. A succeeded run also writes the
candidate-exposure log (plan_candidate), one row per recipe offered to the solver or filtered out.
"""

import logging
import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import GenerationRun
from app.llm.client import LLMClient
from app.llm.errors import LLMDeadlineError, LLMError, LLMWaitTooLongError
from app.llm.pacing import Clock, Deadline, SystemClock
from app.llm.structured import LLMRunContext
from app.planning.candidates import CandidateGenerator, Gap, gap_analysis
from app.planning.constraint_builder import ConstraintError
from app.planning.exposure import log_exposures
from app.planning.ideas import IdeaCandidates
from app.planning.inputs import constraints_for
from app.planning.loader import build_problem
from app.planning.persistence import save_plan
from app.planning.plan_validator import ValidationReport, validate_plan
from app.planning.post_solve import build_rounded_plan, observed_rounding_bias, rounding_fit
from app.planning.problem import PlanningProblem, Tightening
from app.planning.reference import load_reference
from app.planning.rounded import RoundedPlan
from app.planning.shortlist import FULL_SOLVE_MAX, SHORTLIST_PER_SLOT, SHORTLIST_WIDER, shortlist
from app.planning.snap import stepiest_batch
from app.planning.solver.model import (
    Diagnostic,
    EmptyCandidatePoolError,
    SolverInfeasible,
    SolverSolution,
)
from app.planning.solver.solve import explain_infeasible, solve
from app.schemas.plans import PlanRequest

log = logging.getLogger(__name__)

MAX_TARGETED_ROUNDS = 2
MAX_RESOLVES = 2
RESOLVE_MARGIN_KCAL = 5
RESOLVE_MARGIN_PROTEIN_G = Decimal(1)
# held back from an ingredient's inventory after rounding spilled past it under a purchase limit
HOLDBACK_MARGIN = {"g": Decimal(5), "ml": Decimal(5), "count": Decimal(1)}
TARGETED_COUNT = 2
ROUNDING_CODES = frozenset(
    {
        "KCAL_DAY_OVER_CEILING",
        "KCAL_DAY_UNDER_FLOOR",
        "KCAL_WEEK_OVER_CEILING",
        "KCAL_WEEK_UNDER_FLOOR",
        "PROTEIN_DAY_UNDER_TARGET",
        "PROTEIN_WEEK_UNDER_TARGET",
    }
)
AMOUNT_MARGIN = {
    "g": Decimal(1),
    "ml": Decimal(1),
    "count": Decimal("0.1"),
}  # below a daily cap after rounding
MIN_SOLVE_SECONDS = 5.0  # a solve starts only with at least this much of the time budget left
SOLVE_MARGIN_SECONDS = 2.0
OUT_OF_TIME_NOTE = (
    "Recipe generation stopped early: this request ran out of time ({reason}). The recipes made so far are "
    "saved, so planning again carries on from there."
)
WAIT_NOTE = (
    "The recipe service needs a {seconds} s pause, longer than this request can wait, so this plan uses the "
    "recipes you have. Plan again in a minute for new ones."
)

ProgressListener = Callable[[dict[str, Any]], None]


class PlanDeadlineError(RuntimeError):
    """Too little of the request's time budget is left to solve."""


@dataclass
class PlanOutcome:
    status: str  # succeeded | infeasible | failed
    run_id: int
    plan_id: int | None = None
    plan: RoundedPlan | None = None
    report: ValidationReport | None = None
    diagnostics: tuple[Diagnostic, ...] = ()
    error: dict[str, Any] | None = None
    llm_calls: int = 0
    tokens: int = 0
    notes: list[str] = field(default_factory=list)
    retry_after_s: int | None = None  # new recipes had to wait longer than the request could (2b.3b)


# The validator spy hook used by tests: receives every RoundedPlan that is validated.
ValidatorSpy = Callable[[RoundedPlan], None]


def sentences(parts: Iterable[str]) -> str:
    """Messages as one paragraph (P4): each one a sentence, said once, never ".;" between them."""
    out: list[str] = []
    for part in parts:
        text = part.strip().rstrip(";")
        if text and text[-1] not in ".!?":
            text += "."
        if text and text not in out:
            out.append(text)
    return " ".join(out)


def problem_json(
    title: str,
    detail: str,
    *,
    status: int = 422,
    code: str | None = None,
    diagnostics: tuple[Diagnostic, ...] = (),
) -> dict[str, Any]:
    return {
        "type": "about:blank",
        "title": title,
        "status": status,
        "detail": detail,
        "code": code,
        "diagnostics": [
            {
                k: v
                for k, v in {
                    "code": d.code,
                    "message": d.message,
                    "slot": d.slot.value if d.slot else None,
                    "day": d.day.isoformat() if d.day else None,
                    "amount": d.amount,
                    "suggested_cents": d.suggested_cents,
                    "items": list(d.items) or None,
                    "suggested_minutes": d.suggested_minutes,
                    "mood": d.mood,
                }.items()
                if v is not None
            }
            for d in diagnostics
        ],
    }


def tightening_from(
    report: ValidationReport,
    problem: PlanningProblem,
    solution: SolverSolution,
    plan: RoundedPlan,
    *,
    leave_out_stiffest: bool = False,
) -> Tightening:
    """`leave_out_stiffest`: tightening alone already failed once; if no nudge combination rounds into your
    limits, the next solve also leaves out the stiffest batch on its cook day (2b.5, D117)."""
    day_ceiling: dict[date, int] = {}
    day_floor: dict[date, int] = {}
    protein_day: dict[date, Decimal] = {}
    protein_week = Decimal(0)
    holdback: dict[int, Decimal] = {}
    amount_ceiling: dict[tuple[int, date], Decimal] = {}
    week_ceiling = week_floor = budget = 0
    for e in report.errors:
        amount = (e.amount or 0) + RESOLVE_MARGIN_KCAL
        if e.code == "KCAL_DAY_OVER_CEILING" and e.day is not None:
            day_ceiling[e.day] = amount
        elif e.code == "KCAL_DAY_UNDER_FLOOR" and e.day is not None:
            day_floor[e.day] = amount
        elif e.code == "KCAL_WEEK_OVER_CEILING":
            week_ceiling = amount
        elif e.code == "KCAL_WEEK_UNDER_FLOOR":
            week_floor = amount
        elif e.code == "PROTEIN_DAY_UNDER_TARGET" and e.day is not None:
            protein_day[e.day] = Decimal(e.amount or 0) + RESOLVE_MARGIN_PROTEIN_G
        elif e.code == "PROTEIN_WEEK_UNDER_TARGET":
            protein_week = Decimal(e.amount or 0) + RESOLVE_MARGIN_PROTEIN_G
        elif e.code == "PURCHASE_LIMIT_OVER":
            budget = e.amount or 0
            # rounding up spilled past the inventory the solver planned to use: hold some back
            for item in plan.grocery.items:
                if item.kind == "buy" and item.inventory_used > 0:
                    margin = HOLDBACK_MARGIN.get(item.unit, Decimal(1))
                    holdback[item.ingredient_id] = item.to_buy + margin
        elif e.code == "PURCHASE_NOT_ALLOWED":
            # the same spill in "Use what I have": that item must come from your stock alone
            for item in plan.grocery.items:
                if item.ingredient_id == e.details.get("ingredient_id"):
                    margin = HOLDBACK_MARGIN.get(item.unit, Decimal(1))
                    holdback[item.ingredient_id] = item.to_buy + margin
        elif e.code == "DAILY_AMOUNT_OVER" and e.day is not None:
            ingredient_id = int(e.details["ingredient_id"])
            cap = next(d for d in problem.constraints.daily_amount_caps if d.ingredient_id == ingredient_id)
            amount_ceiling[(ingredient_id, e.day)] = Decimal(str(e.details["over"])) + AMOUNT_MARGIN.get(
                cap.unit, Decimal(1)
            )
    forbidden: frozenset[tuple[int, date]] = frozenset()
    # no nudge lands these batches inside your limits: try the week without the stepiest one that day
    if (
        leave_out_stiffest
        and not plan.snapped
        and any(e.code in ROUNDING_CODES for e in report.errors)
        and (index := stepiest_batch(problem, solution)) is not None
    ):
        batch = solution.batches[index]
        forbidden = frozenset({(batch.version_id, batch.cook_on)})
    return Tightening(
        day_ceiling,
        day_floor,
        week_ceiling,
        week_floor,
        budget,
        observed_rounding_bias(problem, solution.batches, plan.batches),
        observed_rounding_bias(problem, solution.batches, plan.batches, "protein_g"),
        protein_day,
        protein_week,
        holdback,
        amount_ceiling=amount_ceiling,
        forbidden=forbidden,
    )


class Orchestrator:
    def __init__(
        self,
        session: Session,
        user_id: int,
        *,
        llm_client: LLMClient | None,
        settings: Settings | None = None,
        clock: Clock | None = None,
        validator_spy: ValidatorSpy | None = None,
        deadline: Deadline | None = None,
        on_progress: ProgressListener | None = None,
        kind: str | None = None,
        ideas: bool = False,
        today: date | None = None,
    ) -> None:
        """`kind`: the saved plan's kind (meal_prep | grocery_advice; None = a week plan from POST /plans).
        `ideas`: fill gaps with the ideas pass (the 2b flows, F20) instead of complete recipes."""
        self.kind = kind
        self.ideas = ideas
        self.today = today  # your local date (calendar-week caps); None = from your timezone
        self.session = session
        self.user_id = user_id
        self.llm_client = llm_client
        self.settings = settings or get_settings()
        self.clock = clock or SystemClock()
        self.validator_spy = validator_spy
        self.deadline = deadline
        self.on_progress = on_progress
        self.notes: list[str] = []
        self.retry_after_s: int | None = None

    def _progress(self, run: GenerationRun, stage: str, **extra: Any) -> None:
        run.progress = {"stage": stage, **extra}
        self.session.flush()
        if self.on_progress is not None:
            self.on_progress(dict(run.progress))

    def _finish(self, run: GenerationRun, outcome: PlanOutcome) -> PlanOutcome:
        run.status = outcome.status
        run.finished_at = datetime.now(UTC)
        if outcome.error is not None:
            run.error = outcome.error
        outcome.llm_calls = run.llm_call_count
        outcome.tokens = run.total_tokens
        outcome.notes = [*self.notes, *outcome.notes]
        outcome.retry_after_s = outcome.retry_after_s or self.retry_after_s
        if outcome.notes:
            run.progress = {**(run.progress or {}), "notes": outcome.notes}
        self.session.flush()
        return outcome

    def run(self, request: PlanRequest, run: GenerationRun | None = None) -> PlanOutcome:
        if run is None:
            run = GenerationRun(user_id=self.user_id, purpose="weekly_plan", status="pending")
            self.session.add(run)
            self.session.flush()
        if self.deadline is None:
            self.deadline = Deadline.after(self.clock, self.settings.plan_time_budget_seconds)
        run.status = "running"
        run.started_at = datetime.now(UTC)
        self._progress(run, "constraints")
        try:
            return self._run(request, run)
        except PlanDeadlineError as exc:
            return self._finish(
                run,
                PlanOutcome(
                    "failed",
                    run.id,
                    error=problem_json("Planning ran out of time", str(exc), status=503, code="deadline"),
                ),
            )
        except ConstraintError as exc:
            return self._finish(
                run,
                PlanOutcome(
                    "failed",
                    run.id,
                    error=problem_json("Settings can't form a week", str(exc), code="constraints"),
                ),
            )
        except LLMError as exc:
            return self._finish(
                run,
                PlanOutcome(
                    "failed",
                    run.id,
                    error=problem_json(
                        "Recipe generation failed",
                        str(exc),
                        status=502 if exc.code != "llm_config" else 500,
                        code=exc.code,
                    ),
                ),
            )

    def _llm(self, run: GenerationRun) -> LLMRunContext | None:
        if self.llm_client is None:
            return None
        return LLMRunContext(
            self.llm_client,
            self.session,
            self.settings,
            run.id,
            self.clock,
            deadline=self.deadline,
            on_wait=lambda seconds: self._progress(run, "waiting", seconds=round(seconds)),
        )

    def _remaining(self) -> float:
        return self.deadline.remaining() if self.deadline is not None else float("inf")

    def _time_limit(self) -> int:
        """The solver's time limit: the configured one, cut to what's left of the request's budget."""
        left = self._remaining()
        if left < MIN_SOLVE_SECONDS:
            raise PlanDeadlineError(
                f"only {left:.0f} s of this request's {self.settings.plan_time_budget_seconds} s time "
                "budget is left, too little to fit the week; try again (recipes made so far are saved)"
            )
        return max(1, min(self.settings.solver_time_limit_seconds, int(left - SOLVE_MARGIN_SECONDS)))

    def _solve(self, problem: PlanningProblem) -> SolverSolution | SolverInfeasible:
        """Solve the shortlist (the best candidates per meal, planning/shortlist.py), then a wider one when
        it can't make a plan, then every eligible recipe before saying no plan fits (2b.3b approval, P3). A
        small library is solved whole from the start.

        Finding that the hands-on time, moods or stock can't make a plan takes a fraction of a second, even
        with every recipe. Money is different: proving that no combination of every recipe fits a budget
        (or inventory mode's top-up) takes longer than any time limit, so with a money limit the planner
        stops at the wider shortlist, as before P3. Explaining why no plan fits (the elastic solve) takes
        seconds on a shortlist and longer than any time limit on a big library, so an infeasible week is
        explained once, from the wider shortlist (the narrow one with a money limit, D126): its fixes always
        make a plan, though a smaller fix might do with every recipe."""
        small = len(problem.candidates) <= FULL_SOLVE_MAX
        if small:
            tiers: tuple[int | None, ...] = (None,)
        elif problem.constraints.has_purchase_limit:
            tiers = (SHORTLIST_PER_SLOT, SHORTLIST_WIDER)
        else:
            tiers = (SHORTLIST_PER_SLOT, SHORTLIST_WIDER, None)
        tried: set[int] = set()
        too_long: SolverInfeasible | None = None
        for per_slot in tiers:
            short = problem if per_slot is None else shortlist(problem, per_slot)
            if too_long is not None:  # the batch sets that ran over still do: the wider try starts with them
                short = short.with_tightening(Tightening(schedule_cuts=too_long.schedule_cuts))
            if len(short.candidates) in tried:
                continue
            tried.add(len(short.candidates))
            result = self._solve_exactly(short)
            if isinstance(result, SolverSolution):
                if too_long is not None:
                    result = replace(result, schedule_cuts=result.schedule_cuts | too_long.schedule_cuts)
                return result
            if result.from_schedule:
                cuts = result.schedule_cuts | (
                    too_long.schedule_cuts if too_long is not None else frozenset()
                )
                too_long = replace(too_long or result, schedule_cuts=cuts)
        # every other limit fits, but the cook days' exact schedules run over (step 2b.9): that is the fix to
        # offer, and the elastic solve (linear limits only) can't see it
        if too_long is not None:
            return too_long
        # a money shortfall is explained from the narrow shortlist, which always holds each meal's cheapest
        # recipes (T2): on the wider one the elastic solve took 4–5 minutes on a pantry-only week (2b.5, D126)
        per_slot = SHORTLIST_PER_SLOT if problem.constraints.has_purchase_limit else SHORTLIST_WIDER
        why = problem if small else shortlist(problem, per_slot)
        return explain_infeasible(why, time_limit_s=self._time_limit())

    def _solve_exactly(self, problem: PlanningProblem) -> SolverSolution | SolverInfeasible:
        return solve(
            problem,
            time_limit_s=self._time_limit(),
            gap_rel=self.settings.solver_gap_rel,
            gap_abs=self.settings.solver_gap_abs,
            explain=False,
        )

    def _generate(
        self, generator: CandidateGenerator | IdeaCandidates, problem: PlanningProblem, gaps: list[Gap]
    ) -> bool:
        """False when the time budget ran out; what was generated before that is saved and used."""
        try:
            generator.generate(problem, gaps)
        except LLMWaitTooLongError as exc:  # a pause, never an error: plan with the recipes made so far
            self.retry_after_s = max(1, math.ceil(exc.retry_after_s))
            self.notes.append(WAIT_NOTE.format(seconds=self.retry_after_s))
            return False
        except LLMDeadlineError as exc:
            self.notes.append(OUT_OF_TIME_NOTE.format(reason=exc))
            return False
        return True

    def _run(self, request: PlanRequest, run: GenerationRun) -> PlanOutcome:
        constraints = constraints_for(self.session, self.user_id, request, today=self.today)
        run.constraints = constraints.canonical()
        self._progress(run, "candidates")
        problem = build_problem(self.session, self.user_id, constraints)
        llm = self._llm(run) if request.allow_llm else None
        generator: CandidateGenerator | IdeaCandidates | None = None
        if llm is not None:
            generator = (
                IdeaCandidates(self.session, self.user_id, llm)
                if self.ideas
                else CandidateGenerator(self.session, self.user_id, llm)
            )
        out_of_time = False
        gaps = gap_analysis(problem)
        if gaps and generator is not None:
            self._progress(run, "generating", slots=[g.slot.value for g in gaps])
            out_of_time = not self._generate(generator, problem, gaps)
            problem = build_problem(self.session, self.user_id, constraints)
        rounds = 0
        while True:
            self._progress(run, "solving", targeted_rounds=rounds)
            kcal, protein = rounding_fit(problem), rounding_fit(problem, "protein_g")
            problem = problem.with_tightening(
                Tightening(
                    kcal_bias=kcal.bias,
                    protein_bias=protein.bias,
                    kcal_scale=kcal.scale,
                    protein_scale=protein.scale,
                )
            )
            try:
                result = self._solve(problem)
            except EmptyCandidatePoolError as exc:
                result = SolverInfeasible((Diagnostic("EMPTY_CANDIDATE_POOL", str(exc)),))
            if isinstance(result, SolverSolution):
                problem = problem.with_tightening(Tightening(schedule_cuts=result.schedule_cuts))
                break
            slots = sorted({d.slot for d in result.diagnostics if d.slot is not None}, key=lambda s: s.value)
            if generator is None or out_of_time or not slots or rounds >= MAX_TARGETED_ROUNDS:
                detail = sentences(d.message for d in result.diagnostics)
                if out_of_time and slots:
                    detail += (
                        " (this request ran out of time for new recipes; the ones made so far are saved, so "
                        "planning again carries on from there)"
                    )
                elif generator is None and slots:
                    detail += " (recipe generation was off for this run)"
                return self._finish(
                    run,
                    PlanOutcome(
                        "infeasible",
                        run.id,
                        diagnostics=result.diagnostics,
                        error=problem_json(
                            "No plan fits this week",
                            detail,
                            code="infeasible",
                            diagnostics=result.diagnostics,
                        ),
                    ),
                )
            rounds += 1
            self._progress(run, "generating", slots=[s.value for s in slots], targeted_round=rounds)
            out_of_time = not self._generate(
                generator, problem, [Gap(s, TARGETED_COUNT, "targeted") for s in slots]
            )
            problem = build_problem(self.session, self.user_id, constraints)
        return self._round_validate_persist(run, problem, result, generator)

    def _round_validate_persist(
        self,
        run: GenerationRun,
        problem: PlanningProblem,
        result: SolverSolution,
        generator: CandidateGenerator | IdeaCandidates | None = None,
    ) -> PlanOutcome:
        resolves = 0
        while True:
            self._progress(run, "pricing", resolves=resolves)  # rounding, absorption, packages, stores, costs
            plan = build_rounded_plan(problem, result)
            self._progress(run, "validating", resolves=resolves)
            if self.validator_spy is not None:
                self.validator_spy(plan)
            reference = load_reference(
                self.session, self.user_id, problem.constraints, [b.version_id for b in plan.batches]
            )
            report = validate_plan(plan, reference)
            if report.ok:
                saved = save_plan(self.session, self.user_id, plan, report, run.id, kind=self.kind)
                log_exposures(
                    self.session,
                    run.id,
                    saved.id,
                    problem,
                    plan,
                    new_version_ids=frozenset(generator.created) if generator is not None else frozenset(),
                )
                return self._finish(
                    run,
                    PlanOutcome(
                        "succeeded",
                        run.id,
                        plan_id=saved.id,
                        plan=plan,
                        report=report,
                        notes=list(plan.notes),
                    ),
                )
            if not report.resolvable or resolves >= MAX_RESOLVES:
                detail = sentences(e.message for e in report.errors)
                return self._finish(
                    run,
                    PlanOutcome(
                        "failed",
                        run.id,
                        plan=plan,
                        report=report,
                        error=problem_json(
                            "The plan didn't pass validation",
                            detail,
                            code="validation",
                            diagnostics=tuple(
                                Diagnostic(e.code, e.message, day=e.day, amount=e.amount)
                                for e in report.errors
                            ),
                        ),
                    ),
                )
            resolves += 1
            problem = problem.with_tightening(
                tightening_from(report, problem, result, plan, leave_out_stiffest=resolves > 1)
            )
            self._progress(run, "re-solving", resolves=resolves)
            resolved = self._solve(problem)
            if isinstance(resolved, SolverInfeasible):
                detail = sentences(e.message for e in report.errors)
                return self._finish(
                    run,
                    PlanOutcome(
                        "failed",
                        run.id,
                        report=report,
                        diagnostics=resolved.diagnostics,
                        error=problem_json(
                            "Rounding pushed the plan past a limit, and no re-solve fits",
                            detail,
                            code="validation",
                            diagnostics=resolved.diagnostics,
                        ),
                    ),
                )
            problem = problem.with_tightening(Tightening(schedule_cuts=resolved.schedule_cuts))
            result = resolved
