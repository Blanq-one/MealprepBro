"""Storage per prep item and stop state (step 2b.10, FLOW_SPEC §19.4, with V1 and V2 as answered: BUILD_PLAN
X2, X3). Code gives each prep batch a fridge window and a freezer rule from its lines and the state it stops
in; the LLM never sets these (CLAUDE.md food-safety rules).

Sources: the FoodSafety.gov Cold Food Storage Chart (storage_chart.py) and the USDA FoodKeeper rows it doesn't
have (foodkeeper.py). The windows follow the existing rules: raw meat, poultry, fish and eggs keep the SHORT
end of the chart's range (fridge_life.py), cooked food your leftover setting (3 days by default), never past
a row's upper end.

Raw or marinated, by what the item has (frozen the same day if it's kept longer):
- poultry pieces, ground meat or poultry, fin fish, raw sausage: 1 day; shrimp, pork chops or roasts: 3 days;
  eggs beaten into a mixture: 2 days (the chart's raw egg whites and yolks);
- no meat, poultry, fish or eggs (cut vegetables, a salad, a yogurt sauce): no row in either source, so it is
  made on the eating day as a 5-minute finish task (V1). So is a raw item whose protein has no raw row.
Partly cooked: with meat, poultry, fish or eggs it is never stored, but finished the same day (V2); without
them (par-boiled potatoes) it keeps like cooked vegetables.
Cooked, your 3 days (each row's upper end at most), frozen only if it freezes well and its rows allow it:
- meat or poultry: the chart's cooked meat or poultry leftovers; eggs: its casseroles with eggs; only
  hard-cooked eggs: its 1 week, never frozen;
- fish and shellfish: FoodKeeper's cooked fish and cooked shellfish;
- none of those: FoodKeeper's leftovers without meat, fish, poultry or egg, plus its cooked rice, pasta or
  quinoa row when the item is only that grain.

The strictest line wins: every row that applies counts, so a curry with shrimp takes the shorter of its rows.
Meat, poultry, fish and eggs are lines whose ingredient has a safety category (they must be cooked), or that
are the protein and tagged as such (canned tuna); a broth or a fish sauce doesn't count.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from app.domain import storage_chart
from app.domain.enums import PrepState
from app.domain.foodkeeper import FoodKeeperRow, foodkeeper_row
from app.domain.fridge_life import fridge_life

MADE_ON_THE_DAY_MINUTES = 5  # a fresh item made on the eating day is a 5-minute finish task (V1)
ANIMAL_TAGS = frozenset({"poultry", "fish", "shellfish", "egg", "pork", "lamb", "beef"})
HARD_COOKED = re.compile(r"\bhard[- ](boiled|cooked)\b", re.IGNORECASE)
GRAIN_ROWS = {  # a cooked item that is only this grain (with its water or broth, fat and seasoning)
    "rice-long-grain-white": "cooked_rice",
    "rice-brown": "cooked_rice",
    "pasta-dry": "cooked_pasta",
    "quinoa": "cooked_quinoa",
}
FREE_ROLES = frozenset({"seasoning", "fat", "other", "garnish"})  # beside a grain or eggs, these don't count
FS_GOV = "FoodSafety.gov Cold Food Storage Chart"


@dataclass(frozen=True)
class StorageLine:
    """One prep-item line, as storage sees it."""

    slug: str
    safety_category: str | None
    diet_tags: frozenset[str]
    role: str
    preparation: str | None = None


@dataclass(frozen=True)
class StorageSource:
    citation: (
        str  # "FoodSafety.gov Cold Food Storage Chart", "USDA FoodKeeper (data version 128), product 178"
    )
    food: str  # the row as printed: "Fresh poultry, chicken or turkey, pieces"
    refrigerator: str  # "1 to 2 days"
    freezer: str  # "9 months"


@dataclass(frozen=True)
class PrepStorage:
    """How a prep item keeps after a stage."""

    state: PrepState
    stored: bool  # False: prep can't stop here (stored = False and made_on_the_day = False: V2)
    made_on_the_day: bool  # no row in either source: made fresh on the eating day (V1)
    fridge_days: int  # eaten from the fridge up to this many days after it's made (0 = that day)
    freezer: bool  # may go to the freezer at this stage (thawed in the fridge the night before)
    sources: tuple[StorageSource, ...]
    note: str  # for the batch view and the recipe page, written by code

    def fridge_until(self, made_on: date) -> date:
        """The last day a portion may come from the fridge."""
        return made_on + timedelta(days=self.fridge_days)


def _chart(key: str) -> StorageSource:
    row = storage_chart.chart_row(key)
    return StorageSource(FS_GOV, f"{row.food}, {row.type.lower()}", row.refrigerator, row.freezer)


def _keeper(row: FoodKeeperRow) -> StorageSource:
    return StorageSource(row.citation, row.food, row.refrigerator, row.freezer)


def _animal(line: StorageLine) -> bool:
    if line.safety_category is not None:
        return True
    return line.role == "protein" and bool(line.diet_tags & ANIMAL_TAGS)


def _is_egg(line: StorageLine) -> bool:
    return line.safety_category == "egg" or "egg" in line.diet_tags


def _days(text: str) -> tuple[int, int]:
    days = storage_chart.parse_days(text)
    assert days is not None, text  # every row used here is a day range
    return days


def _days_word(n: int) -> str:
    return f"{n} day" if n == 1 else f"{n} days"


def _raw(lines: Sequence[StorageLine], state: PrepState) -> PrepStorage:
    """Raw or marinated: each meat, poultry, fish or egg line's raw row, its short end; it can freeze."""
    sources: list[StorageSource] = []
    windows: list[int] = []
    for line in lines:
        if not _animal(line):
            continue
        if _is_egg(line):
            source = _chart("eggs_raw_whites_yolks")
        else:
            life = fridge_life(line.slug, line.safety_category)
            if life is None or not life.freeze_raw:
                return _made_on_the_day(state)  # a protein with no raw row: no storage time to keep to
            source = _chart(storage_chart.APP_STORAGE[life.use])
        sources.append(source)
        windows.append(_days(source.refrigerator)[0])
    if not sources:
        return _made_on_the_day(state)
    days = min(windows)
    state_word = "Marinated" if state is PrepState.MARINATED else "Raw"
    return PrepStorage(
        state,
        stored=True,
        made_on_the_day=False,
        fridge_days=days,
        freezer=True,
        sources=_unique(sources),
        note=(
            f"{state_word}, it keeps {_days_word(days)} in the fridge ({_ranges(sources)}); to keep it "
            "longer, freeze it the same day and thaw it in the fridge the night before."
        ),
    )


