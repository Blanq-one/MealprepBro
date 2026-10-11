"""Plain-text week report for `cli plan-week`: the planning mode, each day's meals, daily and weekly kcal and
protein against the target, hands-on and start-to-finish cooking time, the week's money (cash this trip,
food eaten, leftovers carried into inventory, expected waste), cost by store or the top-up buy list,
freeze-on-shopping-day instructions, notes, warnings, or the infeasibility explanation. Formatting only;
every number comes from the plan."""

from collections.abc import Mapping, Sequence
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.domain.enums import CalorieMode, MealSlot, NutritionPriority, PlanningMode
from app.domain.quantities import format_fraction
from app.planning.orchestrator import PlanOutcome
from app.planning.perishables import freeze_text
from app.planning.rounded import RoundedMeal, RoundedPlan

MAX_TITLE = 70


def _money(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def _minutes(total: int) -> str:
    hours, minutes = divmod(total, 60)
    return f"{hours} h {minutes:02d} min" if hours else f"{minutes} min"


def _amount(quantity: Decimal, unit: str) -> str:
    if unit == "count":
        return format_fraction(quantity.quantize(Decimal("0.5"), ROUND_HALF_UP))
    return f"{quantity.quantize(Decimal(1), ROUND_HALF_UP):,} {unit}"


def mode_line(plan: RoundedPlan) -> str:
    c = plan.constraints
    limit = c.purchase_limit_cents
    if c.planning_mode is PlanningMode.INVENTORY:
        if not limit:
            return "inventory: cook from what you have, buy nothing"
        return f"inventory: cook from what you have, with a top-up of up to {_money(limit)} for missing items"
    first = "shop: your inventory first, then the grocery list"
    if limit is None:
        return f"{first} (no budget: the cost is minimized)"
    return f"{first} (budget: {_money(limit)} on regular groceries this trip, a hard limit; stock-up apart)"


def protein_line(plan: RoundedPlan) -> str:
    c = plan.constraints
    t = plan.totals
    text = f"{_g(t.week_protein_g)} this week ({_g(t.week_protein_g / len(c.days))}/day)"
    focus = [
        p.value
        for p in (c.nutrition_priority, c.secondary_priority)
        if p and p is not NutritionPriority.PROTEIN
    ]
    if focus:
        text += f" | focus: {', then '.join(focus)}"
    target = c.daily_protein_target_g
    if not target:
        return text + " | no protein target"
    if c.calorie_mode is CalorieMode.STRICT_DAILY:
        return text + f" | target {target} g every day (a floor; more earns nothing)"
    week = c.week_protein_target_g
    return text + f" | target {target} g/day, week >= {week:,} g (a floor; more earns nothing)"


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
        f"Mode:      {mode_line(plan)}",
        f"Calories:  {t.week_kcal:,} / {c.weekly_kcal_target:,} kcal planned ({limits_line(plan)})",
        f"Protein:   {protein_line(plan)}",
        f"Cooking:   {_minutes(sum(t.hands_on_minutes.values()))} hands-on, about "
        f"{_minutes(sum(t.elapsed_minutes.values()))} start to finish, over "
        f"{len(t.hands_on_minutes)} cook days"
        f" | {t.meals} meals",
    ]
    for spec in c.days:
        lines.append("")
        cooked = [b for b in plan.batches if b.cook_on == spec.day]
        head = f"{spec.day:%a}".upper() + f" {spec.day:%b} {spec.day.day}"
        if spec.is_cook_day:
            used = t.hands_on_minutes.get(spec.day, 0)
            cook_list = ", ".join(f"{b.title} x{b.portions}" for b in cooked) or "nothing"
            timing = f"{used} of {spec.cook_minutes_available} hands-on min"
            if cooked:
                timing += f", about {_minutes(t.elapsed_minutes.get(spec.day, 0))} start to finish"
            if chill := t.chill_minutes.get(spec.day, 0):
                timing += f", then up to {_minutes(chill)} in the fridge"
            lines.append(f"{head} | cook day ({timing}): {cook_list}")
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
    lines += money_lines(plan)
    g = plan.grocery
    lines.append("")
    if c.planning_mode is PlanningMode.INVENTORY:
        lines += topup_lines(plan, store_names)
    lines.append("Regular groceries by store (estimated prices unless you entered them):")
    buy_counts: dict[int, int] = {}
    regular_cents: dict[int, int] = {}
    for item in g.items:
        if item.kind == "buy" and item.store_id is not None and not item.stock_up:
            buy_counts[item.store_id] = buy_counts.get(item.store_id, 0) + 1
            regular_cents[item.store_id] = regular_cents.get(item.store_id, 0) + (item.cost_cents or 0)
    for store_id in c.store_ids:
        if store_id in c.store_ids[2:] and store_id not in regular_cents:
            continue  # "Other" and further stores only when something regular is bought there
        lines.append(
            f"  {store_names.get(store_id, store_id):14} {_money(regular_cents.get(store_id, 0)):>9}  "
            f"({buy_counts.get(store_id, 0)} items)"
        )
    total = f"  {'Total':14} {_money(g.regular_cents):>9}"
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
    lines += stock_up_lines(plan, store_names)
    if plan.freeze:
        lines += ["", "Freeze on shopping day (raw meat, poultry and fish past their fridge life):"]
        lines += [f"  - {freeze_text(f, _amount(f.quantity, f.unit))}" for f in plan.freeze]
    if plan.notes:
        lines += ["", "Notes:"] + [f"  - {n}" for n in plan.notes]
    if outcome.report and outcome.report.warnings:
        lines += ["", "Warnings:"] + [f"  - {w.message}" for w in outcome.report.warnings]
    return "\n".join(lines)


