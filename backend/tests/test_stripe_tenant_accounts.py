"""Each shop's card money goes to that shop's own Stripe account. Never another's.

Since 2026-10 two shops take cards online: Chick Shack (the original, global
STRIPE_* settings) and Ali Fish & Chips (its own slug-suffixed variables). The
guarantees pinned here:

  (a) the default tenant's slug resolves to the original global settings, so
      Chick Shack's live configuration is unchanged;
  (b) any other slug reads only its own STRIPE_*__<SLUG> variables;
  (c) a non-default tenant with no key of its own is NOT configured, and never
      falls back to the global key, even when one is set;
  (d) such a tenant's checkout refuses with StripeNotConfigured, and the route
      answers 503 without any Stripe call being made;
  (e) every SDK call carries that tenant's own key as a per-request api_key,
      and the module-global `stripe.api_key` is never assigned;
  (f) a webhook is verified with the tenant's own signing secret, and an event
      on one tenant's webhook can never touch another tenant's order; the
      original /public/stripe/webhook still works for the default tenant;
  (g) the success/cancel return URLs (and the currency) are the tenant's own.

In conftest the primary test tenant (`test-restaurant`) plays the default
tenant; `other-restaurant` plays the second shop.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.tenant import Tenant
from app.models.user import User
from app.services import stripe_service
from app.services.stripe_service import StripeError, StripeNotConfigured

OTHER_SLUG = "other-restaurant"
OTHER_SUFFIX = "OTHER_RESTAURANT"
_SUFFIXED = (
    "STRIPE_SECRET_KEY",
    "STRIPE_WEBHOOK_SECRET",
    "STRIPE_SUCCESS_URL",
    "STRIPE_CANCEL_URL",
    "STRIPE_ACCOUNT_CURRENCY",
)


@pytest.fixture
def global_account(monkeypatch):
    """The default tenant's (Chick Shack's) global account, fully configured.

    Set on every test so "no fallback" is proven against a global account that
    really would work, not against an empty one.
    """
    s = stripe_service.settings
    monkeypatch.setattr(s, "STRIPE_SECRET_KEY", "sk_test_global_default")
    monkeypatch.setattr(s, "STRIPE_WEBHOOK_SECRET", "whsec_global_default")
    monkeypatch.setattr(s, "STRIPE_SUCCESS_URL", "https://default-shop.example/ok")
    monkeypatch.setattr(s, "STRIPE_CANCEL_URL", "https://default-shop.example/no")
    monkeypatch.setattr(s, "STRIPE_ACCOUNT_CURRENCY", "gbp")
    return s


@pytest.fixture
def no_other_env(monkeypatch):
    """The second shop has no variables at all."""
    for name in _SUFFIXED:
        monkeypatch.delenv(f"{name}__{OTHER_SUFFIX}", raising=False)


@pytest.fixture
def other_env(monkeypatch, no_other_env):
    """The second shop's own, distinct account."""
    monkeypatch.setenv(f"STRIPE_SECRET_KEY__{OTHER_SUFFIX}", "sk_test_other_shop")
    monkeypatch.setenv(f"STRIPE_WEBHOOK_SECRET__{OTHER_SUFFIX}", "whsec_other_shop")
    monkeypatch.setenv(f"STRIPE_SUCCESS_URL__{OTHER_SUFFIX}", "https://other-shop.example/ok")
    monkeypatch.setenv(f"STRIPE_CANCEL_URL__{OTHER_SUFFIX}", "https://other-shop.example/no")
    monkeypatch.setenv(f"STRIPE_ACCOUNT_CURRENCY__{OTHER_SUFFIX}", "gbp")


def _online_order(tenant_id: uuid.UUID, user_id: uuid.UUID, **overrides) -> Order:
    fields = {
        "tenant_id": tenant_id,
        "order_number": "T250101-001",
        "order_type": "online",
        "status": "confirmed",
        "payment_status": "unpaid",
        "service_type": "delivery",
        "subtotal": 1000,
        "tax_amount": 0,
        "discount_amount": 0,
        "delivery_fee": 300,
        "total": 1300,
        "created_by": user_id,
        "accepted_at": None,
        "rejected_at": None,
        "customer_name": "Card Customer",
        "intends_card_payment": True,
        "stripe_payment_intent_id": "pi_test_123",
        "stripe_checkout_session_id": "cs_test_123",
        "payment_authorized_at": datetime.now(timezone.utc),
        "payment_captured_at": None,
    }
    fields.update(overrides)
    return Order(**fields)


