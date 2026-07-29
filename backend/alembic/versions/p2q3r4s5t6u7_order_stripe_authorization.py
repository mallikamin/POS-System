"""Carry a Stripe authorisation on the order.

The shop charges on ACCEPTANCE, not on placement. That is the client's own
decision (2026-07-29, asked directly: *"Once accepted"*), and it is the right
one for a takeaway that manually accepts every order -- a customer must not be
charged for an order the shop then turns down.

So a card payment is two separate events rather than one, and the order has to
remember what sits between them:

    checkout   PaymentIntent created with capture_method=manual. The money is
               AUTHORISED -- held on the customer's card, not taken.
    accept     the intent is CAPTURED. This is the only moment money moves.
    reject     the intent is CANCELLED. Nothing was ever taken, which is why
               the rejection screen's "nothing has been charged" stays true and
               why no refund path exists anywhere in this feature.

Both Stripe ids are stored because they answer different questions. The session
is where the customer was sent and is what a support query will quote; the
payment intent is what actually holds the money and is the thing captured or
cancelled. They are indexed because a webhook arrives knowing only the Stripe
id and has to find our order from it.

`payment_authorized_at` is not decoration. A card authorisation expires -- about
5 days on Visa, 7 on Mastercard/Amex for card-not-present -- so a pre-order held
longer than that will fail at capture, and the timestamp is what lets us see
that coming rather than discover it on the Accept tap.

All columns are nullable: cash on handover remains the default and every
existing order predates card payment entirely.

Revision ID: p2q3r4s5t6u7
Revises: o1p2q3r4s5t6
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "p2q3r4s5t6u7"
down_revision: str | None = "o1p2q3r4s5t6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column(
            "stripe_checkout_session_id",
            sa.String(length=255),
            nullable=True,
            comment="Stripe Checkout Session the customer was sent to, if paying by card",
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "stripe_payment_intent_id",
            sa.String(length=255),
            nullable=True,
            comment=(
                "PaymentIntent holding the authorisation. "
                "Captured on accept, cancelled on reject."
            ),
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "payment_authorized_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment=(
                "When the card was authorised. The hold expires roughly 5 days "
                "later on Visa and 7 on Mastercard/Amex, so a pre-order cannot "
                "outlive it."
            ),
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "payment_captured_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When the authorisation was actually taken, on acceptance",
        ),
    )

    # A webhook knows only the Stripe id, so both lookups must be indexed.
    op.create_index(
        "ix_orders_stripe_checkout_session_id",
        "orders",
        ["stripe_checkout_session_id"],
    )
    op.create_index(
        "ix_orders_stripe_payment_intent_id",
        "orders",
        ["stripe_payment_intent_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_orders_stripe_payment_intent_id", table_name="orders")
    op.drop_index("ix_orders_stripe_checkout_session_id", table_name="orders")
    op.drop_column("orders", "payment_captured_at")
    op.drop_column("orders", "payment_authorized_at")
    op.drop_column("orders", "stripe_payment_intent_id")
    op.drop_column("orders", "stripe_checkout_session_id")
