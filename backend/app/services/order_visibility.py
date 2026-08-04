"""One definition of "is this order real?", used by every query that counts it.

⚠️ **This module exists because the same rule was written in one place and not
the others, twice in two days.**

OI-61 put the card-payment gate on the pending queue only, and the "All" tab --
which never got it -- is how staff accepted an unpaid order on 2026-08-03.
OI-65 then fixed every queue state but left the *reports* untouched, and on
2026-08-04 the client's own reports screen showed £98.96 of "online revenue"
and "prepaid revenue" when only £36.04 had actually been taken: order
260804-002 had a Stripe Checkout session and no approval, so no money existed,
but every report counted its `Order.total` anyway.

So the predicate lives here, once. Anything that lists, counts, or sums online
orders imports it. Do not re-express it inline -- that is precisely the failure
this module is named after.
"""

from sqlalchemy import or_

from app.models.order import Order


def is_real_order():
    """An order the business actually has: money confirmed, or none was owed yet.

    A card order is real from the moment Stripe confirms the authorisation, and
    not one second before. There is deliberately no timeout: if the customer
    takes two hours on the Checkout page the order becomes real in two hours,
    and if they never pay it never becomes real at all. It must not appear on
    the tablet, and it must not appear in revenue.

    Returns a SQLAlchemy condition, so it composes into any `.where()`.

    The four arms, all deliberate:

    * `stripe_checkout_session_id IS NULL` -- cash on delivery. There is no
      payment to process, so it is real the moment it is placed.
    * `payment_authorized_at IS NOT NULL` -- Stripe confirmed the money.
    * `accepted_at IS NOT NULL` / `rejected_at IS NOT NULL` -- already answered
      by the shop. Hiding an order the kitchen is cooking would be worse than
      showing it, and history has to stay legible. Since `accept_order` refuses
      unconfirmed card orders, a row can only be in that state if it was
      answered before OI-65 shipped.
    """
    return or_(
        Order.stripe_checkout_session_id.is_(None),
        Order.payment_authorized_at.is_not(None),
        Order.accepted_at.is_not(None),
        Order.rejected_at.is_not(None),
    )


def money_actually_taken():
    """Prepaid means the money is IN, not that the customer opened a card page.

    `stripe_checkout_session_id IS NOT NULL` was the old definition of
    "prepaid", and it is the direct cause of the 2026-08-04 report overstating
    revenue: a session is created the instant the customer is sent to Stripe,
    long before -- and regardless of whether -- they ever pay.

    `payment_captured_at` is the only field that means the shop has the money.
    """
    return Order.payment_captured_at.is_not(None)
