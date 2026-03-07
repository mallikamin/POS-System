"""QuickBooks Online OAuth 2.0 service.

Handles the full OAuth lifecycle: authorization URL generation, code exchange,
token encryption/storage, token refresh, and connection management.

Intuit OAuth 2.0 spec:
  https://developer.intuit.com/app/developer/qbo/docs/develop/authentication-and-authorization/oauth-2.0

Token lifetimes (Intuit defaults):
  - Access token:  ~60 minutes
  - Refresh token: ~100 days (rolling -- each use extends by 100 days)
"""

import base64
import hashlib
import logging
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.quickbooks import QBConnection

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Token Encryption
# ---------------------------------------------------------------------------

# Fernet instance is derived once per process from SECRET_KEY.
# We cache it to avoid re-deriving on every encrypt/decrypt call.
_fernet_instance: Fernet | None = None


def _get_fernet() -> Fernet:
    """Derive a Fernet key from SECRET_KEY for encrypting QB tokens.

    Fernet requires a 32-byte URL-safe base64-encoded key.  We derive it
    deterministically from the application SECRET_KEY via SHA-256 so that
    tokens encrypted by one worker can be decrypted by another (all workers
    share the same SECRET_KEY).
    """
    global _fernet_instance
    if _fernet_instance is not None:
        return _fernet_instance

    raw = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(raw)  # 32 bytes -> 44-char b64
    _fernet_instance = Fernet(key)
    return _fernet_instance


def encrypt_token(token: str) -> str:
    """Encrypt a QB access/refresh token for database storage.

    Returns a URL-safe base64-encoded ciphertext string.
    """
    f = _get_fernet()
    return f.encrypt(token.encode("utf-8")).decode("utf-8")


def decrypt_token(encrypted: str) -> str:
    """Decrypt a stored QB token.

    Raises ValueError if decryption fails (wrong key, corrupted data, etc.).
    """
    f = _get_fernet()
    try:
        return f.decrypt(encrypted.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        raise ValueError(
            "Failed to decrypt QuickBooks token. "
            "This usually means SECRET_KEY has changed since the token was stored."
        )


# ---------------------------------------------------------------------------
# OAuth State Management (CSRF protection)
# ---------------------------------------------------------------------------

# In-memory state store.  Each entry is auto-expired after STATE_TTL_SECONDS.
# This is adequate for single-worker dev/staging.  For multi-worker production,
# swap this for a Redis-backed store keyed by `qb_oauth:{state}`.
_oauth_states: dict[str, dict] = {}
STATE_TTL_SECONDS = 600  # 10 minutes


def _purge_expired_states() -> None:
    """Remove expired state entries to prevent unbounded memory growth."""
    now = time.time()
    expired = [k for k, v in _oauth_states.items() if v.get("_expires_at", 0) < now]
    for k in expired:
        _oauth_states.pop(k, None)


def generate_auth_url(tenant_id: uuid.UUID, user_id: uuid.UUID) -> tuple[str, str]:
    """Generate a QuickBooks OAuth authorization URL with CSRF state.

    Returns:
        (authorization_url, state_token) tuple.

    The state token is stored in-memory and must be validated in the callback
    handler via ``validate_state()``.  Both tenant_id and user_id are stored
    so the callback (which is public / no JWT) can identify the user.

    Requested scopes:
        - com.intuit.quickbooks.accounting  (full QBO read/write)
    """
    if not settings.qb_configured:
        raise ValueError(
            "QuickBooks is not configured. "
            "Set QB_CLIENT_ID and QB_CLIENT_SECRET environment variables."
        )

    # Purge stale states on each generate call (cheap, bounded dict)
    _purge_expired_states()

    state = secrets.token_urlsafe(32)
    _oauth_states[state] = {
        "tenant_id": str(tenant_id),
        "user_id": str(user_id),
        "_expires_at": time.time() + STATE_TTL_SECONDS,
    }

    params = {
        "client_id": settings.QB_CLIENT_ID,
        "scope": "com.intuit.quickbooks.accounting",
        "redirect_uri": settings.QB_REDIRECT_URI,
        "response_type": "code",
        "state": state,
    }
    auth_url = f"{settings.qb_auth_url}?{urlencode(params)}"

    logger.info(
        "Generated QB OAuth URL for tenant=%s (state=%s...)",
        tenant_id,
        state[:8],
    )
    return auth_url, state


def validate_state(state: str) -> dict | None:
    """Validate and consume a CSRF state token.

    Returns the stored data dict (contains ``tenant_id``) on success,
    or None if the state is invalid, expired, or already consumed.

    The token is single-use: it is deleted after successful validation.
    """
    _purge_expired_states()

    data = _oauth_states.pop(state, None)
    if data is None:
        logger.warning("QB OAuth state validation failed: unknown or expired state")
        return None

    # Strip internal bookkeeping keys before returning
    return {k: v for k, v in data.items() if not k.startswith("_")}


# ---------------------------------------------------------------------------
# Intuit API Helpers
# ---------------------------------------------------------------------------


def _basic_auth_header() -> str:
    """Build the HTTP Basic Authorization header value for Intuit token endpoint.

    Intuit requires ``Authorization: Basic base64(client_id:client_secret)``.
    """
    credentials = f"{settings.QB_CLIENT_ID}:{settings.QB_CLIENT_SECRET}"
    encoded = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
    return f"Basic {encoded}"


# Shared httpx timeout for all Intuit API calls.
_INTUIT_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)


