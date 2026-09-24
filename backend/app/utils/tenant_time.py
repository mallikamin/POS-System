"""A restaurant's own calendar day.

Anything that says "today" -- an order number's date, the dashboard, a daily
report -- means the restaurant's day, midnight to midnight where it stands, not
the server's UTC day. Using UTC gave a Faisalabad restaurant open past midnight
yesterday's date on every order from 00:00 to 05:00, and a dashboard that at
2 am showed the previous afternoon as "today" (Danny's UAT D-18, D-30,
2026-09-25). The online-ordering code had its own copy of this; this is the one
the rest of the system shares.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.restaurant_config import RestaurantConfig


def zone(tz_name: str | None) -> ZoneInfo | timezone:
    """The named zone, or UTC when the name is missing or unknown."""
    if not tz_name:
        return timezone.utc
    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        return timezone.utc


async def tenant_timezone(db: AsyncSession, tenant_id: uuid.UUID) -> str:
    """The tenant's configured timezone name, UTC if it has none."""
    name = (
        await db.execute(
            select(RestaurantConfig.timezone).where(RestaurantConfig.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    return name or "UTC"


def _utcnow() -> datetime:
    """The one clock this module reads; tests replace it to stand at 1 am."""
    return datetime.now(timezone.utc)


def local_now(tz_name: str | None) -> datetime:
    return _utcnow().astimezone(zone(tz_name))


def local_today(tz_name: str | None) -> date:
    return local_now(tz_name).date()


def local_day_bounds_utc(tz_name: str | None, local_date: date) -> tuple[datetime, datetime]:
    """[start, end) of one local calendar day, as UTC instants for a WHERE clause."""
    return local_range_bounds_utc(tz_name, local_date, local_date)


def local_range_bounds_utc(
    tz_name: str | None, date_from: date, date_to: date
) -> tuple[datetime, datetime]:
    """[start of date_from, end of date_to) in local days, as UTC instants."""
    tz = zone(tz_name)
    start = datetime.combine(date_from, time.min, tzinfo=tz)
    end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=tz)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


async def tenant_range_utc(
    db: AsyncSession, tenant_id: uuid.UUID, date_from: date, date_to: date
) -> tuple[datetime, datetime]:
    """The tenant's local [date_from, date_to] as a UTC [start, end) for queries."""
    return local_range_bounds_utc(await tenant_timezone(db, tenant_id), date_from, date_to)
