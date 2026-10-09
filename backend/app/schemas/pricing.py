"""API models for products and manual price entry (Phase 1)."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import PriceBasis, PriceSource


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProductIn(_Strict):
    ingredient_id: int
    name: str = Field(min_length=1, max_length=120)
    price_basis: PriceBasis
    display_unit: str = Field(min_length=1, max_length=20)
    package_amount: Decimal | None = Field(default=None, gt=0)
    package_unit: str | None = None
    brand: str | None = None
    store_id: int | None = Field(default=None, description="only for store-brand products")
    is_variable_weight: bool = False
    is_default: bool = False


class ProductPatch(_Strict):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    brand: str | None = None
    is_default: bool | None = None
    display_unit: str | None = None


class ProductOut(BaseModel):
    id: int
    ingredient_id: int
    store_id: int | None
    name: str
    brand: str | None
    package_amount: Decimal | None
    package_unit: str
    price_basis: str
    display_unit: str
    is_default: bool


class PriceIn(_Strict):
    product_id: int
    store_id: int  # required: every price belongs to a store
    price_cents: int = Field(ge=0)
    per_amount: Decimal = Field(gt=0, description="the quantity the price covers, e.g. 1 (lb) or 20 (count)")
    per_unit: str = Field(min_length=1, max_length=20)
    observed_on: date
    is_sale: bool = False
    source: PriceSource = PriceSource.MANUAL
    note: str | None = Field(default=None, max_length=300)


class PriceOut(BaseModel):
    id: int
    product_id: int
    store_id: int
    observed_on: date
    price_cents: int
    priced_quantity: Decimal
    priced_unit: str
    is_sale: bool
    source: str
