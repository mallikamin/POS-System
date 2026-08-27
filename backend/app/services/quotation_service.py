"""Quotations: offer a price, then win or lose the business.

    draft -> sent -> accepted -> converted (an order exists)
                  -> declined
                  (and `expired` once valid_until has passed)

Decisions worth knowing
-----------------------
* **Expiry is derived, never stored.** A quotation expires because a date
  passed, not because a job ran. A stored flag would be wrong in the window
  between the date and the next sweep, and would need a scheduler to be right
  at all.
* **A quotation touches nothing else until it is converted.** No stock, no
  kitchen, no takings. Conversion is one explicit step that creates a real
  order through the ordinary order service, and records which order came from
  which quotation.
* 🔴 **Money is INTEGER minor units**, matching `orders` and the tax invoice.
  Prices are VAT-INCLUSIVE, so the VAT shown on the document is backed OUT of
  the total using the same helper the tax invoice uses -- adding it on top
  would overstate the tax on every document.
* **Totals are derived from the lines** on every change, so the header cannot
  disagree with the body.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.menu import MenuItem
from app.models.quotation import Quotation, QuotationItem
from app.models.restaurant_config import RestaurantConfig
from app.services.tax_invoice_service import split_vat_inclusive

logger = logging.getLogger(__name__)

# How long an offer stands when nobody says otherwise.
DEFAULT_VALIDITY_DAYS = 30


class QuotationError(ValueError):
    """A quotation action that cannot be performed as asked."""


def is_expired(quotation: Quotation, today: date | None = None) -> bool:
    """Past its date and not yet decided.

    An accepted or converted quotation is NOT expired, whatever the date says:
    the offer was taken up while it stood, and re-labelling it later would
    rewrite history.
    """
    if quotation.status in ("accepted", "converted", "declined"):
        return False
    return quotation.valid_until < (today or datetime.now(timezone.utc).date())


def display_status(quotation: Quotation, today: date | None = None) -> str:
    """What to show a human. `expired` is a view of the data, not a column."""
    if is_expired(quotation, today):
        return "expired"
    return quotation.status


async def _next_quote_number(db: AsyncSession, tenant_id: uuid.UUID) -> str:
    """Sequential per tenant, date-stamped: QUO-260826-003."""
    today = datetime.now(timezone.utc)
    prefix = f"QUO-{today:%y%m%d}-"
    count = (
        await db.execute(
            select(func.count(Quotation.id)).where(
                Quotation.tenant_id == tenant_id,
                Quotation.quote_number.like(f"{prefix}%"),
            )
        )
    ).scalar_one()
    return f"{prefix}{count + 1:03d}"


def _options():
    return (
        selectinload(Quotation.items),
        selectinload(Quotation.location),
    )


async def get_quotation(
    db: AsyncSession, tenant_id: uuid.UUID, quotation_id: uuid.UUID
) -> Quotation:
    quotation = (
        await db.execute(
            select(Quotation)
            .where(Quotation.id == quotation_id, Quotation.tenant_id == tenant_id)
            .options(*_options())
            # Same reason as the purchase order: without this a re-read after a
            # write returns the identity-map copy with its stale collections.
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if quotation is None:
        raise QuotationError("No such quotation for this restaurant.")
    return quotation


async def list_quotations(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    status: str | None = None,
    limit: int = 200,
) -> list[Quotation]:
    stmt = (
        select(Quotation)
        .where(Quotation.tenant_id == tenant_id)
        .options(*_options())
        .order_by(Quotation.created_at.desc())
        .limit(limit)
    )
    if status and status != "expired":
        stmt = stmt.where(Quotation.status == status)

    rows = list((await db.execute(stmt)).scalars().all())
    if status == "expired":
        # Filtered in Python because expiry is derived. Doing it in SQL would
        # mean duplicating the "accepted quotations never expire" rule in a
        # second place, where it would eventually diverge.
        rows = [q for q in rows if is_expired(q)]
    return rows


async def _recalculate(db: AsyncSession, quotation: Quotation) -> None:
    """Rebuild the totals from the lines. The header never disagrees."""
    subtotal = 0
    for item in quotation.items:
        item.line_total_minor = int(item.unit_price_minor) * int(item.quantity)
        subtotal += item.line_total_minor

    gross = max(0, subtotal - int(quotation.discount_minor or 0))
    # Prices INCLUDE VAT, so back it out. Never add it on top.
    _net, vat = split_vat_inclusive(gross, int(quotation.tax_rate_bps or 0))

    quotation.subtotal_minor = subtotal
    quotation.tax_minor = vat
    quotation.total_minor = gross
    await db.flush()


async def _resolve_lines(
    db: AsyncSession, tenant_id: uuid.UUID, lines: list[dict]
) -> list[dict]:
    """Turn requested lines into snapshotted ones.

    A line naming a menu item takes that item's current name and price unless
    the caller overrides them; a free-text line ("delivery to Abu Dhabi") needs
    both supplied. Either way the values are copied onto the quotation, because
    the offer must not change when the menu does.
    """
    resolved: list[dict] = []
    for position, line in enumerate(lines):
        quantity = int(line.get("quantity") or 0)
        if quantity <= 0:
            raise QuotationError("A quotation line needs a quantity of at least one.")

        name = (line.get("name") or "").strip()
        price = line.get("unit_price_minor")
        menu_item_id = line.get("menu_item_id")

        if menu_item_id is not None:
            item = (
                await db.execute(
                    select(MenuItem).where(
                        MenuItem.id == menu_item_id,
                        MenuItem.tenant_id == tenant_id,
                    )
                )
            ).scalar_one_or_none()
            if item is None:
                raise QuotationError("No such menu item for this restaurant.")
            name = name or item.name
            price = int(item.price) if price is None else int(price)

        if not name:
            raise QuotationError("Every quotation line needs a description.")
        if price is None:
            raise QuotationError(f"{name} needs a price.")
        if int(price) < 0:
            raise QuotationError("A price cannot be negative.")

        resolved.append(
            {
                "menu_item_id": menu_item_id,
                "name": name,
                "description": line.get("description"),
                "quantity": quantity,
                "unit_price_minor": int(price),
                "display_order": position,
            }
        )
    return resolved


async def create_quotation(
    db: AsyncSession, *, tenant_id: uuid.UUID, data: dict, created_by=None
) -> Quotation:
    lines = data.get("lines") or []
    if not lines:
        raise QuotationError("A quotation needs at least one line.")

    config = (
        await db.execute(
            select(RestaurantConfig).where(RestaurantConfig.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()

    # F48: "today" is the tenant's calendar day, not UTC's. A quotation raised
    # at 22:40 UTC was dated the 27th while the buyer in Dubai was on the 28th.
    try:
        zone: ZoneInfo | timezone = ZoneInfo((config.timezone if config else None) or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        zone = timezone.utc
    today = datetime.now(timezone.utc).astimezone(zone).date()
    valid_until = data.get("valid_until") or (
        today + timedelta(days=DEFAULT_VALIDITY_DAYS)
    )
    if valid_until < today:
        raise QuotationError("A quotation cannot expire before it is issued.")

    quotation = Quotation(
        tenant_id=tenant_id,
        quote_number=await _next_quote_number(db, tenant_id),
        location_id=data.get("location_id"),
        customer_id=data.get("customer_id"),
        customer_name=(data.get("customer_name") or "").strip() or "Customer",
        customer_phone=data.get("customer_phone"),
        customer_email=data.get("customer_email"),
        customer_address=data.get("customer_address"),
        customer_trn=data.get("customer_trn"),
        status="draft",
        issue_date=today,
        valid_until=valid_until,
        tax_rate_bps=(
            data["tax_rate_bps"]
            if data.get("tax_rate_bps") is not None
            else ((config.default_tax_rate if config else 0) or 0)
        ),
        discount_minor=int(data.get("discount_minor") or 0),
        notes=data.get("notes"),
        terms=data.get("terms"),
        created_by=created_by,
    )
    db.add(quotation)
    # Flush before the children reference quotation.id.
    await db.flush()

    for line in await _resolve_lines(db, tenant_id, lines):
        db.add(QuotationItem(tenant_id=tenant_id, quotation_id=quotation.id, **line))
    await db.flush()

    quotation = await get_quotation(db, tenant_id, quotation.id)
    await _recalculate(db, quotation)
    return await get_quotation(db, tenant_id, quotation.id)


async def update_quotation(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    quotation_id: uuid.UUID,
    data: dict,
) -> Quotation:
    """Edit a quotation that has not been decided yet.

    A sent quotation CAN still be edited, unlike a purchase order, and the
    difference is deliberate: re-quoting is a normal part of negotiating, and
    the customer gets a fresh document when it is re-sent. What cannot be
    edited is one that has been accepted or converted -- at that point it is
    the record of an agreement.
    """
    quotation = await get_quotation(db, tenant_id, quotation_id)
    if quotation.status in ("accepted", "converted"):
        raise QuotationError(
            f"A {quotation.status} quotation cannot be changed. Raise a new one."
        )

    lines = data.pop("lines", None)
    for field, value in data.items():
        setattr(quotation, field, value)

    if quotation.valid_until < quotation.issue_date:
        raise QuotationError("A quotation cannot expire before it is issued.")

    if lines is not None:
        if not lines:
            raise QuotationError("A quotation needs at least one line.")
        for item in list(quotation.items):
            await db.delete(item)
        await db.flush()
        for line in await _resolve_lines(db, tenant_id, lines):
            db.add(
                QuotationItem(tenant_id=tenant_id, quotation_id=quotation.id, **line)
            )
        await db.flush()

    quotation = await get_quotation(db, tenant_id, quotation_id)
    await _recalculate(db, quotation)
    return await get_quotation(db, tenant_id, quotation_id)


async def mark_sent(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    quotation_id: uuid.UUID,
    sent_to_email: str | None = None,
    email_delivered: bool = False,
    email_error: str | None = None,
) -> Quotation:
    """Record that the offer went out. A failed email does not undo it."""
    quotation = await get_quotation(db, tenant_id, quotation_id)
    if quotation.status in ("accepted", "converted", "declined"):
        raise QuotationError(
            f"A {quotation.status} quotation cannot be sent again."
        )
    if not quotation.items:
        raise QuotationError("A quotation with no lines cannot be sent.")

    quotation.status = "sent"
    quotation.sent_at = quotation.sent_at or datetime.now(timezone.utc)
    if sent_to_email:
        quotation.sent_to_email = sent_to_email
    if email_delivered:
        quotation.email_send_count = (quotation.email_send_count or 0) + 1
        quotation.last_email_error = None
    elif email_error:
        quotation.last_email_error = email_error[:1000]

    await db.flush()
    return await get_quotation(db, tenant_id, quotation_id)


async def decide(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    quotation_id: uuid.UUID,
    accepted: bool,
    reason: str | None = None,
) -> Quotation:
    """The customer said yes or no.

    An expired quotation can still be accepted, and that is on purpose: when a
    customer comes back a week late and the seller is happy to honour the
    price, the system should not be the thing that stops them. What it must not
    do is pretend the date did not pass, so the acceptance is stamped and the
    document keeps its original validity date.
    """
    quotation = await get_quotation(db, tenant_id, quotation_id)
    if quotation.status == "converted":
        raise QuotationError(
            "This quotation has already become an order and cannot be re-decided."
        )
    if quotation.status == "draft":
        raise QuotationError(
            "This quotation has not been sent yet, so there is nothing to accept."
        )

    quotation.status = "accepted" if accepted else "declined"
    quotation.decided_at = datetime.now(timezone.utc)
    quotation.decline_reason = None if accepted else (reason or None)
    await db.flush()
    return await get_quotation(db, tenant_id, quotation_id)


async def convert_to_order(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    quotation_id: uuid.UUID,
    created_by=None,
) -> tuple[Quotation, object]:
    """Turn an accepted quotation into a real order.

    One way, once. The order is created through the ordinary order service, so
    it is indistinguishable from any other order downstream -- kitchen routing,
    stock deduction, tax invoice and profitability all work on it without
    knowing where it came from. The link back is kept for the one question
    worth asking later: what did we quote for this?

    Lines that are not menu items (delivery, packaging) cannot be sent to a
    kitchen and are refused rather than silently dropped, because dropping them
    would quietly change the price the customer agreed to.
    """
    from app.schemas.order import OrderCreate, OrderItemCreate
    from app.services import order_service

    quotation = await get_quotation(db, tenant_id, quotation_id)
    if quotation.status == "converted":
        raise QuotationError("This quotation has already become an order.")
    if quotation.status != "accepted":
        raise QuotationError(
            "Only an accepted quotation can become an order. Mark it accepted "
            "first."
        )

    free_text = [item.name for item in quotation.items if item.menu_item_id is None]
    if free_text:
        raise QuotationError(
            "These lines are not menu items and cannot be turned into an order: "
            + ", ".join(free_text)
            + ". Remove them, or add them to the menu first."
        )

    if created_by is None:
        raise QuotationError(
            "Converting a quotation has to be attributable to a user."
        )

    # The order carries the QUOTED prices, not today's menu prices. That is the
    # whole point of a quotation: the customer accepted a number, and the order
    # has to be for that number even if the menu moved in between.
    order = await order_service.create_order(
        db,
        tenant_id,
        created_by,
        OrderCreate(
            order_type="takeaway",
            customer_name=quotation.customer_name,
            customer_phone=quotation.customer_phone,
            notes=f"From quotation {quotation.quote_number}",
            items=[
                OrderItemCreate(
                    menu_item_id=item.menu_item_id,
                    name=item.name,
                    quantity=item.quantity,
                    unit_price=item.unit_price_minor,
                    modifiers=[],
                )
                for item in quotation.items
            ],
        ),
    )

    quotation.status = "converted"
    quotation.converted_order_id = order.id
    quotation.converted_at = datetime.now(timezone.utc)
    await db.flush()
    return await get_quotation(db, tenant_id, quotation_id), order
