"""QuickBooks Web Connector (QBWC) SOAP endpoint.

This endpoint implements the QBWC protocol for QuickBooks Desktop integration.
QBWC is a Windows application that polls this endpoint periodically (default: every 15 minutes)
to fetch queued QBXML requests and deliver responses back to our system.

Protocol flow:
1. QBWC calls authenticate() → we return a session ticket
2. QBWC calls sendRequestXML() → we return the next queued QBXML request
3. QBWC processes in QB Desktop → QB returns QBXML response
4. QBWC calls receiveResponseXML() → we process the response
5. Steps 2-4 repeat until no more requests in queue
6. QBWC calls closeConnection() → session ends

QBWC spec: https://developer.intuit.com/app/developer/qbdesktop/docs/develop
"""

import logging
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from lxml import etree
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.quickbooks import QBConnection, QBSyncJob
from app.services.quickbooks.oauth import decrypt_token, encrypt_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/qbwc", tags=["qbwc"])

# ---------------------------------------------------------------------------
# Session Management (Redis-backed in production, in-memory for dev)
# ---------------------------------------------------------------------------

# In-memory session store: {ticket: {tenant_id, connection_id, username, started_at}}
# TODO: Move to Redis for multi-worker prod deployment
_qbwc_sessions: dict[str, dict] = {}
SESSION_TTL_SECONDS = 3600  # 1 hour


def _create_session(
    username: str, tenant_id: uuid.UUID, connection_id: uuid.UUID
) -> str:
    """Generate a unique session ticket for QBWC."""
    ticket = secrets.token_urlsafe(32)
    _qbwc_sessions[ticket] = {
        "username": username,
        "tenant_id": str(tenant_id),
        "connection_id": str(connection_id),
        "started_at": time.time(),
        "expires_at": time.time() + SESSION_TTL_SECONDS,
    }
    logger.info(
        "Created QBWC session: ticket=%s... username=%s tenant=%s",
        ticket[:8],
        username,
        tenant_id,
    )
    return ticket


def _get_session(ticket: str) -> dict | None:
    """Retrieve session data by ticket. Returns None if expired or invalid."""
    session = _qbwc_sessions.get(ticket)
    if not session:
        return None

    # Check expiry
    if time.time() > session.get("expires_at", 0):
        _qbwc_sessions.pop(ticket, None)
        logger.warning("QBWC session expired: ticket=%s...", ticket[:8])
        return None

    return session


def _close_session(ticket: str) -> None:
    """Remove session from store."""
    _qbwc_sessions.pop(ticket, None)
    logger.info("Closed QBWC session: ticket=%s...", ticket[:8])


# ---------------------------------------------------------------------------
# SOAP XML Helpers
# ---------------------------------------------------------------------------


def _parse_soap_body(xml_str: str) -> etree._Element:
    """Parse SOAP XML and return the Body element."""
    try:
        root = etree.fromstring(xml_str.encode("utf-8"))
        # SOAP Body is typically: {http://schemas.xmlsoap.org/soap/envelope/}Body
        body = root.find(".//{http://schemas.xmlsoap.org/soap/envelope/}Body")
        if body is None:
            raise ValueError("No SOAP Body found")
        return body
    except Exception as e:
        logger.error("Failed to parse SOAP XML: %s", e, exc_info=True)
        raise ValueError(f"Invalid SOAP XML: {e}") from e


def _build_soap_response(method_name: str, content: str) -> str:
    """Build a SOAP response envelope.

    Args:
        method_name: QBWC method name (e.g., "authenticateResponse")
        content: The inner XML content (e.g., "<authenticateResult>...</authenticateResult>")
    """
    soap_template = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <soap:Body>
    <{method_name} xmlns="http://developer.intuit.com/">
      {content}
    </{method_name}>
  </soap:Body>
