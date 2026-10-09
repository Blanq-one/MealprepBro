"""One planning run, start to finish (deliverable 17), with the generation_run lifecycle:

  constraints → candidate pool (seeds + saved first; the LLM only for uncovered slots) → solve
  → infeasible: targeted generation for the slots the diagnostics name (≤ 2 rounds) or a clear `infeasible`
  → round + absorb → validate the RoundedPlan → calorie / protein / purchase-limit errors: re-solve with the
    observed rounding bias and the bound tightened (≤ 2) → still failing: a clear error
  → persist the plan and its grocery list.

LLM failures end the run as `failed` with a problem+json error; nothing from the failing call and no plan is
persisted (validated recipes from earlier, completed calls stay saved for reuse, per CLAUDE.md rule 7).
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import GenerationRun
from app.llm.client import LLMClient
from app.llm.errors import LLMError
from app.llm.pacing import Clock, SystemClock
from app.llm.structured import LLMRunContext
from app.planning.candidates import CandidateGenerator, Gap, gap_analysis
from app.planning.constraint_builder import ConstraintError
from app.planning.inputs import constraints_for
from app.planning.loader import build_problem
from app.planning.persistence import save_plan
from app.planning.plan_validator import ValidationReport, validate_plan
from app.planning.post_solve import build_rounded_plan, observed_rounding_bias, rounding_fit
from app.planning.problem import PlanningProblem, Tightening
from app.planning.reference import load_reference
from app.planning.rounded import RoundedPlan
from app.planning.solver.model import (
    Diagnostic,
    EmptyCandidatePoolError,
    SolverInfeasible,
    SolverSolution,
)
from app.planning.solver.solve import solve
from app.schemas.plans import PlanRequest

log = logging.getLogger(__name__)

MAX_TARGETED_ROUNDS = 2
MAX_RESOLVES = 2
RESOLVE_MARGIN_KCAL = 5
RESOLVE_MARGIN_PROTEIN_G = Decimal(1)
# held back from an ingredient's inventory after rounding spilled past it under a purchase limit
HOLDBACK_MARGIN = {"g": Decimal(5), "ml": Decimal(5), "count": Decimal(1)}
TARGETED_COUNT = 2


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


# The validator spy hook used by tests: receives every RoundedPlan that is validated.
ValidatorSpy = Callable[[RoundedPlan], None]


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
                }.items()
                if v is not None
            }
            for d in diagnostics
        ],
    }


def tightening_from(
    report: ValidationReport, problem: PlanningProblem, solution: SolverSolution, plan: RoundedPlan
) -> Tightening:
    day_ceiling: dict[date, int] = {}
    day_floor: dict[date, int] = {}
    protein_day: dict[date, Decimal] = {}
    protein_week = Decimal(0)
    holdback: dict[int, Decimal] = {}
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
    ) -> None:
        self.session = session
        self.user_id = user_id
        self.llm_client = llm_client
        self.settings = settings or get_settings()
        self.clock = clock or SystemClock()
        self.validator_spy = validator_spy

    def _progress(self, run: GenerationRun, stage: str, **extra: Any) -> None:
        run.progress = {"stage": stage, **extra}
        self.session.flush()

    def _finish(self, run: GenerationRun, outcome: PlanOutcome) -> PlanOutcome:
        run.status = outcome.status
        run.finished_at = datetime.now(UTC)
        if outcome.error is not None:
            run.error = outcome.error
        outcome.llm_calls = run.llm_call_count
        outcome.tokens = run.total_tokens
        self.session.flush()
        return outcome

    def run(self, request: PlanRequest, run: GenerationRun | None = None) -> PlanOutcome:
        if run is None:
            run = GenerationRun(user_id=self.user_id, purpose="weekly_plan", status="pending")
            self.session.add(run)
            self.session.flush()
        run.status = "running"
        run.started_at = datetime.now(UTC)
        self._progress(run, "constraints")
        try:
            return self._run(request, run)
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
        return LLMRunContext(self.llm_client, self.session, self.settings, run.id, self.clock)

    def _run(self, request: PlanRequest, run: GenerationRun) -> PlanOutcome:
        constraints = constraints_for(self.session, self.user_id, request)
        run.constraints = constraints.canonical()
        self._progress(run, "candidates")
        problem = build_problem(self.session, self.user_id, constraints)
        llm = self._llm(run) if request.allow_llm else None
        generator = CandidateGenerator(self.session, self.user_id, llm) if llm is not None else None
        gaps = gap_analysis(problem)
        if gaps and generator is not None:
            self._progress(run, "generating", slots=[g.slot.value for g in gaps])
            generator.generate(problem, gaps)
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
                result = solve(
                    problem,
                    time_limit_s=self.settings.solver_time_limit_seconds,
                    gap_rel=self.settings.solver_gap_rel,
                    gap_abs=self.settings.solver_gap_abs,
                )
            except EmptyCandidatePoolError as exc:
                result = SolverInfeasible((Diagnostic("EMPTY_CANDIDATE_POOL", str(exc)),))
            if isinstance(result, SolverSolution):
                break
            slots = sorted({d.slot for d in result.diagnostics if d.slot is not None}, key=lambda s: s.value)
            if generator is None or not slots or rounds >= MAX_TARGETED_ROUNDS:
                detail = "; ".join(d.message for d in result.diagnostics)
                if generator is None and slots:
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
            generator.generate(problem, [Gap(s, TARGETED_COUNT, "targeted") for s in slots])
            problem = build_problem(self.session, self.user_id, constraints)
        return self._round_validate_persist(run, problem, result)

    def _round_validate_persist(
        self, run: GenerationRun, problem: PlanningProblem, result: SolverSolution
    ) -> PlanOutcome:
        resolves = 0
        while True:
            self._progress(run, "validating", resolves=resolves)
            plan = build_rounded_plan(problem, result)
            if self.validator_spy is not None:
                self.validator_spy(plan)
            reference = load_reference(
                self.session, self.user_id, problem.constraints, [b.version_id for b in plan.batches]
            )
            report = validate_plan(plan, reference)
            if report.ok:
                saved = save_plan(self.session, self.user_id, plan, report, run.id)
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
                detail = "; ".join(e.message for e in report.errors)
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
            problem = problem.with_tightening(tightening_from(report, problem, result, plan))
            self._progress(run, "re-solving", resolves=resolves)
            resolved = solve(
                problem,
                time_limit_s=self.settings.solver_time_limit_seconds,
                gap_rel=self.settings.solver_gap_rel,
                gap_abs=self.settings.solver_gap_abs,
            )
            if isinstance(resolved, SolverInfeasible):
                detail = "; ".join(e.message for e in report.errors)
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
            result = resolved
