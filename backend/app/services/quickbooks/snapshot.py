"""CoA Snapshot Service — backup and working-copy management.

On OAuth connect, we immediately fetch the partner's full Chart of Accounts
and store two copies:
  1. original_backup (locked, immutable) — the safety net
  2. working_copy (editable) — used for matching and mapping

The original_backup can be exported as JSON for git archival.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quickbooks import QBConnection, QBCoASnapshot
from app.services.quickbooks.client import QBClient

logger = logging.getLogger(__name__)


class SnapshotService:
    """Manages CoA snapshots for a QB connection."""

    def __init__(self, connection: QBConnection, db: AsyncSession):
        self.connection = connection
        self.db = db
        self.tenant_id = connection.tenant_id
        self.client = QBClient(connection, db)

    # -------------------------------------------------------------------
    # Core: Fetch & Create Snapshots
    # -------------------------------------------------------------------

    async def create_initial_snapshots(self) -> dict:
        """Fetch CoA from QB and create both backup + working copy.

        Called automatically after OAuth connect. If snapshots already
        exist for this connection, this creates a new versioned pair.
        """
        # 1. Fetch live CoA
        accounts = await self._fetch_live_accounts()
        now = datetime.now(timezone.utc)

        # 2. Determine version (increment if snapshots already exist)
        version = await self._next_version()

        company_name = self.connection.company_name or "Unknown"
        realm_id = self.connection.realm_id

        # 3. Create original_backup (locked)
        backup = QBCoASnapshot(
            tenant_id=self.tenant_id,
            connection_id=self.connection.id,
            snapshot_type="original_backup",
            coa_data=accounts,
            account_count=len(accounts),
            is_locked=True,
            fetched_at=now,
            qb_company_name=company_name,
            qb_realm_id=realm_id,
            notes=f"Auto-captured on connect (v{version})",
            version=version,
        )
        self.db.add(backup)
        await self.db.flush()

        # 4. Create working_copy (unlocked clone)
        working = QBCoASnapshot(
            tenant_id=self.tenant_id,
            connection_id=self.connection.id,
            snapshot_type="working_copy",
            coa_data=accounts,
            account_count=len(accounts),
            is_locked=False,
            fetched_at=now,
            qb_company_name=company_name,
            qb_realm_id=realm_id,
            notes=f"Working copy from v{version} backup",
            version=version,
        )
        self.db.add(working)
        await self.db.flush()

        logger.info(
            "Created CoA snapshots for %s (realm=%s): %d accounts, v%d",
            company_name, realm_id, len(accounts), version,
        )

        return {
            "backup_id": str(backup.id),
            "working_copy_id": str(working.id),
            "account_count": len(accounts),
            "version": version,
            "company_name": company_name,
            "fetched_at": now.isoformat(),
        }

    async def refresh_snapshots(self) -> dict:
        """Re-fetch CoA from QB and create a new versioned pair.

        Does NOT delete old snapshots — they're kept for audit trail.
        """
        return await self.create_initial_snapshots()

    # -------------------------------------------------------------------
    # Read
    # -------------------------------------------------------------------

    async def get_latest_backup(self) -> QBCoASnapshot | None:
        """Get the most recent original_backup snapshot."""
        stmt = (
            select(QBCoASnapshot)
            .where(
                and_(
                    QBCoASnapshot.tenant_id == self.tenant_id,
                    QBCoASnapshot.connection_id == self.connection.id,
                    QBCoASnapshot.snapshot_type == "original_backup",
                )
            )
            .order_by(QBCoASnapshot.version.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_working_copy(self) -> QBCoASnapshot | None:
        """Get the most recent working_copy snapshot."""
        stmt = (
            select(QBCoASnapshot)
            .where(
                and_(
                    QBCoASnapshot.tenant_id == self.tenant_id,
                    QBCoASnapshot.connection_id == self.connection.id,
                    QBCoASnapshot.snapshot_type == "working_copy",
                )
            )
            .order_by(QBCoASnapshot.version.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_snapshot(self, snapshot_id: str) -> QBCoASnapshot | None:
        """Get a specific snapshot by ID."""
        import uuid as _uuid
        stmt = select(QBCoASnapshot).where(
            and_(
                QBCoASnapshot.id == _uuid.UUID(snapshot_id),
                QBCoASnapshot.tenant_id == self.tenant_id,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_snapshots(self) -> list[QBCoASnapshot]:
        """List all snapshots for this connection."""
        stmt = (
            select(QBCoASnapshot)
            .where(
                and_(
                    QBCoASnapshot.tenant_id == self.tenant_id,
                    QBCoASnapshot.connection_id == self.connection.id,
                )
            )
            .order_by(QBCoASnapshot.version.desc(), QBCoASnapshot.snapshot_type)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # -------------------------------------------------------------------
    # Export
    # -------------------------------------------------------------------

    def export_as_json(self, snapshot: QBCoASnapshot) -> str:
        """Export snapshot as pretty-printed JSON string.

        This JSON can be committed to git for archival.
        """
        export_data = {
            "snapshot_id": str(snapshot.id),
            "snapshot_type": snapshot.snapshot_type,
            "version": snapshot.version,
            "is_locked": snapshot.is_locked,
            "qb_company_name": snapshot.qb_company_name,
            "qb_realm_id": snapshot.qb_realm_id,
            "account_count": snapshot.account_count,
            "fetched_at": snapshot.fetched_at.isoformat() if snapshot.fetched_at else None,
            "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
            "notes": snapshot.notes,
            "accounts": snapshot.coa_data,
        }
        return json.dumps(export_data, indent=2, ensure_ascii=False)

    # -------------------------------------------------------------------
    # Working copy accounts (for matching engine)
    # -------------------------------------------------------------------

    async def get_working_copy_accounts(self) -> list[dict] | None:
        """Get accounts from the latest working copy.

        Returns None if no working copy exists (caller should fetch live).
        """
        wc = await self.get_latest_working_copy()
        if wc is None:
            return None
        return wc.coa_data

    # -------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------

    async def _fetch_live_accounts(self) -> list[dict]:
        """Fetch full CoA from QB API."""
        try:
            raw = await self.client.query("Account", order_by="Name", max_results=1000)
        except Exception as exc:
            logger.error("Failed to fetch QB accounts for snapshot: %s", exc)
            raise RuntimeError(f"Failed to fetch QB accounts: {exc}") from exc

        return [
            {
                "id": str(a.get("Id", "")),
                "name": a.get("Name", ""),
                "account_type": a.get("AccountType", ""),
                "account_sub_type": a.get("AccountSubType"),
                "fully_qualified_name": a.get("FullyQualifiedName"),
                "current_balance": a.get("CurrentBalance", 0),
                "active": a.get("Active", True),
                "description": a.get("Description"),
                "account_number": a.get("AcctNum"),
            }
            for a in raw
        ]

    async def _next_version(self) -> int:
        """Get next version number for this connection's snapshots."""
        from sqlalchemy import func
        stmt = select(func.coalesce(func.max(QBCoASnapshot.version), 0)).where(
            and_(
                QBCoASnapshot.tenant_id == self.tenant_id,
                QBCoASnapshot.connection_id == self.connection.id,
            )
        )
        result = await self.db.execute(stmt)
        current_max = result.scalar_one()
        return current_max + 1