async def _persist(db: AsyncSession, order: Order) -> Order:
    db.add(order)
    await db.flush()
    await db.commit()
    return order


async def _reload(db: AsyncSession, order_id: uuid.UUID) -> Order:
    db.expunge_all()
    return (await db.execute(select(Order).where(Order.id == order_id))).scalar_one()


# ---------------------------------------------------------------------------
# (a) (b) (c) Resolution
# ---------------------------------------------------------------------------


def test_default_slug_resolves_to_the_global_settings(global_account, other_env) -> None:
    """(a) Chick Shack's live config is read exactly as before."""
    account = stripe_service.account_for_slug(global_account.STRIPE_DEFAULT_TENANT_SLUG)

    assert account.secret_key == "sk_test_global_default"
    assert account.webhook_secret == "whsec_global_default"
    assert account.success_url == "https://default-shop.example/ok"
    assert account.cancel_url == "https://default-shop.example/no"
    assert account.currency == "gbp"
    assert account.configured and account.webhook_configured
    assert account.live_mode is False


def test_production_default_slug_is_chick_shack(global_account, monkeypatch) -> None:
    """(a) With the production default, `chick-shack` gets the global account,
    matched case- and whitespace-insensitively, and never its own suffixed
    variables (which would be a second, conflicting source of truth)."""
    monkeypatch.setattr(global_account, "STRIPE_DEFAULT_TENANT_SLUG", "chick-shack")
    monkeypatch.setenv("STRIPE_SECRET_KEY__CHICK_SHACK", "sk_test_should_be_ignored")

    for slug in ("chick-shack", " Chick-Shack "):
        account = stripe_service.account_for_slug(slug)
        assert account.secret_key == "sk_test_global_default"
        assert account.tenant_slug == "chick-shack"


def test_the_production_default_setting_is_chick_shack() -> None:
    """(a) The shipped default itself, not just a patched value."""
    from app.config import Settings

    assert Settings.model_fields["STRIPE_DEFAULT_TENANT_SLUG"].default == "chick-shack"


def test_another_slug_reads_only_its_own_suffixed_variables(
    global_account, other_env
) -> None:
    """(b)"""
    account = stripe_service.account_for_slug(OTHER_SLUG)

    assert account.tenant_slug == OTHER_SLUG
    assert account.secret_key == "sk_test_other_shop"
    assert account.webhook_secret == "whsec_other_shop"
    assert account.success_url == "https://other-shop.example/ok"
    assert account.cancel_url == "https://other-shop.example/no"
    assert account.currency == "gbp"
    assert account.configured and account.webhook_configured


def test_a_live_key_of_its_own_makes_that_tenant_live(global_account, monkeypatch) -> None:
    """(b) Mode is per account: the second shop can be live while the default is test."""
    monkeypatch.setenv(f"STRIPE_SECRET_KEY__{OTHER_SUFFIX}", "rk_live_other")
    assert stripe_service.account_for_slug(OTHER_SLUG).live_mode is True
    assert stripe_service.account_for_slug(
        global_account.STRIPE_DEFAULT_TENANT_SLUG
    ).live_mode is False


def test_an_unconfigured_tenant_never_falls_back_to_the_global_account(
    global_account, no_other_env
) -> None:
    """(c) THE guarantee. A working global key is set; the second shop must
    still get nothing, because a fallback would put its takings in another
    shop's bank."""
    account = stripe_service.account_for_slug(OTHER_SLUG)

    assert account.configured is False
    assert account.webhook_configured is False
    assert account.secret_key == ""
    assert account.webhook_secret == ""
    assert account.success_url == ""
    assert account.cancel_url == ""

    with pytest.raises(StripeNotConfigured, match=OTHER_SLUG):
        stripe_service._client(account)
    with pytest.raises(StripeError, match="refusing"):
        stripe_service.verify_webhook(account, b"{}", "sig")


@pytest.mark.asyncio
async def test_account_for_tenant_resolves_through_the_tenant_slug(
    db: AsyncSession, tenant: Tenant, other_tenant: Tenant, global_account, other_env
) -> None:
    """(a)+(b) via the database, the way every caller actually resolves it."""
    default = await stripe_service.account_for_tenant(db, tenant.id)
    other = await stripe_service.account_for_tenant(db, other_tenant.id)

    assert default.secret_key == "sk_test_global_default"
    assert other.secret_key == "sk_test_other_shop"
    assert stripe_service._slug_cache[other_tenant.id] == OTHER_SLUG


