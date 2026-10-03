"""Google Wallet loyalty cards.

Sitara issues every restaurant's card from one Google Wallet issuer account
(Google's "aggregator" model): one loyalty class per restaurant, one loyalty
object per guest. The guest saves the card from a short signed link; after
that, each counted visit updates the card and pushes a phone notification
("Visit 3 of 5 counted").

Switched off unless GOOGLE_WALLET_ISSUER_ID and the service account's JSON key
are set: GOOGLE_WALLET_KEY_B64 (the key base64-encoded, for the read-only
production container) or GOOGLE_WALLET_KEY_FILE (a path, for local work). The
key is never committed.
"""

from __future__ import annotations

import base64
import json
import logging
import time
import uuid
from dataclasses import dataclass
from functools import lru_cache

import httpx
import jwt
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

API = "https://walletobjects.googleapis.com/walletobjects/v1"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/wallet_object.issuer"
SAVE_URL = "https://pay.google.com/gp/v/save/"

# The card needs a logo Google can fetch. Mirrors frontend/src/lib/tenantBranding.ts;
# a tenant with no logo gets no wallet card.
LOGOS = {"dannys": "/tenant-logos/dannys.jpg"}


class WalletSettings(BaseSettings):
    GOOGLE_WALLET_ISSUER_ID: str = ""
    GOOGLE_WALLET_KEY_FILE: str = ""
    GOOGLE_WALLET_KEY_B64: str = ""
    # Where Google fetches the logo from, and the page allowed to show the save button.
    PUBLIC_APP_URL: str = "https://eats.sitaratech.info"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


class WalletError(RuntimeError):
    """Google refused or could not be reached."""


@lru_cache
def wallet_settings() -> WalletSettings:
    return WalletSettings()


@lru_cache
def _key() -> dict:
    s = wallet_settings()
    if s.GOOGLE_WALLET_KEY_B64:
        return json.loads(base64.b64decode(s.GOOGLE_WALLET_KEY_B64))
    with open(s.GOOGLE_WALLET_KEY_FILE, encoding="utf-8") as fh:
        return json.load(fh)


def enabled() -> bool:
    s = wallet_settings()
    return bool(s.GOOGLE_WALLET_ISSUER_ID and (s.GOOGLE_WALLET_KEY_B64 or s.GOOGLE_WALLET_KEY_FILE))


def available_for(slug: str) -> bool:
    return enabled() and slug in LOGOS


def class_id(slug: str) -> str:
    return f"{wallet_settings().GOOGLE_WALLET_ISSUER_ID}.loyalty_{slug}"


def object_id(customer_id: uuid.UUID) -> str:
    return f"{wallet_settings().GOOGLE_WALLET_ISSUER_ID}.member_{customer_id.hex}"


@dataclass
class Card:
    """What a guest's card shows. Built by loyalty_service from Progress."""

    slug: str
    restaurant_name: str
    customer_id: uuid.UUID
    member_name: str
    phone: str
    masked_phone: str
    toward_next: int
    visits_required: int
    rewards_available: int
    reward_label: str


def class_body(slug: str, restaurant_name: str) -> dict:
    return {
        "id": class_id(slug),
        "issuerName": restaurant_name[:40],
        "programName": "Loyalty card",
        "programLogo": {
            "sourceUri": {"uri": wallet_settings().PUBLIC_APP_URL + LOGOS[slug]},
            "contentDescription": {"defaultValue": {"language": "en", "value": restaurant_name}},
        },
        "hexBackgroundColor": "#0b0a09",
        "reviewStatus": "UNDER_REVIEW",
    }


def object_body(card: Card) -> dict:
    return {
        "id": object_id(card.customer_id),
        "classId": class_id(card.slug),
        "state": "ACTIVE",
        "accountId": card.masked_phone,
        "accountName": card.member_name[:40],
        # Google caps a field value at ~15 characters.
        "loyaltyPoints": {"label": "Visits",
                          "balance": {"string": f"{card.toward_next} of {card.visits_required}"}},
        "secondaryLoyaltyPoints": {"label": "Rewards ready",
                                   "balance": {"int": card.rewards_available}},
        # The guest's own number: a 2D scanner at the till types it into the
        # customer phone field.
        "barcode": {"type": "QR_CODE", "value": card.phone, "alternateText": card.masked_phone},
        "textModulesData": [{
            "id": "rule",
            "header": "Reward",
            "body": f"{card.visits_required} visits = {card.reward_label}",
        }],
    }


