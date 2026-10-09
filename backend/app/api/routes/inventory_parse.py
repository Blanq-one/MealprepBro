from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession, LLMClientFactory
from app.api.presenters import inventory_lots_out
from app.api.problems import ProblemError
from app.config import get_settings
from app.llm.errors import LLMConfigError, LLMError
from app.schemas.inventory import BulkIn, InventoryLotOut, ParseIn, ParseOut, QuickPickOut
from app.services import inventory as inventory_service
from app.services import inventory_parse as service
from app.services.quick_add import quick_picks

router = APIRouter(prefix="/api/v1/inventory", tags=["inventory"])


@router.post("/parse", response_model=ParseOut)
def parse(body: ParseIn, session: DbSession, user: CurrentUser, client_factory: LLMClientFactory) -> ParseOut:
    """Read a note like "2 lb chicken thighs and half a cabbage" into a preview. Nothing is saved: confirm
    the items with POST /inventory/bulk."""
    try:
        client = client_factory()
    except LLMConfigError as exc:
        raise ProblemError(503, "Quick add isn't set up", str(exc)) from exc
    if client is None:
        raise ProblemError(503, "Quick add isn't set up", "No LLM client is configured.")
    try:
        out = service.parse_note(session, user.id, body.text, client, get_settings())
    except LLMError as exc:
        session.commit()  # keep the run record and its LLM calls
        raise ProblemError(502, "Couldn't read that note", str(exc)) from exc
    session.commit()
    return out


@router.post("/bulk", response_model=list[InventoryLotOut], status_code=201)
def add_many(body: BulkIn, session: DbSession, user: CurrentUser) -> list[InventoryLotOut]:
    """Add several lots at once (quick add, or a confirmed note). All or nothing; beef can't be added."""
    reason = "parse_add" if body.source == "parse" else "purchase"
    lots = inventory_service.add_lots(
        session,
        user.id,
        [inventory_service.LotInput(**item.model_dump(), reason=reason) for item in body.items],
    )
    session.commit()
    return inventory_lots_out(session, lots)


@router.get("/quick-picks", response_model=list[QuickPickOut])
def get_quick_picks(session: DbSession, user: CurrentUser) -> list[QuickPickOut]:
    """One-tap adds: the ingredients your recipes use, each with its usual package or a typical amount."""
    return quick_picks(session, user.id)
