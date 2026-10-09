"""Exact purchase covers and the store-split rule (R4)."""

from decimal import Decimal

import pytest

from app.domain.cook_time import day_minutes, mood_allows, mood_time_error
from app.domain.enums import RecipeMood
from app.domain.purchase import Offer, cheapest_cover, choose_stores

LB = Decimal("453.59237")
PRIMARY, SECONDARY = 1, 2


def pack(ref, amount, cents, store=PRIMARY, product=None):
    return Offer(ref, product or ref, store, Decimal(amount), cents, Decimal(cents) / Decimal(amount))


def loose(ref, cents_per_unit, store=PRIMARY):
    return Offer(ref, ref, store, None, None, Decimal(cents_per_unit))


def test_one_package_covers_a_smaller_need_and_leaves_a_remainder():
    cover = cheapest_cover(Decimal("1.7") * LB, [pack(1, 2 * LB, 398)])
    assert cover is not None
    assert [b.packages for b in cover.buys] == [1]
    assert cover.cents == 398
    assert cover.remainder.quantize(Decimal("0.001")) == Decimal("136.078")


def test_mixed_package_sizes_pick_the_cheapest_combination():
    # 2.5 lb with 1 lb ($2.50) and 3 lb ($6.00) packs -> one 3 lb pack
    cover = cheapest_cover(Decimal("2.5") * LB, [pack(1, LB, 250), pack(2, 3 * LB, 600)])
    assert cover is not None
    assert [(b.offer.ref, b.packages) for b in cover.buys] == [(2, 1)]
    assert cover.cents == 600


def test_loose_cost_is_rounded_once_half_up():
    cover = cheapest_cover(Decimal("771.107"), [loose(1, Decimal(199) / LB)])
    assert cover is not None
    assert cover.cents == 338  # 1.7 lb at $1.99/lb
    assert cover.remainder == 0


def test_no_offers_means_no_price():
    assert cheapest_cover(Decimal(100), []) is None


def test_need_within_tolerance_buys_nothing():
    cover = cheapest_cover(Decimal("0.5"), [pack(1, 100, 100)], tolerance=Decimal(1))
    assert cover is not None and cover.buys == () and cover.cents == 0


def test_tie_prefers_smaller_purchase():
    # two 500 g packs or one 1000 g pack at the same price: buy the smaller total if it covers
    cover = cheapest_cover(Decimal(400), [pack(1, 500, 300), pack(2, 1000, 300)])
    assert cover is not None and cover.purchased == 500


def _offers(primary_cents, secondary_cents):
    return {
        10: [pack(1, 1000, primary_cents, PRIMARY), pack(2, 1000, secondary_cents, SECONDARY)],
        11: [pack(3, 500, 200, PRIMARY), pack(4, 500, 200, SECONDARY)],  # same price at both
    }


def test_price_rite_saving_540_splits():
    choice = choose_stores({10: Decimal(1000), 11: Decimal(400)}, _offers(1540, 1000), PRIMARY, 500)
    assert choice.split
    assert choice.savings_cents == 540
    cover = choice.covers[10]
    assert cover is not None and cover.store_ids == {SECONDARY}
    tied = choice.covers[11]
    assert tied is not None and tied.store_ids == {PRIMARY}  # a tie stays at the primary store


def test_saving_490_keeps_everything_at_stop_and_shop():
    choice = choose_stores({10: Decimal(1000), 11: Decimal(400)}, _offers(1490, 1000), PRIMARY, 500)
    assert not choice.split
    assert choice.savings_cents == 490
    assert all(c is not None and c.store_ids == {PRIMARY} for c in choice.covers.values())
    assert choice.chosen_cents == 1490 + 200


def test_lower_threshold_makes_490_split():
    choice = choose_stores({10: Decimal(1000)}, _offers(1490, 1000), PRIMARY, 300)
    assert choice.split


def test_item_only_priced_elsewhere_is_forced_and_listed():
    offers = {12: [pack(5, 100, 150, SECONDARY)], 13: []}
    choice = choose_stores({12: Decimal(50), 13: Decimal(10)}, offers, PRIMARY, 500)
    assert choice.forced_elsewhere == (12,)
    assert choice.unpriced == (13,)
    assert choice.covers[13] is None
    assert choice.split  # something is bought at the secondary store


@pytest.mark.parametrize(
    ("day", "recipe", "ok"),
    [
        (RecipeMood.MEDIUM, RecipeMood.SIMPLE, True),
        (RecipeMood.MEDIUM, RecipeMood.MEDIUM, True),
        (RecipeMood.MEDIUM, RecipeMood.FANCY, False),
        (RecipeMood.SIMPLE, RecipeMood.MEDIUM, False),
        (RecipeMood.FANCY, RecipeMood.SIMPLE, True),
    ],
)
def test_mood_eligibility(day, recipe, ok):
    assert mood_allows(day, recipe) is ok


def test_mood_time_limits_use_hands_on_minutes():
    assert mood_time_error(RecipeMood.SIMPLE, 30) is None
    message = mood_time_error(RecipeMood.SIMPLE, 75)
    assert message is not None and "30 hands-on minutes" in message
    assert mood_time_error(RecipeMood.MEDIUM, 60) is None
    assert mood_time_error(RecipeMood.MEDIUM, 61) is not None
    assert mood_time_error(RecipeMood.FANCY, 200) is None


def test_day_minutes_add_up_active_minutes():
    # overnight oats (5) + air-fryer chicken (15) + sheet-pan chicken (20) + pudding (5) fits 45
    assert day_minutes([5, 15, 20, 5]) == 45
