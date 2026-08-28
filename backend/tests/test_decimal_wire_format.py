"""The decimal wire contract: these fields go out as JSON numbers, not strings.

Why this file exists. `Num` (`app/schemas/location.py`) serialises `Decimal` as a
JSON number because the frontend types every one of these fields as `number` and
does arithmetic on them. When a field slips out from under `Num` the mismatch is
silent in Python, silent in mypy, silent in the TypeScript types (which simply
assert the wrong thing), and it surfaces only as a blank page in front of a
client:

* **F14** - `/admin/ingredients` died with `current_stock.toFixed is not a
  function`.
* **F51** - `/admin/transfers` died with `n.trim is not a function`, found while
  recording the FZ LLC demo. The offending value reached the page through
  `ProductionRunResponse.consumed`, a bare `list[dict]`: a `Decimal` inside an
  untyped dict escapes `Num` and serialises as a string, so one field disagreed
  with every sibling in the same response.

So these assertions are on the JSON, not on the Python objects. A test that
checks `isinstance(x, Decimal)` would have passed happily through both outages.
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal

from app.schemas.location import (
    LocationStockRow,
    ProductionRunResponse,
    StockMovementRow,
    TransferItemResponse,
)

UID = uuid.uuid4()


def _json(model) -> dict:
    """Serialise the way FastAPI does, then read it back as plain JSON."""
    return json.loads(model.model_dump_json())


def _assert_number(payload: dict, field: str) -> None:
    value = payload[field]
    assert isinstance(value, (int, float)) and not isinstance(value, bool), (
        f"{field} serialised as {type(value).__name__} ({value!r}); "
        "the frontend types it as a number and will call number methods on it"
    )


class TestProductionRunResponse:
    """Every decimal in the production response, including the nested list."""

    def _build(self) -> ProductionRunResponse:
        return ProductionRunResponse(
            reference_number="PR-1",
            recipe_id=UID,
            recipe_name="Croissant Dough",
            location_id=UID,
            location_name="Production",
            batches=Decimal("4"),
            produced_ingredient_id=UID,
            produced_quantity=Decimal("20.000"),
            unit_cost=Decimal("12.3456"),
            consumed=[{"ingredient_id": UID, "quantity": Decimal("10.000")}],
        )

    def test_top_level_decimals_are_numbers(self) -> None:
        payload = _json(self._build())
        for field in ("batches", "produced_quantity", "unit_cost"):
            _assert_number(payload, field)

    def test_consumed_quantity_is_a_number(self) -> None:
        """The F51 regression: this one used to come out as "10.000"."""
        payload = _json(self._build())
        assert payload["consumed"], "expected at least one consumed line"
        _assert_number(payload["consumed"][0], "quantity")

    def test_values_survive_the_conversion(self) -> None:
        payload = _json(self._build())
        assert payload["batches"] == 4
        assert payload["produced_quantity"] == 20
        assert payload["unit_cost"] == 12.3456
        assert payload["consumed"][0]["quantity"] == 10


class TestTransferItemResponse:
    """The response that took `/admin/transfers` down."""

    def test_quantities_and_cost_are_numbers(self) -> None:
        payload = _json(
            TransferItemResponse(
                id=UID,
                ingredient_id=UID,
                ingredient_name="Croissant Dough",
                quantity_sent=Decimal("5.000"),
                quantity_received=Decimal("4.500"),
                unit="kg",
                unit_cost=Decimal("12.3456"),
            )
        )
        for field in ("quantity_sent", "quantity_received", "unit_cost"):
            _assert_number(payload, field)

    def test_unreceived_quantity_stays_null(self) -> None:
        """Null is meaningful here: sent but not yet received. Not zero."""
        payload = _json(
            TransferItemResponse(
                id=UID,
                ingredient_id=UID,
                ingredient_name="Croissant Dough",
                quantity_sent=Decimal("5.000"),
                quantity_received=None,
                unit="kg",
                unit_cost=Decimal("12.3456"),
            )
        )
        assert payload["quantity_received"] is None


class TestStockRows:
    """The rows behind `/admin/stock`, which carried the same latent fault."""

    def test_location_stock_row(self) -> None:
        payload = _json(
            LocationStockRow(
                location_id=UID,
                location_name="Production",
                ingredient_id=UID,
                ingredient_name="Flour",
                unit="kg",
                quantity=Decimal("106.45"),
                reorder_point=Decimal("20"),
                reorder_quantity=Decimal("25"),
                cost_per_unit=Decimal("2.75"),
                is_produced=False,
                is_low=False,
            )
        )
        for field in (
            "quantity",
            "reorder_point",
            "reorder_quantity",
            "cost_per_unit",
        ):
            _assert_number(payload, field)

    def test_stock_movement_row(self) -> None:
        payload = _json(
            StockMovementRow(
                id=UID,
                ingredient_id=UID,
                ingredient_name="Flour",
                location_id=UID,
                location_name="Production",
                transaction_type="production_consume",
                quantity=Decimal("-10.000"),
                unit="kg",
                balance_after=Decimal("96.450"),
                unit_cost=Decimal("2.75"),
                total_cost=Decimal("27.50"),
                transaction_date="2026-08-28T00:00:00Z",
                performed_by_name=None,
                notes=None,
                reference_number="PR-1",
                order_id=None,
            )
        )
        for field in ("quantity", "balance_after", "unit_cost", "total_cost"):
            _assert_number(payload, field)
