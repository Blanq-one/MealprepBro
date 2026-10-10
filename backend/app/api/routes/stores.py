from fastapi import APIRouter, Response

from app.api.deps import CurrentUser, DbSession
from app.db.models import Store
from app.schemas.settings import StoreIn, StoreOut
from app.services import settings as service

router = APIRouter(prefix="/api/v1/stores", tags=["settings"])


def _out(store: Store, order: list[str]) -> StoreOut:
    return StoreOut(
        id=store.id,
        name=store.name,
        priority=store.priority,
        order=order.index(store.name) + 1 if store.name in order else None,
    )


@router.get("", response_model=list[StoreOut])
def list_stores(session: DbSession, user: CurrentUser) -> list[StoreOut]:
    """The grocery stores you can pick, with your preference order."""
    order = service.load_settings(session, user.id).store_order
    return [_out(s, order) for s in service.grocery_stores(session)]


@router.post("", response_model=StoreOut, status_code=201)
def add_store(body: StoreIn, session: DbSession, user: CurrentUser, response: Response) -> StoreOut:
    """Add a grocery store by name (201), or get the one you already have with that name (200). Add it to
    your store order in settings to shop there."""
    store, created = service.add_store(session, body.name)
    session.commit()
    if not created:
        response.status_code = 200
    return _out(store, service.load_settings(session, user.id).store_order)
