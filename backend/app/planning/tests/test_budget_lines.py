"""Which side of a classic/budget pair a tier cooks with (the 2b.6 approval, item 4). Pure."""

from decimal import Decimal

from app.domain.price_tiers import PriceTier
from app.planning.budget_lines import BETTER_KEEPS_CLASSIC, choose_lines, picks_budget
from app.planning.problem import BudgetAlternative, IngredientPlan, RecipeLine
from app.testing import factories as f

FRESH, CANNED = 1, 2


def plans(fresh_cents: str, canned_cents: str) -> dict[int, IngredientPlan]:
    return {
        FRESH: f.food(FRESH, "tomato", 18, offers=[f.offer(FRESH, cents_per_unit=fresh_cents)]),
        CANNED: f.food(CANNED, "canned tomatoes", 18, offers=[f.offer(CANNED, cents_per_unit=canned_cents)]),
    }


def tomato_line() -> RecipeLine:
    """400 g of fresh tomatoes for 4 portions, or 400 g canned."""
    return f.line(
        FRESH,
        400,
        recipe_ingredient_id=7,
        budget=BudgetAlternative(CANNED, Decimal(400), "g", Decimal(400), "g"),
    )


def everyone(_: int) -> bool:
    return True


def test_each_tier_by_the_price_difference() -> None:
    line = tomato_line()
    big = plans("0.50", "0.20")  # $1.20 cheaper for 4 portions: 30 cents a portion
    small = plans("0.25", "0.20")  # 5 cents a portion
    for tier in (PriceTier.BROKE, PriceTier.CHEAPEST):
        assert picks_budget(line, tier, big, 4, everyone) and picks_budget(line, tier, small, 4, everyone)
    assert picks_budget(line, PriceTier.BETTER, big, 4, everyone)  # 30 > 25 cents a portion
    # a small difference keeps the classic
    assert not picks_budget(line, PriceTier.BETTER, small, 4, everyone)
    assert BETTER_KEEPS_CLASSIC == 25
    for p in (big, small):
        assert not picks_budget(line, PriceTier.FANCY, p, 4, everyone)
        assert not picks_budget(line, None, p, 4, everyone)  # no tier: the recipe as written


def test_whichever_is_actually_cheaper_and_never_an_unpriced_or_unusable_side() -> None:
    line = tomato_line()
    pricier = plans("0.20", "0.50")  # the "budget" one costs more: keep the classic
    assert not picks_budget(line, PriceTier.BROKE, pricier, 4, everyone)
    unpriced = plans("0.50", "0.20")
    unpriced[CANNED] = f.food(CANNED, "canned tomatoes", 18)
    assert not picks_budget(line, PriceTier.CHEAPEST, unpriced, 4, everyone)
    # a classic the tier can't have: the budget one stands in, even at Fancy
    assert picks_budget(line, PriceTier.FANCY, pricier, 4, lambda i: i != FRESH)
    # a budget side the plan can't use is never picked
    assert not picks_budget(line, PriceTier.BROKE, plans("0.50", "0.20"), 4, lambda i: i != CANNED)


def test_the_budget_side_keeps_the_line_and_remembers_the_classic() -> None:
    line = tomato_line()
    [cooked] = choose_lines([line], PriceTier.BROKE, plans("0.50", "0.20"), 4, everyone)
    assert (cooked.ingredient_id, cooked.classic_ingredient_id, cooked.recipe_ingredient_id) == (
        CANNED,
        FRESH,
        7,
    )
    # a swap keeps a stored batch's sides whatever the prices say now
    [kept] = choose_lines([line], PriceTier.BROKE, plans("0.50", "0.20"), 4, everyone, pinned=frozenset())
    assert kept.ingredient_id == FRESH
