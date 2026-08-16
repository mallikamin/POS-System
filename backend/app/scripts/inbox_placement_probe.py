"""Where do our transactional emails actually land in Gmail? (OI-83 follow-up)

The win-back campaign landed in Promotions, which raised the question of whether
the order confirmation and the Google review email do too. That is a question
about the real emails in a real inbox, so this sends the REAL ones, built by the
production builders in email_service, to one address.

    python /tmp/inbox_placement_probe.py you@example.com

Nothing is written. The Order is loaded, detached from the session with
`expunge`, and only then is its address overridden in memory, so there is no
path by which a flush could persist the change. No customer is emailed.
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import async_session_factory
from app.models.order import Order, OrderItem
from app.models.restaurant_config import RestaurantConfig
from app.models.tenant import Tenant
from app.services.email_service import send_order_email

TENANT_SLUG = "chick-shack"
# A real completed delivery order, so every builder has the fields it wants.
SAMPLE_ORDER = "260802-011"


async def main(to: str) -> int:
    async with async_session_factory() as db:
        tenant = (
            await db.execute(select(Tenant).where(Tenant.slug == TENANT_SLUG))
        ).scalar_one()
        # It lives on RestaurantConfig, NOT Tenant. An earlier version of this
        # probe read it off Tenant with a getattr default, which silently
        # returned "" and made a working feature look switched off.
        review_url = (
            (
                await db.execute(
                    select(RestaurantConfig.google_review_url).where(
                        RestaurantConfig.tenant_id == tenant.id
                    )
                )
            ).scalar_one_or_none()
            or ""
        ).strip()

        order = (
            await db.execute(
                select(Order)
                .where(Order.order_number == SAMPLE_ORDER, Order.tenant_id == tenant.id)
                .options(selectinload(Order.items).selectinload(OrderItem.modifiers))
            )
        ).scalar_one()

        # Detach BEFORE touching anything. A detached instance cannot be flushed.
        db.expunge(order)

    order.customer_email = to

    for event in ("review",):
        ok = await send_order_email(
            order,
            event,
            shop_name="Chick Shack",
            currency="GBP",
            review_url=review_url,
        )
        print(f"{event:10} -> {'sent' if ok else 'NOT SENT'}")
        await asyncio.sleep(2)

    print(f"\nreview_url configured: {bool(review_url)}")
    print("Nothing was written to the database. No customer was emailed.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(asyncio.run(main(sys.argv[1])))
