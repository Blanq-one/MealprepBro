"""Steady-state check: plan week after week, each from the inventory the previous week leaves behind.

Always a dry run: the caller rolls the session back. After each planned week, the lots it took from
inventory are reduced, and this trip's leftovers become lots: raw meat, poultry and fish in the freezer
(frozen on shopping day), long-keeping items where they usually live (the rest of a protein powder tub, a
bag of rice, eggs). At-risk perishables are not carried: they are that week's expected waste.

Seed and saved recipes only (zero LLM calls).
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.db.models import InventoryItem
from app.domain.enums import StorageLocation
from app.domain.units import convert
from app.planning.orchestrator import PlanOutcome
from app.planning.rounded import RoundedPlan
from app.schemas.plans import PlanRequest
from app.services.ingredient_data import load_ingredients
from app.services.inventory import LotInput, add_lot, set_quantity
from app.services.plans import run_plan_now

_Q3 = Decimal("0.001")


@dataclass(frozen=True)
class WeekRun:
    label: str  # "week 1", "week 2, budget $50.00"
    week_start: date
    outcome: PlanOutcome

    @property
    def plan(self) -> RoundedPlan | None:
        return self.outcome.plan if self.outcome.status == "succeeded" else None

    @property
    def protein_per_day(self) -> Decimal | None:
        plan = self.plan
        if plan is None:
            return None
        return (plan.totals.week_protein_g / len(plan.constraints.days)).quantize(
            Decimal("0.1"), ROUND_HALF_UP
        )


@dataclass(frozen=True)
class Carried:
    name: str
    quantity: Decimal
    unit: str
    location: str


@dataclass
class Simulation:
    runs: list[WeekRun] = field(default_factory=list)
    carried: list[list[Carried]] = field(default_factory=list)  # what each week passed on to the next


def carry_over(session: Session, user_id: int, plan: RoundedPlan) -> list[Carried]:
    """Apply one planned week to inventory (see the module docstring); returns the leftover lots added."""
    shop = plan.constraints.shopping_day
    units_by_ingredient = {item.ingredient_id: item.unit for item in plan.grocery.items}
    lots = {lot_id: quantity for lot_id, quantity in plan.grocery.inventory_takes}
    data = load_ingredients(session, {*units_by_ingredient, *(item.ingredient_id for item in plan.leftovers)})
    for lot_id, taken in sorted(lots.items()):
        lot = session.get(InventoryItem, lot_id)
        if lot is None or lot.status != "active":
            continue
        unit = units_by_ingredient.get(lot.ingredient_id, lot.unit)
        used = convert(taken, unit, lot.unit, data[lot.ingredient_id].units) if unit != lot.unit else taken
        left = max(lot.quantity - used.quantize(_Q3, ROUND_HALF_UP), Decimal(0))
        set_quantity(session, user_id, lot_id, left, note=f"simulated: used in the week of {shop}")
    carried = []
    for item in plan.leftovers:
        if item.fate == "at_risk":
            continue  # expected waste: not carried
        typical = data[item.ingredient_id].typical_location or "pantry"
        location = StorageLocation.FREEZER if item.fate == "freeze" else StorageLocation(typical)
        add_lot(
            session,
            user_id,
            LotInput(
                item.ingredient_id,
                item.quantity.quantize(_Q3, ROUND_HALF_UP),
                item.unit,
                location,
                acquired_on=shop,
                opened_on=shop,
                notes="simulated: left over from the week before",
            ),
        )
        carried.append(Carried(item.name, item.quantity, item.unit, location.value))
    session.flush()
    return carried


def simulate(
    session: Session,
    user_id: int,
    week_start: date,
    weeks: int = 2,
    *,
    budget_cents: int | None = None,
    last_week_budget_cents: int | None = None,
) -> Simulation:
    """Plan `weeks` consecutive weeks in shop mode, each from the leftovers of the one before. With
    `last_week_budget_cents`, the last week is planned a second time from the same inventory with that
    budget. The caller rolls the session back."""
    sim = Simulation()
    for n in range(weeks):
        start = week_start + timedelta(days=7 * n)
        last = n == weeks - 1
        if last and last_week_budget_cents is not None:
            savepoint = session.begin_nested()
            sim.runs.append(_run(session, user_id, start, f"week {n + 1}", budget_cents))
            savepoint.rollback()
            label = f"week {n + 1}, budget ${last_week_budget_cents / 100:.2f}"
            sim.runs.append(_run(session, user_id, start, label, last_week_budget_cents))
            break
        run = _run(session, user_id, start, f"week {n + 1}", budget_cents)
        sim.runs.append(run)
        if run.plan is None:
            break  # nothing to carry: the chain stops here
        if not last:
            sim.carried.append(carry_over(session, user_id, run.plan))
    return sim


def _run(session: Session, user_id: int, start: date, label: str, budget_cents: int | None) -> WeekRun:
    request = PlanRequest(week_start=start, budget_cents=budget_cents, allow_llm=False)
    return WeekRun(label, start, run_plan_now(session, user_id, request, None))


def format_table(sim: Simulation) -> str:
    """The steady-state table: one row per planned week."""

    def money(cents: int | None) -> str:
        return f"${cents / 100:,.2f}" if cents is not None else "-"

    header = (
        f"{'Week':32} {'Status':10} {'Regular':>9} {'Stock-up':>9} {'Eaten':>9} {'Waste':>8} "
        f"{'Protein/day':>12}"
    )
    lines = [header, "-" * len(header)]
    for run in sim.runs:
        plan = run.plan
        name = f"{run.week_start:%b %d} ({run.label})"
        if plan is None:
            lines.append(f"{name:32} {run.outcome.status:10} {'-':>9} {'-':>9} {'-':>9} {'-':>8} {'-':>12}")
            continue
        m = plan.costs
        protein = f"{run.protein_per_day} g"
        lines.append(
            f"{name:32} {plan.solver_status:10} {money(m.regular_cash_cents):>9} "
            f"{money(m.stock_up_cash_cents):>9} {money(m.eaten_cents):>9} "
            f"{money(m.expected_waste_cents):>8} {protein:>12}"
        )
    return "\n".join(lines)
