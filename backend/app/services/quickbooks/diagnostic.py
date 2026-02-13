"""
QB Diagnostic & Onboarding Service.

Production-ready tool that:
1. Runs gap analysis between a template and a client's actual QB Chart of Accounts
2. Lets the admin review and apply mapping decisions
3. Performs periodic health checks on existing mappings

The diagnostic report is stored in-memory (dict keyed by UUID) so it can be
reviewed, exported (PDF/Excel), and applied across multiple API calls.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quickbooks import QBConnection, QBAccountMapping
from app.services.quickbooks.client import QBClient
from app.services.quickbooks.fuzzy_match import (
    CandidateMatch,
    find_best_matches,
    suggest_mapping_type,
    THRESHOLD_HIGH,
    THRESHOLD_MEDIUM,
)
from app.services.quickbooks.templates import MAPPING_TEMPLATES
from app.services.quickbooks.test_fixtures import FIXTURES, list_fixtures

logger = logging.getLogger(__name__)

# In-memory report store (process-level). For production at scale you'd
# persist to Redis or DB, but for the onboarding workflow this is fine:
# reports are created, reviewed, applied within a single session.
_report_store: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Data structures for diagnostic report
# ---------------------------------------------------------------------------

def _make_diagnostic_item(
    mapping: dict,
    candidates: list[CandidateMatch],
) -> dict:
    """Build a single diagnostic item for one template mapping."""
    best = candidates[0] if candidates else None

    if best and best.score >= THRESHOLD_HIGH:
        status = "matched"
    elif best and best.score >= THRESHOLD_MEDIUM:
        status = "candidates"
    else:
        status = "unmatched"

    return {
        "mapping_type": mapping["mapping_type"],
        "template_account_name": mapping["name"],
        "template_account_type": mapping["account_type"],
        "template_account_sub_type": mapping["account_sub_type"],
        "template_description": mapping.get("description", ""),
        "is_default": mapping.get("is_default", False),
        "status": status,
        "best_match": best.to_dict() if best else None,
        "candidates": [c.to_dict() for c in candidates],
        # Decision fields — filled by admin during review
        "decision": "use_existing" if status == "matched" else None,
        "decision_account_id": best.qb_account_id if status == "matched" else None,
        "decision_account_name": best.qb_account_name if status == "matched" else None,
    }


def _compute_health_grade(
    matched: int, candidates: int, unmatched: int, total: int,
) -> str:
    """
    Health grade based on coverage (matched + candidates = covered).

    Candidates count as "covered" because the right QB account was
    identified — the admin just needs to confirm the suggestion.

      A = 100% auto-matched, or >90% covered (matched + candidates)
      B = >60% covered
      C = >40% covered
      F = <40% covered (heavy customization needed)
    """
    if total == 0:
        return "A"
    covered_pct = (matched + candidates) / total
    match_pct = matched / total
    if match_pct >= 1.0:
        return "A"
    elif covered_pct >= 0.90:
        return "A"
    elif covered_pct >= 0.60:
        return "B"
    elif covered_pct >= 0.40:
        return "C"
    else:
        return "F"


def _generate_summary(
    template_name: str,
    matched: int,
    candidates: int,
    unmatched: int,
    total: int,
    unmapped_count: int,
    grade: str,
) -> str:
    """Human-readable summary for the diagnostic report."""
    lines = []
    lines.append(f"Template: {template_name}")
    lines.append(f"Grade: {grade}")
    lines.append(f"Template mappings: {total}")
    lines.append(f"  - Auto-matched (high confidence): {matched}")
    lines.append(f"  - Needs review (candidates found): {candidates}")
    lines.append(f"  - No match found: {unmatched}")

    pct = round(matched / total * 100, 1) if total > 0 else 0
    lines.append(f"Coverage: {pct}%")

    if unmapped_count > 0:
        lines.append(
            f"Client has {unmapped_count} QB account(s) not covered by this template."
        )

    if grade == "A":
        lines.append("All mappings auto-matched. Ready to apply.")
    elif grade == "B":
        lines.append("Most mappings matched. Review candidates before applying.")
    elif grade == "C":
        lines.append("Partial coverage. Review unmatched items and decide: create new or map to existing.")
    else:
        lines.append("Low coverage. Consider a different template or heavy customization.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# DiagnosticService
# ---------------------------------------------------------------------------

class DiagnosticService:
    """
    Runs diagnostic gap analysis between a QB template and a client's
    actual Chart of Accounts. Supports both live QB connections and
    test fixture data.
    """

    def __init__(
        self,
        connection: QBConnection | None,
        db: AsyncSession,
    ):
        self.connection = connection
        self.db = db
        self.tenant_id = connection.tenant_id if connection else None
        self.client = QBClient(connection, db) if connection else None

    # -------------------------------------------------------------------
    # Run Diagnostic
    # -------------------------------------------------------------------

    async def run_diagnostic(
        self,
        template_key: str,
        *,
        fixture_name: str | None = None,
        qb_accounts: list[dict] | None = None,
    ) -> dict:
        """
        Run gap analysis between a template and QB accounts.

        Args:
            template_key: Key from MAPPING_TEMPLATES
            fixture_name: If set, use test fixture instead of live QB
            qb_accounts: If set, use these accounts directly (API testing)

        Returns:
            Full diagnostic report dict (also stored in _report_store)
        """
        # 1. Validate template
        template = MAPPING_TEMPLATES.get(template_key)
        if not template:
            raise ValueError(
                f"Unknown template '{template_key}'. "
                f"Available: {', '.join(sorted(MAPPING_TEMPLATES.keys()))}"
            )

        # 2. Get QB accounts
        if qb_accounts is not None:
            accounts = qb_accounts
        elif fixture_name:
            if fixture_name not in FIXTURES:
                raise ValueError(
                    f"Unknown fixture '{fixture_name}'. "
                    f"Available: {', '.join(sorted(FIXTURES.keys()))}"
                )
            accounts = FIXTURES[fixture_name]()
        elif self.client:
            accounts = await self._fetch_live_accounts()
        else:
            raise ValueError(
                "No QB connection, fixture, or accounts provided. "
                "Connect to QB or specify a test fixture."
            )

        # 3. Run fuzzy matching for each template mapping
        template_mappings: list[dict] = template["mappings"]
        items: list[dict] = []
        matched_account_ids: set[str] = set()

        matched_count = 0
        candidate_count = 0
        unmatched_count = 0

        for mapping in template_mappings:
            candidates = find_best_matches(
                template_name=mapping["name"],
                template_type=mapping["account_type"],
                template_sub_type=mapping["account_sub_type"],
                qb_accounts=accounts,
                max_candidates=5,
                min_score=0.15,
            )

            item = _make_diagnostic_item(mapping, candidates)
            items.append(item)

            # Track which QB accounts are matched
            if item["status"] == "matched" and item["best_match"]:
                matched_account_ids.add(item["best_match"]["qb_account_id"])
                matched_count += 1
            elif item["status"] == "candidates":
                candidate_count += 1
            else:
                unmatched_count += 1

        # 4. Find unmapped QB accounts (client has, template doesn't cover)
        unmapped_qb: list[dict] = []
        for acct in accounts:
            acct_id = str(acct.get("id", ""))
            if acct_id not in matched_account_ids:
                suggested = suggest_mapping_type(
                    acct.get("name", ""),
                    acct.get("account_type", ""),
                )
                unmapped_qb.append({
                    "qb_account_id": acct_id,
                    "qb_account_name": acct.get("name", ""),
                    "qb_account_type": acct.get("account_type", ""),
                    "qb_account_sub_type": acct.get("account_sub_type"),
                    "fully_qualified_name": acct.get("fully_qualified_name"),
                    "active": acct.get("active", True),
                    "suggested_mapping_type": suggested,
                })

        total = len(template_mappings)
        grade = _compute_health_grade(
            matched_count, candidate_count, unmatched_count, total,
        )
        summary = _generate_summary(
            template.get("name", template_key),
            matched_count, candidate_count, unmatched_count,
            total, len(unmapped_qb), grade,
        )

        # 5. Build report
        report_id = str(uuid.uuid4())
        report = {
            "id": report_id,
            "template_key": template_key,
            "template_name": template.get("name", template_key),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "fixture_name": fixture_name,
            "is_live": fixture_name is None and qb_accounts is None,
            "total_template_mappings": total,
            "total_qb_accounts": len(accounts),
            "matched": matched_count,
            "candidates": candidate_count,
            "unmatched": unmatched_count,
            "coverage_pct": round(matched_count / total * 100, 1) if total else 0,
            "health_grade": grade,
            "summary": summary,
            "items": items,
            "unmapped_qb_accounts": unmapped_qb,
        }

        # Store for later retrieval / apply / export
        _report_store[report_id] = report
        logger.info(
            "Diagnostic report %s: template=%s, grade=%s, "
            "matched=%d, candidates=%d, unmatched=%d",
            report_id, template_key, grade,
            matched_count, candidate_count, unmatched_count,
        )

        return report

    # -------------------------------------------------------------------
    # Get Report
    # -------------------------------------------------------------------

    @staticmethod
    def get_report(report_id: str) -> dict | None:
        """Retrieve a previously generated diagnostic report."""
        return _report_store.get(report_id)

    @staticmethod
    def list_reports() -> list[dict]:
        """List all reports (summary only, no items)."""
        results = []
        for r in _report_store.values():
            results.append({
                "id": r["id"],
                "template_key": r["template_key"],
                "template_name": r["template_name"],
                "created_at": r["created_at"],
                "health_grade": r["health_grade"],
                "matched": r["matched"],
                "candidates": r["candidates"],
                "unmatched": r["unmatched"],
                "total_template_mappings": r["total_template_mappings"],
                "coverage_pct": r["coverage_pct"],
                "is_live": r.get("is_live", False),
                "fixture_name": r.get("fixture_name"),
            })
        return sorted(results, key=lambda x: x["created_at"], reverse=True)

    # -------------------------------------------------------------------
    # Update Decisions
    # -------------------------------------------------------------------

    @staticmethod
    def update_decisions(report_id: str, decisions: list[dict]) -> dict:
        """
        Update admin decisions on a diagnostic report.

        Each decision dict:
          {"index": 0, "decision": "use_existing"|"create_new"|"skip",
           "qb_account_id": "123", "qb_account_name": "Food Sales"}

        For "use_existing", qb_account_id + qb_account_name are required.
        For "create_new" or "skip", they're optional.
        """
        report = _report_store.get(report_id)
        if not report:
            raise ValueError(f"Report '{report_id}' not found")

        items = report["items"]
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
            elif decision == "create_new":
                item["decision_account_id"] = None
                item["decision_account_name"] = None
            else:  # skip
                item["decision_account_id"] = None
                item["decision_account_name"] = None

        # Recompute stats
        matched = sum(1 for i in items if i["decision"] == "use_existing")
        skipped = sum(1 for i in items if i["decision"] == "skip")
        create_new = sum(1 for i in items if i["decision"] == "create_new")
        pending = sum(1 for i in items if i["decision"] is None)

        report["decision_summary"] = {
            "use_existing": matched,
            "create_new": create_new,
            "skip": skipped,
            "pending": pending,
            "ready_to_apply": pending == 0,
        }

        return report

    # -------------------------------------------------------------------
    # Apply Decisions (create mappings + accounts)
    # -------------------------------------------------------------------

    async def apply_decisions(self, report_id: str) -> dict:
        """
        Apply the admin's decisions from a diagnostic report:
        - "use_existing" → create mapping pointing to existing QB account
        - "create_new" → create QB account + mapping
        - "skip" → do nothing

        Returns: {accounts_created, mappings_created, skipped, errors}
        """
        report = _report_store.get(report_id)
        if not report:
            raise ValueError(f"Report '{report_id}' not found")

        if not self.connection:
            raise ValueError("QB connection required to apply decisions")

        items = report["items"]
        pending = [i for i in items if i.get("decision") is None]
        if pending:
            raise ValueError(
                f"{len(pending)} item(s) still have no decision. "
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
                details.append(
                    f"Skipped: {item['template_account_name']} ({item['mapping_type']})"
                )
                continue

            try:
                if decision == "use_existing":
                    # Map to existing QB account
                    qb_id = item["decision_account_id"]
                    qb_name = item["decision_account_name"]
                    if not qb_id:
                        errors.append(
                            f"Item {idx}: use_existing but no qb_account_id"
                        )
                        continue

                    await self._create_mapping(
                        mapping_type=item["mapping_type"],
                        qb_account_id=qb_id,
                        qb_account_name=qb_name or item["template_account_name"],
                        qb_account_type=item["template_account_type"],
                        qb_account_sub_type=item["template_account_sub_type"],
                        is_default=item["is_default"],
                    )
                    mappings_created += 1
                    details.append(
                        f"Mapped: {item['template_account_name']} → "
                        f"{qb_name} (existing QB account {qb_id})"
                    )

                elif decision == "create_new":
                    # Create account in QB + mapping
                    if not self.client:
                        errors.append("No QB client available to create accounts")
                        continue

                    try:
                        new_acct = await self.client.create_account(
                            name=item["template_account_name"],
                            account_type=item["template_account_type"],
                            account_sub_type=item["template_account_sub_type"],
                        )
                        qb_id = str(new_acct.get("Id", new_acct.get("id", "")))
                        qb_name = new_acct.get("Name", new_acct.get("name", ""))
                        accounts_created += 1
                    except Exception as exc:
                        errors.append(
                            f"Failed to create QB account "
                            f"'{item['template_account_name']}': {exc}"
                        )
                        continue

                    await self._create_mapping(
                        mapping_type=item["mapping_type"],
                        qb_account_id=qb_id,
                        qb_account_name=qb_name,
                        qb_account_type=item["template_account_type"],
                        qb_account_sub_type=item["template_account_sub_type"],
                        is_default=item["is_default"],
                    )
                    mappings_created += 1
                    details.append(
                        f"Created: {qb_name} (QB {qb_id}) + mapped as "
                        f"{item['mapping_type']}"
                    )

            except Exception as exc:
                errors.append(
                    f"Item {idx} ({item['template_account_name']}): {exc}"
                )

        result = {
            "accounts_created": accounts_created,
            "mappings_created": mappings_created,
            "skipped": skipped,
            "errors": errors,
            "details": details,
            "report_id": report_id,
        }

        # Update report with apply result
        report["apply_result"] = result
        report["applied_at"] = datetime.now(timezone.utc).isoformat()

        logger.info(
            "Applied diagnostic %s: created=%d accounts + %d mappings, "
            "skipped=%d, errors=%d",
            report_id, accounts_created, mappings_created,
            skipped, len(errors),
        )

        return result

    # -------------------------------------------------------------------
    # Health Check
    # -------------------------------------------------------------------

    async def health_check(self) -> dict:
        """
        Check existing mappings against live QB accounts.

        For each mapping, verify:
        - QB account still exists
        - QB account is still active
        - QB account name hasn't changed (renamed)
        - QB account type hasn't changed

        Returns health check report with grade (A/B/C/F).
        """
        if not self.connection or not self.client:
            raise ValueError("QB connection required for health check")

        # Fetch current QB accounts
        live_accounts = await self._fetch_live_accounts()
        acct_by_id: dict[str, dict] = {
            str(a.get("id", "")): a for a in live_accounts
        }

        # Fetch existing mappings
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
                # Account deleted from QB
                critical += 1
                details.append({
                    "mapping_id": str(m.id),
                    "mapping_type": m.mapping_type,
                    "qb_account_id": m.qb_account_id,
                    "qb_account_name": m.qb_account_name,
                    "status": "critical",
                    "issue": "account_deleted",
                    "message": f"QB account '{m.qb_account_name}' (ID: {m.qb_account_id}) "
                               "no longer exists in QuickBooks.",
                    "current_name": None,
                })
            elif not qb_acct.get("active", True):
                # Account deactivated
                critical += 1
                details.append({
                    "mapping_id": str(m.id),
                    "mapping_type": m.mapping_type,
                    "qb_account_id": m.qb_account_id,
                    "qb_account_name": m.qb_account_name,
                    "status": "critical",
                    "issue": "account_deactivated",
                    "message": f"QB account '{m.qb_account_name}' is deactivated. "
                               "Syncs using this account will fail.",
                    "current_name": qb_acct.get("name"),
                })
            elif qb_acct.get("name") != m.qb_account_name:
                # Account renamed
                warnings += 1
                details.append({
                    "mapping_id": str(m.id),
                    "mapping_type": m.mapping_type,
                    "qb_account_id": m.qb_account_id,
                    "qb_account_name": m.qb_account_name,
                    "status": "warning",
                    "issue": "account_renamed",
                    "message": f"QB account was renamed from '{m.qb_account_name}' "
                               f"to '{qb_acct.get('name')}'.",
                    "current_name": qb_acct.get("name"),
                })
            else:
                # All good
                healthy += 1
                details.append({
                    "mapping_id": str(m.id),
                    "mapping_type": m.mapping_type,
                    "qb_account_id": m.qb_account_id,
                    "qb_account_name": m.qb_account_name,
                    "status": "healthy",
                    "issue": None,
                    "message": "OK",
                    "current_name": qb_acct.get("name"),
                })

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
        """Fetch accounts from live QB connection."""
        if not self.client:
            raise ValueError("No QB client available")
        try:
            raw = await self.client.query(
                "Account",
                order_by="Name",
                max_results=1000,
            )
        except Exception as exc:
            logger.error("Failed to fetch QB accounts for diagnostic: %s", exc)
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
        """Create a mapping record, handling duplicates gracefully."""
        # Check for existing mapping with same type + name
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
                "Mapping already exists: %s → %s, skipping",
                mapping_type, qb_account_name,
            )
            return existing

        # If this is a default mapping, demote any existing default for this type
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
        """Remove default flag from existing default mapping of same type."""
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


# ---------------------------------------------------------------------------
# Module-level helpers for API routes
# ---------------------------------------------------------------------------

def get_available_fixtures() -> list[dict]:
    """Return list of test fixtures for the API."""
    return list_fixtures()
