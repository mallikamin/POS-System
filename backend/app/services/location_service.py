"""Locations and sales channels: management, plus profitability by both.

The profitability half is the reason this client came to us. Martin's scope doc,
Section 8, calls it out as "a key customized requirement": profit is not
`selling price - product cost`, it is

    selling price - product cost - channel commission

because a Talabat order and a direct WhatsApp order for the identical basket do
not earn the same money. Reporting that treats them as equal hides exactly the
decision he is trying to make.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import Recipe
from app.models.location import Location, SalesChannel
from app.models.order import Order, OrderItem
from app.services.stock_service import StockError

# Orders that never became real revenue must not appear in profit reporting.
# One definition, used everywhere in this module.
REVENUE_STATUSES = ("completed", "served", "ready", "in_kitchen", "confirmed")


# ---------------------------------------------------------------------------
# LOCATIONS
# ---------------------------------------------------------------------------


async def list_locations(
    db: AsyncSession, tenant_id: uuid.UUID, include_inactive: bool = False
) -> list[Location]:
    stmt = select(Location).where(Location.tenant_id == tenant_id)
    if not include_inactive:
        stmt = stmt.where(Location.is_active == True)  # noqa: E712
    return list((await db.execute(stmt.order_by(Location.name))).scalars().all())


async def get_location(
    db: AsyncSession, tenant_id: uuid.UUID, location_id: uuid.UUID
) -> Location:
    result = await db.execute(
        select(Location).where(
            Location.id == location_id, Location.tenant_id == tenant_id
        )
    )
    location = result.scalar_one_or_none()
    if location is None:
        raise StockError("No such location for this restaurant.")
    return location


async def create_location(
    db: AsyncSession, tenant_id: uuid.UUID, data: dict
) -> Location:
    existing = await db.execute(
        select(Location.id).where(
            Location.tenant_id == tenant_id, Location.code == data["code"]
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise StockError(f"A location with code {data['code']!r} already exists.")

    location = Location(tenant_id=tenant_id, **data)
    db.add(location)
    await db.flush()
    if location.is_default:
        await _clear_other_defaults(db, tenant_id, location.id)
    return location


async def update_location(
    db: AsyncSession, tenant_id: uuid.UUID, location_id: uuid.UUID, data: dict
) -> Location:
    location = await get_location(db, tenant_id, location_id)
    for key, value in data.items():
        if value is not None:
            setattr(location, key, value)
    await db.flush()
    if location.is_default:
        await _clear_other_defaults(db, tenant_id, location.id)
    return location


async def _clear_other_defaults(
    db: AsyncSession, tenant_id: uuid.UUID, keep_id: uuid.UUID
) -> None:
    """Exactly one default per tenant. Setting a new one clears the old."""
    result = await db.execute(
        select(Location).where(
            Location.tenant_id == tenant_id,
            Location.is_default == True,  # noqa: E712
            Location.id != keep_id,
        )
    )
    for other in result.scalars().all():
        other.is_default = False
    await db.flush()


# ---------------------------------------------------------------------------
# SALES CHANNELS
# ---------------------------------------------------------------------------


async def list_channels(
    db: AsyncSession, tenant_id: uuid.UUID, include_inactive: bool = False
) -> list[SalesChannel]:
    stmt = select(SalesChannel).where(SalesChannel.tenant_id == tenant_id)
    if not include_inactive:
        stmt = stmt.where(SalesChannel.is_active == True)  # noqa: E712
    return list((await db.execute(stmt.order_by(SalesChannel.name))).scalars().all())


async def get_channel(
    db: AsyncSession, tenant_id: uuid.UUID, channel_id: uuid.UUID
) -> SalesChannel:
    result = await db.execute(
        select(SalesChannel).where(
            SalesChannel.id == channel_id, SalesChannel.tenant_id == tenant_id
        )
    )
    channel = result.scalar_one_or_none()
    if channel is None:
        raise StockError("No such sales channel for this restaurant.")
    return channel


async def create_channel(
    db: AsyncSession, tenant_id: uuid.UUID, data: dict
) -> SalesChannel:
    existing = await db.execute(
        select(SalesChannel.id).where(
            SalesChannel.tenant_id == tenant_id, SalesChannel.code == data["code"]
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise StockError(f"A channel with code {data['code']!r} already exists.")
    channel = SalesChannel(tenant_id=tenant_id, **data)
    db.add(channel)
    await db.flush()
    return channel


async def update_channel(
    db: AsyncSession, tenant_id: uuid.UUID, channel_id: uuid.UUID, data: dict
) -> SalesChannel:
    channel = await get_channel(db, tenant_id, channel_id)
    for key, value in data.items():
        if value is not None:
            setattr(channel, key, value)
    await db.flush()
    return channel


def commission_for(channel: SalesChannel | None, order_total_minor: int) -> int:
    """What this channel charges on an order of this size, in minor units.

    Integer maths throughout: bps * minor // 10000. Rounding down by a fraction
    of a fils is deliberate and consistent -- never a float.
    """
    if channel is None:
        return 0
    # Column defaults are applied by the database at flush, so a freshly
    # constructed (not yet flushed) channel still has None here. Coerce rather
    # than crash: a missing rate means no charge, not a broken report.
    commission_bps = channel.commission_bps or 0
    fixed_fee = channel.fixed_fee_minor or 0
    return (order_total_minor * commission_bps) // 10000 + fixed_fee


async def snapshot_commission(
    db: AsyncSession, tenant_id: uuid.UUID, order: Order
) -> int:
    """Freeze the commission onto the order at the rate in force right now.

    Read live at report time instead, and last month's profit would silently
    change the day a rate is renegotiated. Reports must not move under you.
    """
    if order.sales_channel_id is None:
        order.channel_commission_minor = 0
        return 0
    channel = await get_channel(db, tenant_id, order.sales_channel_id)
    amount = commission_for(channel, order.total)
    order.channel_commission_minor = amount
    await db.flush()
    return amount


# ---------------------------------------------------------------------------
# PROFITABILITY
# ---------------------------------------------------------------------------


async def _product_cost_minor(
    db: AsyncSession, tenant_id: uuid.UUID, order_ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    """Recipe cost of goods sold, per order, in minor units.

    Cost comes from the active recipe's `cost_per_serving`, which for a recipe
    built on sub-recipes is already the fully rolled-up chain cost. An item with
    no recipe contributes zero cost -- visible as an unusually high margin,
    which is the correct prompt to go and build its recipe.
    """
    if not order_ids:
        return {}

    rows = (
        await db.execute(
            select(
                OrderItem.order_id,
                OrderItem.quantity,
                Recipe.cost_per_serving,
            )
            .join(
                Recipe,
                (Recipe.menu_item_id == OrderItem.menu_item_id)
                & (Recipe.tenant_id == tenant_id)
                & (Recipe.is_active == True),  # noqa: E712
                isouter=True,
            )
            .where(OrderItem.order_id.in_(order_ids))
        )
    ).all()

    totals: dict[uuid.UUID, int] = {}
    for order_id, quantity, cost_per_serving in rows:
        if cost_per_serving is None:
            continue
        # `cost_per_serving` is ALREADY in minor units, the same unit as
        # `Order.total`, so there is no conversion to do. It is stored as a
        # Decimal only to keep sub-unit precision while costs are summed from
        # ingredient quantities. Multiplying by 100 here overstated cost by
        # 100x and produced margins of several thousand percent; caught by the
        # live API verification, not by the unit tests, because the tests had
        # the same wrong assumption baked into their fixture.
        line = Decimal(str(cost_per_serving)) * Decimal(int(quantity))
        totals[order_id] = totals.get(order_id, 0) + int(line)
    return totals


async def profitability_report(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict:
    """Net profit broken down by sales channel and by location.

    net = revenue - product cost - channel commission
    """
    stmt = select(Order).where(
        Order.tenant_id == tenant_id, Order.status.in_(REVENUE_STATUSES)
    )
    if date_from:
        stmt = stmt.where(func.cast(Order.created_at, Date) >= date_from)
    if date_to:
        stmt = stmt.where(func.cast(Order.created_at, Date) <= date_to)

    orders = list((await db.execute(stmt)).scalars().all())
    costs = await _product_cost_minor(db, tenant_id, [o.id for o in orders])

    channels = {c.id: c for c in await list_channels(db, tenant_id, include_inactive=True)}
    locations = {loc.id: loc for loc in await list_locations(db, tenant_id, include_inactive=True)}

    def blank(name: str) -> dict:
        return {
            "name": name,
            "orders": 0,
            "revenue_minor": 0,
            "product_cost_minor": 0,
            "commission_minor": 0,
            "net_profit_minor": 0,
        }

    by_channel: dict[str, dict] = {}
    by_location: dict[str, dict] = {}
    totals = blank("All")

    for order in orders:
        cost = costs.get(order.id, 0)
        # Prefer the snapshot; fall back to the live rate for orders written
        # before the snapshot existed, so historical rows still report sensibly.
        commission = order.channel_commission_minor or commission_for(
            channels.get(order.sales_channel_id), order.total
        )
        net = order.total - cost - commission

        channel_name = (
            channels[order.sales_channel_id].name
            if order.sales_channel_id in channels
            else "Direct / unassigned"
        )
        location_name = (
            locations[order.location_id].name
            if order.location_id in locations
            else "Unassigned"
        )

        for bucket, key, label in (
            (by_channel, channel_name, channel_name),
            (by_location, location_name, location_name),
        ):
            entry = bucket.setdefault(key, blank(label))
            entry["orders"] += 1
            entry["revenue_minor"] += order.total
            entry["product_cost_minor"] += cost
            entry["commission_minor"] += commission
            entry["net_profit_minor"] += net

        totals["orders"] += 1
        totals["revenue_minor"] += order.total
        totals["product_cost_minor"] += cost
        totals["commission_minor"] += commission
        totals["net_profit_minor"] += net

    def margin(entry: dict) -> dict:
        revenue = entry["revenue_minor"]
        entry["net_margin_pct"] = (
            round(entry["net_profit_minor"] * 100 / revenue, 2) if revenue else 0.0
        )
        return entry

    return {
        "totals": margin(totals),
        "by_channel": [margin(e) for e in sorted(
            by_channel.values(), key=lambda e: -e["revenue_minor"]
        )],
        "by_location": [margin(e) for e in sorted(
            by_location.values(), key=lambda e: -e["revenue_minor"]
        )],
    }
