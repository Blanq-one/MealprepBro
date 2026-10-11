"""Recipe cards (FLOW_SPEC §5.3): display strings only, every number computed by code. Shared by meal-now
results, the Saved lists and the recipe page's search context (C8)."""

from collections.abc import Mapping, Sequence
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from app.cook.coverage import LineCoverage, Purchase, Status
from app.cook.pool import PoolItem, cost_per_portion
from app.cook.ranking import Ranked
from app.domain.cost import money_display
from app.domain.dish_category import DishCategory
from app.domain.enums import PortionSize
from app.domain.nutrition import kcal_display
from app.schemas.cards import CostLineOut, LineContextOut, MissingLineOut, SubstituteOut, SwapLineOut
from app.schemas.cook import GoalTile, RecipeSuggestionOut

Badge = Literal["favorite", "saved", "new", "draft"]
_ONE = Decimal(1)
_TENTH = Decimal("0.1")
AS_WRITTEN_NOTE = "Numbers are for the recipe as written."


def portions_display(portions: int) -> str:
    return "1 portion" if portions == 1 else f"for {portions} people"


def buy_today(coverage: Sequence[LineCoverage]) -> str:
    """What this meal needs you to buy now, in whole packages (M12): "$4.29 to buy today", "nothing to buy
    today", or "$4.29 to buy today + unpriced items"."""
    needed = [
        cov
        for cov in coverage
        if cov.status in (Status.COULD_BUY, Status.SHORT)
        or (cov.status is Status.MISSING and cov.substitute is None)
    ]
    if not needed:
        return "nothing to buy today"
    priced = [cov.purchase for cov in needed if cov.purchase is not None]
    if not priced:
        return "no price yet for what to buy"
    cents = sum(p.cents for p in priced)
    estimate = " est." if any(p.is_estimate for p in priced) else ""
    unpriced = " + unpriced items" if len(priced) < len(needed) else ""
    return f"{money_display(cents)}{estimate} to buy today{unpriced}"


def numbers(item: PoolItem, goals: Sequence[GoalTile], store_order: Sequence[str]) -> list[str]:
    """Per portion: kcal, protein, time (start to finish) and cost; then what to buy today (M12); plus iron or
    carbs with those goals."""
    calc = item.scaled.calculation
    per = calc.per_portion.amounts
    out = [
        f"{kcal_display(per.get('energy_kcal', Decimal(0)))} kcal",
        f"{per.get('protein_g', Decimal(0)).quantize(_ONE, ROUND_HALF_UP)} g protein",
        f"{item.version.total_minutes} min",
    ]
    cost = cost_per_portion(item.scaled, store_order)
    if cost is None:
        out.append("no price yet")
    else:
        out.append(f"{money_display(cost[0])} a portion" + (" est." if cost[1] else ""))
    out.append(buy_today(item.rank_input.coverage))
    if GoalTile.IRON_RICH in goals:
        iron = per.get("iron_mg", Decimal(0)).quantize(_TENTH, ROUND_HALF_UP)
        heme = (calc.per_portion.heme.heme_mg if calc.per_portion.heme else Decimal(0)).quantize(
            _TENTH, ROUND_HALF_UP
        )
        out.append(f"{iron} mg iron ({heme} mg heme, est.)")
    if GoalTile.HIGH_CARB in goals:
        out.append(f"{per.get('carbohydrate_g', Decimal(0)).quantize(_ONE, ROUND_HALF_UP)} g carbs")
    return out


def cost_line(ingredient_id: int, name: str, purchase: Purchase | None) -> CostLineOut:
    if purchase is None:
        return CostLineOut(
            ingredient_id=ingredient_id,
            name=name,
            cost_cents=None,
            cost_display="no price yet",
            store=None,
            is_estimate=False,
            display=f"{name} · no price yet",
        )
    cost = money_display(purchase.cents) + (" est." if purchase.is_estimate else "")
    return CostLineOut(
        ingredient_id=ingredient_id,
        name=name,
        cost_cents=purchase.cents,
        cost_display=cost,
        store=purchase.store_name,
        is_estimate=purchase.is_estimate,
        display=f"{name} {cost} ({purchase.store_name})",
    )


def _missing(cov: LineCoverage) -> MissingLineOut:
    name = cov.line.name
    if cov.status is Status.SHORT:
        buy = cost_line(cov.line.ingredient_id, name, cov.purchase)
        return MissingLineOut(
            ingredient_id=cov.line.ingredient_id,
            name=name,
            kind="top_up",
            substitute=None,
            buy=buy,
            display=f"more {name} · "
            + (f"buy {buy.cost_display} ({buy.store})" if buy.store else "no price yet"),
        )
    sub = cov.substitute
    if sub is not None:
        return MissingLineOut(
            ingredient_id=cov.line.ingredient_id,
            name=name,
            kind="missing",
            substitute=SubstituteOut(
                ingredient_id=sub.ingredient_id,
                name=sub.name,
                amount_display=sub.display,
                you_have=True,
                note=sub.note,
            ),
            buy=None,
            display=f"{name} → {sub.name} (you have it)",
        )
    buy = cost_line(cov.line.ingredient_id, name, cov.purchase)
    return MissingLineOut(
        ingredient_id=cov.line.ingredient_id,
        name=name,
        kind="missing",
        substitute=None,
        buy=buy,
        display=f"{name} · " + (f"buy {buy.cost_display} ({buy.store})" if buy.store else "no price yet"),
    )


