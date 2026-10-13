"""application/problem+json errors (RFC 9457)."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.problems import ProblemError
from app.auth.passwords import PasswordHashError
from app.cook.search import SearchNotFoundError
from app.cook.single_meal import CookThisError, StepsNotReadyError
from app.db.session import DATABASE_RETRY_AFTER_S, DATABASE_SLOW_DETAIL, DATABASE_SLOW_TITLE
from app.domain.quantities import QuantityParseError
from app.domain.scaling import ScalingError
from app.domain.units import InvalidQuantityError, UnitError
from app.planning.constraint_builder import ConstraintError
from app.planning.persistence import PlanNotFoundError, PlanOverlapError
from app.services.calculations import CalculationError
from app.services.cooking import CookingError
from app.services.errors import ConflictError
from app.services.grocery import GroceryError
from app.services.ingredients import IngredientNotFoundError
from app.services.inventory import InventoryError
from app.services.plans import RunNotFoundError
from app.services.products import ProductError
from app.services.recipe_edits import EditError
from app.services.recipes import RecipeNotFoundError
from app.services.settings import NotSeededError, SettingsError
from app.services.suggestions import SuggestionError

PROBLEM_JSON = "application/problem+json"


def problem(status: int, title: str, detail: str, **extra: Any) -> JSONResponse:
    body = {"type": "about:blank", "title": title, "status": status, "detail": detail, **extra}
    return JSONResponse(jsonable_encoder(body), status_code=status, media_type=PROBLEM_JSON)


NOT_FOUND = (
    IngredientNotFoundError,
    PlanNotFoundError,
    RunNotFoundError,
    RecipeNotFoundError,
    CookingError,
    SearchNotFoundError,
)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]
        return problem(422, "Invalid request", "The request did not pass validation.", errors=errors)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return problem(exc.status_code, "HTTP error", str(exc.detail))

    calc_errors = (UnitError, InvalidQuantityError, QuantityParseError, ScalingError, CalculationError)
    rejected = (
        SettingsError,
        InventoryError,
        ProductError,
        SuggestionError,
        ConstraintError,
        GroceryError,
        CookThisError,
        EditError,
    )

    @app.exception_handler(ValueError)
    async def _domain(request: Request, exc: ValueError) -> JSONResponse:
        if isinstance(exc, calc_errors):
            return problem(422, "Cannot calculate", str(exc))
        if isinstance(exc, rejected):
            message = str(exc)
            status = 404 if "not found" in message else 422
            return problem(status, "Not found" if status == 404 else "Rejected", message)
        raise exc

    @app.exception_handler(LookupError)
    async def _not_found(_: Request, exc: LookupError) -> JSONResponse:
        if isinstance(exc, NOT_FOUND):
            return problem(404, "Not found", str(exc))
        raise exc

    @app.exception_handler(NotSeededError)
    async def _not_seeded(_: Request, exc: NotSeededError) -> JSONResponse:
        return problem(503, "Database not seeded", str(exc))

    @app.exception_handler(ProblemError)
    async def _problem(_: Request, exc: ProblemError) -> JSONResponse:
        response = problem(exc.status, exc.title, exc.detail)
        response.headers.update(exc.headers)
        return response

    @app.exception_handler(ConflictError)
    async def _conflict(_: Request, exc: ConflictError) -> JSONResponse:
        if isinstance(exc, StepsNotReadyError):  # never an error page: try again at retry_after_s
            return problem(
                409, "The steps aren't written yet", str(exc), code=exc.code, retry_after_s=exc.retry_after_s
            )
        if isinstance(exc, PlanOverlapError):  # the "Replace your current plan?" sheet
            return problem(
                409,
                "This plan overlaps your current plan",
                str(exc),
                code="plan_overlap",
                overlapping=[
                    {
                        "plan_id": o.plan_id,
                        "start": o.start.isoformat(),
                        "end": o.end.isoformat(),
                        "meals": o.meals,
                        "message": o.message,
                    }
                    for o in exc.overlapping
                ],
            )
        return problem(409, "Conflict", str(exc))

    @app.exception_handler(PasswordHashError)
    async def _bad_hash(_: Request, exc: PasswordHashError) -> JSONResponse:
        return problem(503, "Sign-in isn't set up", str(exc))

    @app.exception_handler(OperationalError)
    async def _database(_: Request, exc: OperationalError) -> JSONResponse:
        # the database didn't answer after the connect retries (a Neon compute waking up, AC5): try again
        response = problem(503, DATABASE_SLOW_TITLE, DATABASE_SLOW_DETAIL, code="db_unavailable")
        response.headers["Retry-After"] = str(DATABASE_RETRY_AFTER_S)
        return response
