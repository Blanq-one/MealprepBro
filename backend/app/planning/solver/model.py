"""The weekly plan MILP (PuLP).

Decisions:
  * batches: recipe version × portion size × cook day (only on cook days whose mood and hands-on minutes
    allow the recipe), each with a portion multiplier within ±portion_nudge_pct (continuous, so the
    solver can fine-tune a tight day without three near-identical copies of every batch);
  * assignments: each batch portion to one (day, slot) within the fridge window, or later from the
    freezer for freezer-friendly recipes;
  * purchases: packages per (product, store) offer, or a loose amount. An ingredient sold only in packages
    costs at least one whole package once any batch that needs it is cooked, so the cost is close to the
    cash you hand over (whole packages are exact on the grocery list);
  * inventory used (open packages and expiring lots are rewarded).

Hard constraints: every slot filled once, no recipe twice a day, the weekly variety cap on meals, cook
minutes, calorie limits per mode, the protein floor per mode, the purchase limit (shop-mode budget or
inventory-mode top-up), frequency caps, portion requests, supply ≥ need.
The secondary store carries a fixed charge equal to the split threshold, so it is used only when it
saves at least that much (R4); the grocery list re-checks the rule exactly on the rounded plan.

Waste: perishable food bought and not used is penalized, and more steeply once less than a quarter of a
package is used (opening a pack for a sliver of it).

Never-favored capped recipes (pork components) get no nutrient bonus, their cost is counted at no less
than the slot's median candidate cost, inventory they use is charged at purchase price, and a small
tie-breaker makes an otherwise-equal recipe win.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from statistics import median
from typing import Any

import pulp

from app.domain.cook_time import mood_allows
from app.domain.enums import CalorieMode, MealSlot, PortionSize
from app.planning.problem import CandidateRecipe, PlanningProblem, size_multiplier
from app.planning.solver.backend import solve_milp
from app.planning.solver.objective import nutrient_score, weights_for
from app.schemas.constraints import VARIETY_CAPPED_SLOTS

BIG_PORTIONS = 21  # upper bound on portions per batch (need sizing only)
MAX_FROZEN_EXTRAS = 20
SLOT_DEAD_ZONE = 0.15  # deviation within ±15% of a slot target is free
MULTIPLIER_STEP = Decimal("0.001")
# Practical rounding moves a day by a few kcal either way; the solver keeps this much room inside each
# limit so the rounded plan rarely needs a re-solve. The plan validator checks your exact limits.
ROUNDING_MARGIN_DAY_KCAL = 5
ROUNDING_MARGIN_WEEK_KCAL = 20
ROUNDING_MARGIN_DAY_PROTEIN_G = 1
ROUNDING_MARGIN_WEEK_PROTEIN_G = 3
# A perishable package with more than this share left over counts as "opened for a sliver of it".
SMALL_FRACTION_LEFT = 0.75
# Package counts are integers only for perishable packs of at least this price (chicken trays, big yogurt
# tubs), where buying one more pack is a real decision. Every other package offer is costed per unit, with
# a floor of one whole package per ingredient tied to the batch decisions (no extra integer variables);
# the grocery list computes exact packages, stores and costs on the rounded plan. Modeling every offer as an
# integer made a real week take ~56 s; a yes/no per offer for its first package took ~10-50 s.
WHOLE_PACKAGE_MIN_CENTS = 500


class EmptyCandidatePoolError(ValueError):
    """No candidate recipe survived the hard filters (equipment, exclusions, nutrition, time)."""

    def __init__(self, message: str, reasons: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.reasons = reasons


@dataclass(frozen=True)
class SolvedBatch:
    version_id: int
    cook_on: date
    portion_size: PortionSize
    nudge: Decimal  # the solver's fine-tuning multiplier within ±portion_nudge_pct
    portions: int
    portions_to_freeze: int = 0  # extra portions frozen for later weeks (not eaten this week)

    @property
    def multiplier(self) -> Decimal:
        return size_multiplier(self.portion_size) * self.nudge


@dataclass(frozen=True)
class SolvedMeal:
    eat_on: date
    slot: MealSlot
    batch_index: int
    from_freezer: bool = False


@dataclass(frozen=True)
class SolverSolution:
    status: str  # optimal | feasible
    objective: float
    batches: tuple[SolvedBatch, ...]
    meals: tuple[SolvedMeal, ...]
    day_kcal: Mapping[date, Decimal]  # raw, unrounded kcal per day
    stores_used: frozenset[int]
    estimated_purchase_cents: int


@dataclass(frozen=True)
class Diagnostic:
    code: str
    message: str
    slot: MealSlot | None = None
    day: date | None = None
    amount: int | None = None


@dataclass(frozen=True)
class SolverInfeasible:
    diagnostics: tuple[Diagnostic, ...]


SolverResult = SolverSolution | SolverInfeasible


@dataclass(frozen=True)
class _Batch:
    index: int
    recipe: CandidateRecipe
    cook_on: date
    size: PortionSize
    targets: tuple[tuple[date, MealSlot], ...]

    @property
    def size_multiplier(self) -> Decimal:
        return size_multiplier(self.size)

    @property
    def kcal(self) -> float:
        """kcal of one portion at nudge 1."""
        return float(self.recipe.kcal * self.size_multiplier)


@dataclass
class _Model:
    prob: pulp.LpProblem
    batches: list[_Batch]
    x: dict[tuple[int, date, MealSlot], pulp.LpVariable]
    y: dict[int, pulp.LpVariable]
    nudge: dict[int, pulp.LpVariable]
    frozen: dict[int, pulp.LpVariable]
    day_kcal: dict[date, Any]
    purchase_cost: Any
    store_used: dict[int, pulp.LpVariable]
    slacks: dict[str, dict[Any, pulp.LpVariable]] = field(default_factory=dict)
    day_protein: dict[date, Any] = field(default_factory=dict)
    # per ingredient: (amount bought in its planning unit, cents spent on it)
    purchases: dict[int, tuple[Any, Any]] = field(default_factory=dict)


def _f(value: Decimal | int | float) -> float:
    return float(value)


def batch_plan(problem: PlanningProblem) -> list[_Batch]:
    """Every allowed (recipe, cook day, size) with the (day, slot) pairs it could feed."""
    c = problem.constraints
    fridge = c.leftover_fridge_days
    needed = {(d.day, s): c.portion_size_for(d.day, s) for d in c.days for s in d.slots}
    sizes = sorted(set(needed.values()), key=lambda z: z.value)
    batches: list[_Batch] = []
    for recipe in sorted(problem.candidates, key=lambda r: r.version_id):
        for cook in c.days:
            if not cook.is_cook_day or not mood_allows(cook.mood, recipe.mood):
                continue
            if recipe.active_minutes > cook.cook_minutes_available:
                continue
            for size in sizes:
                targets = tuple(
                    (e, s)
                    for (e, s), z in sorted(needed.items(), key=lambda kv: (kv[0][0], kv[0][1].value))
                    if z == size
                    and s in recipe.meal_slots
                    and e >= cook.day
                    and ((e - cook.day).days <= fridge or recipe.freezer_friendly)
                )
                if targets:
                    batches.append(_Batch(len(batches), recipe, cook.day, size, targets))
    return batches


def _median_costs(problem: PlanningProblem) -> dict[MealSlot, Decimal]:
    out: dict[MealSlot, Decimal] = {}
    slots = {s for d in problem.constraints.days for s in d.slots}
    for slot in slots:
        costs = [
            r.cost_cents_per_portion
            for r in problem.candidates
            if slot in r.meal_slots and not r.never_favored and r.cost_cents_per_portion is not None
        ]
        if not costs:
            costs = [
                r.cost_cents_per_portion
                for r in problem.candidates
                if slot in r.meal_slots and r.cost_cents_per_portion is not None
            ]
        if costs:
            out[slot] = Decimal(str(median(costs)))
    return out


def _day_limits(problem: PlanningProblem, day: date) -> tuple[float, float]:
    """(floor, ceiling) for one day, per calorie mode, after any tightening."""
    c = problem.constraints
    spec = c.day(day)
    tol = c.tolerance
    if c.calorie_mode is CalorieMode.STRICT_DAILY:
        ceiling = float(spec.kcal_target)
        floor = spec.kcal_target * (1 - tol.daily_under_pct / 100)
    else:
        ceiling = float(spec.kcal_target + tol.daily_band_kcal)
        floor = float(spec.kcal_target - tol.daily_band_kcal)
    t = problem.tightening
    return (
        floor + ROUNDING_MARGIN_DAY_KCAL + t.day_floor.get(day, 0),
        ceiling - ROUNDING_MARGIN_DAY_KCAL - t.day_ceiling.get(day, 0),
    )


def build_model(
    problem: PlanningProblem, *, elastic: bool = False, allowed_store_ids: Iterable[int] | None = None
) -> _Model:
    c = problem.constraints
    w = weights_for(c.grocery_mode)
    batches = batch_plan(problem)
    prob = pulp.LpProblem("weekly_plan_elastic" if elastic else "weekly_plan", pulp.LpMaximize)
    stores = list(allowed_store_ids) if allowed_store_ids is not None else list(c.store_ids)
    primary = c.primary_store_id
    nudges = problem.nudges()
    lo, hi = _f(min(nudges)), _f(max(nudges))
    wants_frozen = any(req.extra_portions_to_freeze for req in c.portion_requests)

    # ---- variables ----
    x: dict[tuple[int, date, MealSlot], pulp.LpVariable] = {}
    y: dict[int, pulp.LpVariable] = {}
    nudge: dict[int, pulp.LpVariable] = {}
    frozen: dict[int, pulp.LpVariable] = {}
    for b in batches:
        y[b.index] = pulp.LpVariable(f"y_{b.index}", cat=pulp.LpBinary)
        for e, s in b.targets:
            x[(b.index, e, s)] = pulp.LpVariable(f"x_{b.index}_{e:%m%d}_{s.value}", cat=pulp.LpBinary)
        if wants_frozen and b.recipe.freezer_friendly:
            # batches that may freeze extras keep multiplier 1, so need stays linear
            frozen[b.index] = pulp.LpVariable(
                f"fz_{b.index}", lowBound=0, upBound=MAX_FROZEN_EXTRAS, cat=pulp.LpInteger
            )
        elif hi > lo:
            nudge[b.index] = pulp.LpVariable(f"m_{b.index}", lowBound=lo, upBound=hi)

    # scaled[(b, e, s)] = nudge_b × x_bes, linearized exactly (x is binary)
    scaled: dict[tuple[int, date, MealSlot], Any] = {}
    for key, var in x.items():
        bi = key[0]
        if bi not in nudge:
            scaled[key] = var
            continue
        u = pulp.LpVariable(f"u_{bi}_{key[1]:%m%d}_{key[2].value}", lowBound=0, upBound=hi)
        m = nudge[bi]
        tag = f"{bi}_{key[1]:%m%d}_{key[2].value}"
        prob += u <= hi * var, f"mc1_{tag}"
        prob += u >= lo * var, f"mc2_{tag}"
        prob += u <= m - lo * (1 - var), f"mc3_{tag}"
        prob += u >= m - hi * (1 - var), f"mc4_{tag}"
        scaled[key] = u

    by_batch: dict[int, list[tuple[Any, Any]]] = defaultdict(list)  # (x, scaled)
    by_slot: dict[tuple[date, MealSlot], list[tuple[_Batch, Any, Any]]] = defaultdict(list)
    by_recipe_day: dict[tuple[int, date], list[pulp.LpVariable]] = defaultdict(list)
    for key, var in x.items():
        bi, e, s = key
        b = batches[bi]
        by_batch[bi].append((var, scaled[key]))
        by_slot[(e, s)].append((b, var, scaled[key]))
        by_recipe_day[(b.recipe.version_id, e)].append(var)

    def portions(b: _Batch) -> Any:
        terms: list[Any] = [xv for xv, _ in by_batch[b.index]]
        if b.index in frozen:
            terms.append(frozen[b.index])
        return pulp.lpSum(terms)

    def scaled_portions(b: _Batch) -> Any:
        terms: list[Any] = [sv for _, sv in by_batch[b.index]]
        if b.index in frozen:
            terms.append(frozen[b.index])
        return pulp.lpSum(terms)

    slacks: dict[str, dict[Any, pulp.LpVariable]] = defaultdict(dict)

    def slack(kind: str, key: Any, up: float | None = None) -> pulp.LpVariable:
        var = pulp.LpVariable(f"sl_{kind}_{len(slacks[kind])}", lowBound=0, upBound=up)
        slacks[kind][key] = var
        return var

    # ---- batch structure ----
    # Disaggregated links (x ≤ y for every assignment) keep the LP relaxation tight: a batch can't be
    # "1/21 cooked", so cook minutes and batch counts are counted honestly while branching.
    for (bi, e, s), var in x.items():
        prob += var <= y[bi], f"link_{bi}_{e:%m%d}_{s.value}"
    for b in batches:
        if b.index in frozen:
            prob += frozen[b.index] <= MAX_FROZEN_EXTRAS * y[b.index], f"frozen_on_{b.index}"
        prob += portions(b) >= y[b.index], f"batch_nonempty_{b.index}"

    # ---- every planned slot filled exactly once ----
    for d in c.days:
        for s in d.slots:
            options = [xv for _, xv, _ in by_slot[(d.day, s)]]
            if elastic:
                prob += (
                    pulp.lpSum(options) + slack("miss", (d.day, s), 1) == 1,
                    f"fill_{d.day:%m%d}_{s.value}",
                )
            else:
                prob += pulp.lpSum(options) == 1, f"fill_{d.day:%m%d}_{s.value}"

    # ---- no recipe twice in a day ----
    for (vid, e), vars_ in sorted(by_recipe_day.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        if len(vars_) > 1:
            prob += pulp.lpSum(vars_) <= 1, f"once_a_day_{vid}_{e:%m%d}"

    # ---- weekly variety cap on meals (Q14; desserts, snacks and drinks exempt) ----
    by_recipe_meals: dict[int, list[pulp.LpVariable]] = defaultdict(list)
    for (bi, _e, s), var in x.items():
        if s in VARIETY_CAPPED_SLOTS:
            by_recipe_meals[batches[bi].recipe.version_id].append(var)
    for vid, vars_ in sorted(by_recipe_meals.items()):
        if len(vars_) > c.max_portions_per_recipe:
            extra = slack("variety", vid) if elastic else 0
            prob += pulp.lpSum(vars_) <= c.max_portions_per_recipe + extra, f"variety_{vid}"

    # ---- frequency caps (meals eaten from batches containing a member) ----
    for ci, cap in enumerate(c.frequency_caps):
        members = [
            var
            for (bi, _e, _s), var in x.items()
            if batches[bi].recipe.ingredient_ids & cap.member_ingredient_ids
        ]
        if members:
            extra = slack("cap", cap.label) if elastic else 0
            prob += pulp.lpSum(members) <= cap.max_meals_per_week + extra, f"cap_{ci}"

    # ---- hands-on cook minutes per cook day ----
    for d in c.days:
        day_batches = [b for b in batches if b.cook_on == d.day]
        if not day_batches:
            continue
        used = pulp.lpSum(b.recipe.active_minutes * y[b.index] for b in day_batches)
        extra = slack("time", d.day) if elastic else 0
        prob += used <= d.cook_minutes_available + extra, f"minutes_{d.day:%m%d}"

    # ---- calories (from the unrounded recipe lines; the validator re-checks the rounded values) ----
    t = problem.tightening
    tol = c.tolerance
    day_kcal: dict[date, Any] = {}
    bias = {vid: _f(v) for vid, v in t.kcal_bias.items()}
    kcal_scale = {vid: _f(v) for vid, v in t.kcal_scale.items()}

    def meal_kcal(b: _Batch, xv: Any, sv: Any) -> Any:
        """kcal of one assigned portion as practical rounding will make it: planned kcal × nudge × the
        recipe's rounding scale, plus its rounding bias."""
        vid = b.recipe.version_id
        coef = b.kcal * kcal_scale.get(vid, 1.0)
        extra = bias.get(vid, 0.0)
        return coef * sv + extra * xv if extra else coef * sv

    for d in c.days:
        expr = pulp.lpSum(meal_kcal(b, xv, sv) for s in d.slots for b, xv, sv in by_slot[(d.day, s)])
        day_kcal[d.day] = expr
        floor, ceiling = _day_limits(problem, d.day)
        over = slack("kcal_over", d.day) if elastic else 0
        under = slack("kcal_under", d.day) if elastic else 0
        prob += expr <= ceiling + over, f"kcal_max_{d.day:%m%d}"
        prob += expr >= floor - under, f"kcal_min_{d.day:%m%d}"
    if c.calorie_mode is CalorieMode.WEEKLY:
        week = pulp.lpSum(day_kcal.values())
        over = slack("week_over", "week") if elastic else 0
        under = slack("week_under", "week") if elastic else 0
        week_max = c.weekly_kcal_target - ROUNDING_MARGIN_WEEK_KCAL - t.week_ceiling
        week_min = (
            c.weekly_kcal_target * (1 - tol.weekly_under_pct / 100) + ROUNDING_MARGIN_WEEK_KCAL + t.week_floor
        )
        prob += week <= week_max + over, "kcal_week_max"
        prob += week >= week_min - under, "kcal_week_min"

    # ---- protein: a floor per calorie mode; protein above it earns nothing ----
    protein_bias = {vid: _f(v) for vid, v in t.protein_bias.items()}
    protein_scale = {vid: _f(v) for vid, v in t.protein_scale.items()}

    def meal_protein(b: _Batch, xv: Any, sv: Any) -> Any:
        vid = b.recipe.version_id
        coef = _f(b.recipe.protein_g * b.size_multiplier) * protein_scale.get(vid, 1.0)
        extra = protein_bias.get(vid, 0.0)
        return coef * sv + extra * xv if extra else coef * sv

    day_protein: dict[date, Any] = {
        d.day: pulp.lpSum(meal_protein(b, xv, sv) for s in d.slots for b, xv, sv in by_slot[(d.day, s)])
        for d in c.days
    }
    target = c.daily_protein_target_g
    if target > 0:
        if c.calorie_mode is CalorieMode.STRICT_DAILY:
            for d in c.days:
                floor = target + ROUNDING_MARGIN_DAY_PROTEIN_G + _f(t.protein_day_floor.get(d.day, 0))
                short = slack("protein_day", d.day) if elastic else 0
                prob += day_protein[d.day] >= floor - short, f"protein_min_{d.day:%m%d}"
        else:
            floor = c.week_protein_target_g + ROUNDING_MARGIN_WEEK_PROTEIN_G + _f(t.protein_week_floor)
            short = slack("protein_week", "week") if elastic else 0
            prob += pulp.lpSum(day_protein.values()) >= floor - short, "protein_week_min"

    # ---- portion requests ----
    for ri, req in enumerate(c.portion_requests):
        eligible = sorted({b.recipe.version_id for b in batches if req.slot in b.recipe.meal_slots})
        if req.same_recipe:
            pick = {vid: pulp.LpVariable(f"req_{ri}_{vid}", cat=pulp.LpBinary) for vid in eligible}
            prob += pulp.lpSum(pick.values()) == 1, f"req_one_{ri}"
            for day in req.days:
                for b, xv, _ in by_slot[(day, req.slot)]:
                    prob += xv <= pick[b.recipe.version_id], f"req_{ri}_{day:%m%d}_{b.index}"
            if req.extra_portions_to_freeze:
                for vid, choose in pick.items():
                    extras = [
                        frozen[b.index] for b in batches if b.recipe.version_id == vid and b.index in frozen
                    ]
                    prob += (
                        pulp.lpSum(extras) >= req.extra_portions_to_freeze * choose,
                        f"req_freeze_{ri}_{vid}",
                    )
        elif req.extra_portions_to_freeze:
            extras = [
                frozen[b.index] for b in batches if b.recipe.version_id in eligible and b.index in frozen
            ]
            prob += pulp.lpSum(extras) >= req.extra_portions_to_freeze, f"req_freeze_{ri}"

    # ---- ingredient supply, purchases and inventory ----
    week_end = c.week_end
    never_favored_ids = frozenset(
        i for cap in c.frequency_caps if cap.never_favor for i in cap.member_ingredient_ids
    )
    cost_terms: list[Any] = []
    waste_terms: list[Any] = []
    sliver_terms: list[Any] = []
    purchases_by_ingredient: dict[int, tuple[Any, Any]] = {}
    inventory_bonus: list[Any] = []
    inventory_charge: list[Any] = []
    store_used: dict[int, pulp.LpVariable] = {}
    secondary_offer_vars: dict[int, list[pulp.LpVariable]] = defaultdict(list)
    need_terms: dict[int, list[tuple[float, _Batch]]] = defaultdict(list)
    for b in batches:
        for ingredient_id, per_portion in b.recipe.need_per_portion.items():
            if per_portion > 0:
                need_terms[ingredient_id].append((_f(per_portion * b.size_multiplier), b))
    for ingredient_id in sorted(need_terms):
        plan = problem.ingredients[ingredient_id]
        if plan.staple:
            continue
        need = pulp.lpSum(coef * scaled_portions(b) for coef, b in need_terms[ingredient_id])
        max_need = sum(coef * BIG_PORTIONS * hi for coef, _ in need_terms[ingredient_id])
        offers = [o for o in plan.offers if o.store_id in stores]
        open_avail = _f(plan.available_where(opened=True))
        exp_avail = _f(
            sum(
                (
                    lot.quantity
                    for lot in plan.lots
                    if not lot.opened and lot.expires_on is not None and lot.expires_on <= week_end
                ),
                Decimal(0),
            )
        )
        other_avail = _f(plan.available) - open_avail - exp_avail
        holdback = _f(t.inventory_holdback.get(ingredient_id, 0))
        inv_parts = []
        for label, avail in (("open", open_avail), ("exp", exp_avail), ("oth", other_avail)):
            if avail > 0:
                var = pulp.LpVariable(f"inv_{label}_{ingredient_id}", lowBound=0, upBound=avail)
                inv_parts.append((label, avail, var))
        inventory = pulp.lpSum(var for _, _, var in inv_parts)
        if inv_parts:
            prob += inventory <= need, f"inv_le_need_{ingredient_id}"
            if holdback > 0:
                prob += inventory <= max(_f(plan.available) - holdback, 0), f"inv_holdback_{ingredient_id}"
            if ingredient_id in never_favored_ids:
                unit_cents = min((o.cents_per_unit for o in offers), default=Decimal(0))
                inventory_charge.append(_f(unit_cents) / 100 * inventory)
            else:
                for label, avail, var in inv_parts:
                    if label in ("open", "exp"):
                        inventory_bonus.append(var * (1 / avail))
        if not offers:
            if c.has_purchase_limit:
                prob += inventory >= need, f"unpriced_from_inventory_{ingredient_id}"
            continue
        bought = []
        spent = []
        all_whole = True
        for o in sorted(offers, key=lambda o: o.ref):
            if o.package_amount is not None:
                assert o.package_cents is not None
                upper = int(max_need / _f(o.package_amount)) + 2
                whole = plan.perishable and o.package_cents >= WHOLE_PACKAGE_MIN_CENTS
                all_whole = all_whole and whole
                category = pulp.LpInteger if whole else pulp.LpContinuous
                q = pulp.LpVariable(f"pk_{ingredient_id}_{o.ref}", lowBound=0, upBound=upper, cat=category)
                bought.append(_f(o.package_amount) * q)
                spent.append(o.package_cents * q)
            else:
                all_whole = False
                q = pulp.LpVariable(f"ls_{ingredient_id}_{o.ref}", lowBound=0, upBound=max_need + 1)
                bought.append(q)
                spent.append(_f(o.cents_per_unit) * q)
            if o.store_id != primary:
                secondary_offer_vars[o.store_id].append(q)
        purchases = pulp.lpSum(bought)
        per_unit = pulp.lpSum(spent)
        cost: Any = per_unit
        packs = [o for o in offers if o.package_cents is not None]
        # The first package is whole: nobody sells a third of a bottle. Only for ingredients sold in packages
        # alone, with no inventory that might cover them (then the floor could overcharge).
        if packs and len(packs) == len(offers) and not all_whole and not inv_parts:
            first_pack = min(o.package_cents for o in packs if o.package_cents is not None)
            used = pulp.LpVariable(f"used_{ingredient_id}", lowBound=0, upBound=1)
            users = {b.index for _, b in need_terms[ingredient_id]}
            for _, b in need_terms[ingredient_id]:
                prob += used >= y[b.index], f"uses_{ingredient_id}_{b.index}"
            # each meal slot is filled once, so the share of a slot served by batches that need the
            # ingredient is a lower bound on "used" too (much tighter in the LP relaxation)
            for (day, slot), options in sorted(by_slot.items(), key=lambda kv: (kv[0][0], kv[0][1].value)):
                terms = [xv for b, xv, _ in options if b.index in users]
                if terms:
                    prob += used >= pulp.lpSum(terms), f"uses_{ingredient_id}_{day:%m%d}_{slot.value}"
            cost = pulp.LpVariable(f"cash_{ingredient_id}", lowBound=0)
            prob += cost >= per_unit, f"cash_units_{ingredient_id}"
            prob += cost >= first_pack * used, f"cash_first_pack_{ingredient_id}"
        cost_terms.append(cost)
        purchases_by_ingredient[ingredient_id] = (purchases, cost)
        prob += inventory + purchases >= need, f"supply_{ingredient_id}"
        if plan.perishable:
            # cents of perishable food bought and not used: whole packs left over, plus the unused part of a
            # first package
            waste_rate = _f(min(o.cents_per_unit for o in offers))
            waste = waste_rate * (purchases + inventory - need) + (cost - per_unit)
            waste_terms.append(waste)
            if packs:
                smallest = min(o.package_cents for o in packs if o.package_cents is not None)
                sliver = pulp.LpVariable(f"sliver_{ingredient_id}", lowBound=0)
                prob += sliver >= waste - SMALL_FRACTION_LEFT * smallest, f"sliver_{ingredient_id}"
                sliver_terms.append(sliver)
    for store_id in sorted(secondary_offer_vars):
        used = pulp.LpVariable(f"store_{store_id}", cat=pulp.LpBinary)
        store_used[store_id] = used
        for q in secondary_offer_vars[store_id]:
            big = q.upBound if q.upBound is not None else 1000
            prob += q <= big * used, f"store_gate_{store_id}_{q.name}"
    purchase_cost = pulp.lpSum(cost_terms)

    if c.purchase_limit_cents is not None:
        limit = max(c.purchase_limit_cents - t.budget_cents, 0)
        extra = slack("budget", "budget") if elastic else 0
        prob += purchase_cost <= limit + extra, "purchase_limit"

    # ---- objective ----
    if elastic:
        weights = {
            "miss": 1000,
            "kcal_over": 1,
            "kcal_under": 1,
            "week_over": 1,
            "week_under": 1,
            "time": 5,
            "budget": 0.1,
            "protein_day": 2,
            "protein_week": 2,
            "cap": 200,
            "variety": 200,
        }
        # a tiny cost term, so the purchases inside the limit are the cheapest ones too (the diagnostics list
        # what would have to be bought)
        penalty = pulp.lpSum(weights[kind] * var for kind, group in slacks.items() for var in group.values())
        prob += -penalty - 0.0001 * purchase_cost
        return _Model(
            prob,
            batches,
            x,
            y,
            nudge,
            frozen,
            day_kcal,
            purchase_cost,
            store_used,
            dict(slacks),
            day_protein,
            purchases_by_ingredient,
        )

    primary_scores = {r.version_id: nutrient_score(r, c.nutrition_priority) for r in problem.candidates}
    best = max(primary_scores.values(), default=Decimal(0)) or Decimal(1)
    secondary_scores: dict[int, Decimal] = {}
    best_secondary = Decimal(1)
    if c.secondary_priority is not None:
        secondary_scores = {r.version_id: nutrient_score(r, c.secondary_priority) for r in problem.candidates}
        best_secondary = max(secondary_scores.values(), default=Decimal(0)) or Decimal(1)
    medians = _median_costs(problem)
    objective: list[Any] = []
    for key, var in x.items():
        bi, e, s = key
        b = batches[bi]
        r = b.recipe
        per_scaled = 0.0  # per unit of nudge-scaled portion
        per_meal = 0.0  # per portion regardless of nudge
        if not r.never_favored:
            per_scaled += w.primary * _f(primary_scores[r.version_id] * b.size_multiplier / best)
            if secondary_scores:
                per_scaled += w.secondary * _f(
                    secondary_scores[r.version_id] * b.size_multiplier / best_secondary
                )
            if r.is_favorite:
                per_meal += w.preference
        else:
            per_meal -= w.never_favored_tiebreak
            if s in medians and r.cost_cents_per_portion is not None:
                gap = medians[s] - r.cost_cents_per_portion * b.size_multiplier
                if gap > 0:
                    per_meal -= w.cost_per_dollar * _f(gap) / 100
        if r.has_disliked:
            per_meal -= w.preference
        if (e - b.cook_on).days > c.leftover_fridge_days:
            per_meal -= w.from_freezer
        if per_scaled:
            objective.append(per_scaled * scaled[key])
        if per_meal:
            objective.append(per_meal * var)
    # kcal deviation from each slot's target, beyond a dead zone. Whole portions can't hit a slot target
    # exactly, so penalizing every kcal of deviation leaves a gap the LP bound can never close; the day and
    # week limits above stay hard.
    for d in c.days:
        for s in d.slots:
            target = c.slot_target(s).kcal
            zone = target * SLOT_DEAD_ZONE
            meal = pulp.lpSum(meal_kcal(b, xv, sv) for b, xv, sv in by_slot[(d.day, s)])
            dev_plus = pulp.LpVariable(f"dp_{d.day:%m%d}_{s.value}", lowBound=0)
            dev_minus = pulp.LpVariable(f"dm_{d.day:%m%d}_{s.value}", lowBound=0)
            prob += dev_plus >= meal - target - zone, f"dev_up_{d.day:%m%d}_{s.value}"
            prob += dev_minus >= target - zone - meal, f"dev_down_{d.day:%m%d}_{s.value}"
            objective.append(-w.slot_deviation_per_kcal * (dev_plus + dev_minus))
    # aim for the target, not the 97% floor (the ceilings stop it at the target)
    objective.append(w.week_kcal_toward_target * pulp.lpSum(day_kcal.values()))
    objective.append(-w.cost_per_dollar / 100 * purchase_cost)
    for used in store_used.values():
        objective.append(-w.cost_per_dollar / 100 * c.store_split_min_savings_cents * used)
    objective.extend(-w.waste_per_dollar / 100 * term for term in waste_terms)  # all in cents
    objective.extend(-w.small_fraction_per_dollar / 100 * term for term in sliver_terms)
    objective.extend(w.inventory_use * term for term in inventory_bonus)
    objective.extend(-w.cost_per_dollar * term for term in inventory_charge)
    objective.extend(-w.batch * y[b.index] for b in batches)
    prob += pulp.lpSum(objective)
    return _Model(
        prob,
        batches,
        x,
        y,
        nudge,
        frozen,
        day_kcal,
        purchase_cost,
        store_used,
        dict(slacks),
        day_protein,
        purchases_by_ingredient,
    )


