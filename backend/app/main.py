"""FastAPI application."""

from fastapi import FastAPI

from app.api.errors import install_error_handlers
from app.api.routes import calculations, health, ingredients, inventory, plans, products, recipes, settings


def create_app() -> FastAPI:
    app = FastAPI(title="Mealbro", version="0.0.0")
    install_error_handlers(app)
    app.include_router(health.router)
    app.include_router(ingredients.router)
    app.include_router(calculations.router)
    app.include_router(recipes.router)
    app.include_router(recipes.versions_router)
    app.include_router(settings.router)
    app.include_router(inventory.router)
    app.include_router(products.router)
    app.include_router(plans.router)
    return app


app = create_app()