@pytest.mark.asyncio
async def test_an_unknown_tenant_id_is_not_configured(
    db: AsyncSession, global_account
) -> None:
    """(c) A tenant id with no row must not resolve to anything usable, and
    must not be cached as if it were known."""
    unknown = uuid.uuid4()
    account = await stripe_service.account_for_tenant(db, unknown)

    assert account.configured is False
    assert unknown not in stripe_service._slug_cache


# ---------------------------------------------------------------------------
# (d) Checkout for an unconfigured second shop
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_checkout_for_an_unconfigured_tenant_raises_not_configured(
    tenant: Tenant, admin_user: User, global_account, no_other_env
) -> None:
    """(d) Refused before any Stripe call is attempted."""
    order = _online_order(tenant.id, admin_user.id)
    order.items = []

    with patch.object(stripe_service, "_create_session_blocking") as create:
        with pytest.raises(StripeNotConfigured, match=OTHER_SLUG):
            await stripe_service.create_checkout_session(
                stripe_service.account_for_slug(OTHER_SLUG), order, currency="GBP"
            )

    create.assert_not_called()


@pytest.mark.asyncio
async def test_checkout_route_answers_503_for_an_unconfigured_tenant(
    client,
    db: AsyncSession,
    other_tenant: Tenant,
    other_tenant_user: User,
    global_account,
    no_other_env,
) -> None:
    """(d) Through the real route: "card is not available", not a 502, and not
    a session quietly created on the default shop's account."""
    order = await _persist(
        db,
        _online_order(
            other_tenant.id,
            other_tenant_user.id,
            order_number="T250101-002",
            stripe_payment_intent_id=None,
            stripe_checkout_session_id=None,
            payment_authorized_at=None,
        ),
    )

    with patch.object(stripe_service, "_create_session_blocking") as create:
        response = await client.post(
            f"/api/v1/public/{OTHER_SLUG}/orders/{order.id}/checkout-session"
        )

    assert response.status_code == 503
    assert response.json()["detail"] == "Card payment is not available right now."
    create.assert_not_called()

    refreshed = await _reload(db, order.id)
    assert refreshed.stripe_checkout_session_id is None


# ---------------------------------------------------------------------------
# (e) The key travels per request, through the real SDK
# ---------------------------------------------------------------------------


class _RecordingHttpClient:
    """Stands in for stripe's HTTP layer, so the REAL stripe 15.3.1 SDK builds
    every request (including the Authorization header) and only the network is
    faked. A mock of `stripe.checkout.Session.create` could not show which key
    actually reaches Stripe; this can."""

    name = "recording"

    def __init__(self) -> None:
        self.requests: list[dict] = []

    def request_with_retries(self, method, url, headers, post_data=None, *_a, **_k):
        self.requests.append(
            {"method": method, "url": url, "auth": headers.get("Authorization")}
        )
        if "/v1/checkout/sessions" in url:
            body = {
                "id": "cs_rec_1",
                "object": "checkout.session",
                "url": "https://checkout.stripe.com/c/pay/cs_rec_1",
                "payment_intent": {
                    "id": "pi_rec_1",
                    "object": "payment_intent",
                    "status": "requires_capture",
                    "amount_capturable": 1300,
                },
            }
            if method.lower() == "post":
                body["payment_intent"] = "pi_rec_1"
        elif url.endswith("/cancel"):
            body = {"id": "pi_rec_1", "object": "payment_intent", "status": "canceled"}
        elif url.endswith("/capture"):
            body = {"id": "pi_rec_1", "object": "payment_intent", "status": "succeeded"}
        else:
            body = {
                "id": "pi_rec_1",
                "object": "payment_intent",
                "status": "requires_capture",
                "amount_capturable": 1300,
                "amount_received": 0,
            }
        return json.dumps(body), 200, {}

    def close(self) -> None:  # pragma: no cover - SDK housekeeping
        pass


