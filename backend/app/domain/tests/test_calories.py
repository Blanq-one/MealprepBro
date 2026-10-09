import pytest

from app.domain.calories import CalorieError, distribute, slot_targets, weekly_target


def test_weekly_target():
    assert weekly_target(1800, 7) == 12600
    assert weekly_target(1800, 5) == 9000
    with pytest.raises(CalorieError):
        weekly_target(0, 7)


def test_largest_remainder_distribution():
    days = distribute(12000, 7)
    assert sorted(days) == [1714] * 5 + [1715] * 2
    assert days[:2] == [1715, 1715]  # leftover kcal go to the earliest days
    assert sum(days) == 12000
    assert distribute(12600, 7) == [1800] * 7


def test_distribution_errors():
    with pytest.raises(CalorieError):
        distribute(100, 0)
    with pytest.raises(CalorieError):
        distribute(-1, 7)


def test_valid_allocation_with_unallocated_remainder():
    alloc = slot_targets(1800, {"breakfast": 400, "lunch": 550, "dinner": 650})
    assert alloc.unallocated_kcal == 200
    assert alloc.targets["dinner"] == 650


def test_invalid_allocations():
    with pytest.raises(CalorieError, match="exceed"):
        slot_targets(1800, {"lunch": 1000, "dinner": 900})
    with pytest.raises(CalorieError, match="positive"):
        slot_targets(1800, {"lunch": 0})
    with pytest.raises(CalorieError):
        slot_targets(1800, {})
