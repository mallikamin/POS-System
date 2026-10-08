"""Time-boxed online promotions, set in code per shop.

One promotion exists: Chick Shack's "Welcome Back" reopening offer (flyer,
2026-10-07): order GBP 30 and get 20% off the entire menu, Thursday
8 October 2026 only.

The server is the only place a discount is decided. The storefront reads the
active promotion from the menu endpoint to SHOW it, and `create_public_order`
re-derives it from the basket it priced itself, exactly as it does every
other amount on the order.

Rules, as the flyer states them:
  * "Order GBP 30": the food subtotal before the discount, excluding delivery
    fee, platform fee and tip, must be at least the minimum.
  * "20% off entire menu": the percentage comes off the food subtotal only.
    The delivery fee, the platform fee and the tip are not discounted.
  * "Thursday 8 October": the whole UK calendar day. 8 October 2026 is in
    BST (UTC+1), so the window is written in UTC to avoid depending on the
    container's tz database.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class Promotion:
    code: str
    label: str
    percent_bps: int  # 2000 = 20%
    min_subtotal: int  # minor units, food subtotal before discount
    starts_at: datetime  # inclusive, UTC
    ends_at: datetime  # exclusive, UTC


PROMOTIONS: dict[str, tuple[Promotion, ...]] = {
    "chick-shack": (
        Promotion(
            code="welcome-back-2026-10-08",
            label="Welcome Back 20% off",
            percent_bps=2000,
            min_subtotal=3000,
            # 2026-10-08 00:00 BST .. 22:00 BST. Ended at shop close, not
            # midnight (Malik, 2026-10-08), so out-of-hours pre-orders placed
            # Thursday night for Friday do not get it.
            starts_at=datetime(2026, 10, 7, 23, 0, tzinfo=timezone.utc),
            ends_at=datetime(2026, 10, 8, 21, 0, tzinfo=timezone.utc),
        ),
    ),
}


def active_promotion(tenant_slug: str | None, now: datetime | None = None) -> Promotion | None:
    """The promotion running for this shop right now, if any."""
    if not tenant_slug:
        return None
    now = now or datetime.now(timezone.utc)
    for promo in PROMOTIONS.get(tenant_slug, ()):
        if promo.starts_at <= now < promo.ends_at:
            return promo
    return None


def discount_for(promo: Promotion | None, subtotal: int) -> int:
    """Minor units off the food subtotal. 0 below the minimum.

    Rounded half up to the penny, so 20% of 30.03 is 6.01, never a fraction.
    """
    if promo is None or subtotal < promo.min_subtotal:
        return 0
    return (subtotal * promo.percent_bps + 5_000) // 10_000
