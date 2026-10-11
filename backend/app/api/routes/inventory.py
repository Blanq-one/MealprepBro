from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.api.presenters import inventory_lots_out
from app.db.models import InventoryItem
from app.schemas.inventory import (
    CorrectOptionsOut,
    DiscardIn,
    InventoryLotIn,
    InventoryLotOut,
    InventoryLotPatch,
    VersionIn,
)
from app.services import inventory as service
from app.services.pantry_add import correct_options, fraction_quantity, resolve_preset, version_label

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
    if body.preset is not None:  # Pantry's "est." correction: a package size (step 2b.4)
        preset = resolve_preset(session, item.ingredient_id, body.preset)
        item = service.correct_amount(
            session, user.id, item_id, preset.quantity, preset.unit, container=preset.container
        )
    elif body.package_fraction is not None:  # what's left of the package (M2)
        left = fraction_quantity(session, user.id, item_id, body.package_fraction)
        item = service.set_quantity(session, user.id, item_id, left)
    elif body.quantity is not None and body.unit is not None:
        item = service.correct_amount(session, user.id, item_id, body.quantity, body.unit)
    elif body.quantity is not None:
        item = service.set_quantity(session, user.id, item_id, body.quantity)
    session.commit()
    return _out(session, [item])[0]


@router.get("/{item_id}/correct-options", response_model=CorrectOptionsOut)
def get_correct_options(item_id: int, session: DbSession, user: CurrentUser) -> CorrectOptionsOut:
    """Correct amount, for any lot (M2): ¾, ½ or ¼ of the package it came in, another package size, or a
    custom amount."""
    return correct_options(session, user.id, item_id)


@router.post("/{item_id}/version", response_model=InventoryLotOut)
def set_version(item_id: int, body: VersionIn, session: DbSession, user: CurrentUser) -> InventoryLotOut:
    """This lot of a held item is the version on its label (step 2b.4, J4): a new lot of that version takes
    its amount, place and dates. The generic held item stays held."""
    lot = session.get(InventoryItem, item_id)
    if lot is None or lot.user_id != user.id:
        raise service.InventoryError(f"inventory item {item_id} not found")
    label = version_label(session, lot.ingredient_id, body.ingredient_id)
    item = service.relabel_lot(session, user.id, item_id, body.ingredient_id, label)
    session.commit()
    return _out(session, [item])[0]


@router.post("/{item_id}/discard", response_model=InventoryLotOut)
def discard_lot(item_id: int, body: DiscardIn, session: DbSession, user: CurrentUser) -> InventoryLotOut:
    item = service.discard_lot(session, user.id, item_id, body.reason, body.note)
    session.commit()
    return _out(session, [item])[0]
