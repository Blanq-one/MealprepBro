"""Pantry coverage of one recipe card (FLOW_SPEC §14 step 4). Pure.

Every counted line (optional lines, staples and Always-have items aside) is one of:
  have       your toggled-on stock covers it, or you said "have it" (enough for one recipe);
  short      you have some, not enough: the rest is a top-up purchase;
  could buy  one of your "could buy" items: whole packages at the first of your stores that prices it;
  missing    none of the above: a deterministic substitute when there is one, else its price.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

from app.cook.substitutes import AcceptedPair, Have, MissingLine, Substitute, find_substitute
from app.domain.chicken_cuts import CutForm
from app.domain.purchase import EMPTY_COVER_TOLERANCE, Offer, cheapest_cover


class Status(StrEnum):
    HAVE = "have"
    SHORT = "short"
    COULD_BUY = "could_buy"
    MISSING = "missing"
    OWNED = "owned"  # a staple or an Always-have item: yours, never bought, not counted
    OPTIONAL = "optional"  # listed, never counted


@dataclass(frozen=True)
class Stock:
    """One ingredient's stock for this search, in its planning unit."""

    quantity: Decimal | None  # None = a "have it" extra: enough for one recipe
    opened: bool = False  # an open package among the lots
    expires_soon: bool = False  # a lot expiring within 3 days
    earliest_expiry: date | None = None


@dataclass(frozen=True)
class NeedLine:
    """What a card's recipe needs of one ingredient, at its practical amounts (lines of the same ingredient
    added up)."""

    ingredient_id: int
    name: str
    role: str
    category: str
    quantity: Decimal  # planning unit
    planning_unit: str
    grams: Decimal
    count: Decimal | None  # pieces, when the line is counted
    protein_g: Decimal
    kcal: Decimal
    optional: bool = False
    owned: bool = False
    group: str | None = None  # its culinary group (vegetables and herbs, J2)
    cut: CutForm | None = None  # a chicken cut's bone and skin (M6)


@dataclass(frozen=True)
class Purchase:
    cents: int
    store_id: int
    store_name: str
    is_estimate: bool


@dataclass(frozen=True)
class LineCoverage:
    line: NeedLine
    status: Status
    shortfall: Decimal = Decimal(0)
    uses_soon: bool = False  # uses an open package or a lot expiring within 3 days
    purchase: Purchase | None = None  # could buy, a top-up, or a missing line without a substitute
    substitute: Substitute | None = None

    @property
    def counted(self) -> bool:
        return self.status not in (Status.OWNED, Status.OPTIONAL)

    @property
    def yours(self) -> bool:
        """Uses one of your items (stock or a "have it" extra)."""
        return self.status in (Status.HAVE, Status.SHORT)


@dataclass(frozen=True)
class CoverageInputs:
    """Everything coverage reads for one search."""

    stock: Mapping[int, Stock]  # your items (toggled on, or "have it")
    could_buy: frozenset[int]
    offers: Mapping[int, Sequence[Offer]]  # in the planning unit
    store_order: Sequence[int]  # your stores first, then "Other" sources
    store_names: Mapping[int, str]
    haves: Sequence[Have] = ()  # substitute candidates
    pairs: Sequence[AcceptedPair] = ()
    unusable: frozenset[int] = frozenset()  # excluded, held or disliked: never a substitute
    units: str = "us"


def buy_where(
    need: Decimal, unit: str, offers: Sequence[Offer], store_order: Sequence[int], names: Mapping[int, str]
) -> Purchase | None:
    """Whole packages (or loose) at the first store in your order that prices it."""
    tolerance = EMPTY_COVER_TOLERANCE.get(unit, Decimal(0))
    for store_id in store_order:
        at_store = [o for o in offers if o.store_id == store_id]
        cover = cheapest_cover(need, at_store, tolerance) if at_store else None
        if cover is not None and cover.buys:
            estimate = any(b.offer.is_estimate for b in cover.buys)
            return Purchase(cover.cents, store_id, names.get(store_id, "?"), estimate)
    return None


def cover_line(
    line: NeedLine, inputs: CoverageInputs, recipe_ids: frozenset[int], taken: frozenset[int] = frozenset()
) -> LineCoverage:
    if line.optional:
        return LineCoverage(line, Status.OPTIONAL)
    if line.owned:
        return LineCoverage(line, Status.OWNED)
    offers = inputs.offers.get(line.ingredient_id, ())

    def buy(quantity: Decimal) -> Purchase | None:
        return buy_where(quantity, line.planning_unit, offers, inputs.store_order, inputs.store_names)

    stock = inputs.stock.get(line.ingredient_id)
    tolerance = EMPTY_COVER_TOLERANCE.get(line.planning_unit, Decimal(0))
    if stock is not None:
        soon = stock.opened or stock.expires_soon
        if stock.quantity is None or stock.quantity + tolerance >= line.quantity:
            return LineCoverage(line, Status.HAVE, uses_soon=soon)
        if stock.quantity > 0:
            short = line.quantity - stock.quantity
            return LineCoverage(line, Status.SHORT, short, soon, buy(short))
    if line.ingredient_id in inputs.could_buy:
        return LineCoverage(line, Status.COULD_BUY, line.quantity, purchase=buy(line.quantity))
    substitute = find_substitute(
        MissingLine(
            line.ingredient_id,
            line.name,
            line.role,
            line.category,
            line.grams,
            line.count,
            line.protein_g,
            line.kcal,
            line.group,
            line.cut,
        ),
        inputs.haves,
        inputs.pairs,
        unusable=inputs.unusable,
        recipe_ingredient_ids=recipe_ids,
        taken=taken,
        units=inputs.units,
    )
    if substitute is not None:
        return LineCoverage(line, Status.MISSING, line.quantity, substitute=substitute)
    return LineCoverage(line, Status.MISSING, line.quantity, purchase=buy(line.quantity))


def cover(lines: Sequence[NeedLine], inputs: CoverageInputs) -> tuple[LineCoverage, ...]:
    """Each line in recipe order; something you have stands in for at most one line."""
    ids = frozenset(line.ingredient_id for line in lines)
    out: list[LineCoverage] = []
    taken: set[int] = set()
    for line in lines:
        covered = cover_line(line, inputs, ids, frozenset(taken))
        if covered.substitute is not None:
            taken.add(covered.substitute.ingredient_id)
        out.append(covered)
    return tuple(out)