def visit_message(card: Card) -> tuple[str, str]:
    """Notification header (Google: under 29 characters) and body after a visit."""
    if card.rewards_available > 0:
        return ("Your reward is ready",
                f"{card.reward_label} is waiting for you. Ask for it on your next visit.")
    left = card.visits_required - card.toward_next
    return ("Visit counted",
            f"{card.toward_next} of {card.visits_required} done. "
            f"{left} more visit{'' if left == 1 else 's'} to {card.reward_label}.")


def save_url(card: Card) -> str:
    """The "Add to Google Wallet" link. The class and object already exist
    (see `upsert`), so the signed payload carries only the object's ids and
    the link stays short."""
    key = _key()
    claims = {
        "iss": key["client_email"],
        "aud": "google",
        "typ": "savetowallet",
        "iat": int(time.time()),
        "origins": [wallet_settings().PUBLIC_APP_URL],
        "payload": {"loyaltyObjects": [{"id": object_id(card.customer_id),
                                        "classId": class_id(card.slug)}]},
    }
    return SAVE_URL + jwt.encode(claims, key["private_key"], algorithm="RS256")


# --- REST ------------------------------------------------------------------

_token: dict = {"value": None, "expires": 0.0}
_classes_ready: set[str] = set()


async def _access_token(client: httpx.AsyncClient) -> str:
    if _token["value"] and _token["expires"] > time.time() + 60:
        return _token["value"]
    key = _key()
    now = int(time.time())
    assertion = jwt.encode({"iss": key["client_email"], "scope": SCOPE, "aud": TOKEN_URL,
                            "iat": now, "exp": now + 3600},
                           key["private_key"], algorithm="RS256")
    r = await client.post(TOKEN_URL, data={
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion})
    if r.status_code != 200:
        raise WalletError(f"Google sign-in failed: {r.status_code} {r.text[:300]}")
    body = r.json()
    _token["value"] = body["access_token"]
    _token["expires"] = time.time() + int(body.get("expires_in", 3600))
    return _token["value"]


async def _call(client: httpx.AsyncClient, method: str, path: str, body: dict | None = None
                ) -> httpx.Response:
    token = await _access_token(client)
    return await client.request(method, f"{API}/{path}", json=body,
                                headers={"Authorization": f"Bearer {token}"})


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=10)


async def upsert(card: Card, client: httpx.AsyncClient | None = None) -> None:
    """Make sure the restaurant's class and the guest's card exist and are current."""
    own = client is None
    client = client or _client()
    try:
        cid = class_id(card.slug)
        if cid not in _classes_ready:
            r = await _call(client, "POST", "loyaltyClass", class_body(card.slug, card.restaurant_name))
            if r.status_code not in (200, 409):  # 409: made earlier, fine
                raise WalletError(f"Card design not created: {r.status_code} {r.text[:300]}")
            _classes_ready.add(cid)
        body = object_body(card)
        r = await _call(client, "POST", "loyaltyObject", body)
        if r.status_code == 409:
            r = await _call(client, "PATCH", f"loyaltyObject/{body['id']}", body)
        if r.status_code != 200:
            raise WalletError(f"Card not saved: {r.status_code} {r.text[:300]}")
    finally:
        if own:
            await client.aclose()


async def push_update(card: Card, notify: bool, client: httpx.AsyncClient | None = None) -> str:
    """Update a saved card; with `notify`, also send the visit notification.

    Returns 'updated', 'notified' or 'not_saved' (Google has no such card).
    Google allows 3 notifications per card per day; past that the card still
    updates, only the notification is dropped.
    """
    own = client is None
    client = client or _client()
    try:
        oid = object_id(card.customer_id)
        r = await _call(client, "PATCH", f"loyaltyObject/{oid}", object_body(card))
        if r.status_code == 404:
            return "not_saved"
        if r.status_code != 200:
            raise WalletError(f"Card not updated: {r.status_code} {r.text[:300]}")
        if not notify:
            return "updated"
        header, text = visit_message(card)
        r = await _call(client, "POST", f"loyaltyObject/{oid}/addMessage", {"message": {
            "id": f"visit_{uuid.uuid4().hex}", "header": header, "body": text,
            "messageType": "TEXT_AND_NOTIFY"}})
        if r.status_code != 200:
            logger.warning("Wallet notification not sent for %s: %s %s", oid, r.status_code,
                           r.text[:300])
            return "updated"
        return "notified"
    finally:
        if own:
            await client.aclose()
