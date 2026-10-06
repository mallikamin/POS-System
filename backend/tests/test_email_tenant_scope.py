"""Customer email is sent only for tenants listed in EMAIL_TENANT_SLUGS.

EMAIL_FROM, its authenticated sending domain and the email branding belong to
ONE shop (Chick Shack). A second shop's customers must not receive mail from
Chick Shack's address, so a tenant not listed gets no email scheduled at all.

In conftest the primary test tenant (`test-restaurant`) is listed and
`other-restaurant` is not.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, settings
from app.models.order import Order
from app.models.tenant import Tenant
from app.models.user import User
from app.services import public_order_service


def _order(tenant: Tenant, user: User, number: str) -> Order:
    return Order(
        tenant_id=tenant.id,
        order_number=number,
        order_type="online",
        status="confirmed",
        payment_status="unpaid",
        service_type="collection",
        subtotal=1000,
        tax_amount=0,
        discount_amount=0,
        total=1000,
        created_by=user.id,
        customer_name="Email Customer",
        customer_email="customer@example.com",
    )


class _Recorder:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def __call__(self, order, event, **_kw) -> bool:
        self.sent.append((order.order_number, event))
        return True


async def _notify_and_drain(db, tenant_id, order, recorder, monkeypatch) -> None:
    monkeypatch.setattr(public_order_service.email_service, "send_order_email", recorder)
    await public_order_service.notify_customer(db, tenant_id, order, "received")
    # Let any scheduled task run to completion before asserting.
    await asyncio.sleep(0)
    await asyncio.gather(*public_order_service._email_tasks, return_exceptions=True)


def test_the_shipped_default_lists_only_chick_shack() -> None:
    assert Settings.model_fields["EMAIL_TENANT_SLUGS"].default == "chick-shack"
    assert Settings(EMAIL_TENANT_SLUGS=" chick-shack , ,ali-fish-chips ").email_tenant_slugs == {
        "chick-shack",
        "ali-fish-chips",
    }


@pytest.mark.asyncio
async def test_a_listed_tenant_gets_its_email(
    db: AsyncSession, tenant: Tenant, admin_user: User, monkeypatch
) -> None:
    assert tenant.slug in settings.email_tenant_slugs
    recorder = _Recorder()

    await _notify_and_drain(
        db, tenant.id, _order(tenant, admin_user, "E-001"), recorder, monkeypatch
    )

    assert recorder.sent == [("E-001", "received")]


@pytest.mark.asyncio
async def test_an_unlisted_tenant_gets_no_email_scheduled(
    db: AsyncSession,
    other_tenant: Tenant,
    other_tenant_user: User,
    monkeypatch,
) -> None:
    """The second shop. Nothing is scheduled: not sent, not even queued."""
    assert other_tenant.slug not in settings.email_tenant_slugs
    recorder = _Recorder()
    before = set(public_order_service._email_tasks)

    await _notify_and_drain(
        db,
        other_tenant.id,
        _order(other_tenant, other_tenant_user, "E-002"),
        recorder,
        monkeypatch,
    )

    assert recorder.sent == []
    assert set(public_order_service._email_tasks) == before


@pytest.mark.asyncio
async def test_listing_a_second_tenant_turns_its_email_on(
    db: AsyncSession,
    other_tenant: Tenant,
    other_tenant_user: User,
    monkeypatch,
) -> None:
    """The switch is the list, comma-separated, whitespace tolerated."""
    monkeypatch.setattr(
        settings, "EMAIL_TENANT_SLUGS", f"{settings.EMAIL_TENANT_SLUGS}, {other_tenant.slug}"
    )
    recorder = _Recorder()

    await _notify_and_drain(
        db,
        other_tenant.id,
        _order(other_tenant, other_tenant_user, "E-003"),
        recorder,
        monkeypatch,
    )

    assert recorder.sent == [("E-003", "received")]


@pytest.mark.asyncio
async def test_an_unknown_tenant_id_gets_no_email(
    db: AsyncSession, tenant: Tenant, admin_user: User, monkeypatch
) -> None:
    """A tenant id with no row resolves to no slug, which is never listed."""
    import uuid

    recorder = _Recorder()
    await _notify_and_drain(
        db, uuid.uuid4(), _order(tenant, admin_user, "E-004"), recorder, monkeypatch
    )
    assert recorder.sent == []
