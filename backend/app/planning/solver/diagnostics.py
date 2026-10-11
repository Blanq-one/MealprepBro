"""Infeasibility in human units (deliverable 13).

Cheap pre-checks catch the obvious gaps (no drink recipes at all, no cook day with enough minutes). When the
MILP itself is infeasible, an elastic re-solve relaxes every hard limit with penalized slack and reports
which limits had to give, and by how much. When the purchase limit gives, it also lists what would have to
be bought (inventory mode: exactly what's missing from your inventory).
"""

from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import pulp

from app.domain.cook_time import MOOD_ORDER
from app.domain.enums import CalorieMode, MealSlot, PlanningMode, RecipeMood
from app.planning.problem import ExcludedRecipe, PlanningProblem
from app.planning.solver.model import (
    Diagnostic,
    EmptyCandidatePoolError,
    _Model,
    batch_plan,
    build_model,
    run_solver,
)
from app.schemas.constraints import PlanConstraints

SLACK_TOLERANCE = 0.5
# The elastic solves stop within 1 penalty point of the best: 10 cents of a top-up (which is rounded up to
# whole dollars anyway), 1 kcal, a fifth of a minute; proving the last cent is wasted work (2b.5).
EXPLAIN_GAP_ABS = 1.0
MIN_LISTED = {"g": 5.0, "ml": 5.0, "count": 0.25}


def _day(d: date) -> str:
    return f"{d:%a} {d:%b} {d.day}"


def weekday(constraints: PlanConstraints, d: date) -> str:
    """'Monday', or 'Monday Oct 12' when the plan has two Mondays."""
    same = sum(1 for x in constraints.days if x.day.weekday() == d.weekday())
    return f"{d:%A}" if same == 1 else f"{d:%A} {d:%b} {d.day}"


def _slot(slot: MealSlot) -> str:
    return slot.value.replace("_", " ")


def _money(cents: float) -> str:
    return f"${cents / 100:,.2f}"


def _about(quantity: float, unit: str) -> str:
    if unit == "count":
        q = Decimal(str(quantity)).quantize(Decimal("0.5"), ROUND_HALF_UP)
        return f"{q.normalize():f}"
    step = 10 if quantity >= 100 else 1
    return f"{round(quantity / step) * step:,} {unit}"


def shopping_gap(problem: PlanningProblem, model: _Model) -> list[tuple[str, str, int]]:
    """What the relaxed plan buys under the purchase limit: (ingredient, about how much, cents), most
    expensive first. Stock-up items are left out in shop mode (the budget doesn't cover them)."""

    def value(expr: object) -> float:
        v = pulp.value(expr)
        return float(v) if v is not None else 0.0

    items = []
    for ingredient_id, (amount, cents) in model.purchases.items():
        plan = problem.ingredients[ingredient_id]
        if not problem.constraints.limit_covers(plan.stock_up):
            continue
        bought = value(amount)
        if bought < MIN_LISTED.get(plan.planning_unit, 1.0):
            continue
        items.append((plan.name, _about(bought, plan.planning_unit), round(value(cents))))
    return sorted(items, key=lambda item: (-item[2], item[0]))


