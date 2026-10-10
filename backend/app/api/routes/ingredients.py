from datetime import datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, model_validator

from app.api.deps import CurrentUser, DbSession
from app.api.presenters import price_out
from app.domain.enums import IngredientCategory, StorageLocation
from app.domain.units import UnitKind
from app.schemas.api import IngredientDetailOut, IngredientSearchHitOut, NutrientPer100gOut, UnitOut
from app.schemas.inventory import AddOptionsOut
from app.services import ingredients as service
from app.services import suggestions
from app.services.pantry_add import add_options

router = APIRouter(prefix="/api/v1/ingredients", tags=["ingredients"])


@router.get("", response_model=list[IngredientSearchHitOut])
def search_ingredients(
    session: DbSession,
    user: CurrentUser,
    q: str = Query(min_length=1, max_length=80),
    limit: int = Query(default=20, ge=1, le=service.MAX_LIMIT),
) -> list[IngredientSearchHitOut]:
    return [
        IngredientSearchHitOut(
            id=h.id,
            name=h.name,
            slug=h.slug,
            category=h.category,
            matched_alias=h.matched_alias,
            score=h.score,
            status=h.status.value,
            reasons=list(h.reasons),
            frequency_caps=list(h.frequency_caps),
        )
        for h in service.search(session, user.id, q, limit)
    ]


class SuggestionOut(BaseModel):
    name: str
    times_seen: int
    last_seen: datetime


class NewIngredientIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fdc_id: int
    category: IngredientCategory
    default_unit_kind: UnitKind
    is_perishable: bool
    typical_location: StorageLocation
    diet_tags: list[str]  # required, even if empty: you state what it is
    name: str | None = None


class ApproveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    alias_of: int | None = None
    new_ingredient: NewIngredientIn | None = None

    @model_validator(mode="after")
    def _one(self) -> "ApproveIn":
        if (self.alias_of is None) == (self.new_ingredient is None):
            raise ValueError("give exactly one of alias_of or new_ingredient")
        return self


class ApprovedOut(BaseModel):
    name: str
    ingredient_id: int
    created_ingredient: bool


@router.get("/suggested", response_model=list[SuggestionOut])
def list_suggested(session: DbSession, user: CurrentUser) -> list[SuggestionOut]:
    """Names the LLM used that aren't in the ingredient table yet (from the llm_call log)."""
    return [
        SuggestionOut(name=s.name, times_seen=s.times_seen, last_seen=s.last_seen)
        for s in suggestions.list_suggestions(session)
    ]


@router.post("/suggested/{name}/approve", response_model=ApprovedOut, status_code=201)
def approve_suggested(name: str, body: ApproveIn, session: DbSession, user: CurrentUser) -> ApprovedOut:
    if body.alias_of is not None:
        alias = suggestions.approve_as_alias(session, name, body.alias_of)
        session.commit()
        return ApprovedOut(name=name, ingredient_id=alias.ingredient_id, created_ingredient=False)
    assert body.new_ingredient is not None
    ingredient = suggestions.approve_as_new(
        session, name, suggestions.NewIngredient(**body.new_ingredient.model_dump())
    )
    session.commit()
    return ApprovedOut(name=name, ingredient_id=ingredient.id, created_ingredient=True)


@router.get("/{ingredient_id}/add-options", response_model=AddOptionsOut)
def get_add_options(ingredient_id: int, session: DbSession, user: CurrentUser) -> AddOptionsOut:
    """What adding this item asks (step 2b.4): which version of a held item (J4), which form, and the common
    package sizes for each form plus custom units (J5). Send the chosen form's ingredient id and a preset key
    (or not_sure) to POST /inventory/bulk."""
    return add_options(session, user.id, ingredient_id)


@router.get("/{ingredient_id}", response_model=IngredientDetailOut)
def get_ingredient(ingredient_id: int, session: DbSession, user: CurrentUser) -> IngredientDetailOut:
    d = service.detail(session, user.id, ingredient_id)
    i = d.ingredient
    return IngredientDetailOut(
        id=i.id,
        name=i.name,
        slug=i.slug,
        category=i.category,
        default_unit_kind=i.default_unit_kind,
        density_g_per_ml=i.density_g_per_ml,
        count_unit_weight_g=i.count_unit_weight_g,
        diet_tags=list(i.diet_tags),
        status=d.status.value,
        reasons=list(d.reasons),
        frequency_caps=list(d.frequency_caps),
        heme_iron_fraction=i.heme_iron_fraction,
        safety_category=i.safety_category,
        assume_in_stock=i.assume_in_stock,
        nutrition_source=i.nutrition_source,
        fdc_id=i.fdc_id,
        notes=i.notes,
        aliases=list(d.aliases),
        nutrients=[
            NutrientPer100gOut(
                code=n.code,
                display_name=n.display_name,
                unit=n.unit,
                amount_per_100g=n.amount_per_100g,
                source=n.source,
            )
            for n in d.nutrients
        ],
        units=[UnitOut(name=u.name, grams=u.grams, source=u.source) for u in d.units],
        prices=[price_out(p) for p in d.prices],
    )