def swap(cov: LineCoverage) -> SwapLineOut:
    sub = cov.substitute
    assert sub is not None
    return SwapLineOut(
        ingredient_id=cov.line.ingredient_id,
        name=cov.line.name,
        substitute=SubstituteOut(
            ingredient_id=sub.ingredient_id,
            name=sub.name,
            amount_display=sub.display,
            you_have=True,
            note=sub.note,
        ),
        display=f"Swap: {sub.name} instead of {cov.line.name} (you have it)",
    )


def coverage_lines(
    coverage: Sequence[LineCoverage],
) -> tuple[list[str], list[CostLineOut], list[MissingLineOut], list[SwapLineOut]]:
    """(uses, could buy, missing and top-ups, swaps) for a card. A line you can make with something you have
    is a swap, never "Missing" (M11)."""
    uses = [
        cov.line.name + (" (some)" if cov.status is Status.SHORT else "") for cov in coverage if cov.yours
    ]
    could_buy = [
        cost_line(cov.line.ingredient_id, cov.line.name, cov.purchase)
        for cov in coverage
        if cov.status is Status.COULD_BUY
    ]
    missing = [
        _missing(cov)
        for cov in coverage
        if cov.status is Status.SHORT or (cov.status is Status.MISSING and cov.substitute is None)
    ]
    swaps = [swap(cov) for cov in coverage if cov.status is Status.MISSING and cov.substitute is not None]
    return uses, could_buy, missing, swaps


def line_context(coverage: Sequence[LineCoverage]) -> list[LineContextOut]:
    """C8's per-line notes for a search, e.g. "Don't have lemon? Bottled lime juice works (you have it):
    2 tbsp"."""
    out = []
    for cov in coverage:
        if cov.status is Status.OPTIONAL:
            continue
        line = cov.line
        note: str | None = None
        status: Literal["have", "short", "could_buy", "missing", "owned"]
        if cov.status is Status.OWNED:
            status = "owned"
        elif cov.status is Status.HAVE:
            status, note = "have", "You have it"
        elif cov.status is Status.SHORT:
            buy = cost_line(line.ingredient_id, line.name, cov.purchase)
            status = "short"
            note = "You have some; " + (
                f"buy more: {buy.cost_display} ({buy.store})" if buy.store else "buy more"
            )
        elif cov.status is Status.COULD_BUY:
            buy = cost_line(line.ingredient_id, line.name, cov.purchase)
            status = "could_buy"
            note = f"Could buy: {buy.cost_display} ({buy.store})" if buy.store else "Could buy: no price yet"
        else:
            status = "missing"
            if cov.substitute is not None:
                sub = cov.substitute
                works = f"{sub.name[:1].upper()}{sub.name[1:]} works (you have it)"
                note = f"Don't have {line.name}? {works}: {sub.display}"
            else:
                buy = cost_line(line.ingredient_id, line.name, cov.purchase)
                note = (
                    f"Missing: buy {buy.cost_display} ({buy.store})" if buy.store else "Missing: no price yet"
                )
        out.append(LineContextOut(ingredient_id=line.ingredient_id, status=status, note=note))
    return out


def badges(
    item: PoolItem,
    saved_ids: frozenset[int],
    favorite_ids: frozenset[int] | None = None,
    new_ids: frozenset[int] = frozenset(),
) -> list[Badge]:
    out: list[Badge] = []
    favorite = item.rank_input.is_favorite if favorite_ids is None else item.recipe.id in favorite_ids
    if favorite:
        out.append("favorite")
    if item.recipe.id in saved_ids:
        out.append("saved")
    if item.version.id in new_ids:  # an idea just written for this search (C5)
        out.append("new")
    if item.version.is_draft:
        out.append("draft")
    return out


def suggestion(
    item: PoolItem,
    ranked: Ranked,
    *,
    goals: Sequence[GoalTile],
    store_order: Sequence[str],
    portions: int,
    portion_size: PortionSize,
    saved_ids: frozenset[int],
    categories: Mapping[int, DishCategory],
    new_ids: frozenset[int] = frozenset(),
) -> RecipeSuggestionOut:
    uses, could_buy, missing, swaps = coverage_lines(item.rank_input.coverage)
    return RecipeSuggestionOut(
        version_id=item.version.id,
        recipe_id=item.recipe.id,
        title=item.version.title,
        dish_category=categories[item.version.id].value,
        badges=badges(item, saved_ids, new_ids=new_ids),
        steps_ready=item.version.steps_status is None,
        portions=portions,
        portion_size=portion_size,
        portions_display=portions_display(portions),
        numbers=numbers(item, goals, store_order),
        uses=uses,
        could_buy=could_buy,
        missing=missing,
        swaps=swaps,
        why=list(ranked.why),
        score=ranked.score,
        good_match=ranked.good_match,
        section=ranked.section,
    )
