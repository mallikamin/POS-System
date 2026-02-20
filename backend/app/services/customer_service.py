"""Customer service -- CRUD, phone search, order history."""

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
        select(Customer).where(
            Customer.tenant_id == tenant_id, Customer.phone == phone
        )
    )
    return result.scalar_one_or_none()


async def create_customer(
    db: AsyncSession, tenant_id: uuid.UUID, data: CustomerCreate
) -> Customer:
    existing = await get_by_phone(db, tenant_id, data.phone)
    if existing is not None:
        raise ValueError(f"Customer with phone {data.phone} already exists")
    customer = Customer(
        tenant_id=tenant_id,
        name=data.name,
        phone=data.phone,
        email=data.email,
        default_address=data.default_address,
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

    # If phone is being changed, check uniqueness
    new_phone = update_data.get("phone")
    if new_phone is not None and new_phone != customer.phone:
        existing = await get_by_phone(db, tenant_id, new_phone)
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
) -> list[Order]:
    """Return recent orders placed by this customer phone number."""
    stmt = (
        select(Order)
        .where(
            Order.tenant_id == tenant_id,
            Order.customer_phone == customer_phone,
        )
        .order_by(Order.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
