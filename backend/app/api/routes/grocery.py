from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.api.presenters import inventory_lots_out
from app.db.models import Product, Store
from app.schemas.plans import GroceryCompleteIn, GroceryCompleteOut, GroceryItemOut, GroceryItemPatch
from app.services import grocery as service
from app.services.ingredient_data import load_ingredients
from app.services.plans import grocery_item_out

router = APIRouter(prefix="/api/v1", tags=["grocery"])


@router.patch("/grocery-items/{item_id}", response_model=GroceryItemOut)
def check_off(item_id: int, body: GroceryItemPatch, session: DbSession, user: CurrentUser) -> GroceryItemOut:
    """Check an item off (or back on), with what you actually bought and paid if you like. Send only what
    changed; repeating the same request changes nothing, so the offline queue can replay it."""
    changes = body.model_dump(include=body.model_fields_set)
    item = service.check_off(session, user.id, item_id, changes)
    session.commit()
    data = load_ingredients(session, [item.ingredient_id])
    stores = {s.id: s.name for s in session.scalars(select(Store))}
    product = session.get(Product, item.product_id) if item.product_id else None
    return grocery_item_out(item, data, stores, {product.id: product.name} if product else {})


@router.post("/grocery-lists/{list_id}/complete", response_model=GroceryCompleteOut)
def complete(
    list_id: int, body: GroceryCompleteIn, session: DbSession, user: CurrentUser
) -> GroceryCompleteOut:
    """Done shopping: checked items become inventory lots and their actual prices become per-store price
    observations. A repeated call returns what the first one did (nothing is added twice)."""
    result = service.complete(session, user.id, list_id, body.purchased_on)
    session.commit()
    return GroceryCompleteOut(
        grocery_list_id=result.grocery_list.id,
        status=result.grocery_list.status,
        already_done=result.already_done,
        lots_created=len(result.lots),
        prices_recorded=result.prices_recorded,
        lots=inventory_lots_out(session, result.lots),
        not_bought=result.skipped,
    )
