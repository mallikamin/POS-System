"""Locations, per-location stock, production runs, transfers, channels, profit.

Everything a multi-site operator needs that the single-site POS never had.
Every endpoint is tenant-scoped through `current_user.tenant_id` -- a caller can
only ever see and move their own restaurant's stock.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_role
from app.models.user import User
from app.schemas.location import (
    LocationCreate,
    LocationOrderRow,
    LocationResponse,
    LocationStockRow,
    StockMovementRow,
    LocationUpdate,
    ProductionRunRequest,
    ProductionRunResponse,
    ProfitabilityResponse,
    ReorderLevelRequest,
    SalesChannelCreate,
    SalesChannelResponse,
    SalesChannelUpdate,
    StockAdjustRequest,
    TransferCreate,
    TransferItemResponse,
    TransferReceiveRequest,
    TransferResponse,
)
from app.services import (
    location_service,
    production_service,
    stock_service,
    transfer_service,
)
from app.services.stock_service import StockError

router = APIRouter(prefix="/locations", tags=["locations"])


def _bad_request(exc: StockError) -> HTTPException:
    """A StockError is always the caller's problem, never a 500."""
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _transfer_out(transfer) -> TransferResponse:
    """Flatten a transfer for the wire, resolving names the UI needs."""
    return TransferResponse(
        id=transfer.id,
        transfer_number=transfer.transfer_number,
        from_location_id=transfer.from_location_id,
        from_location_name=transfer.from_location.name,
        to_location_id=transfer.to_location_id,
        to_location_name=transfer.to_location.name,
        status=transfer.status,
        notes=transfer.notes,
        sent_at=transfer.sent_at,
        received_at=transfer.received_at,
        created_at=transfer.created_at,
        items=[
            TransferItemResponse(
                id=item.id,
                ingredient_id=item.ingredient_id,
                ingredient_name=item.ingredient.name,
                quantity_sent=item.quantity_sent,
                quantity_received=item.quantity_received,
                unit=item.unit,
                unit_cost=item.unit_cost,
            )
            for item in transfer.items
        ],
    )


# ---------------------------------------------------------------------------
# LOCATIONS
# ---------------------------------------------------------------------------


