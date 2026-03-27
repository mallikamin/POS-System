"""Customer service -- CRUD, phone search, order history, risk & stats."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.order import Order
from app.schemas.customer import CustomerCreate, CustomerUpdate


async def search_by_phone(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    phone_fragment: str,
    limit: int = 10,
) -> list[Customer]:
    """Search customers by partial phone match (digits only).

    Uses LIKE with a trailing wildcard so the call-center agent can type
    the first few digits and see matches immediately.
    """
    digits = "".join(c for c in phone_fragment if c.isdigit())
    if not digits:
        return []
    stmt = (
        select(Customer)
        .where(
            Customer.tenant_id == tenant_id,
            Customer.phone.like(f"%{digits}%"),
        )
        .order_by(Customer.name)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_customer(
    db: AsyncSession, customer_id: uuid.UUID, tenant_id: uuid.UUID
) -> Customer | None:
    result = await db.execute(
        select(Customer).where(
            Customer.id == customer_id, Customer.tenant_id == tenant_id
        )
    )
    return result.scalar_one_or_none()


async def get_by_phone(
    db: AsyncSession, tenant_id: uuid.UUID, phone: str
) -> Customer | None:
    result = await db.execute(
        select(Customer).where(Customer.tenant_id == tenant_id, Customer.phone == phone)
    )
    return result.scalar_one_or_none()


async def create_customer(
    db: AsyncSession, tenant_id: uuid.UUID, data: CustomerCreate
) -> Customer:
    normalized_phone = "".join(c for c in data.phone if c.isdigit())
    existing = await get_by_phone(db, tenant_id, normalized_phone)
    if existing is not None:
        raise ValueError(f"Customer with phone {data.phone} already exists")
    customer = Customer(
        tenant_id=tenant_id,
        name=data.name,
        phone=normalized_phone,
        email=data.email,
        alt_contact=data.alt_contact,
        default_address=data.default_address,
        city=data.city,
        alt_address=data.alt_address,
        alt_city=data.alt_city,
        notes=data.notes,
    )
    db.add(customer)
    await db.flush()
    return customer


async def update_customer(
    db: AsyncSession,
    customer: Customer,
    tenant_id: uuid.UUID,
    data: CustomerUpdate,
) -> Customer:
    update_data = data.model_dump(exclude_unset=True)

    # If phone is being changed, normalize and check uniqueness
    new_phone = update_data.get("phone")
    if new_phone is not None:
        normalized = "".join(c for c in new_phone if c.isdigit())
        update_data["phone"] = normalized
        if normalized != customer.phone:
            existing = await get_by_phone(db, tenant_id, normalized)
            if existing is not None:
                raise ValueError(f"Customer with phone {new_phone} already exists")

    for field, value in update_data.items():
        setattr(customer, field, value)
    await db.flush()
    return customer


async def get_order_history(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    customer_phone: str,
    limit: int = 20,
) -> list[dict]:
    """Return recent orders placed by this customer phone number.

    Returns dicts with items_count included for UI display.
    """
    from app.models.order import OrderItem

    # Subquery for items count per order
    items_count_sq = (
        select(
            OrderItem.order_id,
            func.count(OrderItem.id).label("items_count"),
        )
        .group_by(OrderItem.order_id)
        .subquery()
    )

    stmt = (
        select(
            Order.id,
            Order.order_number,
            Order.order_type,
            Order.status,
            Order.payment_status,
            Order.total,
            Order.created_at,
            func.coalesce(items_count_sq.c.items_count, 0).label("items_count"),
        )
        .outerjoin(items_count_sq, Order.id == items_count_sq.c.order_id)
        .where(
            Order.tenant_id == tenant_id,
            Order.customer_phone == customer_phone,
        )
        .order_by(Order.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [
        {
            "id": row.id,
            "order_number": row.order_number,
            "order_type": row.order_type,
            "status": row.status,
            "payment_status": row.payment_status,
            "total": row.total,
            "items_count": row.items_count,
            "created_at": row.created_at,
        }
        for row in rows
    ]


def compute_risk_flag(order_history: list[dict]) -> str:
    """Compute risk flag from order history.

    Rules:
    - 3+ voided orders OR >30% void rate → "high"
    - Otherwise → "normal"
    """
    if not order_history:
        return "normal"
    total = len(order_history)
    voided = sum(1 for o in order_history if o.get("status") == "voided")
    if voided >= 3 or (total > 0 and voided / total > 0.3):
        return "high"
    return "normal"


async def update_customer_stats(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    customer: Customer,
) -> Customer:
    """Recompute denormalized stats from orders and payments tables."""
    from app.models.payment import Payment

    # Count all orders
    count_result = await db.execute(
        select(func.count(Order.id)).where(
            Order.tenant_id == tenant_id,
            Order.customer_phone == customer.phone,
        )
    )
    customer.order_count = count_result.scalar_one() or 0

    # Sum actual payment amounts (most accurate - handles partial payments correctly)
    # Only count completed payments, exclude refunds
    spent_result = await db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .join(Order, Payment.order_id == Order.id)
        .where(
            Order.tenant_id == tenant_id,
            Order.customer_phone == customer.phone,
            Payment.kind == "payment",
            Payment.status == "completed",
        )
    )
    customer.total_spent = spent_result.scalar_one() or 0

    # Latest order timestamp
    last_result = await db.execute(
        select(func.max(Order.created_at)).where(
            Order.tenant_id == tenant_id,
            Order.customer_phone == customer.phone,
        )
    )
    customer.last_order_at = last_result.scalar_one()

    # Auto-compute risk flag (only if not manually set to "blocked")
    if customer.risk_flag != "blocked":
        history = await get_order_history(db, tenant_id, customer.phone, limit=100)
        customer.risk_flag = compute_risk_flag(history)

    await db.flush()
    await db.refresh(customer)
    return customer