@pytest.mark.asyncio
async def test_every_sdk_call_carries_the_tenants_own_key_and_never_sets_the_global(
    tenant: Tenant, admin_user: User, global_account, other_env, monkeypatch
) -> None:
    """(e) Interleave both shops through every money-moving call and check the
    Authorization header of every request the real SDK sends."""
    import stripe

    recorder = _RecordingHttpClient()
    monkeypatch.setattr(stripe, "default_http_client", recorder)
    monkeypatch.setattr(stripe, "api_key", None)

    default = stripe_service.account_for_slug(global_account.STRIPE_DEFAULT_TENANT_SLUG)
    other = stripe_service.account_for_slug(OTHER_SLUG)

    for account in (other, default):
        order = _online_order(tenant.id, admin_user.id)
        order.items = []
        start = len(recorder.requests)

        url, session_id, _ = await stripe_service.create_checkout_session(
            account, order, currency="GBP", shop_name="Shop"
        )
        assert session_id == "cs_rec_1" and url.startswith("https://checkout.stripe.com/")
        assert await stripe_service.resolve_payment_intent_id(account, "cs_rec_1") == "pi_rec_1"
        assert await stripe_service.authorization_for_session(account, "cs_rec_1") == (
            "pi_rec_1",
            True,
        )
        assert await stripe_service.capture_for_order(account, "pi_rec_1", 1300) == "succeeded"
        assert (await stripe_service.retrieve_payment_intent(account, "pi_rec_1"))[
            "status"
        ] == "requires_capture"
        assert await stripe_service.cancel(account, "pi_rec_1") is True

        sent = recorder.requests[start:]
        # create, retrieve, retrieve(expanded), retrieve+capture, retrieve, cancel
        assert len(sent) == 7
        assert {r["auth"] for r in sent} == {f"Bearer {account.secret_key}"}, sent

    assert stripe.api_key is None, "the module-global key must never be assigned"


def test_client_does_not_assign_the_global_api_key(other_env, monkeypatch) -> None:
    """(e) `_client` itself, the place the old code did `stripe.api_key = ...`."""
    import stripe

    monkeypatch.setattr(stripe, "api_key", None)
    stripe_service._client(stripe_service.account_for_slug(OTHER_SLUG))
    assert stripe.api_key is None


# ---------------------------------------------------------------------------
# (g) Return URLs and currency are the tenant's own
# ---------------------------------------------------------------------------


class _SessionApi:
    def __init__(self) -> None:
        self.captured: dict = {}

    def create(self, **kwargs):  # noqa: ANN003, ANN201 - mirrors the SDK
        self.captured = kwargs
        return {"id": "cs_g", "url": "https://checkout.stripe.com/g", "payment_intent": None}


@pytest.mark.asyncio
async def test_return_urls_come_from_the_tenants_own_account(
    tenant: Tenant, admin_user: User, global_account, other_env
) -> None:
    """(g) A shared default would send one shop's customers back to another
    shop's website after paying."""
    order = _online_order(tenant.id, admin_user.id)
    order.items = []
    sessions = _SessionApi()
    fake_stripe = type("S", (), {"checkout": type("C", (), {"Session": sessions})()})()

    with patch.object(stripe_service, "_client", return_value=fake_stripe):
        await stripe_service.create_checkout_session(
            stripe_service.account_for_slug(OTHER_SLUG), order, currency="GBP"
        )

    assert sessions.captured["success_url"].startswith("https://other-shop.example/ok?")
    assert sessions.captured["cancel_url"].startswith("https://other-shop.example/no?")
    assert sessions.captured["api_key"] == "sk_test_other_shop"
    assert "default-shop" not in json.dumps(sessions.captured, default=str)


@pytest.mark.asyncio
async def test_missing_return_urls_do_not_borrow_the_default_shops(
    tenant: Tenant, admin_user: User, global_account, other_env, monkeypatch
) -> None:
    """(g)+(c) A key but no return URLs: refused, not silently given Chick
    Shack's URLs."""
    monkeypatch.delenv(f"STRIPE_SUCCESS_URL__{OTHER_SUFFIX}")
    monkeypatch.delenv(f"STRIPE_CANCEL_URL__{OTHER_SUFFIX}")
    order = _online_order(tenant.id, admin_user.id)
    order.items = []

    with patch.object(stripe_service, "_create_session_blocking") as create:
        with pytest.raises(StripeNotConfigured, match="STRIPE_SUCCESS_URL"):
            await stripe_service.create_checkout_session(
                stripe_service.account_for_slug(OTHER_SLUG), order, currency="GBP"
            )
    create.assert_not_called()


