"""Calorie targets: weekly totals, exact integer distribution across days, and slot allocations."""

from collections.abc import Mapping
from dataclasses import dataclass


class CalorieError(ValueError):
    pass


def weekly_target(daily_kcal: int, days: int) -> int:
    if daily_kcal <= 0 or days <= 0:
        raise CalorieError("daily target and number of days must be positive")
    return daily_kcal * days


def distribute(total_kcal: int, days: int) -> list[int]:
    """Largest-remainder split into whole kcal; leftover kcal go to the earliest days.
    12,000 over 7 days → two days of 1,715 and five of 1,714."""
    if days <= 0:
        raise CalorieError("days must be positive")
    if total_kcal < 0:
        raise CalorieError("total must not be negative")
    base, extra = divmod(total_kcal, days)
    return [base + 1 if i < extra else base for i in range(days)]


@dataclass(frozen=True)
class SlotAllocation:
    targets: dict[str, int]
    unallocated_kcal: int


def slot_targets(daily_kcal: int, allocations: Mapping[str, int]) -> SlotAllocation:
    if not allocations:
        raise CalorieError("at least one meal slot needs a calorie allocation")
    for slot, kcal in allocations.items():
        if kcal <= 0:
            raise CalorieError(f"{slot}: allocation must be positive")
    allocated = sum(allocations.values())
    if allocated > daily_kcal:
        raise CalorieError(f"slot allocations ({allocated} kcal) exceed the daily target ({daily_kcal} kcal)")
    return SlotAllocation(targets=dict(allocations), unallocated_kcal=daily_kcal - allocated)
