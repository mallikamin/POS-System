"""QuickBooks Web Connector (QWC) file generator.

QWC files are XML configuration files that users import into QBWC to set up
the connection between QBWC and our server. The file contains the server URL,
authentication credentials, and polling schedule.

Once imported, QBWC will automatically poll our server at the specified interval
(default: every 15 minutes) to fetch and process QBXML requests.
"""

import uuid
from datetime import datetime, timezone


def generate_qwc_file(
    tenant_id: uuid.UUID,
    connection_id: uuid.UUID,
    username: str,
    password: str,
    server_url: str,
    app_name: str = "Sitara POS",
    poll_interval_minutes: int = 15,
) -> str:
    """Generate a QWC XML file for QuickBooks Web Connector.

    Args:
        tenant_id: POS tenant UUID
        connection_id: QB connection UUID
        username: QBWC username (stored in qb_connections.qbwc_username)
        password: QBWC password (plain text, user sets this once)
        server_url: Full URL to QBWC SOAP endpoint (e.g., https://pos-demo.duckdns.org/api/v1/qbwc/)
        app_name: Application display name in QBWC
        poll_interval_minutes: How often QBWC should poll (min: 1, max: 30)

    Returns:
        QWC XML file content as string.

    Usage:
        qwc_xml = generate_qwc_file(
            tenant_id=tenant.id,
            connection_id=conn.id,
            username="tenant_abc123",
            password="secure_password",
            server_url="https://pos-demo.duckdns.org/api/v1/qbwc/",
        )
        # User downloads this file and imports into QBWC
    """
    # Validate poll interval
    if not (1 <= poll_interval_minutes <= 30):
        poll_interval_minutes = 15

    # Generate unique IDs for QBWC (must be stable across downloads for same connection)
    owner_id = f"{{{str(connection_id).upper()}}}"  # GUID format with braces
    file_id = f"{{{str(tenant_id).upper()}}}"

    # Build QWC XML
    qwc_xml = f"""<?xml version="1.0"?>
<QBWCXML>
    <AppName>{app_name}</AppName>
    <AppID></AppID>
    <AppURL>{server_url}</AppURL>
    <AppDescription>QuickBooks Desktop integration for Sitara POS - syncs orders, payments, customers, and menu items.</AppDescription>
    <AppSupport>{server_url.replace('/api/v1/qbwc/', '/support')}</AppSupport>
    <UserName>{username}</UserName>
    <OwnerID>{owner_id}</OwnerID>
    <FileID>{file_id}</FileID>
    <QBType>QBFS</QBType>
    <Scheduler>
        <RunEveryNMinutes>{poll_interval_minutes}</RunEveryNMinutes>
    </Scheduler>
    <IsReadOnly>false</IsReadOnly>
</QBWCXML>"""

    return qwc_xml


def generate_qwc_filename(tenant_name: str, connection_id: uuid.UUID) -> str:
    """Generate a safe filename for the QWC file.

    Args:
        tenant_name: Tenant/restaurant name
        connection_id: QB connection UUID

    Returns:
        Filename string (e.g., "sitara_pos_bpoworld_abc123.qwc")
    """
    # Sanitize tenant name (remove special chars, lowercase, replace spaces with _)
    safe_name = "".join(
        c if c.isalnum() or c in (" ", "_", "-") else ""
        for c in tenant_name.lower()
    )
    safe_name = safe_name.replace(" ", "_").strip("_")[:30]  # Max 30 chars

    # Use first 8 chars of connection_id for uniqueness
    conn_short = str(connection_id)[:8]

    return f"sitara_pos_{safe_name}_{conn_short}.qwc"
