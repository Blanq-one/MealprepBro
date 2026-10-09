"""Infeasibility in human units (deliverable 13).

Cheap pre-checks catch the obvious gaps (no drink recipes at all, no cook day with enough minutes). When the
MILP itself is infeasible, an elastic re-solve relaxes every hard limit with penalized slack and reports
which limits had to give, and by how much.
"""

from collections import defaultdict
from datetime import date

import pulp

from app.domain.enums import MealSlot
from app.planning.problem import ExcludedRecipe, PlanningProblem
from app.planning.solver.model import (
    Diagnostic,
    EmptyCandidatePoolError,
    batch_plan,
    build_model,
    run_solver,
)

SLACK_TOLERANCE = 0.5


def _day(d: date) -> str:
    return f"{d:%a} {d:%b} {d.day}"


def _slot(slot: MealSlot) -> str:
    return slot.value.replace("_", " ")


def _reasons_for_slot(excluded: tuple[ExcludedRecipe, ...], slot: MealSlot) -> list[str]:
    return [f"{e.title}: {'; '.join(e.reasons)}" for e in excluded if slot in e.meal_slots]


def held_diagnostic(excluded: tuple[ExcludedRecipe, ...]) -> Diagnostic | None:
    held = sorted({name for e in excluded for name in e.held_ingredients})
    if not held:
        return None
    return Diagnostic(
        "HELD_INGREDIENTS",
        "These held items keep recipes out of the plan until you review them (allow an item in settings "
        f"if its source is fine): {', '.join(held)}",
    )


def empty_pool_error(problem: PlanningProblem) -> EmptyCandidatePoolError:
    reasons = tuple(f"{e.title}: {'; '.join(e.reasons)}" for e in problem.excluded)
    counts: dict[str, int] = defaultdict(int)
    for e in problem.excluded:
        for reason in e.reasons:
            counts[reason] += 1
    summary = "; ".join(
        f"{n} × {why}" if n > 1 else why for why, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    )
    message = "No recipe can be planned with these settings"
    if summary:
        message += f" ({summary})"
    held = held_diagnostic(problem.excluded)
    if held is not None:
        message += f". {held.message}"
    return EmptyCandidatePoolError(message, reasons)


def precheck(problem: PlanningProblem) -> tuple[Diagnostic, ...]:
    c = problem.constraints
    out: list[Diagnostic] = []
    slots = sorted({s for d in c.days for s in d.slots}, key=lambda s: list(MealSlot).index(s))
    for slot in slots:
        if not any(slot in r.meal_slots for r in problem.candidates):
            why = _reasons_for_slot(problem.excluded, slot)
            detail = f" Left out: {' | '.join(why)}." if why else ""
            out.append(
                Diagnostic(
                    "NO_CANDIDATES_FOR_SLOT",
                    f"No {_slot(slot)} recipes are available for this week.{detail}",
                    slot=slot,
                )
            )
    cook_days = [d for d in c.days if d.is_cook_day]
    if not batch_plan(problem):
        most = max((d.cook_minutes_available for d in cook_days), default=0)
        shortest = min((r.active_minutes for r in problem.candidates), default=0)
        out.append(
            Diagnostic(
                "COOK_TIME_TOO_SHORT",
                f"No recipe fits any cook day: the most hands-on time on a cook day is {most} minutes, "
                "and the "
                f"quickest recipe needs {shortest}.",
                amount=shortest - most,
            )
        )
    if out:
        held = held_diagnostic(problem.excluded)
        if held is not None:
            out.append(held)
    return tuple(out)