def _made_on_the_day(state: PrepState) -> PrepStorage:
    return PrepStorage(
        state,
        stored=False,
        made_on_the_day=True,
        fridge_days=0,
        freezer=False,
        sources=(),
        note=f"Made fresh on the day you eat it ({MADE_ON_THE_DAY_MINUTES} min): neither FoodSafety.gov nor "
        "USDA FoodKeeper gives a storage time for it.",
    )


def _cooked_sources(lines: Sequence[StorageLine]) -> list[StorageSource]:
    animal = [line for line in lines if _animal(line)]
    counted = [line for line in lines if line.role not in FREE_ROLES]
    if counted and all(
        _is_egg(line) and line.preparation and HARD_COOKED.search(line.preparation) for line in counted
    ):  # only hard-cooked eggs (and their salt)
        return [_chart("eggs_hard_cooked")]
    sources: list[StorageSource] = []
    for line in animal:
        if _is_egg(line):
            sources.append(_chart("eggs_casseroles"))
        elif "shellfish" in line.diet_tags:
            sources.append(_keeper(foodkeeper_row("cooked_shellfish")))
        elif "fish" in line.diet_tags:
            sources.append(_keeper(foodkeeper_row("cooked_fish")))
        else:
            sources.append(_chart("leftovers_cooked_meat_poultry"))
    if animal:
        return sources
    sources.append(_keeper(foodkeeper_row("leftovers_without_meat")))
    grains = {GRAIN_ROWS.get(line.slug) for line in counted}
    if len(grains) == 1 and None not in grains:  # only that grain
        (grain,) = grains
        assert grain is not None
        sources.append(_keeper(foodkeeper_row(grain)))
    return sources


