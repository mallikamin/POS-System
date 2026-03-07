"""Receipt service -- assembles structured receipt data from an order."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.discount import OrderDiscount
from app.models.order import Order, OrderItem
from app.models.payment import Payment
from app.models.restaurant_config import RestaurantConfig
from app.models.table_session import TableSession
from app.models.tenant import Tenant
from app.schemas.receipt import (
    ReceiptData,
    ReceiptDiscountLine,
    ReceiptItem,
    ReceiptPayment,
)


async def get_receipt_data(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    order_id: uuid.UUID,
    cashier_name: str,
) -> ReceiptData:
    """Assemble receipt data for a given order.

    For dine-in orders attached to a table session, return a consolidated
    session bill by default (all non-voided orders in that session).
    """
    # Fetch order with session info
    result = await db.execute(
        select(Order)
        .options(
            selectinload(Order.items).selectinload(OrderItem.modifiers),
            selectinload(Order.table),
            selectinload(Order.creator),
        )
        .where(Order.id == order_id, Order.tenant_id == tenant_id)
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise ValueError("Order not found")

    if order.table_session_id:
        return await get_session_receipt_data(
            db, tenant_id, order.table_session_id, cashier_name
        )

    # Fetch config + tenant name
    config_result = await db.execute(
        select(RestaurantConfig).where(RestaurantConfig.tenant_id == tenant_id)
    )
    config = config_result.scalar_one_or_none()

    tenant_result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = tenant_result.scalar_one()

    # Fetch payments
    pay_result = await db.execute(
        select(Payment)
        .options(selectinload(Payment.method))
        .where(
            Payment.tenant_id == tenant_id,
            Payment.order_id == order_id,
            Payment.kind == "payment",
            Payment.status == "completed",
        )
        .order_by(Payment.created_at.asc())
    )
    payments = list(pay_result.scalars().all())

    # Build items
    receipt_items: list[ReceiptItem] = []
    for item in order.items:
        modifier_lines = [
            {
                "name": m.name,
                "price_adjustment": m.price_adjustment,
            }
            for m in (item.modifiers or [])
        ]
        receipt_items.append(
            ReceiptItem(
                name=item.name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                total=item.total,
                modifiers=modifier_lines,
            )
        )

    # Build payments
    receipt_payments: list[ReceiptPayment] = []
    for p in payments:
        receipt_payments.append(
            ReceiptPayment(
                method=p.method.display_name if p.method else "Unknown",
                amount=p.amount,
                tendered=p.tendered_amount,
                change=p.change_amount
                if p.change_amount and p.change_amount > 0
                else None,
            )
        )

    # Fetch applied discounts
    disc_result = await db.execute(
        select(OrderDiscount)
        .where(
            OrderDiscount.tenant_id == tenant_id,
            OrderDiscount.order_id == order_id,
        )
        .order_by(OrderDiscount.created_at.asc())
    )
    discount_records = list(disc_result.scalars().all())
    receipt_discounts = [
        ReceiptDiscountLine(
            label=d.label,
            source_type=d.source_type,
            amount=d.amount,
        )
        for d in discount_records
    ]

    tax_rate_bps = config.default_tax_rate if config else 1600
    tax_pct = tax_rate_bps / 100  # e.g., 1600 -> 16.00

    return ReceiptData(
        restaurant_name=tenant.name,
        receipt_header=config.receipt_header if config else None,
        receipt_footer=config.receipt_footer if config else None,
        order_number=order.order_number,
        order_type=order.order_type,
        date=order.created_at,
        table_label=(
            f"Table {order.table.label or order.table.number}" if order.table else None
        ),
        customer_name=order.customer_name,
        customer_phone=order.customer_phone,
        cashier_name=cashier_name,
        waiter_name=order.waiter.full_name if order.waiter else None,
        items=receipt_items,
        subtotal=order.subtotal,
        tax_label="GST" if tax_rate_bps > 0 else "Tax",
        tax_rate_display=f"{tax_pct:.0f}%"
        if tax_pct == int(tax_pct)
        else f"{tax_pct:.2f}%",
        tax_amount=order.tax_amount,
        discount_lines=receipt_discounts,
        discount_amount=order.discount_amount,
        total=order.total,
        payments=receipt_payments,
        payment_status=order.payment_status,
        cash_tax_rate_bps=getattr(config, "cash_tax_rate_bps", 0) or tax_rate_bps,
        card_tax_rate_bps=getattr(config, "card_tax_rate_bps", 0) or tax_rate_bps,
        currency=config.currency if config else "PKR",
    )


async def get_session_receipt_data(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
    cashier_name: str,
) -> ReceiptData:
    """Assemble one consolidated receipt for all non-voided orders in a table session."""
    session_result = await db.execute(
        select(TableSession)
        .options(
            selectinload(TableSession.table),
            selectinload(TableSession.orders)
            .selectinload(Order.items)
            .selectinload(OrderItem.modifiers),
            selectinload(TableSession.orders).selectinload(Order.waiter),
        )
        .where(TableSession.id == session_id, TableSession.tenant_id == tenant_id)
    )
    session = session_result.scalar_one_or_none()
    if session is None:
        raise ValueError("Table session not found")

    orders = sorted(
        [o for o in session.orders if o.status != "voided"],
        key=lambda o: o.created_at,
    )
    if not orders:
        raise ValueError("No billable orders in session")

    config_result = await db.execute(
        select(RestaurantConfig).where(RestaurantConfig.tenant_id == tenant_id)
    )
    config = config_result.scalar_one_or_none()

    tenant_result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = tenant_result.scalar_one()

    order_ids = [o.id for o in orders]

    pay_result = await db.execute(
        select(Payment)
        .options(selectinload(Payment.method))
        .where(
            Payment.tenant_id == tenant_id,
            Payment.order_id.in_(order_ids),
            Payment.kind == "payment",
            Payment.status == "completed",
        )
        .order_by(Payment.created_at.asc())
    )
    payments = list(pay_result.scalars().all())

    receipt_items: list[ReceiptItem] = []
    subtotal = 0
    tax_amount = 0
    discount_amount = 0
    total = 0
    customer_name = None
    customer_phone = None

    for o in orders:
        subtotal += o.subtotal
        tax_amount += o.tax_amount
        discount_amount += o.discount_amount
        total += o.total
        customer_name = customer_name or o.customer_name
        customer_phone = customer_phone or o.customer_phone

        for item in o.items:
            modifier_lines = [
                {"name": m.name, "price_adjustment": m.price_adjustment}
                for m in (item.modifiers or [])
            ]
            receipt_items.append(
                ReceiptItem(
                    name=item.name,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    total=item.total,
                    modifiers=modifier_lines,
                    order_label=o.order_number,
                )
            )

    # Add session-level discounts
    session_disc_result = await db.execute(
        select(OrderDiscount)
        .where(
            OrderDiscount.tenant_id == tenant_id,
            OrderDiscount.table_session_id == session_id,
        )
        .order_by(OrderDiscount.created_at.asc())
    )
    session_discount_records = list(session_disc_result.scalars().all())
    session_discount_amount = sum(d.amount for d in session_discount_records)
    discount_amount += session_discount_amount

    disc_result = await db.execute(
        select(OrderDiscount)
        .where(
            OrderDiscount.tenant_id == tenant_id,
            OrderDiscount.order_id.in_(order_ids),
        )
        .order_by(OrderDiscount.created_at.asc())
    )
    order_discount_records = list(disc_result.scalars().all())
    discount_records = order_discount_records + session_discount_records
    receipt_discounts = [
        ReceiptDiscountLine(label=d.label, source_type=d.source_type, amount=d.amount)
        for d in discount_records
    ]

    # Consolidate payments by method (e.g. two Cash allocations → one Cash line)
    consolidated: dict[str, dict] = {}
    for p in payments:
        method_name = p.method.display_name if p.method else "Unknown"
        if method_name not in consolidated:
            consolidated[method_name] = {
                "amount": 0,
                "tendered": None,
                "change": None,
            }
        consolidated[method_name]["amount"] += p.amount
        # For cash: accumulate tendered/change from each allocation
        if p.tendered_amount and p.tendered_amount > 0:
            consolidated[method_name]["tendered"] = (
                consolidated[method_name]["tendered"] or 0
            ) + p.tendered_amount
        if p.change_amount and p.change_amount > 0:
            consolidated[method_name]["change"] = (
                consolidated[method_name]["change"] or 0
            ) + p.change_amount

    receipt_payments: list[ReceiptPayment] = [
        ReceiptPayment(
            method=method_name,
            amount=data["amount"],
            tendered=data["tendered"],
            change=data["change"],
        )
        for method_name, data in consolidated.items()
    ]

    final_total = max(total - session_discount_amount, 0)
    paid_amount = sum(p.amount for p in payments)
    payment_status = (
        "paid"
        if paid_amount >= final_total
        else ("partial" if paid_amount > 0 else "unpaid")
    )

    tax_rate_bps = config.default_tax_rate if config else 1600
    tax_pct = tax_rate_bps / 100

    # Build readable order number from actual order numbers
    order_numbers = ", ".join(o.order_number for o in orders)

    return ReceiptData(
        restaurant_name=tenant.name,
        receipt_header=config.receipt_header if config else None,
        receipt_footer=config.receipt_footer if config else None,
        order_number=order_numbers,
        order_type="dine_in",
        date=orders[-1].created_at,
        table_label=(
            f"Table {session.table.label or session.table.number}"
            if session.table
            else None
        ),
        customer_name=customer_name,
        customer_phone=customer_phone,
        cashier_name=cashier_name,
        waiter_name=next((o.waiter.full_name for o in orders if o.waiter), None),
        items=receipt_items,
        subtotal=subtotal,
        tax_label="GST" if tax_rate_bps > 0 else "Tax",
        tax_rate_display=f"{tax_pct:.0f}%"
        if tax_pct == int(tax_pct)
        else f"{tax_pct:.2f}%",
        tax_amount=tax_amount,
        discount_lines=receipt_discounts,
        discount_amount=discount_amount,
        total=final_total,
        payments=receipt_payments,
        payment_status=payment_status,
        cash_tax_rate_bps=getattr(config, "cash_tax_rate_bps", 0) or tax_rate_bps,
        card_tax_rate_bps=getattr(config, "card_tax_rate_bps", 0) or tax_rate_bps,
        currency=config.currency if config else "PKR",
    )
