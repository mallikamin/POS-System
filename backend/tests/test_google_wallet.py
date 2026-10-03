"""Google Wallet loyalty card: the save link and the after-payment push.

Google itself is never called here: `upsert` and `push_update` are replaced.
The live API was checked separately on a real phone (2026-10-03).
"""

import uuid

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import func, select

from app.integrations import google_wallet
from app.models.loyalty import LoyaltyWalletPass
from app.services import loyalty_service
from tests.conftest import TestingSessionLocal
from tests.test_loyalty import PHONE, _code, _config, _order, _pay, menu  # noqa: F401 - fixture

ISSUER = "3388000000000000001"


@pytest.fixture
def rsa_key():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    return key, pem


@pytest.fixture
def wallet_on(monkeypatch, rsa_key):
    """Wallet configured for the test tenant, Google replaced by recorders."""
    settings = google_wallet.WalletSettings(GOOGLE_WALLET_ISSUER_ID=ISSUER,
                                            GOOGLE_WALLET_KEY_FILE="unused.json")
    monkeypatch.setattr(google_wallet, "wallet_settings", lambda: settings)
    monkeypatch.setattr(google_wallet, "_key", lambda: {
        "client_email": "wallet@test.iam.gserviceaccount.com", "private_key": rsa_key[1]})
    monkeypatch.setattr(google_wallet, "LOGOS", {"test-restaurant": "/tenant-logos/x.jpg"})
    calls = {"upsert": [], "push": []}

    async def upsert(card, client=None):
        calls["upsert"].append(card)

    async def push_update(card, notify, client=None):
        calls["push"].append((card, notify))
        return "notified" if notify else "updated"

    monkeypatch.setattr(google_wallet, "upsert", upsert)
    monkeypatch.setattr(google_wallet, "push_update", push_update)
    # The push opens its own session after commit; point it at the test database.
    import app.database

    monkeypatch.setattr(app.database, "async_session_factory", TestingSessionLocal)
    return calls


_scheduled: list = []


@pytest.fixture(autouse=True)
def _in_step(monkeypatch):
    """Pushes wait for `_drain` instead of running alongside the next request:
    the test database is one shared SQLite connection, where a push closing its
    session would roll back that request's work. Postgres gives each its own."""
    _scheduled.clear()
    monkeypatch.setattr(loyalty_service, "_schedule", _scheduled.append)
    yield
    for coro in _scheduled:
        coro.close()


async def _drain() -> None:
    while _scheduled:
        await _scheduled.pop(0)


async def _passes(db) -> int:
    return (await db.execute(select(func.count(LoyaltyWalletPass.id)))).scalar_one()


async def _claimed_bill(client, admin_token, db, tenant, menu):
    await _config(db, tenant, menu, per_day=0)
    o = await _order(client, admin_token, menu["karahi"])
    await _pay(client, admin_token, o)
    code = await _code(db, o["id"])
    r = await client.post(f"/api/v1/public/loyalty/{code}", json={"phone": PHONE, "consent": True})
    assert r.status_code == 200, r.text
    await _drain()
    return code


def test_key_from_base64_setting(monkeypatch):
    """Production passes the key as one base64 setting (the container is read-only)."""
    import base64
    import json

    key = {"client_email": "w@x.iam.gserviceaccount.com", "private_key": "pem"}
    settings = google_wallet.WalletSettings(
        GOOGLE_WALLET_ISSUER_ID=ISSUER, GOOGLE_WALLET_KEY_FILE="",
        GOOGLE_WALLET_KEY_B64=base64.b64encode(json.dumps(key).encode()).decode())
    monkeypatch.setattr(google_wallet, "wallet_settings", lambda: settings)
    google_wallet._key.cache_clear()
    try:
        assert google_wallet.enabled() and google_wallet._key() == key
    finally:
        google_wallet._key.cache_clear()


def test_card_and_message_wording():
    card = google_wallet.Card(slug="dannys", restaurant_name="Danny's", customer_id=uuid.uuid4(),
                              member_name="Ali", phone=PHONE, masked_phone="0300****567",
                              toward_next=3, visits_required=5, rewards_available=0,
                              reward_label="Free Cappuccino")
    body = google_wallet.object_body(card)
    assert body["loyaltyPoints"]["balance"]["string"] == "3 of 5"
    assert len(body["loyaltyPoints"]["balance"]["string"]) < 15
    assert body["barcode"]["value"] == PHONE
    header, text = google_wallet.visit_message(card)
    assert header == "Visit counted" and len(header) < 29
    assert text == "3 of 5 done. 2 more visits to Free Cappuccino."
    card.toward_next, card.rewards_available = 0, 1
    assert google_wallet.visit_message(card)[0] == "Your reward is ready"