# ---------------------------------------------------------------------------
# Token Exchange & Storage
# ---------------------------------------------------------------------------


async def exchange_code_for_tokens(
    code: str,
    realm_id: str,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> QBConnection:
    """Exchange an OAuth authorization code for access + refresh tokens.

    Steps:
        1. POST to Intuit token endpoint with ``authorization_code`` grant.
        2. Encrypt both tokens for at-rest security.
        3. Fetch company info from the QBO API.
        4. Upsert a ``QBConnection`` record (if this realm was previously
           connected to this tenant, update rather than duplicate).

    Raises:
        httpx.HTTPStatusError: If the token endpoint returns a non-2xx status.
        ValueError: If the response body is missing expected fields.
    """
    # -- Step 1: Exchange code for tokens ----------------------------------
    logger.info(
        "Exchanging OAuth code for tokens (realm=%s, tenant=%s)", realm_id, tenant_id
    )

    async with httpx.AsyncClient(timeout=_INTUIT_TIMEOUT) as client:
        response = await client.post(
            settings.qb_token_url,
            headers={
                "Authorization": _basic_auth_header(),
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.QB_REDIRECT_URI,
            },
        )

    if response.status_code != 200:
        body = response.text
        logger.error(
            "QB token exchange failed: status=%d body=%s", response.status_code, body
        )
        raise ValueError(
            f"QuickBooks token exchange failed (HTTP {response.status_code}): {body}"
        )

    token_data = response.json()

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in", 3600)  # seconds, default 1 hour
    x_refresh_token_expires_in = token_data.get(
        "x_refresh_token_expires_in", 8726400
    )  # ~101 days

    if not access_token or not refresh_token:
        logger.error(
            "QB token response missing tokens (keys present: %s)",
            list(token_data.keys()),
        )
        raise ValueError(
            "QuickBooks token response is missing access_token or refresh_token"
        )

    # -- Step 2: Encrypt tokens --------------------------------------------
    now = datetime.now(timezone.utc)
    encrypted_access = encrypt_token(access_token)
    encrypted_refresh = encrypt_token(refresh_token)
    access_expires = now + timedelta(seconds=expires_in)
    refresh_expires = now + timedelta(seconds=x_refresh_token_expires_in)

    # -- Step 3: Fetch company info ----------------------------------------
    company_info: dict = {}
    try:
        company_info = await fetch_company_info(access_token, realm_id)
    except Exception:
        # Non-fatal: we can still store the connection without company info.
        # It can be fetched later.
        logger.warning(
            "Failed to fetch QB company info for realm=%s; continuing without it",
            realm_id,
            exc_info=True,
        )

    company_name = company_info.get("CompanyName", f"QuickBooks Company ({realm_id})")
    scope = token_data.get("scope", "com.intuit.quickbooks.accounting")

    # -- Step 4: Upsert QBConnection ---------------------------------------
    # Check if a connection for this tenant+realm already exists (re-connect scenario)
    result = await db.execute(
        select(QBConnection).where(
            QBConnection.tenant_id == tenant_id,
            QBConnection.realm_id == realm_id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing is not None:
        # Update existing connection (re-authorization flow)
        logger.info(
            "Updating existing QB connection id=%s for realm=%s",
            existing.id,
            realm_id,
        )
        existing.access_token_encrypted = encrypted_access
        existing.refresh_token_encrypted = encrypted_refresh
        existing.access_token_expires_at = access_expires
        existing.refresh_token_expires_at = refresh_expires
        existing.scope = scope
        existing.is_active = True
        existing.connected_by = user_id
        existing.connected_at = now
        existing.company_name = company_name
        existing.company_info = company_info
        connection = existing
    else:
        # Create new connection
        connection = QBConnection(
            tenant_id=tenant_id,
            realm_id=realm_id,
            company_name=company_name,
            access_token_encrypted=encrypted_access,
            refresh_token_encrypted=encrypted_refresh,
            access_token_expires_at=access_expires,
            refresh_token_expires_at=refresh_expires,
            scope=scope,
            is_active=True,
            connected_by=user_id,
            connected_at=now,
            company_info=company_info,
        )
        db.add(connection)

    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        logger.error("DB integrity error storing QB connection: %s", exc.orig)
        raise ValueError(f"Failed to store QuickBooks connection: {exc.orig}") from exc

    logger.info(
        "QB connection established: id=%s realm=%s company=%s",
        connection.id,
        realm_id,
        company_name,
    )
    return connection


async def refresh_access_token(
    connection: QBConnection, db: AsyncSession
) -> QBConnection:
    """Refresh an expired access token using the refresh token.

    Steps:
        1. Decrypt the stored refresh token.
        2. POST to Intuit token endpoint with ``refresh_token`` grant.
        3. Encrypt and store the new tokens (Intuit rotates both on refresh).
        4. If the refresh token is rejected (``invalid_grant``), mark the
           connection as inactive -- the user must re-authorize.

    Returns the updated QBConnection.

    Raises:
        ValueError: If the connection is inactive or token decryption fails.
    """
    if not connection.is_active:
        raise ValueError(
            f"QB connection {connection.id} is inactive. Re-authorization required."
        )

    try:
        current_refresh = decrypt_token(connection.refresh_token_encrypted)
    except ValueError:
        logger.error(
            "Cannot decrypt refresh token for QB connection %s; marking inactive",
            connection.id,
        )
        connection.is_active = False
        await db.flush()
        raise ValueError(
            "Failed to decrypt QuickBooks refresh token. "
            "The connection must be re-authorized."
        )

    logger.info("Refreshing QB access token for connection=%s", connection.id)

    async with httpx.AsyncClient(timeout=_INTUIT_TIMEOUT) as client:
        try:
            response = await client.post(
                settings.qb_token_url,
                headers={
                    "Authorization": _basic_auth_header(),
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": current_refresh,
                },
            )
        except httpx.RequestError as exc:
            logger.error(
                "Network error refreshing QB token for connection=%s: %s",
                connection.id,
                exc,
            )
            raise ValueError(
                "Network error contacting QuickBooks. Please try again."
            ) from exc

    if response.status_code != 200:
        body = response.text
        logger.error(
            "QB token refresh failed: status=%d body=%s (connection=%s)",
            response.status_code,
            body,
            connection.id,
        )

        # Intuit returns 400 with error=invalid_grant when the refresh token
        # is expired or revoked.  Mark the connection inactive so callers
        # know re-authorization is required.
        try:
            error_data = response.json()
        except Exception:
            error_data = {}

        error_code = error_data.get("error", "")
        if error_code == "invalid_grant" or response.status_code == 401:
            logger.warning(
                "QB refresh token is invalid/expired for connection=%s; "
                "marking inactive",
                connection.id,
            )
            connection.is_active = False
            await db.flush()
            raise ValueError(
                "QuickBooks refresh token has expired. "
                "Please reconnect your QuickBooks account."
            )

        raise ValueError(
            f"QuickBooks token refresh failed (HTTP {response.status_code}): {body}"
        )

    token_data = response.json()

    new_access = token_data.get("access_token")
    new_refresh = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in", 3600)
    x_refresh_token_expires_in = token_data.get("x_refresh_token_expires_in", 8726400)

    if not new_access or not new_refresh:
        logger.error(
            "QB refresh response missing tokens for connection=%s (keys: %s)",
            connection.id,
            list(token_data.keys()),
        )
        raise ValueError("QuickBooks refresh response is missing tokens")

    now = datetime.now(timezone.utc)
    connection.access_token_encrypted = encrypt_token(new_access)
    connection.refresh_token_encrypted = encrypt_token(new_refresh)
    connection.access_token_expires_at = now + timedelta(seconds=expires_in)
    connection.refresh_token_expires_at = now + timedelta(
        seconds=x_refresh_token_expires_in
    )

    await db.flush()

    logger.info(
        "QB access token refreshed for connection=%s (expires in %ds)",
        connection.id,
        expires_in,
    )
    return connection


async def ensure_valid_token(connection: QBConnection, db: AsyncSession) -> str:
    """Get a valid (non-expired) decrypted access token, refreshing if needed.

    This is the primary entry point for all QB API calls.  It guarantees
    that the returned token is valid for at least a few seconds (we refresh
    with a 5-minute buffer to avoid edge-case expiry during a request).

    Returns:
        The decrypted access token string, ready for an Authorization header.

    Raises:
        ValueError: If the connection is inactive, the refresh token is
            expired, or decryption fails.
    """
    if not connection.is_active:
        raise ValueError(
            "QuickBooks connection is inactive. Please reconnect your account."
        )

    now = datetime.now(timezone.utc)
    # Refresh 5 minutes before actual expiry to avoid mid-request expiration.
    buffer = timedelta(minutes=5)

    needs_refresh = (
        connection.access_token_expires_at is None
        or connection.access_token_expires_at <= (now + buffer)
    )

    if needs_refresh:
        # Check if the refresh token itself is expired before attempting
        if (
            connection.refresh_token_expires_at is not None
            and connection.refresh_token_expires_at <= now
        ):
            logger.warning(
                "QB refresh token expired for connection=%s; marking inactive",
                connection.id,
            )
            connection.is_active = False
            await db.flush()
            raise ValueError(
                "QuickBooks refresh token has expired. "
                "Please reconnect your QuickBooks account."
            )

        connection = await refresh_access_token(connection, db)

    return decrypt_token(connection.access_token_encrypted)


# ---------------------------------------------------------------------------
# Connection Management
# ---------------------------------------------------------------------------


async def get_connection(db: AsyncSession, tenant_id: uuid.UUID) -> QBConnection | None:
    """Get the active QuickBooks connection for a tenant.

    Returns None if no active connection exists.
    """
    result = await db.execute(
        select(QBConnection).where(
            QBConnection.tenant_id == tenant_id,
            QBConnection.is_active == True,  # noqa: E712
        )
    )
    return result.scalar_one_or_none()


async def disconnect(db: AsyncSession, tenant_id: uuid.UUID) -> bool:
    """Disconnect QuickBooks: revoke tokens at Intuit and mark connection inactive.

    Steps:
        1. Find the active connection for the tenant.
        2. Decrypt the refresh token.
        3. POST to Intuit's revoke endpoint (best-effort; we deactivate locally
           even if the revoke call fails, because the user's intent is clear).
        4. Set ``is_active = False`` on the connection.

    Returns True if a connection was found and deactivated, False if no
    active connection exists.
    """
    connection = await get_connection(db, tenant_id)
    if connection is None:
        logger.info("No active QB connection to disconnect for tenant=%s", tenant_id)
        return False

    # Attempt to revoke tokens at Intuit (best-effort)
    token_to_revoke: str | None = None
    try:
        token_to_revoke = decrypt_token(connection.refresh_token_encrypted)
    except ValueError:
        logger.warning(
            "Could not decrypt refresh token for revocation (connection=%s); "
            "proceeding with local disconnect only",
            connection.id,
        )

    if token_to_revoke:
        try:
            async with httpx.AsyncClient(timeout=_INTUIT_TIMEOUT) as client:
                revoke_response = await client.post(
                    settings.qb_revoke_url,
                    headers={
                        "Authorization": _basic_auth_header(),
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                    json={"token": token_to_revoke},
                )
            if revoke_response.status_code == 200:
                logger.info(
                    "Successfully revoked QB tokens at Intuit for connection=%s",
                    connection.id,
                )
            else:
                # Non-fatal: Intuit may return errors for already-revoked tokens.
                logger.warning(
                    "QB token revocation returned status=%d for connection=%s: %s",
                    revoke_response.status_code,
                    connection.id,
                    revoke_response.text,
                )
        except httpx.RequestError as exc:
            # Network error during revocation is non-fatal.  The token will
            # expire naturally, and we still deactivate locally.
            logger.warning(
                "Network error revoking QB tokens for connection=%s: %s",
                connection.id,
                exc,
            )

    # Deactivate locally regardless of Intuit revocation outcome
    connection.is_active = False
    await db.flush()

    logger.info(
        "QB connection %s disconnected for tenant=%s (realm=%s)",
        connection.id,
        tenant_id,
        connection.realm_id,
    )
    return True


# ---------------------------------------------------------------------------
# QuickBooks API Helpers
# ---------------------------------------------------------------------------


async def fetch_company_info(access_token: str, realm_id: str) -> dict:
    """Fetch company info from the QuickBooks Online API.

    Used during initial connection to populate ``company_name`` and
    ``company_info`` on the ``QBConnection`` record.

    Returns the ``CompanyInfo`` dict from the QBO response.

    Raises:
        ValueError: If the API returns a non-200 status or unexpected format.
        httpx.RequestError: On network errors.
    """
    url = f"{settings.qb_base_url}/v3/company/{realm_id}/companyinfo/{realm_id}"

    async with httpx.AsyncClient(timeout=_INTUIT_TIMEOUT) as client:
        response = await client.get(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
        )

    if response.status_code != 200:
        logger.error(
            "Failed to fetch QB company info: status=%d realm=%s body=%s",
            response.status_code,
            realm_id,
            response.text,
        )
        raise ValueError(
            f"Failed to fetch QuickBooks company info (HTTP {response.status_code})"
        )

    data = response.json()

    # The QBO API wraps the response in {"QueryResponse": ...} for queries,
    # but companyinfo returns {"CompanyInfo": {...}, "time": ...}
    company_info = data.get("CompanyInfo")
    if company_info is None:
        logger.error(
            "Unexpected QB company info response format for realm=%s: %s",
            realm_id,
            data,
        )
        raise ValueError("Unexpected response format from QuickBooks company info API")

    logger.info(
        "Fetched QB company info: name=%s realm=%s",
        company_info.get("CompanyName", "?"),
        realm_id,
    )
    return company_info