def run_solver(model: _Model, time_limit_s: int, gap_rel: float, gap_abs: float = 1.0) -> int:
    return solve_milp(model.prob, time_limit_s=time_limit_s, gap_rel=gap_rel, gap_abs=gap_abs)


def _value(var: Any) -> float:
    v = pulp.value(var)
    return float(v) if v is not None else 0.0


def extract(problem: PlanningProblem, model: _Model, sol_status: int) -> SolverSolution:
    c = problem.constraints
    batches: list[SolvedBatch] = []
    meals: list[SolvedMeal] = []
    for b in model.batches:
        if _value(model.y[b.index]) <= 0.5:
            continue
        eaten = [(e, s) for (bi, e, s), var in model.x.items() if bi == b.index and _value(var) > 0.5]
        extras = round(_value(model.frozen[b.index])) if b.index in model.frozen else 0
        if not eaten and not extras:
            continue
        raw = Decimal(str(_value(model.nudge[b.index]))) if b.index in model.nudge else Decimal(1)
        nudge = raw.quantize(MULTIPLIER_STEP, rounding=ROUND_HALF_UP)
        batch_index = len(batches)
        batches.append(
            SolvedBatch(b.recipe.version_id, b.cook_on, b.size, nudge, len(eaten) + extras, extras)
        )
        for e, s in eaten:
            meals.append(SolvedMeal(e, s, batch_index, (e - b.cook_on).days > c.leftover_fridge_days))
    meals.sort(key=lambda m: (m.eat_on, list(MealSlot).index(m.slot)))
    day_kcal = {
        spec.day: sum(
            (
                problem.candidate(batches[m.batch_index].version_id).kcal * batches[m.batch_index].multiplier
                for m in meals
                if m.eat_on == spec.day
            ),
            Decimal(0),
        )
        for spec in c.days
    }
    stores = {c.primary_store_id} | {sid for sid, var in model.store_used.items() if _value(var) > 0.5}
    return SolverSolution(
        status="optimal" if sol_status == pulp.LpSolutionOptimal else "feasible",
        objective=_value(model.prob.objective),
        batches=tuple(batches),
        meals=tuple(meals),
        day_kcal=day_kcal,
        stores_used=frozenset(stores),
        estimated_purchase_cents=round(_value(model.purchase_cost)),
    )
