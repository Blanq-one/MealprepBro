"""API models for recipes and rendered recipe versions (Phase 1)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.api import NutritionOut, StoreCostOut
from app.schemas.cards import CostLineOut, MissingLineOut, SearchContextOut, SwapLineOut


class RenderedLineOut(BaseModel):
    ingredient_id: int
    name: str
    display: str  # "1¼ tsp salt"
    preparation: str | None
    optional: bool
    amount_display: str = ""  # "1¼ tsp": the amount alone
    portion_note: str | None = None  # "1 scoop per portion · 4 scoops for the batch of 4" (A1)


class RenderedStepOut(BaseModel):
    section: str
    text: str
    duration_minutes: int | None
    appliance_temp_f: int | None
    safety_note: str | None
    added_by_app: bool


class RecipeVersionOut(BaseModel):
    version_id: int
    recipe_id: int
    version_number: int
    title: str
    description: str
    badge: str | None  # "draft" for seed versions
    origin: str
    meal_slots: list[str]
    mood: str
    cuisine: str | None
    flavor_tags: list[str]
    equipment: list[str]
    freezer_friendly: bool  # shown as "Freezes well"
    freeze_note: str | None = None  # how to freeze it: "Freeze the chicken and rice; make the sauce fresh"
    base_servings: int
    portions: int
    portion_size: str
    active_minutes: int
    total_minutes: int
    time_note: str  # LLM time estimates are labeled "est."
    lines: list[RenderedLineOut]
    steps: list[RenderedStepOut]
    per_container: str
    labels: list[str]
    heme_note: str | None
    per_portion: NutritionOut
    costs: list[StoreCostOut]
    incomplete_reasons: list[str]
    change_summary: str | None
    created_at: datetime
    # Phase 2b
    dish_category: (
        str  # drink | dessert | oats | eggs | wrap | sandwich | soup | curry | pasta | salad | bowl |
    )
    # roast | snack | other (the app shows its icon)
    is_favorite: bool
    is_saved: bool
    steps_ready: bool = True  # False for an idea whose steps are written on first open (step 2b.3b)
    # with ?search=<id>: that search's coverage and substitute lines for this recipe (step 2b.3a)
    search_context: SearchContextOut | None = None


class RecipeVersionSummaryOut(BaseModel):
    version_id: int
    version_number: int
    created_by: str
    is_draft: bool
    change_summary: str | None
    created_at: datetime


class RecipeOut(BaseModel):
    recipe_id: int
    title: str
    origin: str
    family: str | None
    default_version_id: int | None
    versions: list[RecipeVersionSummaryOut]
    default_version: RecipeVersionOut | None


class SavedRecipeOut(BaseModel):
    """A Saved-list card (C7). Every number is a display string from code, per portion, at your household's
    portions (as the recipe page shows them); coverage is against your current pantry (step 2b.3a)."""

    recipe_id: int
    version_id: int
    title: str
    dish_category: str
    badges: list[Literal["favorite", "saved", "new", "draft"]]
    steps_ready: bool
    portions: int  # your household size
    portion_size: str  # your portion size (the recipe page's portion_size for the same numbers)
    portions_display: str  # "1 portion" / "for 2 people"
    numbers: list[str]  # "540 kcal", "41 g protein", "35 min", "$2.10 a portion est.", "$4.29 to buy today"
    uses: list[str]  # your items it uses
    could_buy: list[CostLineOut]  # always empty here (no could-buy items outside a search)
    missing: list[MissingLineOut]  # what you'd buy, with its price (M11)
    swaps: list[SwapLineOut] = Field(default_factory=list)  # what you can make with something you have
    saved_at: datetime
