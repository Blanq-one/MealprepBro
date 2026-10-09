from fastapi import APIRouter, Query, Response

from app.api.deps import CurrentUser, DbSession
from app.db.models import PriceObservation, Product
from app.schemas.pricing import PriceIn, PriceOut, ProductIn, ProductOut, ProductPatch
from app.services import products as service

router = APIRouter(prefix="/api/v1", tags=["products"])


def _product(p: Product) -> ProductOut:
    return ProductOut(
        id=p.id,
        ingredient_id=p.ingredient_id,
        store_id=p.store_id,
        name=p.name,
        brand=p.brand,
        package_amount=p.package_amount,
        package_unit=p.package_unit,
        price_basis=p.price_basis,
        display_unit=p.display_unit,
        is_default=p.is_default,
    )


def _price(o: PriceObservation) -> PriceOut:
    return PriceOut(
        id=o.id,
        product_id=o.product_id,
        store_id=o.store_id,
        observed_on=o.observed_on,
        price_cents=o.price_cents,
        priced_quantity=o.priced_quantity,
        priced_unit=o.priced_unit,
        is_sale=o.is_sale,
        source=o.source,
    )


@router.get("/products", response_model=list[ProductOut])
def list_products(
    session: DbSession, user: CurrentUser, ingredient_id: int | None = Query(default=None)
) -> list[ProductOut]:
    return [_product(p) for p in service.list_products(session, ingredient_id)]


@router.post("/products", response_model=ProductOut, status_code=201)
def create_product(body: ProductIn, session: DbSession, user: CurrentUser) -> ProductOut:
    product = service.create_product(session, service.ProductInput(**body.model_dump()))
    session.commit()
    return _product(product)


@router.patch("/products/{product_id}", response_model=ProductOut)
def patch_product(product_id: int, body: ProductPatch, session: DbSession, user: CurrentUser) -> ProductOut:
    product = service.update_product(session, product_id, **body.model_dump(exclude_unset=True))
    session.commit()
    return _product(product)


@router.delete("/products/{product_id}", status_code=204)
def archive_product(product_id: int, session: DbSession, user: CurrentUser) -> Response:
    service.archive_product(session, product_id)
    session.commit()
    return Response(status_code=204)


@router.post("/prices", response_model=PriceOut, status_code=201)
def add_price(body: PriceIn, session: DbSession, user: CurrentUser) -> PriceOut:
    """Manual price entry. A store is required: deal detection and grocery lists work per store."""
    obs = service.add_price(session, **body.model_dump())
    session.commit()
    return _price(obs)
