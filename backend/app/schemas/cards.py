"""Recipe-card lines shared by the Cook flow and the recipe pages (Phase 2b): what to buy, what is missing
and its code-computed substitute, and a search's per-line notes. Every amount and price is a display string
computed by code."""

from typing import Literal

from pydantic import BaseModel

from app.domain.enums import PortionSize


class CostLineOut(BaseModel):
    """Something to buy for this meal: whole packages at the first of your stores that prices it."""

    ingredient_id: int
    name: str
    cost_cents: int | None
    cost_display: str  # "$1.29 est." or "no price yet"
    store: str | None
    is_estimate: bool
    display: str  # "chickpeas $1.29 (Stop & Shop)"


class SubstituteOut(BaseModel):
    ingredient_id: int
    name: str
    amount_display: str  # code-computed: "2 tbsp", "150 g"
    you_have: bool
    note: str | None = None  # an accepted pair's culinary note


class MissingLineOut(BaseModel):
    ingredient_id: int
    name: str
    kind: Literal["missing", "top_up"]  # top_up: you have some, not enough
    substitute: SubstituteOut | None
    buy: CostLineOut | None  # when there is no substitute (or for a top-up)
    # "lemon → bottled lime juice (you have it)", "lemon · buy $0.79", "more chicken thigh · buy $5.99"
    display: str


class SwapLineOut(BaseModel):
    """A missing line you can make with something you have (M11): never "Missing"."""

    ingredient_id: int
    name: str
    substitute: SubstituteOut
    display: str  # "Swap: lime juice instead of lemon (you have it)"


class LineContextOut(BaseModel):
    """What a recipe line means for the search it was opened from (C8)."""

    ingredient_id: int
    status: Literal["have", "short", "could_buy", "missing", "owned"]
    note: str | None  # "You have it", "Could buy: $1.29 (Stop & Shop)", "Don't have lemon? …"


class SearchContextOut(BaseModel):
    """GET /recipe-versions/{id}?search=: the coverage and substitute lines from that search."""

    search_id: int
    portions: int
    portion_size: PortionSize
    portions_display: str
    uses: list[str]
    could_buy: list[CostLineOut]
    missing: list[MissingLineOut]  # only what you'd buy (M11)
    swaps: list[SwapLineOut] = []  # what you can make with something you have
    lines: list[LineContextOut]
    note: str  # "Numbers are for the recipe as written."
