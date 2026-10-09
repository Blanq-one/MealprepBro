from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.api.presenters import inventory_lots_out
from app.schemas.inventory import DiscardIn, InventoryLotIn, InventoryLotOut, InventoryLotPatch
from app.services import inventory as service

router = APIRouter(prefix="/api/v1/inventory", tags=["inventory"])


_out = inventory_lots_out


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