async def test_claim_page_says_whether_wallet_is_offered(client, admin_token, db, tenant, menu,
                                                         wallet_on, monkeypatch):
    code = await _claimed_bill(client, admin_token, db, tenant, menu)
    assert (await client.get(f"/api/v1/public/loyalty/{code}")).json()["google_wallet"] is True
    monkeypatch.setattr(google_wallet, "LOGOS", {})  # no logo, no card
    assert (await client.get(f"/api/v1/public/loyalty/{code}")).json()["google_wallet"] is False


async def test_save_link_for_the_guest_on_the_bill(client, admin_token, db, tenant, menu,
                                                   wallet_on, rsa_key):
    code = await _claimed_bill(client, admin_token, db, tenant, menu)
    r = await client.post(f"/api/v1/public/loyalty/{code}/google-wallet", json={"phone": PHONE})
    assert r.status_code == 200, r.text
    url = r.json()["url"]
    assert url.startswith(google_wallet.SAVE_URL)
    claims = jwt.decode(url.removeprefix(google_wallet.SAVE_URL), rsa_key[0].public_key(),
                        algorithms=["RS256"], audience="google")
    (obj,) = claims["payload"]["loyaltyObjects"]
    card = wallet_on["upsert"][0]
    assert obj == {"id": f"{ISSUER}.member_{card.customer_id.hex}",
                   "classId": f"{ISSUER}.loyalty_test-restaurant"}
    assert (card.toward_next, card.visits_required) == (1, 5)
    assert await _passes(db) == 1
    # Asking again (same guest, second tap) keeps one row.
    r = await client.post(f"/api/v1/public/loyalty/{code}/google-wallet", json={"phone": PHONE})
    assert r.status_code == 200 and await _passes(db) == 1


async def test_bill_qr_alone_never_opens_another_guests_card(client, admin_token, db, tenant,
                                                             menu, wallet_on):
    code = await _claimed_bill(client, admin_token, db, tenant, menu)
    other = await _order(client, admin_token, menu["karahi"], "03119998888")  # a real member
    await _pay(client, admin_token, other)
    await _drain()
    r = await client.post(f"/api/v1/public/loyalty/{code}/google-wallet",
                          json={"phone": "03119998888"})
    assert r.status_code == 400, r.text
    assert wallet_on["upsert"] == [] and await _passes(db) == 0


async def test_paid_visit_pushes_to_a_saved_card_after_commit(client, admin_token, db, tenant,
                                                              menu, wallet_on):
    code = await _claimed_bill(client, admin_token, db, tenant, menu)
    await _drain()
    assert wallet_on["push"] == []  # no card handed out yet: Google is not called
    await client.post(f"/api/v1/public/loyalty/{code}/google-wallet", json={"phone": PHONE})

    o = await _order(client, admin_token, menu["karahi"], PHONE)
    await _pay(client, admin_token, o)
    await _drain()
    (card, notify), = wallet_on["push"]
    assert notify is True and (card.toward_next, card.phone) == (2, PHONE)


async def test_rolled_back_visit_never_pushes(db, tenant, menu, wallet_on):
    session = db.sync_session
    await db.execute(select(1))  # a visit is only ever queued inside a transaction
    loyalty_service._queue_wallet_push(db, tenant.id, uuid.uuid4(), notify=True)
    await db.rollback()
    assert loyalty_service._WALLET_KEY not in session.info
    await _drain()
    assert wallet_on["push"] == []


async def test_savepoint_release_is_not_the_commit(db, tenant, wallet_on):
    """The live walk's failure: SQLAlchemy fires after_commit when a SAVEPOINT is
    released. The visit is written in one, so the push ran before the payment
    committed and the phone got "0 of 5"."""
    await db.execute(select(1))
    async with db.begin_nested():
        loyalty_service._queue_wallet_push(db, tenant.id, uuid.uuid4(), notify=True)
    assert _scheduled == [], "pushed on the savepoint, before the payment committed"
    await db.commit()
    assert len(_scheduled) == 1


async def test_savepoint_rollback_keeps_an_earlier_visit(db, tenant, wallet_on):
    await db.execute(select(1))
    loyalty_service._queue_wallet_push(db, tenant.id, uuid.uuid4(), notify=True)
    try:
        async with db.begin_nested():
            raise ValueError("an unrelated step failed in its own savepoint")
    except ValueError:
        pass
    await db.commit()
    assert len(_scheduled) == 1


async def test_wallet_off_queues_nothing(db, tenant, monkeypatch):
    monkeypatch.setattr(google_wallet, "wallet_settings", lambda: google_wallet.WalletSettings(
        GOOGLE_WALLET_ISSUER_ID="", GOOGLE_WALLET_KEY_FILE="", GOOGLE_WALLET_KEY_B64=""))
    loyalty_service._queue_wallet_push(db, tenant.id, uuid.uuid4(), notify=True)
    assert loyalty_service._WALLET_KEY not in db.sync_session.info