@pytest.mark.asyncio
async def test_currency_check_uses_the_tenants_own_account(
    tenant: Tenant, admin_user: User, global_account, other_env, monkeypatch
) -> None:
    """(g) The settlement currency is per account too."""
    monkeypatch.setenv(f"STRIPE_ACCOUNT_CURRENCY__{OTHER_SUFFIX}", "eur")
    order = _online_order(tenant.id, admin_user.id)
    order.items = []

    with pytest.raises(StripeNotConfigured, match="GBP"):
        await stripe_service.create_checkout_session(
            stripe_service.account_for_slug(OTHER_SLUG), order, currency="GBP"
        )


# ---------------------------------------------------------------------------
# (f) Webhooks: verified per tenant, scoped per tenant. Real signatures.
# ---------------------------------------------------------------------------


def _signed(event: dict, secret: str) -> tuple[bytes, dict[str, str]]:
    """Sign a payload exactly as Stripe does (v1 = HMAC-SHA256 of "t.payload"),
    so these tests run the SDK's real `Webhook.construct_event`."""
    payload = json.dumps(event).encode()
    ts = int(time.time())
    sig = hmac.new(
        secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256
    ).hexdigest()
    return payload, {"Stripe-Signature": f"t={ts},v1={sig}"}


def _succeeded_event(order: Order) -> dict:
    return {
        "id": f"evt_{uuid.uuid4().hex[:12]}",
        "object": "event",
        "type": "payment_intent.succeeded",
        "livemode": False,
        "data": {
            "object": {
                "id": order.stripe_payment_intent_id,
                "object": "payment_intent",
                # The metadata tenant MATCHES the order, so it is the per-account
                # check, not the older metadata check, that has to refuse it.
                "metadata": {"order_id": str(order.id), "tenant_id": str(order.tenant_id)},
            }
        },
    }


@pytest.mark.asyncio
async def test_an_event_on_one_tenants_webhook_cannot_touch_another_tenants_order(
    client,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    other_tenant: Tenant,
    global_account,
    other_env,
) -> None:
    """(f) Validly signed by the second shop's account, posted to the second
    shop's webhook, naming the DEFAULT shop's order. Ignored, 200, untouched."""
    order = await _persist(db, _online_order(tenant.id, admin_user.id))

    payload, headers = _signed(_succeeded_event(order), "whsec_other_shop")
    response = await client.post(
        f"/api/v1/public/{OTHER_SLUG}/stripe/webhook", content=payload, headers=headers
    )

    assert response.status_code == 200, "Stripe must never be told to retry"
    assert response.json() == {"status": "ignored"}
    assert (await _reload(db, order.id)).payment_captured_at is None


