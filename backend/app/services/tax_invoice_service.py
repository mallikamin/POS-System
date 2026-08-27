"""Assemble a UAE-compliant A4 VAT tax invoice from an order.

Why this is not just the thermal receipt with a different stylesheet
--------------------------------------------------------------------
A tax invoice is a legal document. It must carry the supplier's registered
legal name and Tax Registration Number, a sequential invoice number, and VAT
shown as its own figure rather than folded into the price. The thermal ticket
carries none of that and should not: it is a kitchen and customer docket.

The one piece of real arithmetic here
-------------------------------------
This POS stores VAT-INCLUSIVE prices (`restaurant_configs.tax_inclusive`), which
is normal for UAE retail: the shelf price is what the customer pays. A tax
invoice must nonetheless show the net and the VAT separately, so the VAT has to
be backed OUT of the gross rather than added on top:

    net = gross * 10000 / (10000 + rate_bps)
    vat = gross - net

Adding 5% to a price that already includes 5% would overstate the tax by about
0.24% of the invoice, on every single document. Doing it as integer arithmetic
in minor units keeps the lines summing exactly to the total, which a float would
not guarantee.
"""

from __future__ import annotations

import uuid
from datetime import timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.customer import Customer
from app.models.location import Location, TaxInvoiceSequence
from app.models.order import Order, OrderItem
from app.models.restaurant_config import RestaurantConfig
from app.models.tenant import Tenant
from app.schemas.tax_invoice import (
    TaxInvoiceData,
    TaxInvoiceLine,
    TaxInvoiceParty,
)


class TaxInvoiceError(ValueError):
    """This order cannot be issued as a tax invoice."""


def split_vat_inclusive(gross_minor: int, rate_bps: int) -> tuple[int, int]:
    """Back the VAT out of a VAT-inclusive gross amount.

    Returns `(net_minor, vat_minor)`. Integer maths, and the two always sum
    back to `gross_minor` exactly because the VAT is the remainder rather than
    a second rounded calculation.
    """
    if rate_bps <= 0:
        return gross_minor, 0
    net = (gross_minor * 10000) // (10000 + rate_bps)
    return net, gross_minor - net


def add_vat_exclusive(net_minor: int, rate_bps: int) -> tuple[int, int]:
    """VAT added on top of a net price, for tenants not pricing inclusive."""
    if rate_bps <= 0:
        return net_minor, 0
    vat = (net_minor * rate_bps) // 10000
    return net_minor, vat


