from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.api.presenters import price_out
from app.schemas.api import IngredientDetailOut, IngredientSearchHitOut, NutrientPer100gOut, UnitOut
from app.services import ingredients as service

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
