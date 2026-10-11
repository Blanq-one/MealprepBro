"""Natural-language quick add (Phase 2): the LLM reads a note into items; code does everything else.

Nothing is saved here. Each parsed item is resolved to a canonical ingredient, its amount converted by code,
and checked for numeric fidelity: every quantity must appear in the note itself ("2", "1.5", "½", "half",
"a", "dozen"), so an amount the model made up comes back as `needs_confirmation`. Excluded foods (beef) are
flagged and can't be saved; held items can be, with a note that plans won't use them until you allow them.
Pork is allowed in inventory (its cap applies to meals). You confirm the preview with POST /inventory/bulk.
A rate-limit wait longer than the request can wait answers `waiting` with `retry_after_s` (step 2b.3b).
"""

import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import GenerationRun, Product
from app.domain.enums import StorageLocation
from app.domain.exclusions import ExclusionStatus
from app.domain.units import UnitError, normalize_unit, to_base
from app.llm.client import LLMClient
from app.llm.errors import LLMRateLimitedError, LLMWaitTooLongError
from app.llm.pacing import Deadline, SystemClock
from app.llm.prompts import inventory_parse
from app.llm.structured import LLMRunContext, StructuredSpec
from app.planning.resolver import IngredientResolver
from app.schemas.inventory import ParsedLotOut, ParseOut, SuggestionOut
from app.schemas.llm_inventory import ParsedInventory, ParsedInventoryItem, ParsedUnit
from app.services.ingredients import search
from app.services.plans import amount_display

PARSE_TIME_BUDGET_S = 60.0
Q3 = Decimal("0.001")
NUMBER_WORDS = {
    "a": Decimal(1),
    "an": Decimal(1),
    "one": Decimal(1),
    "half": Decimal("0.5"),
    "quarter": Decimal("0.25"),
    "couple": Decimal(2),
    "two": Decimal(2),
    "three": Decimal(3),
    "four": Decimal(4),
    "five": Decimal(5),
    "six": Decimal(6),
    "seven": Decimal(7),
    "eight": Decimal(8),
    "nine": Decimal(9),
    "ten": Decimal(10),
    "eleven": Decimal(11),
    "twelve": Decimal(12),
    "dozen": Decimal(12),
}
UNICODE_FRACTIONS = {"½": "1/2", "¼": "1/4", "¾": "3/4", "⅓": "1/3", "⅔": "2/3"}
_NUMBER = re.compile(r"(\d+)\s+(\d+)/(\d+)|(\d+)/(\d+)|(\d+(?:\.\d+)?)")
_WORD = re.compile(r"[a-z]+")
# The LLM's units -> the app's unit codes ("package" uses your usual package size instead)
UNIT_CODES = {u: u.value for u in ParsedUnit if u is not ParsedUnit.PACKAGE}


class ParseError(ValueError):
    pass


def numbers_written(note: str) -> set[Decimal]:
    """Every amount the note spells out: digits, decimals, fractions (1/2, 1 1/2, ½) and number words."""
    text = note.lower()
    for char, plain in UNICODE_FRACTIONS.items():
        text = text.replace(char, f" {plain}")
    found: set[Decimal] = set()
    for mixed_whole, mixed_n, mixed_d, frac_n, frac_d, plain in _NUMBER.findall(text):
        if mixed_whole:
            found.add(Decimal(mixed_whole) + Decimal(mixed_n) / Decimal(mixed_d))
            found.add(Decimal(mixed_whole))
        elif frac_n:
            if Decimal(frac_d) != 0:
                found.add(Decimal(frac_n) / Decimal(frac_d))
        else:
            found.add(Decimal(plain))
    found |= {NUMBER_WORDS[w] for w in _WORD.findall(text) if w in NUMBER_WORDS}
    return found


def is_written(quantity: float, note: str) -> bool:
    value = Decimal(str(quantity))
    return any(abs(value - n) <= Decimal("0.001") for n in numbers_written(note))


@dataclass
class _Context:
    session: Session
    user_id: int
    resolver: IngredientResolver


def _suggestions(ctx: _Context, name: str) -> list[SuggestionOut]:
    return [
        SuggestionOut(ingredient_id=h.id, name=h.name)
        for h in search(ctx.session, ctx.user_id, name, limit=3)
    ]


def _default_package(session: Session, ingredient_id: int) -> Product | None:
    products = list(
        session.scalars(
            select(Product)
            .where(
                Product.ingredient_id == ingredient_id,
                Product.archived_at.is_(None),
                Product.package_amount.is_not(None),
            )
            .order_by(Product.is_default.desc(), Product.id)
        )
    )
    return products[0] if products else None


