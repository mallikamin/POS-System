"""Audit logging service -- records user actions for compliance and debugging."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


async def log_action(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
    user_name: str | None = None,
    entity_type: str,
    entity_id: uuid.UUID | None = None,
    action: str,
    changes: dict | None = None,
    ip_address: str | None = None,
    detail: str | None = None,
) -> None:
    """Record an audit log entry.

    This should be called after the action succeeds (inside the same transaction).
    It intentionally does NOT commit — the caller's transaction handles that.

    Args:
        db: Database session (should be in an active transaction).
        tenant_id: Tenant scope.
        user_id: User who performed the action (None for system actions).
        user_name: Denormalized user name for quick reads.
        entity_type: Type of entity acted upon (order, user, payment, config, etc.).
        entity_id: UUID of the specific entity.
        action: What was done (create, update, delete, void, status_change, login, etc.).
        changes: Dict of field changes: {"field": {"old": X, "new": Y}}.
        ip_address: Client IP if available.
        detail: Free-text additional context.
    """
    try:
        async with db.begin_nested():
            entry = AuditLog(
                tenant_id=tenant_id,
                user_id=user_id,
                user_name=user_name,
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                changes=changes,
                ip_address=ip_address,
                detail=detail,
            )
            db.add(entry)
            await db.flush()
    except Exception:
        # Audit logging is non-critical — never break the main operation.
        # The SAVEPOINT (begin_nested) ensures only the audit insert is
        # rolled back, not the caller's pending work.
        pass
