"""What to buy, and where: the exact cheapest way to cover a need from a store's offers, and the store-split
rule (R4): buy at the secondary store only when that saves at least the threshold for the week.

Stock-up items (rice, oil, protein powder) are bought as whole packages of the cheapest offer per unit,
since the rest stays in the pantry for later weeks; they follow the store decision but don't drive it.

All quantities are in one base unit per ingredient (the caller converts). Money is integer cents: a
package costs its package price; a loose purchase is rounded half-up once per line (§7.1).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from itertools import product

from app.domain.cost import round_cents

MAX_ENUMERATED_PACKAGES = 60  # per offer; beyond this, fall back to the cheapest single offer


@dataclass(frozen=True)
class Offer:
    """One way to buy an ingredient at one store (from its current price observation)."""

    ref: int  # the price observation id
    product_id: int
    store_id: int
    package_amount: Decimal | None  # None = sold loose
    package_cents: int | None  # price per package; None when loose
    cents_per_unit: Decimal  # loose price, or package price / package amount
    is_estimate: bool = False  # from an estimated price (shown as "est.")

    def __post_init__(self) -> None:
        if (self.package_amount is None) != (self.package_cents is None):
            raise ValueError("a package offer needs both an amount and a package price")
        if self.package_amount is not None and self.package_amount <= 0:
            raise ValueError("package amount must be positive")


@dataclass(frozen=True)
class Buy:
    offer: Offer
    packages: int | None  # None for loose
    quantity: Decimal  # base units bought with this offer
    cents: int


@dataclass(frozen=True)
class Cover:
    buys: tuple[Buy, ...]
    need: Decimal
    purchased: Decimal
    cents: int

    @property
    def remainder(self) -> Decimal:
        return max(Decimal(0), self.purchased - self.need)

    @property
    def store_ids(self) -> frozenset[int]:
        return frozenset(b.offer.store_id for b in self.buys)


EMPTY_COVER_TOLERANCE = {"g": Decimal(1), "ml": Decimal(1), "count": Decimal(0)}


def _ceil(value: Decimal) -> int:
    return int(value.to_integral_value(rounding=ROUND_CEILING))


def _loose(need: Decimal, offer: Offer) -> Buy:
    return Buy(offer, None, need, round_cents(need * offer.cents_per_unit))


def cheapest_cover(need: Decimal, offers: Sequence[Offer], tolerance: Decimal = Decimal(0)) -> Cover | None:
    """Cheapest set of purchases with total ≥ need − tolerance; None when there are no offers.

    Ties go to the smaller purchase (less left over), then the lower store id, then the lower ref, so the
    result is deterministic."""
    if need <= tolerance:
        return Cover((), need, Decimal(0), 0)
    if not offers:
        return None
    target = need - tolerance
    loose = sorted((o for o in offers if o.package_amount is None), key=lambda o: (o.cents_per_unit, o.ref))
    packs = sorted((o for o in offers if o.package_amount is not None), key=lambda o: o.ref)
    candidates: list[Cover] = []
    for offer in loose:
        buy = _loose(need, offer)
        candidates.append(Cover((buy,), need, need, buy.cents))
    if packs:
        limits = []
        for o in packs:
            assert o.package_amount is not None
            limits.append(min(_ceil(target / o.package_amount), MAX_ENUMERATED_PACKAGES))
        for counts in product(*(range(limit + 1) for limit in limits)):
            if not any(counts):
                continue
            buys = []
            bought = Decimal(0)
            cents = 0
            for o, count in zip(packs, counts, strict=True):
                if count:
                    assert o.package_amount is not None and o.package_cents is not None
                    buys.append(Buy(o, count, o.package_amount * count, o.package_cents * count))
                    bought += o.package_amount * count
                    cents += o.package_cents * count
            if bought >= target:
                candidates.append(Cover(tuple(buys), need, bought, cents))
            elif loose:  # top up the rest loose
                top_up = _loose(need - bought, loose[0])
                candidates.append(Cover((*buys, top_up), need, need, cents + top_up.cents))
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda c: (
            c.cents,
            c.purchased,
            min(b.offer.store_id for b in c.buys),
            [b.offer.ref for b in c.buys],
        ),
    )


def per_unit_cover(need: Decimal, offers: Sequence[Offer], tolerance: Decimal = Decimal(0)) -> Cover | None:
    """A stock-up item: enough whole packages of the offer that is cheapest per unit (a 5 lb tub over a
    small one), or loose. Ties go to the smaller package, then the lower store id, then the lower ref."""
    if need <= tolerance:
        return Cover((), need, Decimal(0), 0)
    if not offers:
        return None
    best = min(offers, key=lambda o: (o.cents_per_unit, o.package_amount or Decimal(0), o.store_id, o.ref))
    if best.package_amount is None:
        buy = _loose(need, best)
        return Cover((buy,), need, need, buy.cents)
    assert best.package_cents is not None
    count = max(1, _ceil((need - tolerance) / best.package_amount))
    amount = best.package_amount * count
    return Cover(
        (Buy(best, count, amount, best.package_cents * count),), need, amount, best.package_cents * count
    )


def _per_unit(cover: Cover | None) -> Decimal:
    if cover is None or not cover.buys:
        return Decimal(0)
    return min(b.offer.cents_per_unit for b in cover.buys)


@dataclass(frozen=True)
class StoreChoice:
    covers: dict[int, Cover | None]  # ingredient id -> chosen cover (None = no price anywhere)
    split: bool  # True when the R4 rule sends items your primary store sells to another store
    primary_only_cents: int | None  # all-primary cost for the items the primary sells
    chosen_cents: int
    savings_cents: int  # primary-only minus chosen, over the items the primary sells
    forced_elsewhere: tuple[int, ...]  # ingredients the primary store has no price for
    unpriced: tuple[int, ...]


def choose_stores(
    needs: Mapping[int, Decimal],
    offers: Mapping[int, Sequence[Offer]],
    primary_store_id: int,
    threshold_cents: int,
    tolerance: Mapping[int, Decimal] | None = None,
    *,
    stock_up_ids: frozenset[int] = frozenset(),
) -> StoreChoice:
    """Everything at the primary store, unless buying some items elsewhere saves ≥ threshold (R4).

    Items the primary store doesn't price are bought wherever they are priced and listed as forced; they
    don't count toward the savings comparison, and neither do stock-up items (cheapest per unit wherever
    this week's trips go)."""
    tolerance = tolerance or {}
    primary: dict[int, Cover | None] = {}
    best: dict[int, Cover | None] = {}
    for ingredient_id in sorted(needs):
        need = needs[ingredient_id]
        tol = tolerance.get(ingredient_id, Decimal(0))
        all_offers = list(offers.get(ingredient_id, ()))
        at_primary = [o for o in all_offers if o.store_id == primary_store_id]
        if ingredient_id in stock_up_ids:
            primary[ingredient_id] = per_unit_cover(need, at_primary, tol)
            best_cover = per_unit_cover(need, all_offers, tol)
            p = primary[ingredient_id]
            if p is not None and best_cover is not None and _per_unit(p) <= _per_unit(best_cover):
                best_cover = p  # a tie stays at the primary store
            best[ingredient_id] = best_cover
            continue
        primary[ingredient_id] = cheapest_cover(need, at_primary, tol)
        best_cover = cheapest_cover(need, all_offers, tol)
        # a tie stays at the primary store
        if primary[ingredient_id] is not None and best_cover is not None:
            p = primary[ingredient_id]
            assert p is not None
            if p.cents <= best_cover.cents:
                best_cover = p
        best[ingredient_id] = best_cover
    forced = tuple(i for i in sorted(needs) if primary[i] is None and best[i] is not None)
    unpriced = tuple(i for i in sorted(needs) if best[i] is None)
    comparable = [i for i in sorted(needs) if primary[i] is not None and i not in stock_up_ids]
    primary_cents = sum(c.cents for i in comparable if (c := primary[i]) is not None)
    best_cents = sum(c.cents for i in comparable if (c := best[i]) is not None)
    savings = primary_cents - best_cents
    split = savings >= threshold_cents and savings > 0
    chosen: dict[int, Cover | None] = {}
    for i in sorted(needs):
        chosen[i] = best[i] if (split or primary[i] is None) else primary[i]
    chosen_cents = sum(c.cents for c in chosen.values() if c is not None)
    uses_other = any(
        b.offer.store_id != primary_store_id
        for i, c in chosen.items()
        if c is not None and i not in forced
        for b in c.buys
    )
    return StoreChoice(
        covers=chosen,
        split=uses_other,
        primary_only_cents=primary_cents if comparable else None,
        chosen_cents=chosen_cents,
        savings_cents=savings,
        forced_elsewhere=forced,
        unpriced=unpriced,
    )
