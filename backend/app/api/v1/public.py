"""Storefront endpoints -- an UNAUTHENTICATED half and an AUTHENTICATED half.

This file has two distinct halves and the distinction is visible in the URL.
Read which half you are in before adding anything.

**`/public/{tenant_slug}/...` -- anyone on the internet can call these.**
  1. No `Depends(get_current_user)`. Nothing here may expose anything an
     anonymous caller should not see.
  2. Never trust a price, a total or a fee from the request body. The service
     layer recomputes every amount from the database.
  3. Return the customer's own order only -- never a list, never another
     customer's data.
  4. The tenant is named explicitly in the path. It is never guessed.

**`/public/manage/...` -- staff only, `get_current_user` required.**
  These are part of the online-ordering flow, which is why they live here, but
  they are shop actions on the shop's own data: the queue, accept, reject and
  the printable ticket. They carry customer names, phone numbers and home
  addresses, so they are guarded accordingly. **Their tenant comes from the
  caller's token, never from the URL**, so no path segment can be edited to
  reach another restaurant's orders.

Order IDs are UUID4, so the customer's status route is guarded by an
unguessable identifier rather than a session -- the same model Just Eat and
Deliveroo use for a guest tracking link, and the reason that response is
deliberately thin. See PublicOrderStatusResponse.
"""

import uuid
from typing import Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.database import get_db
from app.models.order import Order
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.public_order import (
    MerchantOrderSummary,
    MerchantQueueResponse,
    PublicMenuResponse,
    PublicOrderCreate,
    PublicOrderLine,
    PublicOrderResponse,
    PublicOrderStatusResponse,
)
from app.services import escpos, print_service, public_order_service
from app.services.public_order_service import PublicOrderError

router = APIRouter(prefix="/public", tags=["public"])

_manager_dep = require_role("admin")


# Slugs that would collide with the /public/manage/... routes below. A tenant
# named "manage" would make `/public/manage/orders` ambiguous, so it is refused
# at the door rather than debugged later.
_RESERVED_TENANT_SLUGS = frozenset({"manage", "orders", "menu", "health"})


async def _resolve_tenant_id(db: AsyncSession, tenant_slug: str) -> uuid.UUID:
    """Resolve the storefront's tenant from the slug in the URL.

    ⚠️ **This used to be `SELECT id FROM tenants WHERE is_active LIMIT 1`.**
    That was safe only while exactly one tenant existed. This deployment
    already carries several (`demo-restaurant`, `yk-online`, `yk-desktop`,
    `chick-shack`), and that query has no ORDER BY, so it returned an arbitrary
    row -- meaning a UK storefront could have been served a Pakistani menu in
    rupees, or worse, had its orders written against another tenant.

    Every public route therefore names its tenant explicitly in the path. A
    slug is used rather than the hostname because the browser talks to *our*
    API domain, not the storefront's, so the Host header identifies us and not
    the shop. It is a path segment rather than a header because a custom header
    would force a CORS preflight on every request and cannot be opened in a
    browser to debug.
    """
    if tenant_slug in _RESERVED_TENANT_SLUGS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Unknown restaurant."
        )

    result = await db.execute(
        select(Tenant.id).where(
            Tenant.slug == tenant_slug, Tenant.is_active.is_(True)
        )
    )
    tenant_id = result.scalar_one_or_none()
    if tenant_id is None:
        # Deliberately identical to the reserved-slug response: an unauthenticated
        # caller learns nothing about which tenants exist or are merely inactive.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Unknown restaurant."
        )
    return tenant_id


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------


@router.get("/{tenant_slug}/menu", response_model=PublicMenuResponse)
async def get_public_menu(
    tenant_slug: str,
    db: AsyncSession = Depends(get_db),
) -> PublicMenuResponse:
    """The live menu, filtered to what can actually be ordered right now."""
    tenant_id = await _resolve_tenant_id(db, tenant_slug)
    currency, categories = await public_order_service.get_public_menu(db, tenant_id)
    return PublicMenuResponse.model_validate(
        {"currency": currency, "categories": categories}, from_attributes=True
    )


# ---------------------------------------------------------------------------
# Placing an order
# ---------------------------------------------------------------------------