@pytest.mark.asyncio
async def test_the_default_webhook_cannot_touch_another_tenants_order(
    client,
    db: AsyncSession,
    other_tenant: Tenant,
    other_tenant_user: User,
    global_account,
    other_env,
) -> None:
    """(f) The mirror image: the original route, signed by the default account,
    naming the second shop's order."""
    order = await _persist(db, _online_order(other_tenant.id, other_tenant_user.id))

    payload, headers = _signed(_succeeded_event(order), "whsec_global_default")
    response = await client.post(
        "/api/v1/public/stripe/webhook", content=payload, headers=headers
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ignored"}
    assert (await _reload(db, order.id)).payment_captured_at is None


@pytest.mark.asyncio
async def test_a_tenant_webhook_rejects_another_accounts_signature(
    client,
    db: AsyncSession,
    other_tenant: Tenant,
    other_tenant_user: User,
    global_account,
    other_env,
) -> None:
    """(f) Signed with the DEFAULT account's secret but posted to the second
    shop's webhook: the signature check itself fails (400)."""
    order = await _persist(db, _online_order(other_tenant.id, other_tenant_user.id))

    payload, headers = _signed(_succeeded_event(order), "whsec_global_default")
    response = await client.post(
        f"/api/v1/public/{OTHER_SLUG}/stripe/webhook", content=payload, headers=headers
    )

    assert response.status_code == 400
    assert (await _reload(db, order.id)).payment_captured_at is None


@pytest.mark.asyncio
async def test_an_unconfigured_tenant_webhook_refuses_everything(
    client,
    db: AsyncSession,
    other_tenant: Tenant,
    other_tenant_user: User,
    global_account,
    no_other_env,
) -> None:
    """(f)+(c) No signing secret of its own: refused, even when signed with the
    default account's (configured) secret."""
    order = await _persist(db, _online_order(other_tenant.id, other_tenant_user.id))

    payload, headers = _signed(_succeeded_event(order), "whsec_global_default")
    response = await client.post(
        f"/api/v1/public/{OTHER_SLUG}/stripe/webhook", content=payload, headers=headers
    )

    assert response.status_code == 400
    assert (await _reload(db, order.id)).payment_captured_at is None


@pytest.mark.asyncio
async def test_a_tenant_webhook_processes_its_own_order(
    client,
    db: AsyncSession,
    other_tenant: Tenant,
    other_tenant_user: User,
    global_account,
    other_env,
) -> None:
    """(f) The positive case for the new route."""
    order = await _persist(db, _online_order(other_tenant.id, other_tenant_user.id))

    payload, headers = _signed(_succeeded_event(order), "whsec_other_shop")
    response = await client.post(
        f"/api/v1/public/{OTHER_SLUG}/stripe/webhook", content=payload, headers=headers
    )

    assert response.status_code == 200
    assert response.json() != {"status": "ignored"}
    assert (await _reload(db, order.id)).payment_captured_at is not None


@pytest.mark.asyncio
async def test_the_original_webhook_still_works_for_the_default_tenant(
    client,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    global_account,
    other_env,
) -> None:
    """(f) The URL registered in Chick Shack's Stripe dashboard since launch."""
    order = await _persist(db, _online_order(tenant.id, admin_user.id))

    payload, headers = _signed(_succeeded_event(order), "whsec_global_default")
    response = await client.post(
        "/api/v1/public/stripe/webhook", content=payload, headers=headers
    )

    assert response.status_code == 200
    assert response.json() != {"status": "ignored"}
    assert (await _reload(db, order.id)).payment_captured_at is not None


@pytest.mark.asyncio
async def test_the_original_webhook_rejects_the_other_shops_signature(
    client,
    db: AsyncSession,
    tenant: Tenant,
    admin_user: User,
    global_account,
    other_env,
) -> None:
    """(f) The default route verifies with the default secret only."""
    order = await _persist(db, _online_order(tenant.id, admin_user.id))

    payload, headers = _signed(_succeeded_event(order), "whsec_other_shop")
    response = await client.post(
        "/api/v1/public/stripe/webhook", content=payload, headers=headers
    )

    assert response.status_code == 400
    assert (await _reload(db, order.id)).payment_captured_at is None


# ---------------------------------------------------------------------------
# Callers resolve the order's OWN tenant's account
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_accept_captures_on_the_orders_own_tenant_account(
    db: AsyncSession,
    other_tenant: Tenant,
    other_tenant_user: User,
    global_account,
    other_env,
) -> None:
    """Accept on the second shop's order captures with the second shop's key."""
    from unittest.mock import AsyncMock

    from app.services import public_order_service

    order = await _persist(db, _online_order(other_tenant.id, other_tenant_user.id))

    with patch.object(
        stripe_service, "capture_for_order", new=AsyncMock(return_value="succeeded")
    ) as capture:
        await public_order_service.accept_order(
            db, other_tenant.id, order.id, other_tenant_user.id, 30
        )

    account = capture.await_args.args[0]
    assert account.tenant_slug == OTHER_SLUG
    assert account.secret_key == "sk_test_other_shop"
    assert capture.await_args.args[1:] == ("pi_test_123", 1300)


@pytest.mark.asyncio
async def test_reject_on_an_unconfigured_tenant_still_rejects_without_the_global_key(
    db: AsyncSession,
    other_tenant: Tenant,
    other_tenant_user: User,
    global_account,
    no_other_env,
    monkeypatch,
) -> None:
    """Reject must never be blocked, and must never reach Stripe with the
    default shop's key on another shop's intent."""
    import stripe

    from app.services import public_order_service

    recorder = MagicMock()
    monkeypatch.setattr(stripe, "default_http_client", recorder)

    order = await _persist(db, _online_order(other_tenant.id, other_tenant_user.id))
    rejected = await public_order_service.reject_order(
        db, other_tenant.id, order.id, other_tenant_user.id, "Too busy"
    )

    assert rejected.rejected_at is not None
    recorder.request_with_retries.assert_not_called()
