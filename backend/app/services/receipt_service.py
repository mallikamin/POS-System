"""Receipt service -- assembles structured receipt data from an order."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.discount import OrderDiscount
from app.models.order import Order, OrderItem
from app.models.payment import Payment
from app.models.restaurant_config import RestaurantConfig
from app.models.tenant import Tenant
from app.schemas.receipt import ReceiptData, ReceiptDiscountLine, ReceiptItem, ReceiptPayment


async def get_receipt_data(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    order_id: uuid.UUID,
    cashier_name: str,
) -> ReceiptData:
    """Assemble receipt data for a given order."""
    # Fetch order with items and modifiers
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

    # Fetch config + tenant name
    config_result = await db.execute(
        select(RestaurantConfig).where(RestaurantConfig.tenant_id == tenant_id)
    )
    config = config_result.scalar_one_or_none()

    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
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
                change=p.change_amount if p.change_amount and p.change_amount > 0 else None,
            )
        )

    # Fetch applied discounts
    disc_result = await db.execute(
        select(OrderDiscount).where(
            OrderDiscount.tenant_id == tenant_id,
            OrderDiscount.order_id == order_id,
        ).order_by(OrderDiscount.created_at.asc())
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
            f"Table {order.table.label or order.table.number}"
            if order.table
            else None
        ),
        customer_name=order.customer_name,
        customer_phone=order.customer_phone,
        cashier_name=cashier_name,
        items=receipt_items,
        subtotal=order.subtotal,
        tax_label="GST" if tax_rate_bps > 0 else "Tax",
        tax_rate_display=f"{tax_pct:.0f}%" if tax_pct == int(tax_pct) else f"{tax_pct:.2f}%",
        tax_amount=order.tax_amount,
        discount_lines=receipt_discounts,
        discount_amount=order.discount_amount,
        total=order.total,
        payments=receipt_payments,
        payment_status=order.payment_status,
        currency=config.currency if config else "PKR",
    )