async def _next_invoice_number(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    order: Order,
    location: Location | None,
) -> str:
    """Reserve this order's tax invoice number, once, and remember it.

    The number this returns must never change for a given order, and no two
    orders in a tenant may ever share one. The previous implementation derived
    it from a live COUNT of the tenant's orders, which satisfied neither: seven
    separate sales all read `FZD-00007`, and every number shifted upward as new
    orders arrived (F33). A UAE tax invoice has to carry a sequential number
    that uniquely identifies the document.

    Already issued, so return what was issued. Regenerating the same invoice
    tomorrow, after fifty more sales, must reproduce the identical document.
    """
    if order.tax_invoice_number:
        return order.tax_invoice_number

    prefix = (location.invoice_prefix if location else "INV") or "INV"

    # SELECT ... FOR UPDATE serialises two tills issuing at the same instant.
    # Without the lock both read the same next_value and the unique constraint
    # on (tenant_id, tax_invoice_number) turns a duplicate into a 500 at the
    # counter, which is a worse failure than waiting a few milliseconds.
    seq = (
        await db.execute(
            select(TaxInvoiceSequence)
            .where(
                TaxInvoiceSequence.tenant_id == tenant_id,
                TaxInvoiceSequence.prefix == prefix,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()

    if seq is None:
        # First ever invoice on this series. Two concurrent first-issues race
        # here, so the loser catches the unique violation and re-reads the row
        # the winner committed, inside a SAVEPOINT to keep the outer
        # transaction alive. Same shape as the order-number retry.
        seq = TaxInvoiceSequence(tenant_id=tenant_id, prefix=prefix, next_value=1)
        try:
            async with db.begin_nested():
                db.add(seq)
                await db.flush()
        except IntegrityError:
            seq = (
                await db.execute(
                    select(TaxInvoiceSequence)
                    .where(
                        TaxInvoiceSequence.tenant_id == tenant_id,
                        TaxInvoiceSequence.prefix == prefix,
                    )
                    .with_for_update()
                )
            ).scalar_one()

    number = seq.next_value
    seq.next_value = number + 1
    issued = f"{prefix}-{number:05d}"
    order.tax_invoice_number = issued
    await db.flush()
    return issued


async def get_tax_invoice(
    db: AsyncSession, tenant_id: uuid.UUID, order_id: uuid.UUID
) -> TaxInvoiceData:
    order = (
        await db.execute(
            select(Order)
            .options(selectinload(Order.items).selectinload(OrderItem.modifiers))
            .where(Order.id == order_id, Order.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if order is None:
        raise TaxInvoiceError("Order not found.")
    if order.status in ("draft", "voided"):
        raise TaxInvoiceError(
            f"A {order.status} order cannot be issued as a tax invoice."
        )

    tenant = (
        await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    ).scalar_one()
    config = (
        await db.execute(
            select(RestaurantConfig).where(RestaurantConfig.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()

    # Resolve through the SHARED resolver, not the raw column. Reading
    # order.location_id directly is what produced a UAE tax invoice with no TRN
    # on every sale the POS had ever taken (F31): stock movement went through
    # resolve_location and picked up the default site, this document did not.
    # One reader and several ignorers of the same idea is how F19 happened too.
    location = None
    if order.location_id is not None:
        location = (
            await db.execute(
                select(Location).where(
                    Location.id == order.location_id,
                    Location.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
    if location is None:
        from app.services.stock_service import StockError, resolve_location

        try:
            location = await resolve_location(db, tenant_id, None)
        except StockError:
            # No locations configured, or several with no default flagged.
            # Fall back to the tenant identity, which is the pre-locations
            # behaviour every existing single-site tenant relies on.
            location = None

    rate_bps = (config.default_tax_rate if config else 0) or 0
    prices_include_vat = bool(config.tax_inclusive) if config else True
    currency = (config.currency if config else "AED") or "AED"

    # Supplier identity comes from the LOCATION when it has one, because a
    # tenant may bill under a different registered entity per site. Falling
    # back to the tenant name keeps single-site tenants working.
    supplier = TaxInvoiceParty(
        name=(location.legal_name if location and location.legal_name else tenant.name),
        trn=location.tax_registration_number if location else None,
        address_line1=location.address_line1 if location else None,
        address_line2=location.address_line2 if location else None,
        city=location.city if location else None,
        country=location.country if location else None,
        phone=location.phone if location else None,
        email=location.email if location else None,
    )

    recipient = None
    if order.customer_id is not None:
        customer = (
            await db.execute(select(Customer).where(Customer.id == order.customer_id))
        ).scalar_one_or_none()
        if customer is not None:
            recipient = TaxInvoiceParty(
                name=customer.name or "Customer",
                phone=customer.phone,
                address_line1=getattr(customer, "address", None),
            )
    if recipient is None and (order.customer_name or order.customer_phone):
        recipient = TaxInvoiceParty(
            name=order.customer_name or "Customer",
            phone=order.customer_phone,
            address_line1=order.delivery_address,
        )

    lines: list[TaxInvoiceLine] = []
    subtotal_net = 0
    vat_total = 0

    for item in order.items:
        # Modifiers are part of what was sold, so their price belongs in the
        # line they were sold with, not silently dropped from the invoice.
        modifier_total = sum(m.price_adjustment for m in item.modifiers) * item.quantity
        gross = item.total + modifier_total

        if prices_include_vat:
            net, vat = split_vat_inclusive(gross, rate_bps)
        else:
            net, vat = add_vat_exclusive(gross, rate_bps)
            gross = net + vat

        unit_net = net // item.quantity if item.quantity else net

        lines.append(
            TaxInvoiceLine(
                description=item.name,
                quantity=item.quantity,
                unit_price_net_minor=unit_net,
                line_net_minor=net,
                vat_rate_bps=rate_bps,
                vat_amount_minor=vat,
                line_gross_minor=gross,
            )
        )
        subtotal_net += net
        vat_total += vat

    total_gross = subtotal_net + vat_total - order.discount_amount

    return TaxInvoiceData(
        invoice_number=await _next_invoice_number(db, tenant_id, order, location),
        order_number=order.order_number,
        issue_date=order.created_at.date(),
        issued_at=order.created_at.astimezone(timezone.utc),
        supplier=supplier,
        recipient=recipient,
        currency=currency,
        lines=lines,
        subtotal_net_minor=subtotal_net,
        discount_minor=order.discount_amount,
        vat_total_minor=vat_total,
        total_gross_minor=total_gross,
        vat_rate_bps=rate_bps,
        prices_include_vat=prices_include_vat,
        location_id=location.id if location else None,
        location_name=location.name if location else None,
        payment_status=order.payment_status,
        notes=order.notes,
    )
