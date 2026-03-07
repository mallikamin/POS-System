"""
QB Account Matching Service (Attempt 2 — client-centric, no templates).

Flow:
  1. JV Partner connects QB via OAuth
  2. We pull their Chart of Accounts
  3. For each POS accounting need, fuzzy-match against their QB accounts
  4. Partner reviews matches, customizes, saves
  5. Mappings are created — sync starts

No template selection step. The POS declares what it needs, the fuzzy
engine finds the best matches in whatever QB company is connected.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quickbooks import QBConnection, QBAccountMapping
from app.services.quickbooks.client import QBClient
from app.services.quickbooks.fuzzy_match import (
    find_best_matches,
    suggest_mapping_type,
    THRESHOLD_HIGH,
    THRESHOLD_MEDIUM,
)
from app.services.quickbooks.pos_needs import (
    POS_ACCOUNTING_NEEDS,
    AccountingNeed,
)

logger = logging.getLogger(__name__)

# In-memory match result store. For the onboarding workflow this is fine:
# results are created, reviewed, and applied within a single admin session.
_match_store: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_match_item(need: AccountingNeed, candidates: list) -> dict:
    """Build a single match item for one POS need."""
    best = candidates[0] if candidates else None

    if best and best.score >= THRESHOLD_HIGH:
        status = "matched"
    elif best and best.score >= THRESHOLD_MEDIUM:
        status = "candidates"
    else:
        status = "unmatched"

    return {
        "need_key": need.key,
        "need_label": need.label,
        "need_description": need.description,
        "expected_qb_types": need.expected_qb_types,
        "expected_qb_sub_type": need.expected_qb_sub_type,
        "required": need.required,
        "status": status,
        "best_match": best.to_dict() if best else None,
        "candidates": [c.to_dict() for c in candidates],
        # Decision fields — filled by admin during review
        "decision": "use_existing" if status == "matched" else None,
        "decision_account_id": best.qb_account_id if status == "matched" else None,
        "decision_account_name": best.qb_account_name if status == "matched" else None,
    }


def _compute_grade(matched: int, candidates: int, total: int) -> str:
    """Health grade based on coverage."""
    if total == 0:
        return "A"
    covered = (matched + candidates) / total
    if matched / total >= 1.0:
        return "A"
    elif covered >= 0.90:
        return "A"
    elif covered >= 0.60:
        return "B"
    elif covered >= 0.40:
        return "C"
    return "F"


# ---------------------------------------------------------------------------
# MatchingService — the core of Attempt 2
# ---------------------------------------------------------------------------


class MatchingService:
    """
    Matches POS accounting needs directly against a JV partner's
    QB Chart of Accounts. No templates involved.
    """

    def __init__(self, connection: QBConnection | None, db: AsyncSession):
        self.connection = connection
        self.db = db
        self.tenant_id = connection.tenant_id if connection else None
        self.client = QBClient(connection, db) if connection else None

    # -------------------------------------------------------------------
    # Run Matching
    # -------------------------------------------------------------------

    async def run_matching(
        self,
        *,
        qb_accounts: list[dict] | None = None,
    ) -> dict:
        """
        Match POS accounting needs against QB Chart of Accounts.

        Args:
            qb_accounts: If provided, use these directly (for testing).
                          Otherwise fetches from live QB.

        Returns:
            Full match result dict (also stored in _match_store).
        """
        # 1. Get QB accounts
        if qb_accounts is not None:
            accounts = qb_accounts
        elif self.client:
            accounts = await self._fetch_live_accounts()
        else:
            raise ValueError(
                "No QB connection or accounts provided. Connect to QuickBooks first."
            )

        # 2. For each POS need, fuzzy-match against QB accounts
        items: list[dict] = []
        matched_account_ids: set[str] = set()
        matched_count = 0
        candidate_count = 0
        unmatched_count = 0

        for need in POS_ACCOUNTING_NEEDS:
            # Build a search name from the need's label + hints
            # The fuzzy engine will score each QB account against this
            search_name = need.label

            # Use the first expected type for type matching
            search_type = (
                need.expected_qb_types[0] if need.expected_qb_types else "Income"
            )

            candidates = find_best_matches(
                template_name=search_name,
                template_type=search_type,
                template_sub_type=need.expected_qb_sub_type,
                qb_accounts=accounts,
                max_candidates=5,
                min_score=0.15,
            )

            # Also try matching with each search hint to find better matches
            for hint in need.search_hints:
                hint_candidates = find_best_matches(
                    template_name=hint,
                    template_type=search_type,
                    template_sub_type=need.expected_qb_sub_type,
                    qb_accounts=accounts,
                    max_candidates=3,
                    min_score=0.15,
                )
                # Merge — keep the best score per QB account
                existing_ids = {c.qb_account_id for c in candidates}
                for hc in hint_candidates:
                    if hc.qb_account_id not in existing_ids:
                        candidates.append(hc)
                        existing_ids.add(hc.qb_account_id)
                    else:
                        # Update score if this hint produced a better match
                        for i, existing in enumerate(candidates):
                            if (
                                existing.qb_account_id == hc.qb_account_id
                                and hc.score > existing.score
                            ):
                                candidates[i] = hc
                                break

            # Re-sort and trim to top 5
            candidates.sort(key=lambda c: c.score, reverse=True)
            candidates = candidates[:5]

            item = _build_match_item(need, candidates)
            items.append(item)

            if item["status"] == "matched" and item["best_match"]:
                matched_account_ids.add(item["best_match"]["qb_account_id"])
                matched_count += 1
            elif item["status"] == "candidates":
                candidate_count += 1
            else:
                unmatched_count += 1

        # 3. Find unmapped QB accounts (partner has but POS doesn't need)
        unmapped_qb: list[dict] = []
        for acct in accounts:
            acct_id = str(acct.get("id", ""))
            if acct_id not in matched_account_ids:
                suggested = suggest_mapping_type(
                    acct.get("name", ""),
                    acct.get("account_type", ""),
                )
                unmapped_qb.append(
                    {
                        "qb_account_id": acct_id,
                        "qb_account_name": acct.get("name", ""),
                        "qb_account_type": acct.get("account_type", ""),
                        "qb_account_sub_type": acct.get("account_sub_type"),
                        "fully_qualified_name": acct.get("fully_qualified_name"),
                        "active": acct.get("active", True),
                        "suggested_mapping_type": suggested,
                    }
                )

        total = len(POS_ACCOUNTING_NEEDS)
        required_total = sum(1 for n in POS_ACCOUNTING_NEEDS if n.required)
        required_matched = sum(
            1 for item in items if item["required"] and item["status"] == "matched"
        )
        grade = _compute_grade(matched_count, candidate_count, total)

        # 4. Build result
        result_id = str(uuid.uuid4())
        result = {
            "id": result_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "is_live": qb_accounts is None,
            "total_needs": total,
            "total_qb_accounts": len(accounts),
            "matched": matched_count,
            "candidates": candidate_count,
            "unmatched": unmatched_count,
            "required_total": required_total,
            "required_matched": required_matched,
            "coverage_pct": round(matched_count / total * 100, 1) if total else 0,
            "health_grade": grade,
            "items": items,
            "unmapped_qb_accounts": unmapped_qb,
        }

        _match_store[result_id] = result
        logger.info(
            "Account matching %s: grade=%s, matched=%d, candidates=%d, unmatched=%d",
            result_id,
            grade,
            matched_count,
            candidate_count,
            unmatched_count,
        )

        return result

    # -------------------------------------------------------------------
    # Get / List Results
    # -------------------------------------------------------------------

    @staticmethod
    def get_result(result_id: str) -> dict | None:
        return _match_store.get(result_id)

    @staticmethod
    def list_results() -> list[dict]:
        results = []
        for r in _match_store.values():
            results.append(
                {
                    "id": r["id"],
                    "created_at": r["created_at"],
                    "health_grade": r["health_grade"],
                    "matched": r["matched"],
                    "candidates": r["candidates"],
                    "unmatched": r["unmatched"],
                    "total_needs": r["total_needs"],
                    "coverage_pct": r["coverage_pct"],
                    "is_live": r.get("is_live", False),
                }
            )
        return sorted(results, key=lambda x: x["created_at"], reverse=True)

    # -------------------------------------------------------------------
    # Update Decisions
    # -------------------------------------------------------------------

    @staticmethod
    def update_decisions(result_id: str, decisions: list[dict]) -> dict:
        """
        Update admin decisions on match results.

        Each decision: {"index": 0, "decision": "use_existing"|"create_new"|"skip",
                        "qb_account_id": "123", "qb_account_name": "Food Sales"}
        """
        result = _match_store.get(result_id)
        if not result:
            raise ValueError(f"Match result '{result_id}' not found")

        items = result["items"]
        for dec in decisions:
            idx = dec.get("index")
            if idx is None or idx < 0 or idx >= len(items):
                continue

            item = items[idx]
            decision = dec.get("decision", "")
            if decision not in ("use_existing", "create_new", "skip"):
                continue

            item["decision"] = decision
            if decision == "use_existing":
                item["decision_account_id"] = dec.get("qb_account_id")
                item["decision_account_name"] = dec.get("qb_account_name")
            else:
                item["decision_account_id"] = None
                item["decision_account_name"] = None

        # Recompute decision summary
        use_existing = sum(1 for i in items if i["decision"] == "use_existing")
        create_new = sum(1 for i in items if i["decision"] == "create_new")
        skipped = sum(1 for i in items if i["decision"] == "skip")
        pending = sum(1 for i in items if i["decision"] is None)

        result["decision_summary"] = {
            "use_existing": use_existing,
            "create_new": create_new,
            "skip": skipped,
            "pending": pending,
            "ready_to_apply": pending == 0,
        }

        return result

    # -------------------------------------------------------------------
    # Apply Decisions
    # -------------------------------------------------------------------

    async def apply_decisions(self, result_id: str) -> dict:
        """
        Apply admin decisions — create QB accounts and POS mappings.
        """
        result = _match_store.get(result_id)
        if not result:
            raise ValueError(f"Match result '{result_id}' not found")

        if not self.connection:
            raise ValueError("QB connection required to apply decisions")

        items = result["items"]
        pending = [i for i in items if i.get("decision") is None]
        if pending:
            raise ValueError(
                f"{len(pending)} item(s) still pending. "
                "Review all items before applying."
            )

        accounts_created = 0
        mappings_created = 0
        skipped = 0
        errors: list[str] = []
        details: list[str] = []

        for idx, item in enumerate(items):
            decision = item["decision"]

            if decision == "skip":
                skipped += 1
                details.append(f"Skipped: {item['need_label']} ({item['need_key']})")
                continue

            try:
                if decision == "use_existing":
                    qb_id = item["decision_account_id"]
                    qb_name = item["decision_account_name"]
                    if not qb_id:
                        errors.append(f"Item {idx}: use_existing but no qb_account_id")
                        continue

                    # Get the QB account type from the candidate
                    qb_type = (
                        item["expected_qb_types"][0]
                        if item["expected_qb_types"]
                        else "Income"
                    )
                    if (
                        item["best_match"]
                        and item["best_match"]["qb_account_id"] == qb_id
                    ):
                        qb_type = item["best_match"]["qb_account_type"]

                    await self._create_mapping(
                        mapping_type=item["need_key"],
                        qb_account_id=qb_id,
                        qb_account_name=qb_name or item["need_label"],
                        qb_account_type=qb_type,
                        qb_account_sub_type=item.get("expected_qb_sub_type"),
                        is_default=True,
                    )
                    mappings_created += 1
                    details.append(
                        f"Mapped: {item['need_label']} -> {qb_name} (QB {qb_id})"
                    )

                elif decision == "create_new":
                    if not self.client:
                        errors.append("No QB client available")
                        continue

                    try:
                        qb_type = (
                            item["expected_qb_types"][0]
                            if item["expected_qb_types"]
                            else "Income"
                        )
                        new_acct = await self.client.create_account(
                            name=item["need_label"],
                            account_type=qb_type,
                            account_sub_type=item.get("expected_qb_sub_type"),
                        )
                        qb_id = str(new_acct.get("Id", new_acct.get("id", "")))
                        qb_name = new_acct.get("Name", new_acct.get("name", ""))
                        accounts_created += 1
                    except Exception as exc:
                        errors.append(
                            f"Failed to create QB account '{item['need_label']}': {exc}"
                        )
                        continue

                    await self._create_mapping(
                        mapping_type=item["need_key"],
                        qb_account_id=qb_id,
                        qb_account_name=qb_name,
                        qb_account_type=qb_type,
                        qb_account_sub_type=item.get("expected_qb_sub_type"),
                        is_default=True,
                    )
                    mappings_created += 1
                    details.append(
                        f"Created: {qb_name} (QB {qb_id}) + mapped as {item['need_key']}"
                    )

            except Exception as exc:
                errors.append(f"Item {idx} ({item['need_label']}): {exc}")

        apply_result = {
            "accounts_created": accounts_created,
            "mappings_created": mappings_created,
            "skipped": skipped,
            "errors": errors,
            "details": details,
            "result_id": result_id,
        }

        result["apply_result"] = apply_result
        result["applied_at"] = datetime.now(timezone.utc).isoformat()

        logger.info(
            "Applied matching %s: created=%d accounts + %d mappings, skipped=%d, errors=%d",
            result_id,
            accounts_created,
            mappings_created,
            skipped,
            len(errors),
        )

        return apply_result

    # -------------------------------------------------------------------
    # Health Check (unchanged — checks existing mappings against live QB)
    # -------------------------------------------------------------------

    async def health_check(self) -> dict:
        """Check existing mappings against live QB accounts."""
        if not self.connection or not self.client:
            raise ValueError("QB connection required for health check")

        live_accounts = await self._fetch_live_accounts()
        acct_by_id: dict[str, dict] = {str(a.get("id", "")): a for a in live_accounts}

        stmt = select(QBAccountMapping).where(
            and_(
                QBAccountMapping.tenant_id == self.tenant_id,
                QBAccountMapping.connection_id == self.connection.id,
            )
        )
        result = await self.db.execute(stmt)
        mappings = result.scalars().all()

        healthy = 0
        warnings = 0
        critical = 0
        details: list[dict] = []

        for m in mappings:
            qb_acct = acct_by_id.get(m.qb_account_id)

            if qb_acct is None:
                critical += 1
                details.append(
                    {
                        "mapping_id": str(m.id),
                        "mapping_type": m.mapping_type,
                        "qb_account_id": m.qb_account_id,
                        "qb_account_name": m.qb_account_name,
                        "status": "critical",
                        "issue": "account_deleted",
                        "message": f"QB account '{m.qb_account_name}' no longer exists.",
                        "current_name": None,
                    }
                )
            elif not qb_acct.get("active", True):
                critical += 1
                details.append(
                    {
                        "mapping_id": str(m.id),
                        "mapping_type": m.mapping_type,
                        "qb_account_id": m.qb_account_id,
                        "qb_account_name": m.qb_account_name,
                        "status": "critical",
                        "issue": "account_deactivated",
                        "message": f"QB account '{m.qb_account_name}' is deactivated.",
                        "current_name": qb_acct.get("name"),
                    }
                )
            elif qb_acct.get("name") != m.qb_account_name:
                warnings += 1
                details.append(
                    {
                        "mapping_id": str(m.id),
                        "mapping_type": m.mapping_type,
                        "qb_account_id": m.qb_account_id,
                        "qb_account_name": m.qb_account_name,
                        "status": "warning",
                        "issue": "account_renamed",
                        "message": f"Renamed from '{m.qb_account_name}' to '{qb_acct.get('name')}'.",
                        "current_name": qb_acct.get("name"),
                    }
                )
            else:
                healthy += 1
                details.append(
                    {
                        "mapping_id": str(m.id),
                        "mapping_type": m.mapping_type,
                        "qb_account_id": m.qb_account_id,
                        "qb_account_name": m.qb_account_name,
                        "status": "healthy",
                        "issue": None,
                        "message": "OK",
                        "current_name": qb_acct.get("name"),
                    }
                )

        total = len(mappings)
        if total == 0:
            grade = "F"
        elif critical == 0 and warnings == 0:
            grade = "A"
        elif critical == 0:
            grade = "B"
        elif critical <= total * 0.3:
            grade = "C"
        else:
            grade = "F"

        return {
            "grade": grade,
            "total_mappings": total,
            "healthy": healthy,
            "warnings": warnings,
            "critical": critical,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "details": details,
        }

    # -------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------

    async def _fetch_live_accounts(self) -> list[dict]:
        if not self.client:
            raise ValueError("No QB client available")
        try:
            raw = await self.client.query("Account", order_by="Name", max_results=1000)
        except Exception as exc:
            logger.error("Failed to fetch QB accounts: %s", exc)
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
            }
            for a in raw
        ]

    async def _create_mapping(
        self,
        mapping_type: str,
        qb_account_id: str,
        qb_account_name: str,
        qb_account_type: str,
        qb_account_sub_type: str | None,
        is_default: bool,
    ) -> QBAccountMapping:
        # Check for existing
        stmt = select(QBAccountMapping).where(
            and_(
                QBAccountMapping.connection_id == self.connection.id,
                QBAccountMapping.tenant_id == self.tenant_id,
                QBAccountMapping.mapping_type == mapping_type,
                QBAccountMapping.qb_account_name == qb_account_name,
            )
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            logger.info(
                "Mapping already exists: %s -> %s", mapping_type, qb_account_name
            )
            return existing

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
            is_default=is_default,
            is_auto_created=True,
        )
        self.db.add(mapping)
        await self.db.flush()
        return mapping

    async def _demote_existing_default(self, mapping_type: str) -> None:
        stmt = select(QBAccountMapping).where(
            and_(
                QBAccountMapping.connection_id == self.connection.id,
                QBAccountMapping.tenant_id == self.tenant_id,
                QBAccountMapping.mapping_type == mapping_type,
                QBAccountMapping.is_default.is_(True),
            )
        )
        result = await self.db.execute(stmt)
        for m in result.scalars().all():
            m.is_default = False
        await self.db.flush()
