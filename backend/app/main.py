"""FastAPI application."""

from fastapi import APIRouter, Depends, FastAPI

from app.api.errors import install_error_handlers
from app.api.routes import (
    auth,
    calculations,
    cook,
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
from app.api.timing import ConnectLogMiddleware
from app.auth.dependencies import check_origin, require_session
from app.config import get_settings
from app.production import check_production

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
    cook.router,
)


def create_app() -> FastAPI:
    settings = get_settings()
    check_production(settings)  # refuses to start on unsafe production settings (step 2b.13)
    docs = not settings.vercel  # no public API docs on the deployed app
    app = FastAPI(
        title="Mealbro",
        version="0.2.0",
        docs_url="/docs" if docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs else None,
    )
    install_error_handlers(app)
    app.add_middleware(ConnectLogMiddleware)  # a run record's slow-start facts (AC5)
    app.include_router(health.router)
    app.include_router(auth.router)
    guarded = [Depends(check_origin), Depends(require_session)]
    for router in PROTECTED:
        app.include_router(router, dependencies=guarded)
    return app


app = create_app()
