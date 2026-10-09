"""application/problem+json errors (RFC 9457)."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.quantities import QuantityParseError
from app.domain.scaling import ScalingError
from app.domain.units import InvalidQuantityError, UnitError
from app.services.calculations import CalculationError
from app.services.ingredients import IngredientNotFoundError
from app.services.settings import NotSeededError

PROBLEM_JSON = "application/problem+json"


def problem(status: int, title: str, detail: str, **extra: Any) -> JSONResponse:
    body = {"type": "about:blank", "title": title, "status": status, "detail": detail, **extra}
    return JSONResponse(jsonable_encoder(body), status_code=status, media_type=PROBLEM_JSON)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]
        return problem(422, "Invalid request", "The request did not pass validation.", errors=errors)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return problem(exc.status_code, "HTTP error", str(exc.detail))

    domain_errors = (UnitError, InvalidQuantityError, QuantityParseError, ScalingError, CalculationError)

    @app.exception_handler(ValueError)
    async def _domain(request: Request, exc: ValueError) -> JSONResponse:
        if isinstance(exc, domain_errors):
            return problem(422, "Cannot calculate", str(exc))
        raise exc

    @app.exception_handler(IngredientNotFoundError)
    async def _not_found(_: Request, exc: IngredientNotFoundError) -> JSONResponse:
        return problem(404, "Not found", str(exc))

    @app.exception_handler(NotSeededError)
    async def _not_seeded(_: Request, exc: NotSeededError) -> JSONResponse:
        return problem(503, "Database not seeded", str(exc))
