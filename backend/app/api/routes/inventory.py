from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.db.models import InventoryItem
from app.schemas.inventory import DiscardIn, InventoryLotIn, InventoryLotOut, InventoryLotPatch
from app.services import inventory as service
from app.services.ingredient_data import load_ingredients
from app.services.plans import amount_display

router = APIRouter(prefix="/api/v1/inventory", tags=["inventory"])


def _out(session: DbSession, items: list[InventoryItem]) -> list[InventoryLotOut]:
    names = {i: d.name for i, d in load_ingredients(session, {it.ingredient_id for it in items}).items()}
    return [
        InventoryLotOut(
            id=it.id,
            ingredient_id=it.ingredient_id,
            name=names.get(it.ingredient_id, "?"),
            product_id=it.product_id,
            quantity=it.quantity,
            unit=it.unit,
            display=amount_display(it.quantity, it.unit),
            location=it.location,
            acquired_on=it.acquired_on,
            opened_on=it.opened_on,
            expires_on=it.expires_on,
            expiry_is_estimate=it.expiry_is_estimate,
            status=it.status,
            notes=it.notes,
            created_at=it.created_at,
        )
        for it in items
    ]


@router.get("", response_model=list[InventoryLotOut])
def list_inventory(
    session: DbSession, user: CurrentUser, include_inactive: bool = Query(default=False)
) -> list[InventoryLotOut]:
    return _out(session, service.list_lots(session, user.id, include_inactive))


@router.post("", response_model=InventoryLotOut, status_code=201)
def add_lot(body: InventoryLotIn, session: DbSession, user: CurrentUser) -> InventoryLotOut:
    item = service.add_lot(session, user.id, service.LotInput(**body.model_dump()))
    session.commit()
    return _out(session, [item])[0]


@router.patch("/{item_id}", response_model=InventoryLotOut)
def patch_lot(
    item_id: int, body: InventoryLotPatch, session: DbSession, user: CurrentUser
) -> InventoryLotOut:
    item = service.update_lot(
        session,
        user.id,
        item_id,
        location=body.location,
        opened_on=body.opened_on,
        expires_on=body.expires_on,
        notes=body.notes,
    )
    if body.quantity is not None:
        item = service.set_quantity(session, user.id, item_id, body.quantity)
    session.commit()
    return _out(session, [item])[0]


@router.post("/{item_id}/discard", response_model=InventoryLotOut)
def discard_lot(item_id: int, body: DiscardIn, session: DbSession, user: CurrentUser) -> InventoryLotOut:
    item = service.discard_lot(session, user.id, item_id, body.reason, body.note)
    session.commit()
    return _out(session, [item])[0]