@router.get("", response_model=list[LocationResponse])
async def list_locations(
    include_inactive: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[LocationResponse]:
    """Every location this restaurant operates."""
    rows = await location_service.list_locations(
        db, current_user.tenant_id, include_inactive
    )
    return [LocationResponse.model_validate(r) for r in rows]


@router.post(
    "",
    response_model=LocationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("admin"))],
)
async def create_location(
    data: LocationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LocationResponse:
    try:
        location = await location_service.create_location(
            db, current_user.tenant_id, data.model_dump()
        )
    except StockError as exc:
        raise _bad_request(exc) from exc
    await db.commit()
    return LocationResponse.model_validate(location)


@router.get("/{location_id}", response_model=LocationResponse)
async def get_location(
    location_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LocationResponse:
    try:
        location = await location_service.get_location(
            db, current_user.tenant_id, location_id
        )
    except StockError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return LocationResponse.model_validate(location)


@router.patch(
    "/{location_id}",
    response_model=LocationResponse,
    dependencies=[Depends(require_role("admin"))],
)
async def update_location(
    location_id: uuid.UUID,
    data: LocationUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LocationResponse:
    try:
        location = await location_service.update_location(
            db, current_user.tenant_id, location_id, data.model_dump(exclude_unset=True)
        )
    except StockError as exc:
        raise _bad_request(exc) from exc
    await db.commit()
    return LocationResponse.model_validate(location)


# ---------------------------------------------------------------------------
# SALES CHANNELS
# ---------------------------------------------------------------------------


@router.get("/channels/all", response_model=list[SalesChannelResponse])
async def list_channels(
    include_inactive: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SalesChannelResponse]:
    """Sales channels and the commission each one charges."""
    rows = await location_service.list_channels(
        db, current_user.tenant_id, include_inactive
    )
    return [SalesChannelResponse.model_validate(r) for r in rows]


@router.post(
    "/channels",
    response_model=SalesChannelResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("admin"))],
)
async def create_channel(
    data: SalesChannelCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SalesChannelResponse:
    try:
        channel = await location_service.create_channel(
            db, current_user.tenant_id, data.model_dump()
        )
    except StockError as exc:
        raise _bad_request(exc) from exc
    await db.commit()
    return SalesChannelResponse.model_validate(channel)


@router.patch(
    "/channels/{channel_id}",
    response_model=SalesChannelResponse,
    dependencies=[Depends(require_role("admin"))],
)
async def update_channel(
    channel_id: uuid.UUID,
    data: SalesChannelUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SalesChannelResponse:
    try:
        channel = await location_service.update_channel(
            db, current_user.tenant_id, channel_id, data.model_dump(exclude_unset=True)
        )
    except StockError as exc:
        raise _bad_request(exc) from exc
    await db.commit()
    return SalesChannelResponse.model_validate(channel)


# ---------------------------------------------------------------------------
# STOCK
# ---------------------------------------------------------------------------


@router.get("/stock/position", response_model=list[LocationStockRow])
async def stock_position(
    location_id: uuid.UUID | None = Query(None),
    low_only: bool = Query(False, description="Only at-or-below reorder point"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[LocationStockRow]:
    """Stock on hand, per location. `low_only=true` is the low-stock alert."""
    rows = await stock_service.get_location_stock(
        db, current_user.tenant_id, location_id, low_only
    )
    return [LocationStockRow(**r) for r in rows]


@router.get("/stock/movements", response_model=list[StockMovementRow])
async def stock_movements(
    ingredient_id: uuid.UUID | None = Query(None),
    location_id: uuid.UUID | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[StockMovementRow]:
    """Why the stock figure is what it is: every movement, newest first.

    🔴 The ledger behind this has been written since the module shipped and was
    unreadable until 2026-08-27 -- no endpoint, no screen. The mandatory reason
    on a manual adjustment went into the database and could never be seen again,
    which made "stock never changes without an explanation" a claim the customer
    had to take on trust. This is the door.

    Deliberately readable by any signed-in user, not just admin and manager,
    unlike the adjust endpoint next to it. Making a change is privileged;
    inspecting why the number moved is the opposite of privileged, and a history
    that only managers can see does not settle an argument on the floor.
    """
    rows = await stock_service.get_stock_movements(
        db,
        current_user.tenant_id,
        ingredient_id=ingredient_id,
        location_id=location_id,
        limit=limit,
        offset=offset,
    )
    return [StockMovementRow(**r) for r in rows]


@router.post(
    "/stock/adjust",
    response_model=LocationStockRow,
    dependencies=[Depends(require_role("admin", "manager"))],
)
async def adjust_stock(
    data: StockAdjustRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LocationStockRow:
    """An authorised manual correction. The reason is mandatory and recorded."""
    try:
        txn = await stock_service.move_stock(
            db,
            tenant_id=current_user.tenant_id,
            ingredient_id=data.ingredient_id,
            quantity_delta=data.quantity_delta,
            transaction_type="adjustment",
            location_id=data.location_id,
            performed_by=current_user.id,
            notes=data.reason,
        )
    except StockError as exc:
        raise _bad_request(exc) from exc
    await db.commit()

    rows = await stock_service.get_location_stock(
        db, current_user.tenant_id, txn.location_id
    )
    row = next((r for r in rows if r["ingredient_id"] == data.ingredient_id), None)
    if row is None:  # pragma: no cover -- the row was just written
        raise HTTPException(status_code=500, detail="Stock row vanished after write.")
    return LocationStockRow(**row)


@router.post(
    "/stock/reorder-level",
    response_model=LocationStockRow,
    dependencies=[Depends(require_role("admin", "manager"))],
)
async def set_reorder_level(
    data: ReorderLevelRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LocationStockRow:
    """Set the low-stock threshold for one ingredient at one location."""
    try:
        await stock_service.resolve_location(
            db, current_user.tenant_id, data.location_id
        )
        row = await stock_service.get_or_create_stock_row(
            db, current_user.tenant_id, data.location_id, data.ingredient_id
        )
    except StockError as exc:
        raise _bad_request(exc) from exc

    row.reorder_point = data.reorder_point
    row.reorder_quantity = data.reorder_quantity
    await db.commit()

    rows = await stock_service.get_location_stock(
        db, current_user.tenant_id, data.location_id
    )
    out = next((r for r in rows if r["ingredient_id"] == data.ingredient_id), None)
    if out is None:  # pragma: no cover
        raise HTTPException(status_code=500, detail="Stock row vanished after write.")
    return LocationStockRow(**out)


# ---------------------------------------------------------------------------
# PRODUCTION
# ---------------------------------------------------------------------------


@router.post(
    "/production/run",
    response_model=ProductionRunResponse,
    dependencies=[Depends(require_role("admin", "manager"))],
)
async def run_production(
    data: ProductionRunRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProductionRunResponse:
    """Make a batch: consume the raw ingredients, add the produced stock."""
    try:
        result = await production_service.run_production(
            db,
            tenant_id=current_user.tenant_id,
            recipe_id=data.recipe_id,
            batches=data.batches,
            location_id=data.location_id,
            performed_by=current_user.id,
            reference_number=data.reference_number,
        )
    except StockError as exc:
        raise _bad_request(exc) from exc
    await db.commit()
    return ProductionRunResponse(**result)


# ---------------------------------------------------------------------------
# TRANSFERS
# ---------------------------------------------------------------------------


@router.get("/transfers/all", response_model=list[TransferResponse])
async def list_transfers(
    status_filter: str | None = Query(None, alias="status"),
    location_id: uuid.UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TransferResponse]:
    rows = await transfer_service.list_transfers(
        db, current_user.tenant_id, status_filter, location_id
    )
    return [_transfer_out(t) for t in rows]


@router.post(
    "/transfers",
    response_model=TransferResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("admin", "manager"))],
)
async def create_transfer(
    data: TransferCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransferResponse:
    """Draft a transfer. Nothing moves until it is sent."""
    try:
        transfer = await transfer_service.create_transfer(
            db,
            tenant_id=current_user.tenant_id,
            from_location_id=data.from_location_id,
            to_location_id=data.to_location_id,
            lines=[line.model_dump() for line in data.lines],
            created_by=current_user.id,
            notes=data.notes,
        )
    except StockError as exc:
        raise _bad_request(exc) from exc
    await db.commit()
    return _transfer_out(transfer)


@router.get("/transfers/{transfer_id}", response_model=TransferResponse)
async def get_transfer(
    transfer_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransferResponse:
    try:
        transfer = await transfer_service.get_transfer(
            db, current_user.tenant_id, transfer_id
        )
    except StockError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _transfer_out(transfer)


@router.post(
    "/transfers/{transfer_id}/send",
    response_model=TransferResponse,
    dependencies=[Depends(require_role("admin", "manager"))],
)
async def send_transfer(
    transfer_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransferResponse:
    """Stock leaves the source now; it arrives only when received."""
    try:
        transfer = await transfer_service.send_transfer(
            db,
            tenant_id=current_user.tenant_id,
            transfer_id=transfer_id,
            performed_by=current_user.id,
        )
    except StockError as exc:
        raise _bad_request(exc) from exc
    await db.commit()
    return _transfer_out(transfer)


@router.post(
    "/transfers/{transfer_id}/receive",
    response_model=TransferResponse,
    dependencies=[Depends(require_role("admin", "manager"))],
)
async def receive_transfer(
    transfer_id: uuid.UUID,
    data: TransferReceiveRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransferResponse:
    """Confirm arrival. Omitted lines are received in full."""
    received = {
        line.item_id: line.quantity_received for line in (data.lines if data else [])
    }
    try:
        transfer = await transfer_service.receive_transfer(
            db,
            tenant_id=current_user.tenant_id,
            transfer_id=transfer_id,
            received=received,
            performed_by=current_user.id,
        )
    except StockError as exc:
        raise _bad_request(exc) from exc
    await db.commit()
    return _transfer_out(transfer)


@router.post(
    "/transfers/{transfer_id}/cancel",
    response_model=TransferResponse,
    dependencies=[Depends(require_role("admin", "manager"))],
)
async def cancel_transfer(
    transfer_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransferResponse:
    """Cancel. If it was already sent, the stock returns to the source."""
    try:
        transfer = await transfer_service.cancel_transfer(
            db,
            tenant_id=current_user.tenant_id,
            transfer_id=transfer_id,
            performed_by=current_user.id,
        )
    except StockError as exc:
        raise _bad_request(exc) from exc
    await db.commit()
    return _transfer_out(transfer)


# ---------------------------------------------------------------------------
# PROFITABILITY
# ---------------------------------------------------------------------------


@router.get("/{location_id}/orders", response_model=list[LocationOrderRow])
async def location_orders(
    location_id: uuid.UUID,
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[LocationOrderRow]:
    """Invoiceable sales at one location, newest first.

    Feeds the tax-invoice screen. Deliberately its own endpoint rather than a
    filter bolted onto the main orders list, which a live restaurant depends on.
    """
    from sqlalchemy import select

    from app.models.location import SalesChannel
    from app.models.order import Order

    await location_service.get_location(db, current_user.tenant_id, location_id)

    rows = (
        await db.execute(
            select(Order, SalesChannel.name)
            .join(SalesChannel, SalesChannel.id == Order.sales_channel_id, isouter=True)
            .where(
                Order.tenant_id == current_user.tenant_id,
                Order.location_id == location_id,
                Order.status.notin_(["draft", "voided"]),
            )
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
    ).all()

    return [
        LocationOrderRow(
            id=order.id,
            order_number=order.order_number,
            order_type=order.order_type,
            status=order.status,
            payment_status=order.payment_status,
            total_minor=order.total,
            channel_name=channel_name,
            customer_name=order.customer_name,
            created_at=order.created_at,
        )
        for order, channel_name in rows
    ]


@router.get("/reports/profitability", response_model=ProfitabilityResponse)
async def profitability(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfitabilityResponse:
    """Net profit after product cost AND channel commission, per channel and site."""
    data = await location_service.profitability_report(
        db, current_user.tenant_id, date_from, date_to
    )
    return ProfitabilityResponse(**data)
