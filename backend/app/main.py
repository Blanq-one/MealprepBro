"""FastAPI application."""

from fastapi import APIRouter, Depends, FastAPI

from app.api.errors import install_error_handlers
from app.api.routes import (
    auth,
    calculations,
    cook_batches,
    grocery,
    health,
    ingredients,
    inventory,
    inventory_parse,
    plans,
    products,
    recipes,
    settings,
    stores,
)
from app.auth.dependencies import check_origin, require_session
from app.config import get_settings

# Everything under /api/v1 needs a signed-in session and a same-origin request, except sign-in itself.
PROTECTED: tuple[APIRouter, ...] = (
    ingredients.router,
    calculations.router,
    recipes.router,
    recipes.versions_router,
    settings.router,
    stores.router,
    inventory_parse.router,  # before inventory: /inventory/parse and /inventory/bulk aren't lot ids
    inventory.router,
    products.router,
    plans.router,
    grocery.router,
    cook_batches.router,
)


def create_app() -> FastAPI:
    docs = not get_settings().vercel  # no public API docs on the deployed app
    app = FastAPI(
        title="Mealbro",
        version="0.2.0",
        docs_url="/docs" if docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs else None,
    )
    install_error_handlers(app)
    app.include_router(health.router)
    app.include_router(auth.router)
    guarded = [Depends(check_origin), Depends(require_session)]
    for router in PROTECTED:
        app.include_router(router, dependencies=guarded)
    return app


app = create_app()
