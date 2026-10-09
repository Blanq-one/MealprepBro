"""Plain-text week report for `cli plan-week`: each day's meals, daily and weekly kcal and protein, cost
by store, notes, warnings, or the infeasibility explanation. Formatting only; every number comes from the
plan."""

from collections.abc import Mapping, Sequence
from decimal import ROUND_HALF_UP, Decimal

from app.domain.enums import CalorieMode, MealSlot
from app.planning.orchestrator import PlanOutcome
from app.planning.rounded import RoundedMeal, RoundedPlan

MAX_TITLE = 70


def _money(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def _minutes(total: int) -> str:
    hours, minutes = divmod(total, 60)
    return f"{hours} h {minutes:02d} min" if hours else f"{minutes} min"


def _g(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.1'), ROUND_HALF_UP):,} g"


def _slot(slot: MealSlot) -> str:
    return slot.value.replace("_", " ").capitalize()


def limits_line(plan: RoundedPlan) -> str:
    c = plan.constraints
    tol = c.tolerance
    target = c.days[0].kcal_target
    if c.calorie_mode is CalorieMode.STRICT_DAILY:
        floor = round(target * (1 - tol.daily_under_pct / 100))
        return f"strict daily mode: each day {floor:,}-{target:,} kcal"
    week_floor = round(c.weekly_kcal_target * (1 - tol.weekly_under_pct / 100))
    return (
        f"weekly mode: each day {target - tol.daily_band_kcal:,}-{target + tol.daily_band_kcal:,} kcal, "
        f"week {week_floor:,}-{c.weekly_kcal_target:,}"
    )


def _meal_title(plan: RoundedPlan, meal: RoundedMeal, drafts: set[int]) -> str:
    batch = plan.batches[meal.batch_index]
    title = batch.title + (" [draft]" if batch.version_id in drafts else "")
    if meal.from_freezer:
        title += " (from freezer: thaw overnight)"
    elif batch.cook_on != meal.eat_on:
        title += f" (cooked {batch.cook_on:%a})"
    return title


def format_plan(
    plan: RoundedPlan, outcome: PlanOutcome, store_names: Mapping[int, str], drafts: set[int]
) -> str:
    c = plan.constraints
    t = plan.totals
    width = min(
        MAX_TITLE, max((_meal_title(plan, m, drafts) for m in plan.meals), key=len, default="").__len__()
    )
    lines = [
        f"Week of {c.week_start:%a %b} {c.week_start.day}, {c.week_start.year}"
        + (f"  (plan #{outcome.plan_id}, draft)" if outcome.plan_id else ""),
        f"Run #{outcome.run_id}: {outcome.llm_calls} LLM calls, {outcome.tokens:,} tokens",
        "",
        f"Calories:  {t.week_kcal:,} / {c.weekly_kcal_target:,} kcal planned ({limits_line(plan)})",
        f"Protein:   {_g(t.week_protein_g)} this week ({_g(t.week_protein_g / len(c.days))}/day)"
        f" | focus: {c.nutrition_priority.value}"
        + (f", then {c.secondary_priority.value}" if c.secondary_priority else ""),
        f"Cooking:   {_minutes(sum(t.hands_on_minutes.values()))} hands-on over "
        f"{len(t.hands_on_minutes)} cook days"
        f" | {t.meals} meals",
    ]
    if c.weekly_budget_cents is not None:
        lines.append(f"Budget:    {_money(c.weekly_budget_cents)} ({'hard' if c.budget_is_hard else 'soft'})")
    for spec in c.days:
        lines.append("")
        cooked = [b for b in plan.batches if b.cook_on == spec.day]
        head = f"{spec.day:%a}".upper() + f" {spec.day:%b} {spec.day.day}"
        if spec.is_cook_day:
            used = t.hands_on_minutes.get(spec.day, 0)
            cook_list = ", ".join(f"{b.title} x{b.portions}" for b in cooked) or "nothing"
            lines.append(
                f"{head} | cook day ({used} of {spec.cook_minutes_available} hands-on min): {cook_list}"
            )
        else:
            lines.append(f"{head} | leftovers, no cooking")
        for meal in (m for m in plan.meals if m.eat_on == spec.day):
            title = _meal_title(plan, meal, drafts)[:width]
            lines.append(
                f"  {_slot(meal.slot):16} {title:{width}} {meal.kcal:>6,} kcal "
                f"{_g(meal.protein_g):>9} protein"
            )
        lines.append(
            f"  {'Day':16} {'':{width}} {t.day_kcal[spec.day]:>6,} kcal "
            f"{_g(t.day_protein_g[spec.day]):>9} protein"
        )
    lines += ["", f"  {'WEEK':16} {'':{width}} {t.week_kcal:>6,} kcal {_g(t.week_protein_g):>9} protein", ""]
    g = plan.grocery
    lines.append("Grocery cost by store (estimated prices unless you entered them):")
    buy_counts: dict[int, int] = {}
    for item in g.items:
        if item.kind == "buy" and item.store_id is not None:
            buy_counts[item.store_id] = buy_counts.get(item.store_id, 0) + 1
    for store_id in c.store_ids:
        cents = g.store_cents.get(store_id, 0)
        lines.append(
            f"  {store_names.get(store_id, store_id):14} {_money(cents):>9}  "
            f"({buy_counts.get(store_id, 0)} items)"
        )
    total = f"  {'Total':14} {_money(g.total_cents):>9}"
    if g.unpriced:
        total += f" + {', '.join(g.unpriced)} (no price yet, so the cost is incomplete)"
    lines.append(total)
    primary = store_names.get(c.primary_store_id, "your primary store")
    threshold = _money(c.store_split_min_savings_cents)
    if g.split:
        lines.append(
            f"  Splitting stores saves {_money(g.savings_cents)} vs {primary} alone "
            f"(you split only for {threshold} or more)."
        )
    elif g.savings_cents > 0:
        lines.append(
            f"  Everything at {primary}: another store would save only {_money(g.savings_cents)} "
            f"(under {threshold})."
        )
    staples = sorted({item.name for item in g.items if item.kind == "staple"})
    if staples:
        lines.append(f"  Check you have: {', '.join(staples)}")
    from_inventory = sorted({item.name for item in g.items if item.kind == "from_inventory"})
    if from_inventory:
        lines.append(f"  From your inventory: {', '.join(from_inventory)}")
    if plan.notes:
        lines += ["", "Notes:"] + [f"  - {n}" for n in plan.notes]
    if outcome.report and outcome.report.warnings:
        lines += ["", "Warnings:"] + [f"  - {w.message}" for w in outcome.report.warnings]
    return "\n".join(lines)


def format_failure(outcome: PlanOutcome) -> str:
    error = outcome.error or {}
    lines = [
        f"Run #{outcome.run_id}: {outcome.status.upper()} "
        f"({outcome.llm_calls} LLM calls, {outcome.tokens:,} tokens)",
        f"{error.get('title', 'No plan')}:",
    ]
    diagnostics: Sequence[dict[str, object]] = error.get("diagnostics") or []
    if diagnostics:
        lines += [f"  - {d['message']}" for d in diagnostics]
    else:
        lines.append(f"  - {error.get('detail', 'unknown error')}")
    return "\n".join(lines)