</soap:Envelope>"""
    return soap_template


# ---------------------------------------------------------------------------
# QBWC Protocol Methods
# ---------------------------------------------------------------------------


async def _authenticate(
    username: str, password: str, db: AsyncSession
) -> tuple[str, str]:
    """Authenticate QBWC client.

    Returns:
        (ticket, company_file_path) tuple. If auth fails, ticket is empty string or error code.

    QBWC ticket return values:
    - UUID string: Success, proceed with session
    - "" (empty): Invalid credentials
    - "nvu": Invalid user
    - "none": No work to do (valid user, but no pending requests)
    """
    logger.info("QBWC authenticate request: username=%s", username)

    # Find connection by qbwc_username
    result = await db.execute(
        select(QBConnection).where(
            QBConnection.qbwc_username == username,
            QBConnection.connection_type == "desktop",
            QBConnection.is_active == True,  # noqa: E712
        )
    )
    connection = result.scalar_one_or_none()

    if not connection:
        logger.warning("QBWC auth failed: unknown username=%s", username)
        return ("nvu", "")  # Invalid user

    # Verify password
    try:
        stored_password = decrypt_token(connection.qbwc_password_encrypted)
    except ValueError:
        logger.error(
            "Failed to decrypt QBWC password for connection=%s", connection.id
        )
        return ("", "")

    if password != stored_password:
        logger.warning("QBWC auth failed: incorrect password for username=%s", username)
        return ("", "")

    # Check if there's work to do (pending sync jobs)
    pending_result = await db.execute(
        select(QBSyncJob)
        .where(
            QBSyncJob.connection_id == connection.id,
            QBSyncJob.status == "pending",
        )
        .limit(1)
    )
    has_pending = pending_result.scalar_one_or_none() is not None

    if not has_pending:
        logger.info("QBWC auth: no pending work for username=%s", username)
        return ("none", "")

    # Success: create session
    ticket = _create_session(username, connection.tenant_id, connection.id)

    # Update last poll time
    connection.last_qbwc_poll_at = datetime.now(timezone.utc)
    await db.commit()

    company_file = connection.company_file_path or ""
    logger.info("QBWC auth success: username=%s ticket=%s...", username, ticket[:8])
    return (ticket, company_file)


async def _send_request_xml(ticket: str, db: AsyncSession) -> str:
    """Fetch the next QBXML request for QBWC to process.

    Returns:
        - QBXML string: Next request to send to QB Desktop
        - "" (empty): No more requests, QBWC will call closeConnection
    """
    session = _get_session(ticket)
    if not session:
        logger.error("sendRequestXML called with invalid ticket")
        return ""

    connection_id = uuid.UUID(session["connection_id"])

    # Fetch next pending job (FIFO by priority, then created_at)
    result = await db.execute(
        select(QBSyncJob)
        .where(
            QBSyncJob.connection_id == connection_id,
            QBSyncJob.status == "pending",
            QBSyncJob.request_xml.isnot(None),
        )
        .order_by(QBSyncJob.priority, QBSyncJob.created_at)
        .limit(1)
    )
    job = result.scalar_one_or_none()

    if not job:
        logger.info("sendRequestXML: no more pending jobs for ticket=%s...", ticket[:8])
        return ""

    # Mark as processing
    job.status = "processing"
    job.started_at = datetime.now(timezone.utc)
    job.qbwc_fetched_at = datetime.now(timezone.utc)
    await db.commit()

    logger.info(
        "sendRequestXML: returning job_id=%s type=%s for ticket=%s...",
        job.id,
        job.job_type,
        ticket[:8],
    )
    return job.request_xml


async def _receive_response_xml(
    ticket: str, response: str, db: AsyncSession
) -> int:
    """Process QBXML response from QB Desktop.

    Returns:
        - Percentage complete (0-100). QBWC will continue if < 100.
        - Return 100 when no more work.
    """
    session = _get_session(ticket)
    if not session:
        logger.error("receiveResponseXML called with invalid ticket")
        return 100  # End session

    connection_id = uuid.UUID(session["connection_id"])

    # Find the job that was just processed (most recent "processing" job for this connection)
    result = await db.execute(
        select(QBSyncJob)
        .where(
            QBSyncJob.connection_id == connection_id,
            QBSyncJob.status == "processing",
            QBSyncJob.qbwc_fetched_at.isnot(None),
        )
        .order_by(QBSyncJob.qbwc_fetched_at.desc())
        .limit(1)
    )
    job = result.scalar_one_or_none()

    if not job:
        logger.warning(
            "receiveResponseXML: no processing job found for ticket=%s...", ticket[:8]
        )
        return 100

    # Store response
    job.response_xml = response
    job.completed_at = datetime.now(timezone.utc)

    # Parse response to determine success/failure
    from app.services.quickbooks.qbxml.parsers import parse_qbxml_response

    try:
        parse_result = parse_qbxml_response(response)

        if parse_result.success:
            job.status = "completed"
            # Store QB-assigned IDs in result JSON
            job.result = {
                "txn_id": parse_result.txn_id,
                "list_id": parse_result.list_id,
                "time_created": parse_result.time_created,
                "status_message": parse_result.status_message,
            }
            logger.info(
                "QBXML response processed successfully for job_id=%s: txn_id=%s list_id=%s",
                job.id,
                parse_result.txn_id,
                parse_result.list_id,
            )
        else:
            job.status = "failed"
            job.error_message = parse_result.user_message or parse_result.status_message
            job.error_detail = {
                "status_code": parse_result.status_code,
                "status_severity": parse_result.status_severity,
                "status_message": parse_result.status_message,
            }
            logger.warning(
                "QBXML response error for job_id=%s: code=%s message=%s",
                job.id,
                parse_result.status_code,
                parse_result.status_message,
            )
    except Exception as e:
        # Parser failed (malformed XML or unexpected format)
        job.status = "failed"
        job.error_message = f"Failed to parse QBXML response: {e}"
        logger.error(
            "QBXML parser failed for job_id=%s: %s", job.id, e, exc_info=True
        )

    await db.commit()

    # Check if more pending jobs exist
    pending_result = await db.execute(
        select(QBSyncJob)
        .where(
            QBSyncJob.connection_id == connection_id,
            QBSyncJob.status == "pending",
        )
        .limit(1)
    )
    has_more = pending_result.scalar_one_or_none() is not None

    if has_more:
        # Return < 100 to tell QBWC to call sendRequestXML again
        return 50  # Arbitrary progress indicator
    else:
        # All done
        return 100


async def _get_last_error(ticket: str) -> str:
    """Return last error message for debugging.

    Called by QBWC when an error occurs.
    """
    session = _get_session(ticket)
    if not session:
        return "Invalid session"

    # TODO: Store and return actual error from last failed operation
    return "No error"


async def _close_connection(ticket: str) -> str:
    """Clean up session after QBWC finishes.

    Returns:
        "OK" or error message.
    """
    _close_session(ticket)
    logger.info("closeConnection called for ticket=%s...", ticket[:8])
    return "OK"


# ---------------------------------------------------------------------------
# FastAPI SOAP Endpoint (Single POST handler)
# ---------------------------------------------------------------------------


@router.post("/", include_in_schema=False)
async def qbwc_soap_handler(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Unified SOAP endpoint for all QBWC methods.

    QBWC sends SOAP POST requests to this endpoint. We parse the SOAP envelope
    to determine which method is being called, then dispatch to the appropriate handler.
    """
    # Read raw request body
    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8")

    logger.debug("QBWC SOAP request received: %s...", body_str[:200])

    try:
        soap_body = _parse_soap_body(body_str)
    except ValueError as e:
        logger.error("Invalid SOAP request: %s", e)
        return Response(
            content="Invalid SOAP request",
            media_type="text/xml",
            status_code=400,
        )

    # Determine which QBWC method was called
    # Methods are in namespace: http://developer.intuit.com/
    ns = {"qbwc": "http://developer.intuit.com/"}

    # Check each method
    if soap_body.find(".//qbwc:authenticate", ns) is not None:
        # authenticate(strUserName, strPassword)
        auth_elem = soap_body.find(".//qbwc:authenticate", ns)
        username = auth_elem.findtext(".//qbwc:strUserName", default="", namespaces=ns)
        password = auth_elem.findtext(".//qbwc:strPassword", default="", namespaces=ns)

        ticket, company_file = await _authenticate(username, password, db)

        response_content = f"""
            <authenticateResult>
                <string>{ticket}</string>
                <string>{company_file}</string>
            </authenticateResult>
        """
        soap_response = _build_soap_response("authenticateResponse", response_content)

    elif soap_body.find(".//qbwc:sendRequestXML", ns) is not None:
        # sendRequestXML(ticket, strHCPResponse, strCompanyFileName, qbXMLCountry, qbXMLMajorVers, qbXMLMinorVers)
        send_elem = soap_body.find(".//qbwc:sendRequestXML", ns)
        ticket = send_elem.findtext(".//qbwc:ticket", default="", namespaces=ns)

        qbxml_request = await _send_request_xml(ticket, db)

        response_content = f"""
            <sendRequestXMLResult>{qbxml_request}</sendRequestXMLResult>
        """
        soap_response = _build_soap_response("sendRequestXMLResponse", response_content)

    elif soap_body.find(".//qbwc:receiveResponseXML", ns) is not None:
        # receiveResponseXML(ticket, response, hresult, message)
        recv_elem = soap_body.find(".//qbwc:receiveResponseXML", ns)
        ticket = recv_elem.findtext(".//qbwc:ticket", default="", namespaces=ns)
        response_xml = recv_elem.findtext(".//qbwc:response", default="", namespaces=ns)

        percentage = await _receive_response_xml(ticket, response_xml, db)

        response_content = f"""
            <receiveResponseXMLResult>{percentage}</receiveResponseXMLResult>
        """
        soap_response = _build_soap_response(
            "receiveResponseXMLResponse", response_content
        )

    elif soap_body.find(".//qbwc:getLastError", ns) is not None:
        # getLastError(ticket)
        error_elem = soap_body.find(".//qbwc:getLastError", ns)
        ticket = error_elem.findtext(".//qbwc:ticket", default="", namespaces=ns)

        error_msg = await _get_last_error(ticket)

        response_content = f"""
            <getLastErrorResult>{error_msg}</getLastErrorResult>
        """
        soap_response = _build_soap_response("getLastErrorResponse", response_content)

    elif soap_body.find(".//qbwc:closeConnection", ns) is not None:
        # closeConnection(ticket)
        close_elem = soap_body.find(".//qbwc:closeConnection", ns)
        ticket = close_elem.findtext(".//qbwc:ticket", default="", namespaces=ns)

        result = await _close_connection(ticket)

        response_content = f"""
            <closeConnectionResult>{result}</closeConnectionResult>
        """
        soap_response = _build_soap_response("closeConnectionResponse", response_content)

    else:
        logger.error("Unknown QBWC method in SOAP request")
        return Response(
            content="Unknown QBWC method",
            media_type="text/xml",
            status_code=400,
        )

    logger.debug("QBWC SOAP response: %s...", soap_response[:200])
    return Response(content=soap_response, media_type="text/xml")
