"""The ONE place this system calls an LLM.

Everything goes through `call_model`. Nothing else constructs an Anthropic
client, names a model, or touches the API. That is deliberate, and it is what
makes the rest of this file possible:

  * **Instrumentation (playbook F1/F2).** Every call writes an `ai_usage_log`
    row with its four token classes and an estimated cost. A call site that
    bypassed this would be invisible, and invisible spend is the failure mode
    the playbook exists to prevent.
  * **Caps (playbook D).** Per-tenant, per-UTC-day, on both call count and
    tokens, env-tunable, checked BEFORE the call. Reaching a cap degrades
    gracefully -- the caller is told, and falls back to the manual path. It
    never crashes and never silently half-works.
  * **Caching (playbook A1/A2/A3).** The system block is passed separately from
    the per-request payload and marked cacheable, so the static instructions are
    a cache read rather than full-price input on every call.
  * 🔴 **The B1 rule.** Whatever is in the cached system block must NOT be
    repeated in the user message. Callers pass a small, compact delta. On the
    project this playbook came from, that single fix cut per-user input from
    ~50-63k tokens a day to ~5-15k.
  * **Resilience (playbook G).** A failure here is returned, never raised into
    a request handler. Both AI features are assists on top of a workflow that
    works without them.

The model is one constant, `settings.AI_MODEL`. Do not hardcode a model
anywhere else.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.ai_usage import AIUsageLog
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)


class AIUnavailable(RuntimeError):
    """The model could not be called, and the caller should fall back.

    Carries a message written for the person on the screen, not for a log:
    "AI receiving is not configured on this server, type the delivery in by
    hand" is actionable; "AuthenticationError" is not.
    """


# 🔴 Estimated USD per 1M tokens, for the cost column ONLY. Verified against
# the `claude-api` skill's model table (cached 2026-06-24) rather than quoted
# from memory. The Anthropic console is the authority; this is a running
# estimate to reconcile against it, never an invoice. Cache read is ~0.1x input
# and cache write ~1.25x input, per the published pricing model.
_RATES_PER_MTOK: dict[str, tuple[Decimal, Decimal]] = {
    "claude-opus-5": (Decimal("5.00"), Decimal("25.00")),
    "claude-opus-4-8": (Decimal("5.00"), Decimal("25.00")),
    "claude-sonnet-5": (Decimal("2.00"), Decimal("10.00")),
    "claude-haiku-4-5": (Decimal("1.00"), Decimal("5.00")),
}
_DEFAULT_RATE = (Decimal("5.00"), Decimal("25.00"))
_CACHE_WRITE_MULTIPLIER = Decimal("1.25")
_CACHE_READ_MULTIPLIER = Decimal("0.1")
_MILLION = Decimal("1000000")


def estimate_cost_usd(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_creation_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> Decimal:
    """Running cost estimate for one call, in USD."""
    rate_in, rate_out = _RATES_PER_MTOK.get(model, _DEFAULT_RATE)
    total = (
        Decimal(input_tokens) * rate_in
        + Decimal(output_tokens) * rate_out
        + Decimal(cache_creation_tokens) * rate_in * _CACHE_WRITE_MULTIPLIER
        + Decimal(cache_read_tokens) * rate_in * _CACHE_READ_MULTIPLIER
    ) / _MILLION
    return total.quantize(Decimal("0.000001"))


async def daily_usage(
    db: AsyncSession, tenant_id: uuid.UUID
) -> tuple[int, int, Decimal]:
    """(calls, tokens, cost) for this tenant so far today, UTC.

    Failed calls count towards the CALL cap but contribute no tokens. A run of
    failures that did not count would let a retry loop hammer the API for free
    from the cap's point of view, which is exactly the runaway the cap exists
    to stop.
    """
    today = datetime.now(timezone.utc).date()
    row = (
        await db.execute(
            select(
                func.count(AIUsageLog.id),
                func.coalesce(
                    func.sum(
                        AIUsageLog.input_tokens
                        + AIUsageLog.output_tokens
                        + AIUsageLog.cache_creation_tokens
                        + AIUsageLog.cache_read_tokens
                    ),
                    0,
                ),
                func.coalesce(func.sum(AIUsageLog.estimated_cost_usd), 0),
            ).where(
                AIUsageLog.tenant_id == tenant_id,
                AIUsageLog.usage_date == today,
            )
        )
    ).one()
    return int(row[0]), int(row[1]), Decimal(str(row[2]))


async def usage_summary(
    db: AsyncSession, tenant_id: uuid.UUID, date_from, date_to
) -> dict:
    """What AI has cost this restaurant over a period (playbook F3).

    Broken out by `kind` because an aggregate hides the thing worth seeing: one
    feature quietly becoming 90% of the bill. The cost is an ESTIMATE from the
    published rate table, for reconciling against the Anthropic console -- it is
    not the invoice, and it is labelled as such wherever it is shown.
    """
    totals = (
        await db.execute(
            select(
                func.count(AIUsageLog.id),
                func.coalesce(func.sum(AIUsageLog.input_tokens), 0),
                func.coalesce(func.sum(AIUsageLog.output_tokens), 0),
                func.coalesce(func.sum(AIUsageLog.cache_creation_tokens), 0),
                func.coalesce(func.sum(AIUsageLog.cache_read_tokens), 0),
                func.coalesce(func.sum(AIUsageLog.estimated_cost_usd), 0),
            ).where(
                AIUsageLog.tenant_id == tenant_id,
                AIUsageLog.usage_date >= date_from,
                AIUsageLog.usage_date <= date_to,
            )
        )
    ).one()

    by_kind = [
        {
            "kind": kind,
            "calls": int(calls),
            "tokens": int(tokens),
            "estimated_cost_usd": Decimal(str(cost)),
            "failures": int(failures),
        }
        for kind, calls, tokens, cost, failures in (
            await db.execute(
                select(
                    AIUsageLog.kind,
                    func.count(AIUsageLog.id),
                    func.coalesce(
                        func.sum(
                            AIUsageLog.input_tokens
                            + AIUsageLog.output_tokens
                            + AIUsageLog.cache_creation_tokens
                            + AIUsageLog.cache_read_tokens
                        ),
                        0,
                    ),
                    func.coalesce(func.sum(AIUsageLog.estimated_cost_usd), 0),
                    func.coalesce(
                        func.sum(
                            case((AIUsageLog.succeeded == False, 1), else_=0)  # noqa: E712
                        ),
                        0,
                    ),
                )
                .where(
                    AIUsageLog.tenant_id == tenant_id,
                    AIUsageLog.usage_date >= date_from,
                    AIUsageLog.usage_date <= date_to,
                )
                .group_by(AIUsageLog.kind)
            )
        ).all()
    ]

    today_calls, today_tokens, today_cost = await daily_usage(db, tenant_id)

    return {
        "date_from": date_from,
        "date_to": date_to,
        "calls": int(totals[0]),
        "input_tokens": int(totals[1]),
        "output_tokens": int(totals[2]),
        "cache_creation_tokens": int(totals[3]),
        "cache_read_tokens": int(totals[4]),
        "estimated_cost_usd": Decimal(str(totals[5])),
        "by_kind": sorted(by_kind, key=lambda row: -row["calls"]),
        "today_calls": today_calls,
        "today_tokens": today_tokens,
        # Today's spend against the ceiling that actually binds. Shown together
        # so the admin screen can answer "how close am I?" without arithmetic.
        "today_cost_usd": today_cost,
        "daily_call_cap": settings.AI_DAILY_CALL_CAP_PER_TENANT,
        "daily_token_cap": settings.AI_DAILY_TOKEN_CAP_PER_TENANT,
        "daily_cost_cap_usd": settings.AI_DAILY_COST_CAP_USD_PER_TENANT,
    }


async def _check_tenant_enabled(db: AsyncSession, tenant_id: uuid.UUID) -> None:
    """Is this restaurant allowed to spend at all? (playbook D, blast radius.)

    🔴 The API key is a property of the SERVER; permission to spend it is a
    property of the TENANT. Conflating the two is how "switch the AI on for this
    client" quietly means "switch it on for everyone sharing the box". Four
    production tenants share this one, so without this gate the real ceiling is
    the per-tenant cap times four, and three of those four never asked for the
    feature.

    Checked before the caps because it is the cheaper and more restrictive
    question: a tenant that may not spend at all need not have its daily total
    computed.
    """
    allowed = settings.ai_enabled_tenant_slugs
    if not allowed:
        raise AIUnavailable(
            "AI features are not enabled for any restaurant on this server. "
            "Everything works by hand; ask your administrator to enable them."
        )

    slug = (
        await db.execute(select(Tenant.slug).where(Tenant.id == tenant_id))
    ).scalar_one_or_none()

    if slug is None or slug.lower() not in allowed:
        raise AIUnavailable(
            "AI features are not enabled for this restaurant. Everything works "
            "by hand; ask your administrator to enable them."
        )


async def _check_caps(db: AsyncSession, tenant_id: uuid.UUID) -> None:
    """Three ceilings, checked before the call. Any one of them stops it.

    Deliberately three, in three different units. The cost cap is the one that
    answers the question an owner actually asks, but it is derived from a rate
    table this codebase maintains by hand -- if Anthropic changes its prices and
    nobody updates `_RATES_PER_MTOK`, the money cap silently drifts. The call and
    token caps cannot drift, because the API reports those directly. Belt and
    braces, and the braces are the ones denominated in money.
    """
    calls, tokens, cost = await daily_usage(db, tenant_id)
    if calls >= settings.AI_DAILY_CALL_CAP_PER_TENANT:
        raise AIUnavailable(
            "Today's AI allowance for this restaurant has been used up "
            f"({calls} calls). It resets at midnight UTC. Everything still "
            "works by hand in the meantime."
        )
    if tokens >= settings.AI_DAILY_TOKEN_CAP_PER_TENANT:
        raise AIUnavailable(
            "Today's AI allowance for this restaurant has been used up. It "
            "resets at midnight UTC. Everything still works by hand in the "
            "meantime."
        )
    if cost >= settings.AI_DAILY_COST_CAP_USD_PER_TENANT:
        # Says the number out loud. "Allowance used up" invites a support call;
        # "$5.02 of $5.00" tells the operator exactly what happened and that
        # raising it is a decision someone can make.
        raise AIUnavailable(
            "Today's AI spending limit for this restaurant has been reached "
            f"(about ${cost:.2f} of ${settings.AI_DAILY_COST_CAP_USD_PER_TENANT:.2f}). "
            "It resets at midnight UTC. Everything still works by hand in the "
            "meantime, and your administrator can raise the limit."
        )


async def _record(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    kind: str,
    model: str,
    usage: Any | None,
    latency_ms: int,
    succeeded: bool,
    error: str | None,
    requested_by: uuid.UUID | None,
) -> None:
    """Write the usage row. Never allowed to fail the caller.

    Same reasoning as the SAVEPOINT around audit logging elsewhere in this
    codebase: a bookkeeping side effect must not poison the transaction that
    did the real work.
    """
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    cache_creation = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)
    cache_read = int(getattr(usage, "cache_read_input_tokens", 0) or 0)

    try:
        async with db.begin_nested():
            db.add(
                AIUsageLog(
                    tenant_id=tenant_id,
                    kind=kind,
                    model=model,
                    usage_date=datetime.now(timezone.utc).date(),
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cache_creation_tokens=cache_creation,
                    cache_read_tokens=cache_read,
                    estimated_cost_usd=estimate_cost_usd(
                        model, input_tokens, output_tokens, cache_creation, cache_read
                    ),
                    latency_ms=latency_ms,
                    succeeded=succeeded,
                    error=(error or None),
                    requested_by=requested_by,
                    called_at=datetime.now(timezone.utc),
                )
            )
    except Exception:  # noqa: BLE001 -- logging must never break the caller
        logger.exception("Could not write the AI usage row for %r", kind)
        return

    logger.info(
        "ai_call kind=%s model=%s in=%d out=%d cache_write=%d cache_read=%d "
        "latency_ms=%d ok=%s",
        kind,
        model,
        input_tokens,
        output_tokens,
        cache_creation,
        cache_read,
        latency_ms,
        succeeded,
    )


def _client():
    """Build the Anthropic async client. Imported lazily on purpose.

    The `anthropic` package is only needed by the two optional AI features. A
    deployment without a key should not fail to boot because of an import, and
    the test suite should not need the dependency to exercise everything else.
    """
    if not settings.ai_configured:
        raise AIUnavailable(
            "AI is not configured on this server. Everything works by hand; "
            "ask your administrator to add an API key to enable it."
        )
    try:
        from anthropic import AsyncAnthropic
    except ImportError as exc:  # pragma: no cover -- packaging problem
        raise AIUnavailable(
            "The AI library is not installed on this server."
        ) from exc
    return AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)


async def call_model(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    kind: str,
    system: str,
    content: list[dict],
    output_model: type[BaseModel],
    requested_by: uuid.UUID | None = None,
    max_tokens: int | None = None,
) -> BaseModel:
    """One structured model call. The only path to Anthropic in this codebase.

    `system` is the STATIC instruction block: identical across calls of the same
    `kind`, and marked cacheable so it is a cache read rather than full-price
    input every time. `content` is the small per-request delta -- 🔴 it must not
    repeat anything already in `system`.

    `output_model` is a Pydantic model; the response is validated against it by
    the SDK, so a malformed answer is a retry inside the SDK rather than a
    parsing bug here.

    Raises `AIUnavailable` for anything the caller should fall back from: no
    key, cap reached, rate limited, model error. It does not raise anything
    else.
    """
    # Order matters: may this tenant spend at all, then has it spent enough
    # today, then is the server even configured. Cheapest and most restrictive
    # question first, and every one of them before any billable call.
    await _check_tenant_enabled(db, tenant_id)
    await _check_caps(db, tenant_id)

    client = _client()
    model = settings.AI_MODEL
    started = time.monotonic()

    try:
        response = await client.messages.parse(
            model=model,
            max_tokens=max_tokens or settings.AI_MAX_OUTPUT_TOKENS,
            # A list with `cache_control` rather than a bare string: this is the
            # cached prefix, and it must stay byte-identical between calls or it
            # silently stops caching.
            system=[
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": content}],
            output_format=output_model,
        )
    except Exception as exc:  # noqa: BLE001 -- classified and re-raised below
        latency_ms = int((time.monotonic() - started) * 1000)
        await _record(
            db,
            tenant_id=tenant_id,
            kind=kind,
            model=model,
            usage=None,
            latency_ms=latency_ms,
            succeeded=False,
            error=f"{type(exc).__name__}: {exc}"[:1000],
            requested_by=requested_by,
        )
        logger.exception("AI call %r failed", kind)
        name = type(exc).__name__
        if name == "RateLimitError":
            raise AIUnavailable(
                "The AI service is busy right now. Try again in a minute, or "
                "enter it by hand."
            ) from exc
        if name in ("AuthenticationError", "PermissionDeniedError"):
            raise AIUnavailable(
                "The AI key on this server was rejected. Ask your "
                "administrator to check it."
            ) from exc
        raise AIUnavailable(
            "The AI service could not complete that request. Enter it by hand "
            "for now."
        ) from exc

    latency_ms = int((time.monotonic() - started) * 1000)
    await _record(
        db,
        tenant_id=tenant_id,
        kind=kind,
        model=model,
        usage=response.usage,
        latency_ms=latency_ms,
        succeeded=True,
        error=None,
        requested_by=requested_by,
    )

    parsed = response.parsed_output
    if parsed is None:  # pragma: no cover -- output_format guarantees it
        raise AIUnavailable("The AI service returned nothing usable.")
    return parsed