def explain(problem: PlanningProblem, *, time_limit_s: int = 20) -> tuple[Diagnostic, ...]:
    """Relax every hard limit and report the ones that had to give."""
    c = problem.constraints
    model = build_model(problem, elastic=True)
    status = run_solver(model, time_limit_s, 0.0, 0.0)
    if status not in (pulp.LpSolutionOptimal, pulp.LpSolutionIntegerFeasible):
        return (
            Diagnostic(
                "INFEASIBLE",
                "No plan fits these settings, and the solver could not narrow down why "
                "(check portion requests).",
            ),
        )
    out: list[Diagnostic] = []

    def amount(var: pulp.LpVariable) -> float:
        v = pulp.value(var)
        return float(v) if v is not None else 0.0

    missing: dict[MealSlot, list[date]] = defaultdict(list)
    for (day, slot), var in model.slacks.get("miss", {}).items():
        if amount(var) > SLACK_TOLERANCE:
            missing[slot].append(day)
    for slot, days in sorted(missing.items(), key=lambda kv: list(MealSlot).index(kv[0])):
        out.append(
            Diagnostic(
                "SLOT_UNFILLABLE",
                f"{_slot(slot).capitalize()} can't be filled on "
                f"{', '.join(_day(d) for d in sorted(days))}: no "
                "recipe can be cooked in time for those days within the fridge window and your other limits.",
                slot=slot,
                amount=len(days),
            )
        )
    tol = c.tolerance
    for d in c.days:
        under = model.slacks.get("kcal_under", {}).get(d.day)
        over = model.slacks.get("kcal_over", {}).get(d.day)
        if c.calorie_mode.value == "strict_daily":
            floor = round(d.kcal_target * (1 - tol.daily_under_pct / 100))
            ceiling = d.kcal_target
        else:
            floor = d.kcal_target - tol.daily_band_kcal
            ceiling = d.kcal_target + tol.daily_band_kcal
        if under is not None and amount(under) > SLACK_TOLERANCE:
            short = round(amount(under))
            out.append(
                Diagnostic(
                    "KCAL_DAY_BELOW_FLOOR",
                    f"{_day(d.day)} can only reach about {floor - short:,} kcal; the minimum is {floor:,} "
                    f"(short by {short:,} kcal).",
                    day=d.day,
                    amount=short,
                )
            )
        if over is not None and amount(over) > SLACK_TOLERANCE:
            extra = round(amount(over))
            out.append(
                Diagnostic(
                    "KCAL_DAY_ABOVE_CEILING",
                    f"{_day(d.day)} can't get below about {ceiling + extra:,} kcal; the ceiling is "
                    f"{ceiling:,} (over by {extra:,} kcal).",
                    day=d.day,
                    amount=extra,
                )
            )
    week_limits = {
        "week_over": ("KCAL_WEEK_ABOVE_CEILING", "above", c.weekly_kcal_target),
        "week_under": (
            "KCAL_WEEK_BELOW_FLOOR",
            "below",
            round(c.weekly_kcal_target * (1 - tol.weekly_under_pct / 100)),
        ),
    }
    for kind, (code, label, limit) in week_limits.items():
        var = model.slacks.get(kind, {}).get("week")
        if var is not None and amount(var) > SLACK_TOLERANCE:
            n = round(amount(var))
            out.append(
                Diagnostic(
                    code, f"The week would be {n:,} kcal {label} its limit of {limit:,} kcal.", amount=n
                )
            )
    for day, var in model.slacks.get("time", {}).items():
        if amount(var) > SLACK_TOLERANCE:
            n = round(amount(var))
            have = c.day(day).cook_minutes_available
            out.append(
                Diagnostic(
                    "COOK_TIME_SHORT",
                    f"{_day(day)} needs about {have + n} hands-on minutes; you have {have} (short by {n}).",
                    day=day,
                    amount=n,
                )
            )
    budget = model.slacks.get("budget", {}).get("budget")
    if budget is not None and amount(budget) > SLACK_TOLERANCE:
        cents = round(amount(budget))
        assert c.weekly_budget_cents is not None
        out.append(
            Diagnostic(
                "BUDGET_SHORT",
                f"The cheapest plan that fits costs about ${(c.weekly_budget_cents + cents) / 100:.2f}, "
                f"${cents / 100:.2f} over your hard budget of ${c.weekly_budget_cents / 100:.2f}.",
                amount=cents,
            )
        )
    for label, var in model.slacks.get("cap", {}).items():
        if amount(var) > SLACK_TOLERANCE:
            out.append(
                Diagnostic("FREQUENCY_CAP", f"{label}: the limit would have to rise by {round(amount(var))}.")
            )
    for vid, var in model.slacks.get("variety", {}).items():
        if amount(var) > SLACK_TOLERANCE:
            title = problem.candidate(vid).title
            out.append(
                Diagnostic(
                    "VARIETY_CAP",
                    f"{title} would be needed {c.max_portions_per_recipe + round(amount(var))} times; "
                    "the weekly "
                    f"limit per recipe is {c.max_portions_per_recipe}. More recipes would help.",
                )
            )
    if not out:
        out.append(
            Diagnostic(
                "INFEASIBLE", "No plan fits all limits at once (the solver timed out narrowing it down)."
            )
        )
    held = held_diagnostic(problem.excluded)
    if held is not None:
        out.append(held)
    return tuple(out)
