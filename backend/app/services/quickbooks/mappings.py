"""QuickBooks Chart of Accounts mapping service.

Handles smart-default template application, CRUD for account mappings, QB account
discovery, and validation.  The mapping layer is the intelligence that connects
POS accounting concepts (food sales, tax payable, cash register, etc.) to specific
QuickBooks Chart of Accounts entries.

40 restaurant templates covering every cuisine, format, business model, and tax
jurisdiction.  Templates are imported from ``templates.py`` — the QB Playbook.
"""

import logging
import uuid
from typing import Any

from sqlalchemy import select, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quickbooks import QBConnection, QBAccountMapping, QBEntityMapping
from app.services.quickbooks.client import QBClient
from app.services.quickbooks.templates import MAPPING_TEMPLATES

logger = logging.getLogger(__name__)


# Mapping-type constants (re-exported from templates for backward compat)
_INCOME_TYPE = "income"
_COGS_TYPE = "cogs"
_TAX_PAYABLE_TYPE = "tax_payable"
_BANK_TYPE = "bank"
_EXPENSE_TYPE = "expense"
_OTHER_CURRENT_LIABILITY_TYPE = "other_current_liability"
_DISCOUNT_TYPE = "discount"
_ROUNDING_TYPE = "rounding"
_CASH_OVER_SHORT_TYPE = "cash_over_short"
_TIPS_TYPE = "tips"
_GIFT_CARD_TYPE = "gift_card_liability"
_SERVICE_CHARGE_TYPE = "service_charge"
_DELIVERY_FEE_TYPE = "delivery_fee"
_FOODPANDA_COMMISSION_TYPE = "foodpanda_commission"

# Required mapping types that must exist for sync to function.  If any of
# these are missing a default, ``validate_mappings`` flags it.
_REQUIRED_DEFAULT_TYPES = [
    _INCOME_TYPE,
    _COGS_TYPE,
    _TAX_PAYABLE_TYPE,
    _BANK_TYPE,
    _DISCOUNT_TYPE,
    _ROUNDING_TYPE,
    _CASH_OVER_SHORT_TYPE,
]


# ---------------------------------------------------------------------------
# MappingService
# ---------------------------------------------------------------------------

