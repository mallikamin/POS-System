"""Background timer that sends the "how did we do" review-request emails.

Why this exists as a timer inside the app rather than a cron job:

* **The tablet cannot drive it.** The obvious place would have been the
  merchant-orders poll, which is how `publish_authorized_card_orders` already
  runs. But an order accepted at 21:45 falls due at 00:45, hours after the shop
  has shut and the tablet has been switched off. A sweep that only runs while
  someone is looking at the tablet would hold every late order until the next
  service. The backend container runs 24/7, so it can simply keep its own time.
* **No new infrastructure.** No cron, no queue, no scheduler, nothing to
  install on the droplet and nothing else to keep alive.

⚠️ **This runs in all four uvicorn workers.** `--workers 4` means four copies of
this loop, so four sweeps per interval. That is safe and deliberate: the claim
in `send_due_review_emails` is a conditional UPDATE, so the database picks one
winner per order and the other three see `rowcount == 0`. It costs three extra
cheap queries a minute, which is a fair price for needing no leader election.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.database import async_session_factory
from app.models.tenant import Tenant
from app.services import public_order_service

logger = logging.getLogger(__name__)

#: How often to look for orders that have come due.
#:
#: Deliberately slack. The delay being measured is THREE HOURS, so an email
#: arriving up to a quarter of an hour past its due moment is invisible to the
#: customer, and polling faster buys nothing but load. At 15 minutes each
#: worker wakes 96 times a day; with 4 workers that is ~384 cheap queries a
#: day against a shop doing ~11 orders. Going to 5 minutes would triple that
#: for no gain a human could perceive.
#:
#: The overnight window makes most of those wake-ups nearly free: outside
#: 09:00-22:00 shop-local, `send_due_review_emails` returns after a single
#: small config SELECT per tenant, without touching the orders table.
SWEEP_INTERVAL_SECONDS = 900


async def _sweep_once() -> int:
    """One pass over every active tenant. Returns how many emails were claimed."""
    sent = 0
    async with async_session_factory() as db:
        tenant_ids = (
            (await db.execute(select(Tenant.id).where(Tenant.is_active.is_(True))))
            .scalars()
            .all()
        )
        for tenant_id in tenant_ids:
            try:
                claimed = await public_order_service.send_due_review_emails(
                    db, tenant_id
                )
            except Exception:
                # One tenant's bad data must not stop the others being swept,
                # and must not kill the loop for the life of the process.
                logger.exception("Review email sweep failed for tenant %s", tenant_id)
                await db.rollback()
                continue
            sent += len(claimed)
    return sent


async def run_review_email_worker() -> None:
    """Sweep forever. Cancelled on shutdown by the lifespan handler."""
    logger.info(
        "Review email worker started (every %ss)", SWEEP_INTERVAL_SECONDS
    )
    while True:
        try:
            await asyncio.sleep(SWEEP_INTERVAL_SECONDS)
            sent = await _sweep_once()
            if sent:
                logger.info("Review email sweep sent %d email(s)", sent)
        except asyncio.CancelledError:
            # Shutdown. Propagate so the task actually ends.
            logger.info("Review email worker stopping")
            raise
        except Exception:
            # Belt and braces: `_sweep_once` already swallows per-tenant
            # failures, so reaching here means something broader (the database
            # being unreachable, say). Log and keep the loop alive -- a dead
            # worker is invisible until someone notices no reviews are coming.
            logger.exception("Review email sweep failed; continuing")