def money_lines(plan: RoundedPlan) -> list[str]:
    m = plan.costs
    by_fate: dict[str, int] = {}
    for item in plan.leftovers:
        by_fate[item.fate] = by_fate.get(item.fate, 0) + item.cents
    labels = (("freeze", "raw protein to freeze"), ("keeps", "keeps"), ("at_risk", "at risk"))
    parts = [f"{label} {_money(by_fate[fate])}" for fate, label in labels if by_fate.get(fate)]
    eaten = f"  Food eaten         {_money(m.eaten_cents):>9}  this week"
    if m.from_inventory_cents:
        eaten += f", {_money(m.from_inventory_cents)} of it from your inventory"
    left = f"  Left over          {_money(m.leftover_cents):>9}  carries into your inventory"
    if parts:
        left += f" ({', '.join(parts)})"
    cash = f"  Cash this trip     {_money(m.cash_cents):>9}  whole packages"
    if m.stock_up_cash_cents:
        cash += f": {_money(m.regular_cash_cents)} regular + {_money(m.stock_up_cash_cents)} stock-up"
    lines = ["Money (estimated prices unless you entered them; staples not counted):", cash, eaten, left]
    if m.frozen_portions_cents:
        frozen = _money(m.frozen_portions_cents)
        lines.append(f"  Frozen portions    {frozen:>9}  cooked extras for later weeks")
    lines.append(f"  Expected waste     {_money(m.expected_waste_cents):>9}  perishables likely to spoil")
    if not m.complete:
        lines.append(f"  Incomplete: no price yet for {', '.join(m.unpriced)}")
    return lines


def stock_up_lines(plan: RoundedPlan, store_names: Mapping[int, str]) -> list[str]:
    """Stock-up purchases: long-life items bought occasionally, outside a shop-mode budget."""
    bought = [item for item in plan.grocery.items if item.kind == "buy" and item.stock_up]
    if not bought:
        return []
    lines = [
        "",
        f"Also buy this week (stock-up, lasts beyond this week): {_money(plan.grocery.stock_up_cents)}",
    ]
    for item in bought:
        if item.packages:
            what = f"{item.packages} pack" + ("" if item.packages == 1 else "s")
        else:
            what = _amount(item.bought or item.to_buy, item.unit)
        store = store_names.get(item.store_id or 0, "?")
        lines.append(f"  {item.name:40} {what:>10}  {_money(item.cost_cents or 0):>8}  at {store}")
    return lines


def topup_lines(plan: RoundedPlan, store_names: Mapping[int, str]) -> list[str]:
    bought = [item for item in plan.grocery.items if item.kind == "buy"]
    if not bought:
        return ["Top-up buy list: nothing to buy, everything comes from your inventory."]
    limit = plan.constraints.purchase_limit_cents or 0
    lines = [f"Top-up buy list ({_money(plan.grocery.total_cents)} of your {_money(limit)} top-up):"]
    for item in bought:
        if item.packages:
            what = f"{item.packages} pack" + ("" if item.packages == 1 else "s")
        else:
            what = _amount(item.bought or item.to_buy, item.unit)
        store = store_names.get(item.store_id or 0, "?")
        lines.append(f"  {item.name:40} {what:>10}  {_money(item.cost_cents or 0):>8}  at {store}")
    return lines


def format_failure(outcome: PlanOutcome) -> str:
    error = outcome.error or {}
    lines = [
        f"Run #{outcome.run_id}: {outcome.status.upper()} "
        f"({outcome.llm_calls} LLM calls, {outcome.tokens:,} tokens)",
        f"{error.get('title', 'No plan')}:",
    ]
    diagnostics: Sequence[dict[str, Any]] = error.get("diagnostics") or []
    for d in diagnostics:
        lines.append(f"  - {d['message']}")
        if items := d.get("items"):
            lines.append(f"    It would buy: {'; '.join(str(i) for i in items)}.")
        dollars = int(d["suggested_cents"]) // 100 if d.get("suggested_cents") else None
        if dollars is not None and d.get("code") == "INVENTORY_SHORT":
            lines.append(f"    Raise --topup to at least {dollars}, or plan with --mode shop.")
        elif dollars is not None and d.get("code") == "BUDGET_SHORT":
            lines.append(f"    Raise --budget to at least {dollars}.")
    if not diagnostics:
        lines.append(f"  - {error.get('detail', 'unknown error')}")
    return "\n".join(lines)
