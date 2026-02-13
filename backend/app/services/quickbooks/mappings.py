"""QuickBooks Chart of Accounts mapping service (Attempt 2 — no templates).

Handles CRUD for account mappings, QB account discovery, and validation.
The mapping layer connects POS accounting concepts to specific QuickBooks
Chart of Accounts entries.

Template system removed — mappings are created by the MatchingService
after fuzzy-matching POS needs against the partner's QB accounts.
"""

import logging
import uuid
from typing import Any

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quickbooks import QBConnection, QBAccountMapping, QBEntityMapping
from app.services.quickbooks.client import QBClient
from app.services.quickbooks.pos_needs import REQUIRED_NEEDS

logger = logging.getLogger(__name__)

_INCOME_TYPE = "income"


class MappingService:
    """Account mapping CRUD + validation for QuickBooks integration."""

    def __init__(self, connection: QBConnection, db: AsyncSession):
        self.connection = connection
        self.db = db
        self.tenant_id = connection.tenant_id
        self.client = QBClient(connection, db)

    # -----------------------------------------------------------------------
    # CRUD
    # -----------------------------------------------------------------------

    async def list_mappings(
        self, mapping_type: str | None = None
    ) -> list[QBAccountMapping]:
        stmt = select(QBAccountMapping).where(
            and_(
                QBAccountMapping.tenant_id == self.tenant_id,
                QBAccountMapping.connection_id == self.connection.id,
            )
        )
        if mapping_type is not None:
            stmt = stmt.where(QBAccountMapping.mapping_type == mapping_type)

        stmt = stmt.order_by(
            QBAccountMapping.mapping_type,
            QBAccountMapping.is_default.desc(),
            QBAccountMapping.qb_account_name,
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_mapping(
        self,
        mapping_type: str,
        qb_account_id: str,
        qb_account_name: str,
        qb_account_type: str,
        qb_account_sub_type: str | None = None,
        pos_reference_id: uuid.UUID | None = None,
        pos_reference_type: str | None = None,
        pos_reference_name: str | None = None,
        is_default: bool = False,
        _is_auto_created: bool = False,
    ) -> QBAccountMapping:
        if is_default:
            await self._demote_existing_default(mapping_type)

        mapping = QBAccountMapping(
            tenant_id=self.tenant_id,
            connection_id=self.connection.id,
            mapping_type=mapping_type,
            qb_account_id=qb_account_id,
            qb_account_name=qb_account_name,
            qb_account_type=qb_account_type,
            qb_account_sub_type=qb_account_sub_type,
            pos_reference_id=pos_reference_id,
            pos_reference_type=pos_reference_type,
            pos_reference_name=pos_reference_name,
            is_default=is_default,
            is_auto_created=_is_auto_created,
        )
        self.db.add(mapping)
        await self.db.flush()

        logger.info(
            "Created mapping: type=%s name='%s' qb_id=%s default=%s",
            mapping_type, qb_account_name, qb_account_id, is_default,
        )
        return mapping

    async def update_mapping(
        self, mapping_id: uuid.UUID, **updates: Any
    ) -> QBAccountMapping:
        mapping = await self._get_mapping_or_raise(mapping_id)

        allowed = {
            "qb_account_id", "qb_account_name", "qb_account_type",
            "qb_account_sub_type", "pos_reference_id", "pos_reference_type",
            "pos_reference_name", "is_default", "mapping_type",
        }

        if updates.get("is_default") is True and not mapping.is_default:
            target_type = updates.get("mapping_type", mapping.mapping_type)
            await self._demote_existing_default(target_type)

        applied = []
        for key, value in updates.items():
            if key in allowed and hasattr(mapping, key):
                setattr(mapping, key, value)
                applied.append(key)

        if applied:
            await self.db.flush()
            logger.info("Updated mapping %s: fields=%s", mapping_id, applied)

        return mapping

    async def delete_mapping(self, mapping_id: uuid.UUID) -> bool:
        mapping = await self._get_mapping_or_raise(mapping_id)
        await self.db.delete(mapping)
        await self.db.flush()
        logger.info("Deleted mapping %s", mapping_id)
        return True

    async def get_default_mapping(
        self, mapping_type: str
    ) -> QBAccountMapping | None:
        result = await self.db.execute(
            select(QBAccountMapping).where(
                and_(
                    QBAccountMapping.tenant_id == self.tenant_id,
                    QBAccountMapping.connection_id == self.connection.id,
                    QBAccountMapping.mapping_type == mapping_type,
                    QBAccountMapping.is_default == True,  # noqa: E712
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_mapping_for_category(
        self, category_id: uuid.UUID
    ) -> QBAccountMapping | None:
        result = await self.db.execute(
            select(QBAccountMapping).where(
                and_(
                    QBAccountMapping.tenant_id == self.tenant_id,
                    QBAccountMapping.connection_id == self.connection.id,
                    QBAccountMapping.mapping_type == _INCOME_TYPE,
                    QBAccountMapping.pos_reference_type == "category",
                    QBAccountMapping.pos_reference_id == category_id,
                )
            )
        )
        specific = result.scalar_one_or_none()
        if specific is not None:
            return specific
        return await self.get_default_mapping(_INCOME_TYPE)

    # -----------------------------------------------------------------------
    # QB Account Discovery
    # -----------------------------------------------------------------------

    async def fetch_qb_accounts(self) -> list[dict]:
        try:
            raw_accounts = await self.client.query(
                "Account", where="Active = true", order_by="Name",
            )
        except Exception as exc:
            logger.error("Failed to fetch QB accounts: %s", exc)
            raise RuntimeError(f"Failed to fetch QuickBooks accounts: {exc}") from exc

        return [
            {
                "id": str(acct.get("Id", "")),
                "name": acct.get("Name", ""),
                "account_type": acct.get("AccountType", ""),
                "account_sub_type": acct.get("AccountSubType"),
                "fully_qualified_name": acct.get("FullyQualifiedName"),
                "current_balance": acct.get("CurrentBalance"),
                "active": acct.get("Active", True),
            }
            for acct in raw_accounts
        ]

    # -----------------------------------------------------------------------
    # Validation
    # -----------------------------------------------------------------------

    async def validate_mappings(self) -> dict:
        all_mappings = await self.list_mappings()
        by_type: dict[str, list[QBAccountMapping]] = {}
        for m in all_mappings:
            by_type.setdefault(m.mapping_type, []).append(m)

        missing_required: list[str] = []
        for need in REQUIRED_NEEDS:
            type_mappings = by_type.get(need.key, [])
            has_default = any(m.is_default for m in type_mappings)
            if not has_default:
                missing_required.append(need.key)

        warnings: list[str] = []
        for m in all_mappings:
            if not m.qb_account_id or not m.qb_account_id.strip():
                warnings.append(
                    f"Mapping '{m.qb_account_name}' ({m.mapping_type}) "
                    f"has an empty QB account ID"
                )

        summary = {t: len(ms) for t, ms in by_type.items()}
        is_valid = len(missing_required) == 0

        return {
            "is_valid": is_valid,
            "missing_required": missing_required,
            "warnings": warnings,
            "summary": summary,
        }

    # -----------------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------------

    async def _get_mapping_or_raise(self, mapping_id: uuid.UUID) -> QBAccountMapping:
        result = await self.db.execute(
            select(QBAccountMapping).where(
                and_(
                    QBAccountMapping.id == mapping_id,
                    QBAccountMapping.tenant_id == self.tenant_id,
                    QBAccountMapping.connection_id == self.connection.id,
                )
            )
        )
        mapping = result.scalar_one_or_none()
        if mapping is None:
            raise ValueError(f"Account mapping {mapping_id} not found")
        return mapping

    async def _demote_existing_default(self, mapping_type: str) -> None:
        result = await self.db.execute(
            select(QBAccountMapping).where(
                and_(
                    QBAccountMapping.tenant_id == self.tenant_id,
                    QBAccountMapping.connection_id == self.connection.id,
                    QBAccountMapping.mapping_type == mapping_type,
                    QBAccountMapping.is_default == True,  # noqa: E712
                )
            )
        )
        existing_default = result.scalar_one_or_none()
        if existing_default is not None:
            existing_default.is_default = False
