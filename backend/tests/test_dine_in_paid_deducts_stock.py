"""A dine-in order completed by its payment must leave the stock, like any other.

Paying a served dine-in order in full auto-completes it
(`payment_service._sync_order_payment_status`). That path used to skip the
recipe deduction the manual `completed` transition runs, so the commonest
restaurant flow -- serve, then settle the bill -- never touched inventory.
Found seeding the Danny's demo tenant, 2026-09-24.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import Ingredient, InventoryTransaction, Recipe, RecipeItem
from app.models.location import Location, LocationStock
from app.models.menu import Category, MenuItem
from app.models.order import Order, OrderItem
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.payment import PaymentCreate
from app.services import payment_service, stock_service


async def _served_dine_in_order(db: AsyncSession, tenant: Tenant, user: User):
    site = Location(
        tenant_id=tenant.id, name="Restaurant", code="MAIN", location_type="retail",
        invoice_format="thermal_ticket", is_default=True,
    )
    chicken = Ingredient(tenant_id=tenant.id, name="Chicken", unit="kg", cost_per_unit=Decimal("700"))
    category = Category(tenant_id=tenant.id, name="Pakistani", display_order=0)
    db.add_all([site, chicken, category])
    await db.flush()

    karahi = MenuItem(tenant_id=tenant.id, category_id=category.id, name="Chicken Karahi", price=250000)
    db.add(karahi)
    await db.flush()
    recipe = Recipe(tenant_id=tenant.id, menu_item_id=karahi.id, yield_servings=Decimal("1"))
    db.add(recipe)
    await db.flush()
    db.add(RecipeItem(
        tenant_id=tenant.id, recipe_id=recipe.id, ingredient_id=chicken.id,
        quantity=Decimal("0.5"), unit="kg", waste_factor=Decimal("0"),
    ))
    await stock_service.move_stock(
        db, tenant_id=tenant.id, ingredient_id=chicken.id, quantity_delta=Decimal("10"),
        transaction_type="purchase", location_id=site.id,
    )

    order = Order(
        tenant_id=tenant.id, order_number="T-001", order_type="dine_in", status="served",
        payment_status="unpaid", subtotal=250000, tax_amount=0, discount_amount=0,
        total=250000, created_by=user.id, location_id=site.id,
    )
    db.add(order)
    await db.flush()
    db.add(OrderItem(
        tenant_id=tenant.id, order_id=order.id, menu_item_id=karahi.id, name=karahi.name,
        quantity=2, unit_price=250000 // 2, total=250000,
    ))
    await db.flush()
    return order, site, chicken


async def _on_hand(db: AsyncSession, site: Location, ingredient: Ingredient) -> Decimal:
    row = (
        await db.execute(
            select(LocationStock).where(
                LocationStock.location_id == site.id, LocationStock.ingredient_id == ingredient.id
            )
        )
    ).scalar_one()
    return Decimal(str(row.quantity))


async def test_paying_a_served_dine_in_order_completes_it_and_deducts_stock(
    db: AsyncSession, tenant: Tenant, admin_user: User
):
    order, site, chicken = await _served_dine_in_order(db, tenant, admin_user)

    await payment_service.create_payment(
        db, tenant.id, admin_user.id,
        PaymentCreate(order_id=order.id, method_code="cash", amount=250000, tendered_amount=250000),
    )

    refreshed = (await db.execute(select(Order).where(Order.id == order.id))).scalar_one()
    assert refreshed.status == "completed"
    # Two karahis at 0.5 kg each.
    assert await _on_hand(db, site, chicken) == Decimal("9")
    consumed = (
        await db.execute(
            select(InventoryTransaction).where(
                InventoryTransaction.order_id == order.id,
                InventoryTransaction.transaction_type == "consumption",
            )
        )
    ).scalars().all()
    assert len(consumed) == 1


async def test_a_partial_payment_does_not_complete_or_deduct(
    db: AsyncSession, tenant: Tenant, admin_user: User
):
    order, site, chicken = await _served_dine_in_order(db, tenant, admin_user)

    await payment_service.create_payment(
        db, tenant.id, admin_user.id,
        PaymentCreate(order_id=order.id, method_code="cash", amount=100000, tendered_amount=100000),
    )

    refreshed = (await db.execute(select(Order).where(Order.id == order.id))).scalar_one()
    assert refreshed.status == "served"
    assert await _on_hand(db, site, chicken) == Decimal("10")