@router.post(
    "/{tenant_slug}/orders",
    response_model=PublicOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_public_order(
    tenant_slug: str,
    body: PublicOrderCreate,
    db: AsyncSession = Depends(get_db),
) -> PublicOrderResponse:
    """Place an order from the storefront.

    Returns 409 with a customer-readable message when the basket no longer
    matches the menu (item withdrawn, option removed, below delivery minimum).
    That is a normal outcome of a stale tab, not a server fault.
    """
    tenant_id = await _resolve_tenant_id(db, tenant_slug)
    try:
        order = await public_order_service.create_public_order(db, tenant_id, body)
    except PublicOrderError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    await db.commit()

    # After the commit, never before: an email announcing an order that then
    # failed to commit cannot be recalled. Never raises.
    await public_order_service.notify_customer(db, tenant_id, order, "received")

    currency = await public_order_service.get_currency(db, tenant_id)
    return _to_public_response(order, currency)


@router.get(
    "/{tenant_slug}/orders/{order_id}/status",
    response_model=PublicOrderStatusResponse,
)
async def get_public_order_status(
    tenant_slug: str,
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> PublicOrderStatusResponse:
    """Polled by the confirmation page while the customer waits for acceptance."""
    tenant_id = await _resolve_tenant_id(db, tenant_slug)
    result = await db.execute(
        select(Order).where(
            Order.id == order_id,
            Order.tenant_id == tenant_id,
            Order.order_type == "online",
        )
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Order not found."
        )

    return PublicOrderStatusResponse(
        order_number=order.order_number,
        status=order.status,
        accepted=order.accepted_at is not None,
        rejected=order.rejected_at is not None,
        rejection_reason=order.rejection_reason,
        eta_minutes=order.eta_minutes,
        service_type=order.service_type or "collection",
        # `ready` stays true once reached: the later states are downstream of
        # it, and a page that flipped back to "being prepared" on completion
        # would read as the order going backwards.
        ready=order.status in ("ready", "served", "completed"),
        completed=order.status == "completed",
        paid=order.payment_status == "paid",
    )


# ---------------------------------------------------------------------------
# Merchant accept / reject -- AUTHENTICATED, despite living in this file
# ---------------------------------------------------------------------------
# These sit here because they are part of the online-ordering flow, but they
# are staff actions and are guarded accordingly. They are mounted under
# /public/manage rather than /public so the distinction is visible in the URL.


@router.get("/manage/orders", response_model=MerchantQueueResponse)
async def list_merchant_orders(
    state: Literal["pending", "active", "all"] = Query(
        "pending",
        description="pending = awaiting accept/reject; active = accepted and "
        "still being worked; all = everything including rejected",
    ),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MerchantQueueResponse:
    """The order queue the shop's tablet polls.

    The tenant comes from the caller's own token, never from the URL -- unlike
    the customer-facing routes above, which must name their tenant because
    nobody is logged in. That means a staff member cannot read another
    restaurant's orders by editing a path segment.
    """
    orders = await public_order_service.list_merchant_orders(
        db, current_user.tenant_id, state=state, limit=limit
    )
    currency = await public_order_service.get_currency(db, current_user.tenant_id)

    return MerchantQueueResponse(
        state=state,
        count=len(orders),
        orders=[_to_merchant_summary(order, currency) for order in orders],
    )


@router.post("/manage/orders/{order_id}/accept", response_model=PublicOrderResponse)
async def accept_online_order(
    order_id: uuid.UUID,
    eta_minutes: int = Body(..., ge=1, le=240, embed=True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PublicOrderResponse:
    """Accept an online order, promise an ETA, and fire it to the kitchen."""
    try:
        order = await public_order_service.accept_order(
            db, current_user.tenant_id, order_id, current_user.id, eta_minutes
        )
    except PublicOrderError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    await db.commit()
    await public_order_service.notify_customer(
        db, current_user.tenant_id, order, "accepted"
    )
    currency = await public_order_service.get_currency(db, current_user.tenant_id)
    return _to_public_response(order, currency)


@router.post("/manage/orders/{order_id}/ready", response_model=PublicOrderResponse)
async def mark_online_order_ready(
    order_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PublicOrderResponse:
    """The food is made: out for delivery, or waiting on the counter.

    One button, two meanings, decided by the order's own service type. The shop
    taps the same thing either way; the customer is told the right thing.
    """
    try:
        order = await public_order_service.advance_order(
            db, current_user.tenant_id, order_id, current_user.id, "ready"
        )
    except PublicOrderError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    await db.commit()
    await public_order_service.notify_customer(
        db, current_user.tenant_id, order, "on_the_way"
    )
    currency = await public_order_service.get_currency(db, current_user.tenant_id)
    return _to_public_response(order, currency)


@router.post("/manage/orders/{order_id}/complete", response_model=PublicOrderResponse)
async def complete_online_order(
    order_id: uuid.UUID,
    mark_paid: bool = Body(
        False,
        embed=True,
        description="Also record the balance as settled in cash. This is the "
        "handover moment for a cash order, so the two usually happen together.",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PublicOrderResponse:
    """Handed over. The order is done and leaves the queue.

    `mark_paid` is a flag rather than a separate mandatory step because for a
    cash takeaway the money and the food change hands at the same instant.
    Keeping it optional still allows the shop to settle payment separately when
    a driver returns with the cash later.
    """
    try:
        if mark_paid:
            # Settle BEFORE completing. `_maybe_send_to_kitchen_after_payment`
            # and the payment status sync both look at a live order, and a
            # completed order is a worse thing to be mutating.
            await public_order_service.mark_order_paid(
                db, current_user.tenant_id, order_id, current_user.id
            )
        order = await public_order_service.advance_order(
            db, current_user.tenant_id, order_id, current_user.id, "completed"
        )
    except PublicOrderError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    await db.commit()
    currency = await public_order_service.get_currency(db, current_user.tenant_id)
    return _to_public_response(order, currency)


@router.post("/manage/orders/{order_id}/paid", response_model=PublicOrderResponse)
async def mark_online_order_paid(
    order_id: uuid.UUID,
    method_code: str = Body(
        "cash",
        embed=True,
        pattern=r"^(cash|card|mobile_wallet|bank_transfer)$",
        description="How the customer actually paid at the door or the counter",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PublicOrderResponse:
    """Record payment for an online order settled on handover.

    Writes a real `Payment` row rather than flipping a flag, because the
    Z-report, the drawer session and every sales report read payments. A status
    change alone would show money that no report could account for.
    """
    try:
        order = await public_order_service.mark_order_paid(
            db, current_user.tenant_id, order_id, current_user.id, method_code
        )
    except PublicOrderError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    await db.commit()
    currency = await public_order_service.get_currency(db, current_user.tenant_id)
    return _to_public_response(order, currency)


@router.post("/manage/orders/{order_id}/reject", response_model=PublicOrderResponse)
async def reject_online_order(
    order_id: uuid.UUID,
    reason: str = Body(..., min_length=1, max_length=500, embed=True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PublicOrderResponse:
    """Reject an online order with a reason. Terminal."""
    try:
        order = await public_order_service.reject_order(
            db, current_user.tenant_id, order_id, current_user.id, reason
        )
    except PublicOrderError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    await db.commit()
    await public_order_service.notify_customer(
        db, current_user.tenant_id, order, "rejected"
    )
    currency = await public_order_service.get_currency(db, current_user.tenant_id)
    return _to_public_response(order, currency)


@router.get("/manage/orders/{order_id}/ticket")
async def get_order_ticket(
    order_id: uuid.UUID,
    fmt: Literal["rawbt", "prn", "preview"] = Query(
        "rawbt",
        alias="format",
        description="rawbt = JSON with the rawbt: URL the tablet opens; "
        "prn = raw ESC/POS bytes; preview = plain text for support",
    ),
    width: int = Query(
        48, ge=24, le=96, description="Characters per line: 48 for 80mm, 32 for 58mm"
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The kitchen ticket for an online order, ready to print.

    ⚠️ **Authenticated on purpose.** Unlike the customer-facing routes at the
    top of this file, a ticket carries the customer's name, phone and full
    delivery address. An unauthenticated version of this would be a data leak
    guarded by nothing but a UUID.

    How the tablet uses it: on a successful Accept it fetches `format=rawbt`
    and navigates to the returned URL, which hands the job to the RawBT app,
    which opens TCP:9100 to the kitchen printer on the shop LAN.

    `format=prn` exists because RawBT also registers as a handler for URLs
    ending in `.prn`. That path carries the payload as a download rather than
    inside a URL, sidestepping URL length limits on very large orders.

    `format=preview` renders the same bytes as readable text. That is for
    support: it answers "what did that ticket actually say" without needing
    access to the printer.
    """
    try:
        payload = await print_service.build_ticket_for_order(
            db, current_user.tenant_id, order_id, width=width
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Order not found."
        ) from exc

    if fmt == "prn":
        return Response(
            content=payload,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="order-{order_id}.prn"'
            },
        )
    if fmt == "preview":
        return PlainTextResponse(escpos.preview(payload))
    return {"url": print_service.to_rawbt_url(payload), "bytes": len(payload)}


# ---------------------------------------------------------------------------


def _to_merchant_summary(order: Order, currency: str) -> MerchantOrderSummary:
    """One card for the shop's tablet.

    Unlike `_to_public_response` this carries the phone number, the delivery
    address and the customer's notes, because the shop cannot work an order
    without them.
    """
    return MerchantOrderSummary(
        id=order.id,
        order_number=order.order_number,
        status=order.status,
        payment_status=order.payment_status,
        service_type=order.service_type or "collection",
        placed_at=order.created_at,
        customer_name=order.customer_name or "",
        customer_phone=order.customer_phone,
        delivery_address=order.delivery_address,
        delivery_area=order.delivery_area,
        notes=order.notes,
        lines=[
            PublicOrderLine(
                name=item.name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                total=item.total,
                modifiers=[m.name for m in item.modifiers],
            )
            for item in order.items
        ],
        subtotal=order.subtotal,
        tax_amount=order.tax_amount,
        delivery_fee=order.delivery_fee,
        total=order.total,
        currency=currency,
        accepted_at=order.accepted_at,
        rejected_at=order.rejected_at,
        rejection_reason=order.rejection_reason,
        eta_minutes=order.eta_minutes,
    )


def _to_public_response(order: Order, currency: str) -> PublicOrderResponse:
    return PublicOrderResponse(
        id=order.id,
        order_number=order.order_number,
        status=order.status,
        payment_status=order.payment_status,
        service_type=order.service_type or "collection",
        customer_name=order.customer_name or "",
        lines=[
            PublicOrderLine(
                name=item.name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                total=item.total,
                modifiers=[m.name for m in item.modifiers],
            )
            for item in order.items
        ],
        subtotal=order.subtotal,
        tax_amount=order.tax_amount,
        delivery_fee=order.delivery_fee,
        total=order.total,
        currency=currency,
        eta_minutes=order.eta_minutes,
        created_at=order.created_at,
    )
