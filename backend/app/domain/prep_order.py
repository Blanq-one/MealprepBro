"""A cook day's prep order (FLOW_SPEC C1b, step 2b.5): what to start first (the oven, rice, anything that
simmers, chills or marinates), then what to cook while those run. Pure and deterministic, built from each
batch's step sections and times; no LLM.

  waits     a batch "waits" when it has passive time (start to finish minus hands-on). Its kind comes from
            its steps: chill (a no-cook recipe that sits in the fridge), marinate, oven, slow (a pressure or
            slow cooker), rice, simmer (stovetop), else a plain wait
  order     batches that wait start first: chilling and marinating (the longest waits), then the oven, the
            cooker, rice and simmering; ties by the longer wait. Hands-on batches come after, cooked while the
            first one runs
  none      a day with one batch, or with only hands-on batches, has no order
"""

from collections.abc import Sequence
from dataclasses import dataclass

KIND_RANK = {"chill": 0, "marinate": 1, "oven": 2, "slow": 3, "rice": 4, "simmer": 5, "wait": 6}
START_PHRASE = {
    "chill": "it chills in the fridge",
    "marinate": "it marinates",
    "oven": "it goes in the oven",
    "slow": "it goes in the cooker",
    "rice": "start the rice",
    "simmer": "it simmers on the stove",
    "wait": "it needs time to cook",
}
WHILE_PHRASE = {
    "chill": "it chills",
    "marinate": "it marinates",
    "oven": "the oven runs",
    "slow": "the cooker runs",
    "rice": "the rice cooks",
    "simmer": "it simmers",
    "wait": "it cooks",
}
SLOW_EQUIPMENT = frozenset({"pressure_cooker", "slow_cooker"})
COOKING_EQUIPMENT = frozenset(
    {"stovetop", "oven", "air_fryer", "microwave", "rice_cooker", "pressure_cooker", "slow_cooker", "grill"}
)


@dataclass(frozen=True)
class PrepBatch:
    title: str
    active_minutes: int
    total_minutes: int
    equipment: frozenset[str]
    sections: tuple[str, ...]  # the recipe's step sections, in order

    @property
    def wait(self) -> int:
        return max(self.total_minutes - self.active_minutes, 0)

    @property
    def kind(self) -> str | None:
        """What the batch waits for, or None for a hands-on batch."""
        if self.wait == 0:
            return None
        if not self.equipment & COOKING_EQUIPMENT:
            return "chill"
        if "marinate" in self.sections:
            return "marinate"
        if "oven" in self.sections or "oven" in self.equipment:
            return "oven"
        if self.equipment & SLOW_EQUIPMENT:
            return "slow"
        if "rice" in self.sections or "rice_cooker" in self.equipment:
            return "rice"
        if "stovetop" in self.sections:
            return "simmer"
        return "wait"


def prep_order(batches: Sequence[PrepBatch]) -> list[str]:
    """The day's numbered lines, e.g. ["1. Start Sheet-pan chicken first: it goes in the oven", "2. Cook Egg
    fried rice while the oven runs"]; [] when there's no order to give."""
    if len(batches) < 2:
        return []
    starters = sorted(
        (b for b in batches if b.kind is not None),
        key=lambda b: (KIND_RANK[b.kind or "wait"], -b.wait, b.title),
    )
    if not starters:
        return []
    hands_on = sorted((b for b in batches if b.kind is None), key=lambda b: (-b.active_minutes, b.title))
    first = starters[0]
    while_first = WHILE_PHRASE[first.kind or "wait"]
    lines = [f"Start {first.title} first: {START_PHRASE[first.kind or 'wait']}"]
    lines += [f"While {while_first}, start {b.title}: {START_PHRASE[b.kind or 'wait']}" for b in starters[1:]]
    lines += [f"Cook {b.title} while {while_first}" for b in hands_on]
    return [f"{n}. {line}" for n, line in enumerate(lines, start=1)]
