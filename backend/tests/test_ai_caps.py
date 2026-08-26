"""The spending guardrails on the two AI features.

🔴 WHY THIS FILE EXISTS. Before 2026-08-26 the caps in `ai_client._check_caps`
had **zero test coverage**. They were the only thing standing between a client
tenant and a runaway invoice, and nothing checked that they fired. This file is
that check.

It is deliberately paranoid about one specific failure, the one written up in
`ERROR_LOG.md` as "a green magnitude check that proved nothing": an assertion
that passes over an empty set is not evidence. So every cap test first asserts
that the usage it seeded is actually THERE, and only then asserts that the cap
refused the call. A test that silently seeded nothing would report green while
proving the opposite of what it claims.

The other thing under test here is ORDERING. `_check_caps` runs before
`_client()`, which means a tenant over its cap is refused for being over its
cap, not for the key being missing. If someone reorders those two lines, the
error message changes and these tests fail. That matters because the cap must
hold even on a server where the key IS configured.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.ai_usage import AIUsageLog
from app.models.tenant import Tenant
from app.services import ai_client
from app.services.ai_client import AIUnavailable, estimate_cost_usd

# `asyncio_mode = "auto"` in pyproject.toml, so async tests need no marker.


@pytest.fixture(autouse=True)
def _enable_the_test_tenants(monkeypatch):
    """The cap tests are about caps, so put their tenants past the tenant gate.

    `_check_tenant_enabled` runs BEFORE `_check_caps`, so without this every cap
    test would stop at "not enabled for this restaurant" and prove nothing about
    caps. The gate has its own tests further down.
    """
    monkeypatch.setattr(
        settings, "AI_ENABLED_TENANT_SLUGS", "test-restaurant,other-restaurant"
    )


@pytest.fixture(autouse=True)
def _never_reach_the_network(monkeypatch):
    """🔴 Blank the API key for EVERY test in this file. Not optional.

    Found the hard way on 2026-08-26. These tests were written assuming the test
    environment has no key, using "AI is not configured" as the proof that a cap
    did NOT fire. The local dev container **does** have a key, so three tests
    sailed past `_client()` and made **real, billed Anthropic calls**.

    Two things were wrong and both are fixed here. A test suite must never be
    able to spend money, and a test must never depend on an ambient credential
    being absent -- "it passed because the machine happened to be unconfigured"
    is not a property, it is luck. Blanking the key makes `_client()` raise
    deterministically, on any machine, with or without a key in the environment.
    """
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "")


class _Dummy(BaseModel):
    """Stand-in output model. No call ever gets far enough to use it."""

    ok: bool = True


async def _log_call(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    cost: str = "0",
    input_tokens: int = 0,
    output_tokens: int = 0,
    succeeded: bool = True,
    days_ago: int = 0,
) -> AIUsageLog:
    """Write one usage row, exactly as `_record` would."""
    day = (datetime.now(timezone.utc) - timedelta(days=days_ago)).date()
    row = AIUsageLog(
        tenant_id=tenant_id,
        kind="ocr_receiving",
        model="claude-opus-5",
        usage_date=day,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_tokens=0,
        cache_read_tokens=0,
        estimated_cost_usd=Decimal(cost),
        latency_ms=100,
        succeeded=succeeded,
        error=None if succeeded else "boom",
        requested_by=None,
        called_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )
    db.add(row)
    await db.flush()
    return row


async def _assert_rows_exist(db: AsyncSession, tenant_id: uuid.UUID) -> int:
    """Guard against the empty-set trap. Returns the count so callers can use it.

    Every cap test seeds usage and then asserts the cap refused the call. If the
    seed silently wrote nothing, the refusal would have to come from somewhere
    else, and the test would be asserting a coincidence. So: prove the rows are
    there first.
    """
    count = (
        await db.execute(
            select(func.count(AIUsageLog.id)).where(AIUsageLog.tenant_id == tenant_id)
        )
    ).scalar_one()
    assert count > 0, "seeded no usage rows; this test would prove nothing"
    return int(count)


async def _call(db: AsyncSession, tenant_id: uuid.UUID):
    return await ai_client.call_model(
        db,
        tenant_id=tenant_id,
        kind="ocr_receiving",
        system="static",
        content=[{"type": "text", "text": "delta"}],
        output_model=_Dummy,
    )


# ---------------------------------------------------------------------------
# THE COST CAP -- the one an owner actually cares about
# ---------------------------------------------------------------------------


async def test_cost_cap_refuses_the_call_once_the_day_is_spent(
    db: AsyncSession, tenant: Tenant, monkeypatch
):
    monkeypatch.setattr(settings, "AI_DAILY_COST_CAP_USD_PER_TENANT", Decimal("5.00"))

    # 5.00 exactly. The cap is `>=`, so landing on the number is over it: a cap
    # you can sit precisely on forever is not a cap.
    for _ in range(5):
        await _log_call(db, tenant.id, cost="1.00")
    await _assert_rows_exist(db, tenant.id)

    _calls, _tokens, cost = await ai_client.daily_usage(db, tenant.id)
    assert cost == Decimal("5.00"), f"seeded usage did not add up: {cost}"

    with pytest.raises(AIUnavailable) as exc:
        await _call(db, tenant.id)

    message = str(exc.value)
    assert "spending limit" in message
    # 🔴 Proves ORDERING: the caps are checked before the client is built. With
    # no key configured in tests, a cap checked too late would surface as
    # "AI is not configured" and the guardrail would not hold on a server that
    # DOES have a key -- which is the only server that can spend money.
    assert "not configured" not in message


async def test_cost_cap_message_names_both_numbers(
    db: AsyncSession, tenant: Tenant, monkeypatch
):
    """An operator has to be able to act on it, not just be told "no"."""
    monkeypatch.setattr(settings, "AI_DAILY_COST_CAP_USD_PER_TENANT", Decimal("2.00"))
    await _log_call(db, tenant.id, cost="2.50")
    await _assert_rows_exist(db, tenant.id)

    with pytest.raises(AIUnavailable) as exc:
        await _call(db, tenant.id)

    message = str(exc.value)
    assert "$2.50" in message, message
    assert "$2.00" in message, message
    assert "midnight UTC" in message
    assert "by hand" in message


async def test_under_the_cost_cap_the_call_is_allowed_through(
    db: AsyncSession, tenant: Tenant, monkeypatch
):
    """The complement. Without this, a cap stuck permanently on would pass.

    Under the cap, `_check_caps` returns and `_client()` is reached -- which
    fails in tests because no key is configured. That specific failure is the
    proof the cap did NOT fire.
    """
    monkeypatch.setattr(settings, "AI_DAILY_COST_CAP_USD_PER_TENANT", Decimal("5.00"))
    await _log_call(db, tenant.id, cost="4.99")
    await _assert_rows_exist(db, tenant.id)

    with pytest.raises(AIUnavailable) as exc:
        await _call(db, tenant.id)

    assert "not configured" in str(exc.value)
    assert "spending limit" not in str(exc.value)


async def test_yesterdays_spend_does_not_count_against_today(
    db: AsyncSession, tenant: Tenant, monkeypatch
):
    """The cap is per UTC day. A spent yesterday must not block this morning."""
    monkeypatch.setattr(settings, "AI_DAILY_COST_CAP_USD_PER_TENANT", Decimal("5.00"))
    await _log_call(db, tenant.id, cost="500.00", days_ago=1)
    await _assert_rows_exist(db, tenant.id)

    _calls, _tokens, cost = await ai_client.daily_usage(db, tenant.id)
    assert cost == Decimal("0"), "yesterday's row leaked into today's total"

    with pytest.raises(AIUnavailable) as exc:
        await _call(db, tenant.id)
    assert "not configured" in str(exc.value)


async def test_one_tenants_spend_cannot_block_another(
    db: AsyncSession, tenant: Tenant, monkeypatch
):
    """Caps are PER TENANT. On a shared box this is the whole point.

    Chick Shack must never be locked out of anything because the FZ LLC demo
    tenant burned its allowance, and vice versa.
    """
    monkeypatch.setattr(settings, "AI_DAILY_COST_CAP_USD_PER_TENANT", Decimal("5.00"))

    other = Tenant(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        name="Other Restaurant",
        slug="other-restaurant",
        is_active=True,
    )
    db.add(other)
    await db.flush()

    await _log_call(db, tenant.id, cost="99.00")
    await _assert_rows_exist(db, tenant.id)

    # The spent tenant is refused...
    with pytest.raises(AIUnavailable) as spent:
        await _call(db, tenant.id)
    assert "spending limit" in str(spent.value)

    # ...and the other one is not.
    _c, _t, other_cost = await ai_client.daily_usage(db, other.id)
    assert other_cost == Decimal("0")
    with pytest.raises(AIUnavailable) as fresh:
        await _call(db, other.id)
    assert "not configured" in str(fresh.value)


# ---------------------------------------------------------------------------
# THE CALL AND TOKEN CAPS -- the ones that cannot drift with pricing
# ---------------------------------------------------------------------------


async def test_call_cap_refuses_once_reached(
    db: AsyncSession, tenant: Tenant, monkeypatch
):
    monkeypatch.setattr(settings, "AI_DAILY_CALL_CAP_PER_TENANT", 3)
    monkeypatch.setattr(settings, "AI_DAILY_COST_CAP_USD_PER_TENANT", Decimal("999"))

    for _ in range(3):
        await _log_call(db, tenant.id, cost="0.001")
    assert await _assert_rows_exist(db, tenant.id) == 3

    with pytest.raises(AIUnavailable) as exc:
        await _call(db, tenant.id)
    assert "3 calls" in str(exc.value)


async def test_failed_calls_still_count_against_the_call_cap(
    db: AsyncSession, tenant: Tenant, monkeypatch
):
    """Documented behaviour, and the reason matters.

    A failing call costs nothing in tokens, so if failures did not count, a
    retry loop could hammer the API indefinitely and the cap would never see it.
    """
    monkeypatch.setattr(settings, "AI_DAILY_CALL_CAP_PER_TENANT", 2)
    monkeypatch.setattr(settings, "AI_DAILY_COST_CAP_USD_PER_TENANT", Decimal("999"))

    await _log_call(db, tenant.id, cost="0", succeeded=False)
    await _log_call(db, tenant.id, cost="0", succeeded=False)
    await _assert_rows_exist(db, tenant.id)

    calls, tokens, cost = await ai_client.daily_usage(db, tenant.id)
    assert calls == 2
    assert tokens == 0, "failed calls should contribute no tokens"
    assert cost == Decimal("0"), "failed calls should contribute no cost"

    with pytest.raises(AIUnavailable) as exc:
        await _call(db, tenant.id)
    assert "2 calls" in str(exc.value)


async def test_token_cap_refuses_once_reached(
    db: AsyncSession, tenant: Tenant, monkeypatch
):
    monkeypatch.setattr(settings, "AI_DAILY_TOKEN_CAP_PER_TENANT", 1000)
    monkeypatch.setattr(settings, "AI_DAILY_CALL_CAP_PER_TENANT", 999)
    monkeypatch.setattr(settings, "AI_DAILY_COST_CAP_USD_PER_TENANT", Decimal("999"))

    await _log_call(db, tenant.id, input_tokens=600, output_tokens=400, cost="0.01")
    await _assert_rows_exist(db, tenant.id)

    _calls, tokens, _cost = await ai_client.daily_usage(db, tenant.id)
    assert tokens == 1000

    with pytest.raises(AIUnavailable) as exc:
        await _call(db, tenant.id)
    assert "allowance" in str(exc.value)
    assert "not configured" not in str(exc.value)


# ---------------------------------------------------------------------------
# THE TENANT GATE -- who is allowed to spend at all
#
# The key is a property of the SERVER. Four tenants share the production box.
# Without this gate, "enable the AI for Martin" silently means "enable it for
# everyone", and the ceiling becomes the per-tenant cap times four.
# ---------------------------------------------------------------------------


async def test_a_tenant_not_on_the_allowlist_cannot_spend(
    db: AsyncSession, tenant: Tenant, monkeypatch
):
    """The whole point: one tenant enabled must not mean all tenants enabled."""
    monkeypatch.setattr(settings, "AI_ENABLED_TENANT_SLUGS", "martin-fz")

    # No usage at all, so nothing else could possibly be refusing this.
    calls, _tokens, cost = await ai_client.daily_usage(db, tenant.id)
    assert (calls, cost) == (0, Decimal("0"))

    with pytest.raises(AIUnavailable) as exc:
        await _call(db, tenant.id)

    message = str(exc.value)
    assert "not enabled for this restaurant" in message
    # Refused for the right reason, not incidentally by a cap or a missing key.
    assert "spending limit" not in message
    assert "not configured" not in message


async def test_an_allowlisted_tenant_passes_the_gate(
    db: AsyncSession, tenant: Tenant, monkeypatch
):
    """Complement. Without it, a gate stuck permanently shut would pass."""
    monkeypatch.setattr(settings, "AI_ENABLED_TENANT_SLUGS", "test-restaurant")

    with pytest.raises(AIUnavailable) as exc:
        await _call(db, tenant.id)

    # Got past the gate and the caps, and stopped at the blanked key.
    assert "not configured" in str(exc.value)


async def test_an_empty_allowlist_means_nobody_not_everybody(
    db: AsyncSession, tenant: Tenant, monkeypatch
):
    """🔴 The default, and the direction it fails in.

    An empty setting must not be read as "unrestricted". If it were, forgetting
    to configure the allowlist on a server that HAS a key would silently enable
    every tenant on it. Empty fails loudly and costs nothing.
    """
    monkeypatch.setattr(settings, "AI_ENABLED_TENANT_SLUGS", "")

    with pytest.raises(AIUnavailable) as exc:
        await _call(db, tenant.id)
    assert "not enabled for any restaurant" in str(exc.value)


async def test_the_allowlist_tolerates_spacing_and_case(
    db: AsyncSession, tenant: Tenant, monkeypatch
):
    """It is hand-edited in an env file, so it will be typed untidily."""
    monkeypatch.setattr(
        settings, "AI_ENABLED_TENANT_SLUGS", " Chick-Shack , TEST-RESTAURANT ,, "
    )
    assert settings.ai_enabled_tenant_slugs == {"chick-shack", "test-restaurant"}

    with pytest.raises(AIUnavailable) as exc:
        await _call(db, tenant.id)
    assert "not configured" in str(exc.value)


async def test_the_gate_is_checked_before_the_caps(
    db: AsyncSession, tenant: Tenant, monkeypatch
):
    """Ordering, asserted rather than assumed.

    A tenant that may not spend at all should never have its daily total
    computed. If these two were swapped, a non-allowlisted tenant sitting over
    its cap would be told about a spending limit it was never entitled to use.
    """
    monkeypatch.setattr(settings, "AI_ENABLED_TENANT_SLUGS", "somebody-else")
    monkeypatch.setattr(settings, "AI_DAILY_COST_CAP_USD_PER_TENANT", Decimal("1.00"))
    await _log_call(db, tenant.id, cost="99.00")
    await _assert_rows_exist(db, tenant.id)

    with pytest.raises(AIUnavailable) as exc:
        await _call(db, tenant.id)

    assert "not enabled for this restaurant" in str(exc.value)
    assert "spending limit" not in str(exc.value)


# ---------------------------------------------------------------------------
# THE COST ESTIMATE ITSELF
# ---------------------------------------------------------------------------


def test_cost_estimate_is_hand_checkable():
    """Arithmetic, worked out by hand, on `claude-opus-5` at $5 in / $25 out.

    1,000,000 input  = $5.00
    1,000,000 output = $25.00
    """
    assert estimate_cost_usd("claude-opus-5", 1_000_000, 0) == Decimal("5.000000")
    assert estimate_cost_usd("claude-opus-5", 0, 1_000_000) == Decimal("25.000000")
    assert estimate_cost_usd("claude-opus-5", 1_000_000, 1_000_000) == Decimal(
        "30.000000"
    )


def test_cache_reads_are_cheaper_and_cache_writes_dearer_than_plain_input():
    """The whole economic case for the cached system block, in one assertion.

    If this ever inverts, the caching in `call_model` is costing money rather
    than saving it and the design needs revisiting, not the test.
    """
    plain = estimate_cost_usd("claude-opus-5", 100_000, 0)
    read = estimate_cost_usd("claude-opus-5", 0, 0, cache_read_tokens=100_000)
    write = estimate_cost_usd("claude-opus-5", 0, 0, cache_creation_tokens=100_000)

    assert read < plain < write
    assert read == Decimal("0.050000")  # 0.1x
    assert write == Decimal("0.625000")  # 1.25x


def test_an_unknown_model_falls_back_to_the_dearest_rate():
    """A model we do not have a rate for must not be costed at zero.

    Costing an unknown model at zero would make the spending cap invisible to
    it, which is the exact opposite of what a cap is for. Over-estimating is the
    safe direction.
    """
    unknown = estimate_cost_usd("claude-something-new", 1_000_000, 0)
    assert unknown == Decimal("5.000000")
    assert unknown > 0


# ---------------------------------------------------------------------------
# THE TRIPWIRE (api-cost-playbook F2)
# ---------------------------------------------------------------------------


def test_only_ai_client_may_call_anthropic():
    """Pins the number of model call sites at exactly one.

    Every guardrail in this file hangs off `call_model` being the only door.
    A second call site anywhere else would be uncapped, unlogged and invisible
    in the usage summary -- and would look completely normal in review. This
    fails the build instead.

    On the project the playbook came from, the first usage figures undercounted
    by ~83% for exactly this reason: a second call path nobody remembered.
    """
    app_dir = Path(__file__).resolve().parents[1] / "app"
    pattern = re.compile(r"messages\.(parse|create|stream)|AsyncAnthropic|\bAnthropic\(")

    offenders = sorted(
        path.relative_to(app_dir).as_posix()
        for path in app_dir.rglob("*.py")
        if pattern.search(path.read_text(encoding="utf-8"))
    )

    assert offenders == ["services/ai_client.py"], (
        "Anthropic is being called from somewhere other than ai_client.call_model. "
        "Every model call must go through that one wrapper or it is uncapped and "
        f"unlogged. Found in: {offenders}"
    )