def _cooked(
    lines: Sequence[StorageLine], state: PrepState, *, freezes_well: bool, leftover_fridge_days: int
) -> PrepStorage:
    sources = _cooked_sources(lines)
    hard_cooked = sources == [_chart("eggs_hard_cooked")]
    upper = min(_days(s.refrigerator)[1] for s in sources)
    days = upper if hard_cooked else min(leftover_fridge_days, upper)  # hard-cooked eggs: the row's 1 week
    freezer = freezes_well and all(_freezes(s) for s in sources)
    whose = "" if hard_cooked else "your setting, "
    note = f"Keeps {_days_word(days)} in the fridge ({whose}{_ranges(sources)})."
    if freezer:
        note += " Freezes well: thaw it in the fridge the night before."
    return PrepStorage(
        state,
        stored=True,
        made_on_the_day=False,
        fridge_days=days,
        freezer=freezer,
        sources=_unique(sources),
        note=note,
    )


def _freezes(source: StorageSource) -> bool:
    text = source.freezer.lower()
    return not (text.startswith("do not freeze") or text.startswith("not recommended"))


def _ranges(sources: Sequence[StorageSource]) -> str:
    return "; ".join(f"{s.citation.split(' (')[0]}: {s.food}, {s.refrigerator}" for s in _unique(sources))


def _unique(sources: Sequence[StorageSource]) -> tuple[StorageSource, ...]:
    return tuple(dict.fromkeys(sources))


def prep_storage(
    lines: Sequence[StorageLine],
    state: PrepState,
    *,
    freezes_well: bool,
    leftover_fridge_days: int,
) -> PrepStorage:
    """How an item made of `lines` keeps when prep stops in `state`. `freezes_well`: the item's flag, for
    cooked food (raw and marinated meat, poultry and fish always freeze); `leftover_fridge_days`: your setting
    (at most the chart's 4)."""
    if state in (PrepState.RAW, PrepState.MARINATED):
        return _raw(lines, state)
    if state is PrepState.PARTLY_COOKED:
        if any(_animal(line) for line in lines):
            return PrepStorage(
                state,
                stored=False,
                made_on_the_day=False,
                fridge_days=0,
                freezer=False,
                sources=(),
                note="Partly cooked meat, poultry, fish or eggs isn't stored: finish it the same day.",
            )
        return _cooked(lines, state, freezes_well=freezes_well, leftover_fridge_days=leftover_fridge_days)
    return _cooked(lines, state, freezes_well=freezes_well, leftover_fridge_days=leftover_fridge_days)


def dish_storage(leftover_fridge_days: int, *, freezes_well: bool) -> PrepStorage:
    """A whole dish, stored as every dish is today (FLOW_SPEC §19.2): your leftover days, frozen when it
    freezes well."""
    source = _chart("leftovers_cooked_meat_poultry")
    note = f"Keeps {_days_word(leftover_fridge_days)} in the fridge (your setting, {_ranges([source])})."
    if freezes_well:
        note += " Freezes well: thaw it in the fridge the night before."
    return PrepStorage(
        PrepState.COOKED,
        stored=True,
        made_on_the_day=False,
        fridge_days=leftover_fridge_days,
        freezer=freezes_well,
        sources=(source,),
        note=note,
    )


def stop_stages(
    lines: Sequence[StorageLine],
    states: Sequence[PrepState],
    *,
    freezes_well: bool,
    leftover_fridge_days: int,
) -> list[PrepStorage]:
    """Each stage's storage, in order (stage n is `states[n - 1]`). Prep may stop after a stage whose storage
    is `stored`; a fresh item (made on the day) is made whole on the eating day."""
    return [
        prep_storage(lines, s, freezes_well=freezes_well, leftover_fridge_days=leftover_fridge_days)
        for s in states
    ]