def _whole_dollars(cents: int) -> int:
    """A limit to offer, rounded up to whole dollars ($36.20 -> $37)."""
    return -(-cents // 100) * 100


def _gap_items(items: list[tuple[str, str, int]]) -> tuple[str, ...]:
    """What the smallest fix would buy, one line each ("chicken thigh about 2 lb ($8.98)")."""
    return tuple(f"{name} about {amount} ({_money(cents)})" for name, amount, cents in items)


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


def _reason_summary(excluded: tuple[ExcludedRecipe, ...]) -> str:
    counts: dict[str, int] = defaultdict(int)
    for e in excluded:
        for reason in e.reasons:
            counts[reason] += 1
    return "; ".join(
        f"{why} ({n} recipes)" if n > 1 else why
        for why, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    )


OTHER_REASONS = {  # the other filters, in plain words (P4)
    "excluded": "use an ingredient that's off your list",
    "frequency_cap": "use an ingredient whose frequency cap is 0",
    "equipment": "need equipment you don't have",
    "nutrition_incomplete": "have incomplete nutrition data",
    "unpriced": "have an ingredient with no price yet",
    "conversion": "have an amount that can't be converted",
}


def _capitalized(text: str) -> str:
    return text[:1].upper() + text[1:]


def _recipes(n: int) -> str:
    return f"{n} recipe{'s' if n != 1 else ''}"


SINGULAR = {"use": "uses", "need": "needs", "have": "has"}


def _recipes_that(n: int, phrase: str) -> str:
    """'3 recipes have incomplete nutrition data', '1 recipe has incomplete nutrition data'."""
    verb, _, rest = phrase.partition(" ")
    return f"{_recipes(n)} {SINGULAR.get(verb, verb) if n == 1 else verb} {rest}"


def left_out_diagnostic(
    excluded: tuple[ExcludedRecipe, ...], constraints: PlanConstraints
) -> Diagnostic | None:
    """Why recipes are missing from the pool, for an infeasible week (fewer recipes, fewer ways to fit), in
    plain words with the fix the app can offer (P4): "6 recipes are fancy and your cook days are set to
    medium" comes with "Allow fancy recipes"."""
    if not excluded:
        return None
    cook_days = [d for d in constraints.days if d.is_cook_day]
    parts: list[str] = []
    by_mood: dict[RecipeMood, int] = defaultdict(int)
    for e in excluded:
        if e.blocker == "mood" and e.mood is not None:
            by_mood[e.mood] += 1
    blocked_mood: RecipeMood | None = None
    if by_mood:
        moods = sorted(by_mood, key=lambda m: MOOD_ORDER[m])
        blocked_mood = moods[-1]
        top = max((d.mood for d in cook_days), key=lambda m: MOOD_ORDER[m], default=RecipeMood.SIMPLE)
        items = []
        for i, m in enumerate(moods):
            n = by_mood[m]
            verb = "is" if n == 1 else "are"
            items.append(f"{_recipes(n) if i == 0 else n} {verb} {m.value}")
        comma = "," if len(items) > 1 else ""
        parts.append(f"{' and '.join(items)}{comma} and your cook days are set to {top.value}")
    slow = [e for e in excluded if e.blocker == "minutes"]
    if slow:
        longest = max((d.cook_minutes_available for d in cook_days), default=0)
        parts.append(
            _recipes_that(len(slow), f"need more than the {longest} minutes of hands-on cooking a day allows")
        )
    unpriced: dict[str, int] = defaultdict(int)
    other: dict[str, int] = defaultdict(int)
    for e in excluded:
        for name in e.unpriced_ingredients:
            unpriced[name] += 1
        for code in e.codes:
            if code in OTHER_REASONS and not (code == "unpriced" and e.unpriced_ingredients):
                other[code] += 1
    if constraints.planning_mode is PlanningMode.INVENTORY:
        no_price = "isn't in your inventory and has no price at your stores, so a top-up can't include it"
    else:
        no_price = (
            "has no price at your stores, so your budget can't be checked (enter a price, or plan without "
            "a budget)"
        )
    for name, n in sorted(unpriced.items(), key=lambda kv: (-kv[1], kv[0])):
        parts.append(_recipes_that(n, f"use {name}, which {no_price}"))
    for code, n in sorted(other.items(), key=lambda kv: (-kv[1], kv[0])):
        parts.append(_recipes_that(n, OTHER_REASONS[code]))
    if not parts:
        return None
    return Diagnostic(
        "RECIPES_LEFT_OUT",
        _capitalized("; ".join(parts)) + ".",
        amount=len(excluded),
        mood=blocked_mood.value if blocked_mood is not None else None,
    )


def empty_pool_error(problem: PlanningProblem) -> EmptyCandidatePoolError:
    reasons = tuple(f"{e.title}: {'; '.join(e.reasons)}" for e in problem.excluded)
    summary = _reason_summary(problem.excluded)
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
    """Relax hard limits and report the ones that had to give. With a purchase limit, first relax only that:
    if every other limit can be met, the money is the only thing in the way, and the report says exactly
    what the cheapest such plan costs and buys (instead of trading a few dollars for a few minutes)."""
    if problem.constraints.purchase_limit_cents is not None:
        money_only = build_model(problem, elastic=True)
        for kind, group in money_only.slacks.items():
            if kind != "budget":
                for var in group.values():
                    var.upBound = 0
        status = run_solver(money_only, time_limit_s, 0.0, EXPLAIN_GAP_ABS)
        if status in (pulp.LpSolutionOptimal, pulp.LpSolutionIntegerFeasible):
            return _report(problem, money_only)
    model = build_model(problem, elastic=True)
    status = run_solver(model, time_limit_s, 0.0, EXPLAIN_GAP_ABS)
    if status not in (pulp.LpSolutionOptimal, pulp.LpSolutionIntegerFeasible):
        return (
            Diagnostic(
                "INFEASIBLE",
                "No plan fits these settings, and the solver could not narrow down why "
                "(check portion requests).",
            ),
        )
    return _report(problem, model)


def _report(problem: PlanningProblem, model: _Model) -> tuple[Diagnostic, ...]:
    """The limits a solved elastic model had to relax, in human units."""
    c = problem.constraints
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
        if c.calorie_mode is CalorieMode.STRICT_DAILY:
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
                    f"{weekday(c, day)} needs {have + n} minutes of hands-on cooking; you set {have}.",
                    day=day,
                    amount=n,
                    suggested_minutes=have + n,
                )
            )
    target = c.daily_protein_target_g
    for day, var in model.slacks.get("protein_day", {}).items():
        if amount(var) > SLACK_TOLERANCE:
            short = round(amount(var))
            out.append(
                Diagnostic(
                    "PROTEIN_SHORT",
                    f"{_day(day)} can reach only about {target - short} g protein; your target is {target} g "
                    f"(short by {short} g).",
                    day=day,
                    amount=short,
                )
            )
    week_short = model.slacks.get("protein_week", {}).get("week")
    if week_short is not None and amount(week_short) > SLACK_TOLERANCE:
        short = round(amount(week_short))
        goal = c.week_protein_target_g
        out.append(
            Diagnostic(
                "PROTEIN_SHORT",
                f"The week can reach only about {goal - short:,} g protein; your target is {goal:,} g "
                f"({target} g a day, short by {short} g).",
                amount=short,
            )
        )
    budget = model.slacks.get("budget", {}).get("budget")
    if budget is not None and amount(budget) > SLACK_TOLERANCE:
        cents = round(amount(budget))
        purchase_limit = c.purchase_limit_cents
        assert purchase_limit is not None
        needed = purchase_limit + cents
        gap = shopping_gap(problem, model)
        if c.planning_mode is PlanningMode.INVENTORY:
            start = (
                "Your inventory doesn't cover this week"
                if purchase_limit == 0
                else f"Your inventory plus a {_money(purchase_limit)} top-up doesn't cover this week"
            )
            message = f"{start}. The smallest top-up that makes a plan is about {_money(needed)}."
            out.append(
                Diagnostic(
                    "INVENTORY_SHORT",
                    message,
                    amount=cents,
                    suggested_cents=_whole_dollars(needed),
                    items=_gap_items(gap),
                )
            )
        else:
            message = (
                f"The cheapest plan that fits costs about {_money(needed)} in regular groceries, "
                f"{_money(cents)} over your budget of {_money(purchase_limit)}."
            )
            out.append(
                Diagnostic(
                    "BUDGET_SHORT",
                    message,
                    amount=cents,
                    suggested_cents=_whole_dollars(needed),
                    items=_gap_items(gap),
                )
            )
    for (label, monday), var in model.slacks.get("cap", {}).items():
        if amount(var) > SLACK_TOLERANCE:
            used = c.cap_used(monday, label)
            elsewhere = f" ({used} already in your other plans that week)" if used else ""
            out.append(
                Diagnostic(
                    "FREQUENCY_CAP",
                    f"{label}: the limit for the week of {_day(monday)} would have to rise by "
                    f"{round(amount(var))}{elsewhere}.",
                    day=monday,
                )
            )
    for (label, day), var in model.slacks.get("amount", {}).items():
        if amount(var) > SLACK_TOLERANCE:
            out.append(
                Diagnostic(
                    "DAILY_AMOUNT_CAP", f"{label} on {_day(day)} would go over your daily maximum.", day=day
                )
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
    elif (left_out := left_out_diagnostic(problem.excluded, c)) is not None:
        out.append(left_out)
    return tuple(out)