def preview_item(ctx: _Context, item: ParsedInventoryItem, note: str) -> ParsedLotOut:
    base = {"text": item.text, "name_as_written": item.name}
    ingredient_id, _ = ctx.resolver.lookup(item.name)
    if ingredient_id is None:
        return ParsedLotOut(
            **base,
            status="unresolved",
            message=f"'{item.name}' isn't in the ingredient list; pick one of the suggestions or skip it.",
            suggestions=_suggestions(ctx, item.name),
        )
    data = ctx.resolver.data[ingredient_id]
    status = ctx.resolver.statuses[ingredient_id]
    found = {
        **base,
        "ingredient_id": ingredient_id,
        "ingredient_name": data.name,
        "location": item.location or StorageLocation(data.typical_location or "fridge"),
    }
    if status.status is ExclusionStatus.EXCLUDED:
        return ParsedLotOut(
            **found, status="excluded", message=f"{data.name} is excluded ({'; '.join(status.reasons)})."
        )
    held_note = (
        f"Held: plans won't use {data.name} until you allow it in settings."
        if status.status is ExclusionStatus.HELD
        else None
    )
    if item.quantity is None:
        return ParsedLotOut(**found, status="needs_confirmation", message="How much? The note doesn't say.")
    product_id: int | None = None
    try:
        if item.unit is ParsedUnit.PACKAGE:
            product = _default_package(ctx.session, ingredient_id)
            if product is None or product.package_amount is None:
                return ParsedLotOut(
                    **found,
                    status="needs_confirmation",
                    message=f"There's no usual package size for {data.name}; enter the amount.",
                )
            amount = Decimal(str(item.quantity)) * product.package_amount
            quantity = to_base(amount, product.package_unit, data.units)
            product_id = product.id
        else:
            unit = normalize_unit(UNIT_CODES[item.unit], data.units.named_units)
            quantity = to_base(Decimal(str(item.quantity)), unit, data.units)
    except (UnitError, ValueError) as exc:
        return ParsedLotOut(**found, status="needs_confirmation", message=f"Check the amount: {exc}.")
    out = {
        **found,
        "quantity": quantity.amount.quantize(Q3),
        "unit": quantity.unit.value,
        "display": amount_display(quantity.amount, quantity.unit.value),
        "product_id": product_id,
    }
    if not is_written(item.quantity, note):
        return ParsedLotOut(
            **out,
            status="needs_confirmation",
            message=f"The note doesn't say {item.quantity:g}; check the amount before saving.",
        )
    return ParsedLotOut(**out, status="ok", message=held_note)


def parse_note(session: Session, user_id: int, note: str, client: LLMClient, settings: Settings) -> ParseOut:
    """LLM parse (validated, retried with the errors) → resolution → a preview. Saves nothing but the run
    record and its LLM calls."""
    run = GenerationRun(user_id=user_id, purpose=inventory_parse.PURPOSE, status="running")
    session.add(run)
    session.flush()
    clock = SystemClock()
    llm = LLMRunContext(
        client, session, settings, run.id, clock, deadline=Deadline.after(clock, PARSE_TIME_BUDGET_S)
    )
    spec = StructuredSpec(
        purpose=inventory_parse.PURPOSE,
        prompt_version=inventory_parse.PROMPT_VERSION,
        messages=inventory_parse.build_messages(note),
        response_model=ParsedInventory,
    )
    try:
        result = llm.generate(spec)
    except (LLMWaitTooLongError, LLMRateLimitedError) as exc:  # a pause, never an error (FLOW_SPEC §5.5)
        run.status, run.finished_at = "failed", datetime.now(UTC)
        run.error = {"code": exc.code, "detail": str(exc)}
        session.flush()
        retry = max(1, math.ceil(exc.retry_after_s or 60))
        return ParseOut(
            run_id=run.id, llm_call_count=run.llm_call_count, items=[], status="waiting", retry_after_s=retry
        )
    except Exception:
        run.status, run.finished_at = "failed", datetime.now(UTC)
        session.flush()
        raise
    ctx = _Context(session, user_id, IngredientResolver(session, user_id))
    items = [preview_item(ctx, item, note) for item in result.value.items]
    run.status, run.finished_at = "succeeded", datetime.now(UTC)
    session.flush()
    return ParseOut(run_id=run.id, llm_call_count=run.llm_call_count, items=items)
