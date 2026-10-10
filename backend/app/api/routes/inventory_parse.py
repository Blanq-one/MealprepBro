from datetime import UTC, datetime

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession, LLMClientFactory
from app.api.presenters import inventory_lots_out
from app.api.problems import ProblemError
from app.config import get_settings
from app.llm.errors import LLMConfigError, LLMError
from app.schemas.inventory import BulkIn, InventoryLotOut, ParseIn, ParseOut, QuickPickOut
from app.services import inventory as inventory_service
from app.services import inventory_parse as service
from app.services.ingredient_data import load_ingredients
from app.services.pantry_add import estimated_expiry, resolve_preset
from app.services.quick_add import quick_picks, resolve_amount

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
    """Add several lots at once (quick add, or a confirmed note). All or nothing; beef can't be added. Each
    amount comes as quantity + unit, a quick pick's amount option, or a custom amount in one of its units."""
    reason = "parse_add" if body.source == "parse" else "purchase"
    inputs = []
    for item in body.items:
        extra: dict[str, object] = {}
        if item.quantity is not None and item.unit is not None:
            quantity, unit = item.quantity, item.unit
        elif item.preset is not None or item.not_sure:
            preset = resolve_preset(session, item.ingredient_id, item.preset)
            quantity, unit = preset.quantity, preset.unit
            extra = {"container": preset.container, "quantity_is_estimate": preset.is_estimate or None}
            if item.expires_on is None:  # a use-by estimate from its shelf life where it's kept
                data = load_ingredients(session, [item.ingredient_id]).get(item.ingredient_id)
                if data is not None:
                    start = item.acquired_on or datetime.now(UTC).date()
                    extra["expires_on"] = estimated_expiry(data, item.location, start)
        else:
            quantity, unit = resolve_amount(
                session,
                user.id,
                item.ingredient_id,
                item.product_id,
                option=item.amount_option,
                custom_amount=item.custom_amount,
                custom_unit=item.custom_unit,
            )
        fields = item.model_dump(
            exclude={
                "quantity",
                "unit",
                "amount_option",
                "custom_amount",
                "custom_unit",
                "preset",
                "not_sure",
            }
        )
        fields.update(extra)
        inputs.append(inventory_service.LotInput(**fields, quantity=quantity, unit=unit, reason=reason))
    lots = inventory_service.add_lots(session, user.id, inputs)
    session.commit()
    return inventory_lots_out(session, lots)


@router.get("/quick-picks", response_model=list[QuickPickOut])
def get_quick_picks(session: DbSession, user: CurrentUser) -> list[QuickPickOut]:
    """One-tap adds: the ingredients your recipes use, each with its usual package or a typical amount."""
    return quick_picks(session, user.id)
