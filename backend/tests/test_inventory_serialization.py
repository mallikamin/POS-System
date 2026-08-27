"""The JSON contract for inventory Decimals.

UAT finding F14: `/admin/ingredients` died on
`current_stock.toFixed is not a function`. Pydantic v2 serialises `Decimal` to a
JSON *string*, while every frontend type in this domain declares `number` and
does arithmetic on it. Several call sites only survived because JS coerces
strings in `*`, `/` and `>`; they were working by accident.

These tests pin BOTH halves of the fix, because getting one without the other is
the actual danger:
  - outbound must be a JSON number, so the client contract holds;
  - inbound must still be a `Decimal`, so no money is ever parsed as a float on
    the server, and the value constraints still bite.

A test that only asserted the first half would pass against a schema that had
been "fixed" by changing the field type to `float`, which would silently move
server-side money into binary floating point.
"""

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.inventory import (
    IngredientCreate,
    IngredientResponse,
    RecipeItemResponse,
)


def _ingredient_response(**overrides) -> IngredientResponse:
    payload = dict(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        name="Flour",
        category="Dry Goods",
        unit="kg",
        cost_per_unit=Decimal("350.00"),
        reorder_point=Decimal("4.167"),
        reorder_quantity=Decimal("25"),
        current_stock=Decimal("12.500"),
        is_produced=False,
        created_at=datetime.now(timezone.utc),
        updated_at=None,
    )
    payload.update(overrides)
    return IngredientResponse(**payload)


@pytest.mark.parametrize(
    "field",
    ["cost_per_unit", "current_stock", "reorder_point", "reorder_quantity"],
)
def test_ingredient_decimals_serialise_as_json_numbers(field):
    """The exact assertion whose absence let F14 reach a client."""
    payload = json.loads(_ingredient_response().model_dump_json())
    value = payload[field]
    assert isinstance(value, (int, float)), (
        f"{field} serialised as {type(value).__name__}; the frontend calls "
        f".toFixed() on it and will crash the page"
    )
    assert not isinstance(value, str)


def test_serialised_values_are_numerically_correct():
    payload = json.loads(_ingredient_response().model_dump_json())
    assert payload["current_stock"] == pytest.approx(12.5)
    assert payload["reorder_point"] == pytest.approx(4.167)
    assert payload["cost_per_unit"] == pytest.approx(350.0)


def test_zero_and_negative_stock_still_serialise_as_numbers():
    """Stock is allowed to go negative by design (a made batch must be
    recordable even without the inputs on the books). A negative must not
    fall back to a string representation."""
    payload = json.loads(
        _ingredient_response(current_stock=Decimal("-3.250")).model_dump_json()
    )
    assert payload["current_stock"] == pytest.approx(-3.25)
    assert isinstance(payload["current_stock"], float)


def test_recipe_item_costs_serialise_as_numbers():
    """The same landmine sat under every recipe cost field."""
    item = RecipeItemResponse(
        id=uuid.uuid4(),
        recipe_id=uuid.uuid4(),
        ingredient_id=uuid.uuid4(),
        quantity=Decimal("2.500"),
        unit="kg",
        waste_factor=Decimal("2.00"),
        cost_per_unit_snapshot=Decimal("350.00"),
        total_cost=Decimal("892.50"),
    )
    payload = json.loads(item.model_dump_json())
    for field in ("quantity", "waste_factor", "cost_per_unit_snapshot", "total_cost"):
        assert isinstance(payload[field], (int, float)), field


def test_inbound_parsing_still_uses_decimal_not_float():
    """The other half of the fix. If someone later 'simplifies' the schema by
    declaring these `float`, this test fails -- server-side money must never be
    binary floating point."""
    created = IngredientCreate(
        name="Flour", unit="kg", cost_per_unit="350.55", reorder_point="0.1"
    )
    assert isinstance(created.cost_per_unit, Decimal)
    assert created.cost_per_unit == Decimal("350.55")
    assert isinstance(created.reorder_point, Decimal)


def test_inbound_constraints_still_enforced():
    """Serialisation changes must not have loosened validation."""
    with pytest.raises(ValidationError, match="greater than or equal"):
        IngredientCreate(name="Flour", unit="kg", cost_per_unit="-1")