class MappingService:
    """Account mapping intelligence layer for QuickBooks integration.

    Manages the linkage between POS accounting concepts and QuickBooks Chart
    of Accounts entries.  Provides smart-default templates, CRUD, category-level
    lookup with fallback, QB account discovery, and pre-sync validation.
    """

    def __init__(self, connection: QBConnection, db: AsyncSession):
        self.connection = connection
        self.db = db
        self.tenant_id = connection.tenant_id
        self.client = QBClient(connection, db)

    # -----------------------------------------------------------------------
    # Smart Defaults
    # -----------------------------------------------------------------------

    async def apply_smart_defaults(
        self,
        template: str = "pakistani_restaurant",
        auto_create_accounts: bool = True,
    ) -> dict:
        """Apply a template of default account mappings.

        For each mapping in the template:
          1. Check if a mapping with the same mapping_type+name already exists.
          2. If not, and ``auto_create_accounts`` is True, find or create the
             matching account in QuickBooks.
          3. Save the QBAccountMapping record locally.

        Args:
            template: Key into ``MAPPING_TEMPLATES``.
            auto_create_accounts: When True, creates accounts in QB that don't
                already exist.  When False, skips mappings whose accounts cannot
                be found in QB.

        Returns:
            dict with keys: accounts_created, mappings_created, mappings_skipped,
            errors, details.
        """
        if template not in MAPPING_TEMPLATES:
            raise ValueError(
                f"Unknown template '{template}'. "
                f"Available: {', '.join(MAPPING_TEMPLATES.keys())}"
            )

        template_data = MAPPING_TEMPLATES[template]
        mapping_defs = template_data["mappings"]

        accounts_created = 0
        mappings_created = 0
        mappings_skipped = 0
        errors = 0
        details: list[str] = []

        # Pre-fetch existing mappings for this connection to do fast
        # duplicate detection without N queries.
        existing = await self._get_existing_mapping_index()

        for defn in mapping_defs:
            mapping_type: str = defn["mapping_type"]
            name: str = defn["name"]
            account_type: str = defn["account_type"]
            account_sub_type: str | None = defn.get("account_sub_type")
            is_default: bool = defn.get("is_default", False)
            description: str | None = defn.get("description")

            # Build a dedup key: type + name (global/default mappings have no
            # pos_reference_id so type+name is sufficient).
            dedup_key = (mapping_type, name)
            if dedup_key in existing:
                mappings_skipped += 1
                details.append(f"SKIP: {mapping_type}/{name} (already exists)")
                continue

            # Find or create the account in QB
            qb_account_id: str | None = None
            qb_account_name: str = name
            was_created = False

            if auto_create_accounts:
                try:
                    qb_account_id, qb_account_name, was_created = (
                        await self._find_or_create_account(
                            name=name,
                            account_type=account_type,
                            account_sub_type=account_sub_type,
                            description=description,
                        )
                    )
                    if was_created:
                        accounts_created += 1
                        details.append(
                            f"CREATED QB ACCOUNT: {qb_account_name} "
                            f"({account_type}/{account_sub_type})"
                        )
                except Exception as exc:
                    errors += 1
                    details.append(
                        f"ERROR creating account '{name}': {exc}"
                    )
                    logger.warning(
                        "Failed to find/create QB account '%s' for template '%s': %s",
                        name,
                        template,
                        exc,
                    )
                    continue
            else:
                # Try to find the account; skip if not found.
                try:
                    found = await self._find_account_by_name_and_type(
                        name=name, account_type=account_type
                    )
                    if found is None:
                        mappings_skipped += 1
                        details.append(
                            f"SKIP: {mapping_type}/{name} "
                            f"(account not found in QB, auto_create=False)"
                        )
                        continue
                    qb_account_id = found["id"]
                    qb_account_name = found["name"]
                except Exception as exc:
                    errors += 1
                    details.append(
                        f"ERROR searching account '{name}': {exc}"
                    )
                    logger.warning(
                        "Failed to search QB account '%s': %s", name, exc
                    )
                    continue

            # Save the mapping locally
            try:
                mapping = await self.create_mapping(
                    mapping_type=mapping_type,
                    qb_account_id=qb_account_id,  # type: ignore[arg-type]
                    qb_account_name=qb_account_name,
                    qb_account_type=account_type,
                    qb_account_sub_type=account_sub_type,
                    is_default=is_default,
                    _is_auto_created=True,
                )
                mappings_created += 1
                details.append(
                    f"MAPPED: {mapping_type}/{name} -> QB#{qb_account_id} "
                    f"({qb_account_name})"
                    + (" [DEFAULT]" if is_default else "")
                )
                # Update the local index so subsequent entries detect dupes.
                existing[dedup_key] = mapping
            except IntegrityError:
                await self.db.rollback()
                mappings_skipped += 1
                details.append(
                    f"SKIP: {mapping_type}/{name} (concurrent create / integrity)"
                )
            except Exception as exc:
                errors += 1
                details.append(
                    f"ERROR saving mapping '{mapping_type}/{name}': {exc}"
                )
                logger.warning(
                    "Failed to save mapping %s/%s: %s", mapping_type, name, exc
                )

        # Final flush to persist any remaining changes.
        try:
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            logger.warning("Integrity error during final flush of smart defaults")

        logger.info(
            "Smart defaults applied: template=%s created=%d skipped=%d errors=%d "
            "accounts_created=%d",
            template,
            mappings_created,
            mappings_skipped,
            errors,
            accounts_created,
        )

        return {
            "accounts_created": accounts_created,
            "mappings_created": mappings_created,
            "mappings_skipped": mappings_skipped,
            "errors": errors,
            "details": details,
        }

    async def _find_or_create_account(
        self,
        name: str,
        account_type: str,
        account_sub_type: str | None = None,
        description: str | None = None,
    ) -> tuple[str, str, bool]:
        """Find an existing QB account by name/type, or create it.

        Search strategy:
          1. Query QB for accounts matching name (case-insensitive, exact).
          2. If multiple matches, prefer the one with matching account_type.
          3. If no match and auto-create is desired, create the account via
             the QB API.

        Returns:
            (qb_account_id, qb_account_name, was_created)

        Raises:
            RuntimeError: If the account cannot be found or created.
        """
        # Step 1: Search by name
        found = await self._find_account_by_name_and_type(name, account_type)
        if found is not None:
            return found["id"], found["name"], False

        # Step 2: Create the account in QB
        logger.info(
            "Creating QB account: name='%s' type='%s' sub_type='%s'",
            name,
            account_type,
            account_sub_type,
        )

        create_payload: dict[str, Any] = {
            "Name": name,
            "AccountType": account_type,
        }
        if account_sub_type:
            create_payload["AccountSubType"] = account_sub_type
        if description:
            create_payload["Description"] = description

        try:
            result = await self.client.create("account", create_payload)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to create QB account '{name}' ({account_type}): {exc}"
            ) from exc

        # QB returns the created account inside an "Account" wrapper.
        account = result.get("Account", result)
        qb_id = str(account.get("Id", ""))
        qb_name = account.get("Name", name)

        if not qb_id:
            raise RuntimeError(
                f"QB account creation returned no ID for '{name}'. "
                f"Response: {result}"
            )

        logger.info(
            "Created QB account: id=%s name='%s' type='%s'",
            qb_id,
            qb_name,
            account_type,
        )
        return qb_id, qb_name, True

    async def _find_account_by_name_and_type(
        self, name: str, account_type: str
    ) -> dict | None:
        """Search QB for an account matching name and type.

        Returns a dict with 'id' and 'name' keys, or None if not found.
        Uses the QBO Query API with an exact name match.
        """
        # QB query language uses single quotes around string literals.
        # Escape single quotes in the account name.
        escaped_name = name.replace("'", "\\'")

        try:
            accounts = await self.client.query(
                "Account", where=f"Name = '{escaped_name}'"
            )
        except Exception as exc:
            logger.warning("QB account query failed for '%s': %s", name, exc)
            return None

        if not accounts:
            return None

        # Prefer exact type match if multiple accounts share the same name.
        for acct in accounts:
            if acct.get("AccountType") == account_type:
                return {"id": str(acct["Id"]), "name": acct["Name"]}

        # Fallback: return the first match even if type differs.
        first = accounts[0]
        return {"id": str(first["Id"]), "name": first["Name"]}

    async def _get_existing_mapping_index(
        self,
    ) -> dict[tuple[str, str], QBAccountMapping]:
        """Build an in-memory index of existing mappings for fast dedup.

        Key: (mapping_type, qb_account_name)
        """
        result = await self.db.execute(
            select(QBAccountMapping).where(
                and_(
                    QBAccountMapping.tenant_id == self.tenant_id,
                    QBAccountMapping.connection_id == self.connection.id,
                )
            )
        )
        mappings = result.scalars().all()
        return {
            (m.mapping_type, m.qb_account_name): m
            for m in mappings
        }

    # -----------------------------------------------------------------------
    # CRUD
    # -----------------------------------------------------------------------

    async def list_mappings(
        self, mapping_type: str | None = None
    ) -> list[QBAccountMapping]:
        """List all account mappings for this connection, optionally filtered.

        Args:
            mapping_type: If provided, only return mappings of this type
                (e.g. 'income', 'bank', 'tax_payable').

        Returns:
            List of QBAccountMapping ORM objects.
        """
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
        """Create a new account mapping.

        If ``is_default`` is True, any existing default mapping for the same
        mapping_type is demoted (is_default set to False) to enforce the
        invariant that at most one default exists per type.

        Args:
            mapping_type: Semantic purpose (income, cogs, bank, etc.).
            qb_account_id: QuickBooks account ID.
            qb_account_name: QuickBooks account display name.
            qb_account_type: QB top-level classification.
            qb_account_sub_type: QB sub-classification (optional).
            pos_reference_id: POS entity UUID for entity-specific mappings.
            pos_reference_type: POS entity type (category, payment_method, etc.).
            pos_reference_name: Human-readable POS entity name.
            is_default: Whether this should be the default for its mapping_type.
            _is_auto_created: Internal flag set when created by template application.

        Returns:
            The newly created QBAccountMapping.
        """
        # Enforce single-default invariant: demote existing default.
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
            "Created account mapping: type=%s name='%s' qb_id=%s default=%s "
            "pos_ref=%s tenant=%s",
            mapping_type,
            qb_account_name,
            qb_account_id,
            is_default,
            pos_reference_id,
            self.tenant_id,
        )
        return mapping

    async def update_mapping(
        self, mapping_id: uuid.UUID, **updates: Any
    ) -> QBAccountMapping:
        """Update an existing account mapping.

        Accepts keyword arguments matching QBAccountMapping column names.
        Unknown keys are silently ignored for forward-compatibility.

        If ``is_default`` is being set to True, the previous default for the
        same mapping_type is demoted.

        Raises:
            ValueError: If the mapping does not exist or belongs to a different
                tenant/connection.

        Returns:
            The updated QBAccountMapping.
        """
        mapping = await self._get_mapping_or_raise(mapping_id)

        # Allowed mutable fields.
        allowed = {
            "qb_account_id",
            "qb_account_name",
            "qb_account_type",
            "qb_account_sub_type",
            "pos_reference_id",
            "pos_reference_type",
            "pos_reference_name",
            "is_default",
            "mapping_type",
        }

        # If promoting to default, demote the current default first.
        if updates.get("is_default") is True and not mapping.is_default:
            target_type = updates.get("mapping_type", mapping.mapping_type)
            await self._demote_existing_default(target_type)

        applied = []
        for key, value in updates.items():
            if key in allowed and hasattr(mapping, key):
                setattr(mapping, key, value)
                applied.append(key)

        if not applied:
            logger.debug(
                "No applicable updates for mapping %s (keys: %s)",
                mapping_id,
                list(updates.keys()),
            )
            return mapping

        await self.db.flush()

        logger.info(
            "Updated mapping %s: fields=%s", mapping_id, applied
        )
        return mapping

    async def delete_mapping(self, mapping_id: uuid.UUID) -> bool:
        """Delete an account mapping.

        Raises:
            ValueError: If the mapping does not exist or belongs to a different
                tenant/connection.

        Returns:
            True on successful deletion.
        """
        mapping = await self._get_mapping_or_raise(mapping_id)
        await self.db.delete(mapping)
        await self.db.flush()

        logger.info(
            "Deleted mapping %s: type=%s name='%s'",
            mapping_id,
            mapping.mapping_type,
            mapping.qb_account_name,
        )
        return True

    async def get_default_mapping(
        self, mapping_type: str
    ) -> QBAccountMapping | None:
        """Get the default mapping for a mapping_type.

        Returns None if no default is configured for the given type.
        """
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
        """Get the income mapping for a specific menu category.

        Lookup order:
          1. Category-specific mapping (pos_reference_type='category',
             pos_reference_id=category_id).
          2. Default income mapping.

        This allows granular per-category revenue tracking (e.g. "BBQ & Grill
        Sales") while falling back to the catch-all "Food Sales" for categories
        that haven't been individually mapped.

        Returns None if no income mapping exists at all.
        """
        # Try category-specific first.
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

        # Fallback to default income.
        return await self.get_default_mapping(_INCOME_TYPE)

    # -----------------------------------------------------------------------
    # QB Account Discovery
    # -----------------------------------------------------------------------

    async def fetch_qb_accounts(self) -> list[dict]:
        """Fetch all accounts from QuickBooks for the mapping wizard UI.

        Returns a list of dicts with keys: id, name, account_type,
        account_sub_type, fully_qualified_name, current_balance, active.
        """
        try:
            raw_accounts = await self.client.query(
                "Account",
                where="Active = true",
                order_by="Name",
            )
        except Exception as exc:
            logger.error("Failed to fetch QB accounts: %s", exc)
            raise RuntimeError(
                f"Failed to fetch QuickBooks accounts: {exc}"
            ) from exc

        accounts = []
        for acct in raw_accounts:
            accounts.append({
                "id": str(acct.get("Id", "")),
                "name": acct.get("Name", ""),
                "account_type": acct.get("AccountType", ""),
                "account_sub_type": acct.get("AccountSubType"),
                "fully_qualified_name": acct.get("FullyQualifiedName"),
                "current_balance": acct.get("CurrentBalance"),
                "active": acct.get("Active", True),
            })

        logger.info("Fetched %d QB accounts for mapping wizard", len(accounts))
        return accounts

    async def get_available_templates(self) -> list[dict]:
        """Return available mapping templates with descriptions.

        Used by the frontend mapping wizard to display template choices.

        Returns:
            List of dicts with keys: template_name, name, description,
            mapping_count.
        """
        templates = []
        for key, data in MAPPING_TEMPLATES.items():
            templates.append({
                "template_name": key,
                "name": data["name"],
                "description": data["description"],
                "mapping_count": len(data["mappings"]),
            })
        return templates

    # -----------------------------------------------------------------------
    # Validation
    # -----------------------------------------------------------------------

    async def validate_mappings(self) -> dict:
        """Check if all required mappings exist for QB sync to function.

        Validates:
          1. Every required mapping_type has a default mapping.
          2. Every mapping's qb_account_id is still a non-empty string (basic
             sanity -- full QB-side validation would require an API call).
          3. Advisory warnings for categories without specific income mappings.

        Returns:
            {
                is_valid: bool,
                missing_required: list of missing mapping_type names,
                warnings: list of advisory messages,
                summary: {type: count} of existing mappings,
            }
        """
        all_mappings = await self.list_mappings()

        # Build a lookup: mapping_type -> list of mappings.
        by_type: dict[str, list[QBAccountMapping]] = {}
        for m in all_mappings:
            by_type.setdefault(m.mapping_type, []).append(m)

        missing_required: list[str] = []
        for req_type in _REQUIRED_DEFAULT_TYPES:
            type_mappings = by_type.get(req_type, [])
            has_default = any(m.is_default for m in type_mappings)
            if not has_default:
                missing_required.append(req_type)

        # Check for empty qb_account_id values (data corruption guard).
        warnings: list[str] = []
        for m in all_mappings:
            if not m.qb_account_id or not m.qb_account_id.strip():
                warnings.append(
                    f"Mapping '{m.qb_account_name}' ({m.mapping_type}) "
                    f"has an empty QB account ID -- it will not sync correctly"
                )

        # Advisory: check if there are categories without dedicated income
        # mappings (they'll use the default, which is fine but suboptimal
        # for detailed P&L reporting).
        category_mapped_ids = set()
        for m in by_type.get(_INCOME_TYPE, []):
            if m.pos_reference_type == "category" and m.pos_reference_id:
                category_mapped_ids.add(m.pos_reference_id)

        # We don't query categories here to avoid coupling this validation
        # to the menu module.  The frontend can cross-reference separately.
        # Instead, we just report how many categories have explicit mappings.
        if category_mapped_ids:
            warnings.append(
                f"{len(category_mapped_ids)} categories have explicit "
                f"income mappings; remaining categories use the default "
                f"income account"
            )
        else:
            default_income = by_type.get(_INCOME_TYPE, [])
            if default_income:
                warnings.append(
                    "No category-level income mappings configured -- all "
                    "food revenue will be recorded under the default income "
                    "account.  Consider mapping high-revenue categories "
                    "(e.g. BBQ, Karahi, Biryani) for better P&L visibility."
                )

        # Build summary counts.
        summary = {t: len(ms) for t, ms in by_type.items()}

        is_valid = len(missing_required) == 0

        logger.info(
            "Mapping validation: valid=%s missing=%s warnings=%d total_mappings=%d",
            is_valid,
            missing_required,
            len(warnings),
            len(all_mappings),
        )

        return {
            "is_valid": is_valid,
            "missing_required": missing_required,
            "warnings": warnings,
            "summary": summary,
        }

    # -----------------------------------------------------------------------
    # Internal Helpers
    # -----------------------------------------------------------------------

    async def _get_mapping_or_raise(
        self, mapping_id: uuid.UUID
    ) -> QBAccountMapping:
        """Fetch a mapping by ID, scoped to this tenant+connection.

        Raises ValueError if not found.
        """
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
            raise ValueError(
                f"Account mapping {mapping_id} not found for this connection"
            )
        return mapping

    async def _demote_existing_default(self, mapping_type: str) -> None:
        """Set is_default=False on any existing default for the given type.

        Ensures the single-default-per-type invariant is maintained before
        promoting a new mapping.
        """
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
            logger.debug(
                "Demoted previous default mapping for type '%s': %s",
                mapping_type,
                existing_default.id,
            )
