"""Tests for the public storefront ordering contract.

The rule these exist to defend:

    THE BROWSER SENDS IDs AND QUANTITIES. IT NEVER SENDS PRICES.

`POST /api/v1/public/orders` is reachable by anyone on the internet. The
authenticated POS schema accepts `unit_price` from its caller, which is fine for
a till operated by trusted staff and is a "set your own price" button here. If
someone ever relaxes `extra="forbid"` on the public item schema, or adds a price
field to it, these tests fail loudly.
"""

import uuid

import pytest
from pydantic import ValidationError

from app.schemas.public_order import PublicOrderCreate, PublicOrderItemRequest


def _order(**overrides) -> dict:
    payload = {
        "service_type": "collection",
        "customer_name": "Test Customer",
        "customer_phone": "07909313456",
        "items": [{"menu_item_id": str(uuid.uuid4()), "quantity": 2}],
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# The price boundary -- the reason this file exists
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("price_field", ["unit_price", "total", "price"])
def test_client_cannot_supply_a_price(price_field: str) -> None:
    """Any attempt to put a price on a basket line is rejected outright."""
    with pytest.raises(ValidationError):
        PublicOrderCreate(
            **_order(
                items=[
                    {
                        "menu_item_id": str(uuid.uuid4()),
                        "quantity": 1,
                        price_field: 1,
                    }
                ]
            )
        )


def test_item_schema_forbids_extra_fields() -> None:
    """`extra="forbid"` is load-bearing, not cosmetic.

    Pydantic's default would silently ignore an unknown field, which is safe but
    leaves the caller believing it was accepted.
    """
    assert PublicOrderItemRequest.model_config.get("extra") == "forbid"


def test_delivery_fee_never_becomes_model_data() -> None:
    """A stray delivery_fee in the body must not survive onto the model."""
    model = PublicOrderCreate(**_order(delivery_fee=0))
    assert not hasattr(model, "delivery_fee")


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------


def test_delivery_requires_area_and_address() -> None:
    with pytest.raises(ValidationError):
        PublicOrderCreate(
            **_order(service_type="delivery", delivery_address="1 High Street")
        )
    with pytest.raises(ValidationError):
        PublicOrderCreate(
            **_order(service_type="delivery", delivery_area_id="arrochar")
        )


def test_delivery_with_area_and_address_is_valid() -> None:
    model = PublicOrderCreate(
        **_order(
            service_type="delivery",
            delivery_area_id="arrochar",
            delivery_address="1 High Street",
        )
    )
    assert model.delivery_area_id == "arrochar"


def test_collection_needs_no_address() -> None:
    assert PublicOrderCreate(**_order()).service_type == "collection"


# ---------------------------------------------------------------------------
# Payment intent -- request-only, never persisted, see `email_service.
# _payment_status_text`. Defaults to "cash" so every existing caller that
# never sends this field keeps behaving exactly as before.
# ---------------------------------------------------------------------------


def test_payment_method_defaults_to_cash() -> None:
    assert PublicOrderCreate(**_order()).payment_method == "cash"


def test_payment_method_accepts_card() -> None:
    assert PublicOrderCreate(**_order(payment_method="card")).payment_method == "card"


def test_payment_method_rejects_anything_else() -> None:
    with pytest.raises(ValidationError):
        PublicOrderCreate(**_order(payment_method="bank_transfer"))


# ---------------------------------------------------------------------------
# Basket sanity
# ---------------------------------------------------------------------------


def test_empty_basket_rejected() -> None:
    with pytest.raises(ValidationError):
        PublicOrderCreate(**_order(items=[]))


@pytest.mark.parametrize("quantity", [0, -1, 100])
def test_quantity_bounds(quantity: int) -> None:
    with pytest.raises(ValidationError):
        PublicOrderCreate(
            **_order(items=[{"menu_item_id": str(uuid.uuid4()), "quantity": quantity}])
        )


def test_duplicate_modifiers_on_one_line_rejected() -> None:
    """Sending the same modifier twice would double its price adjustment."""
    modifier_id = str(uuid.uuid4())
    with pytest.raises(ValidationError):
        PublicOrderCreate(
            **_order(
                items=[
                    {
                        "menu_item_id": str(uuid.uuid4()),
                        "quantity": 1,
                        "modifier_ids": [modifier_id, modifier_id],
                    }
                ]
            )
        )


@pytest.mark.parametrize("service_type", ["dine_in", "takeaway", "", "DELIVERY"])
def test_service_type_is_restricted(service_type: str) -> None:
    with pytest.raises(ValidationError):
        PublicOrderCreate(**_order(service_type=service_type))


def test_customer_name_and_phone_required() -> None:
    for field in ("customer_name", "customer_phone"):
        payload = _order()
        del payload[field]
        with pytest.raises(ValidationError):
            PublicOrderCreate(**payload)
