"""Danny's D-68 + D-73 (2026-09-26): one drawer figure, shown before close.

    D-68 Malik: cash paid out and taken in outside sales (cash expenses, cash
         other income) count against the drawer at close, so the close screen
         and the Z-Report show one figure.
    D-73 The close screen needs that figure BEFORE the count is committed:
         GET /payments/drawer/summary.

Driven through the routes. SQLite keeps server-default timestamps as
second-resolution text, so the drawer is opened a second earlier (see the D-67
test in test_payments.py) and every window is checked with a positive control:
the sale must be in it.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from app.models.payment import CashDrawerSession

pytestmark = pytest.mark.asyncio


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _today() -> str:
    # No config row: the test tenant's day is the UTC day.
    return datetime.now(timezone.utc).date().isoformat()


async def _open_drawer(client: AsyncClient, db, headers, float_minor: int) -> str:
    opened = await client.post(
        "/api/v1/payments/drawer/open", json={"opening_float": float_minor}, headers=headers
    )
    assert opened.status_code == 201, opened.text
    session = await db.get(CashDrawerSession, uuid.UUID(opened.json()["id"]))
    session.opened_at = session.opened_at - timedelta(seconds=1)
    await db.commit()
    return opened.json()["id"]


async def _day_of_cash(client: AsyncClient, headers, order) -> None:
    """Rs 100 cash sale, Rs 200 cash expense, Rs 3,500 cash scrap income, and a
    Rs 20,000 bank receipt that never touches the till."""
    paid = await client.post(
        "/api/v1/payments",
        json={
            "order_id": str(order.id),
            "method_code": "cash",
            "amount": 10_000,
            "tendered_amount": 10_000,
        },
        headers=headers,
    )
    assert paid.status_code == 201, paid.text
    spent = await client.post(
        "/api/v1/expenses",
        json={
            "expense_date": _today(),
            "payee": "Electrician",
            "amount_minor": 20_000,
            "status": "paid",
            "payment_method": "Cash",
            "paid_on": _today(),
        },
        headers=headers,
    )
    assert spent.status_code == 201, spent.text
    for payer, amount, method in (
        ("Kabari (scrap dealer)", 350_000, "cash"),
        ("Upstairs tenant", 2_000_000, "bank"),
    ):
        income = await client.post(
            "/api/v1/other-income",
            json={
                "received_on": _today(),
                "payer": payer,
                "amount_minor": amount,
                "method": method,
            },
            headers=headers,
        )
        assert income.status_code == 201, income.text


async def test_no_open_drawer_has_no_summary(client: AsyncClient, admin_token: str) -> None:
    r = await client.get("/api/v1/payments/drawer/summary", headers=_auth(admin_token))
    assert r.status_code == 200, r.text
    assert r.json() is None


async def test_summary_shows_what_should_be_in_the_drawer(
    client: AsyncClient, db, admin_token: str, admin_user, order
) -> None:
    """Rs 5,000 float + Rs 100 sale - Rs 200 expense + Rs 3,500 scrap = Rs 8,400."""
    headers = _auth(admin_token)
    session_id = await _open_drawer(client, db, headers, 500_000)
    await _day_of_cash(client, headers, order)

    r = await client.get("/api/v1/payments/drawer/summary", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == session_id
    assert body["opened_by_name"] == admin_user.full_name
    assert body["opening_float"] == 500_000
    assert body["cash_taken"] == 10_000  # positive control: the sale is in the window
    assert body["cash_refunds"] == 0
    assert body["cash_paid_out"] == 20_000
    assert body["other_cash_in"] == 350_000
    assert body["expected_in_drawer"] == 840_000


async def test_close_and_z_report_agree_on_the_drawer(
    client: AsyncClient, db, admin_token: str, order
) -> None:
    """D-68: counted Rs 8,390 against Rs 8,400 expected is Rs 10 short, on the
    close response and on the Z-Report alike. Before D-68 the close ignored the
    expense and the income and expected Rs 5,100, reporting Rs 3,290 OVER."""
    headers = _auth(admin_token)
    await _open_drawer(client, db, headers, 500_000)
    await _day_of_cash(client, headers, order)

    closed = await client.post(
        "/api/v1/payments/drawer/close",
        json={"closing_balance_counted": 839_000},
        headers=headers,
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["closing_balance_expected"] == 840_000

    report = await client.get(
        "/api/v1/reports/z-report", params={"date": _today()}, headers=headers
    )
    assert report.status_code == 200, report.text
    [drawer] = report.json()["cash_position"]["drawers"]
    assert drawer["cash_taken"] == 10_000  # positive control
    assert drawer["expected_in_drawer"] == 840_000
    assert drawer["counted_closing"] == 839_000
    assert drawer["over_short"] == -1_000

    after = await client.get("/api/v1/payments/drawer/summary", headers=headers)
    assert after.json() is None


async def test_correcting_a_paid_expense_date_moves_its_payment_date(
    client: AsyncClient, db, admin_token: str
) -> None:
    """D-76: a Rs 200 cash expense saved on yesterday's date (D-75, the UTC
    day at 03:31 PKT) and corrected to today, the way the Expenses screen
    sends it: the date alone, no `paid_on`. It must then count in today's
    drawer. Before the fix `paid_on` stayed on yesterday."""
    from datetime import date

    headers = _auth(admin_token)
    await _open_drawer(client, db, headers, 500_000)
    yday = (date.fromisoformat(_today()) - timedelta(days=1)).isoformat()
    created = await client.post(
        "/api/v1/expenses",
        json={
            "expense_date": yday,
            "payee": "Electrician",
            "amount_minor": 20_000,
            "status": "paid",
            "payment_method": "Cash",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["paid_on"] == yday
    before = (await client.get("/api/v1/payments/drawer/summary", headers=headers)).json()
    assert before["cash_paid_out"] == 0  # yesterday's expense is not today's drawer

    fixed = await client.patch(
        f"/api/v1/expenses/{created.json()['id']}",
        json={"expense_date": _today(), "payee": "Electrician", "status": "paid"},
        headers=headers,
    )
    assert fixed.status_code == 200, fixed.text
    assert fixed.json()["paid_on"] == _today()
    after = (await client.get("/api/v1/payments/drawer/summary", headers=headers)).json()
    assert after["cash_paid_out"] == 20_000
    assert after["expected_in_drawer"] == 480_000


async def test_close_note_and_attachment_reach_the_z_report(
    client: AsyncClient, db, admin_token: str, other_tenant_token: str
) -> None:
    """D-78 (Malik): "ask for optional notes/reason, any attachment cashier/
    owner wants to do before closing the drawer". Note on close, a PDF pinned
    to the session, both shown on the Z-Report; the file is served inline with
    nosniff and never to another restaurant."""
    import io

    headers = _auth(admin_token)
    session_id = await _open_drawer(client, db, headers, 500_000)
    closed = await client.post(
        "/api/v1/payments/drawer/close",
        json={"closing_balance_counted": 499_100, "note": "Rs 9 short: change to a regular"},
        headers=headers,
    )
    assert closed.status_code == 200, closed.text

    pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n%%EOF\n"
    uploaded = await client.post(
        f"/api/v1/payments/drawer/{session_id}/attachments",
        files={"file": ("count-slip.pdf", io.BytesIO(pdf), "application/pdf")},
        headers=headers,
    )
    assert uploaded.status_code == 201, uploaded.text
    url = uploaded.json()["url"]

    report = await client.get(
        "/api/v1/reports/z-report", params={"date": _today()}, headers=headers
    )
    [drawer] = report.json()["cash_position"]["drawers"]
    assert drawer["note"] == "Rs 9 short: change to a regular"
    assert [(a["filename"], a["url"]) for a in drawer["attachments"]] == [("count-slip.pdf", url)]

    fetched = await client.get(url, headers=headers)
    assert fetched.status_code == 200
    assert fetched.content == pdf
    assert fetched.headers["x-content-type-options"] == "nosniff"

    theirs = await client.get(url, headers=_auth(other_tenant_token))
    assert theirs.status_code == 404
    poke = await client.post(
        f"/api/v1/payments/drawer/{session_id}/attachments",
        files={"file": ("x.pdf", io.BytesIO(pdf), "application/pdf")},
        headers=_auth(other_tenant_token),
    )
    assert poke.status_code == 404


async def test_a_paid_expense_must_say_how_it_was_paid(
    client: AsyncClient, db, admin_token: str
) -> None:
    """D-77: a paid expense with no method never reached the drawer. Refused on
    create and on marking paid; unpaid needs none; a method keeps it paid."""
    # A refused request rolls back the shared test session, which would take
    # the not-yet-committed admin user with it and 401 the next call.
    await db.commit()
    headers = _auth(admin_token)
    base = {"expense_date": _today(), "payee": "Electrician", "amount_minor": 20_000}

    refused = await client.post(
        "/api/v1/expenses", json={**base, "status": "paid"}, headers=headers
    )
    assert refused.status_code == 400
    assert "Cash, Bank or Cheque" in refused.json()["detail"]

    unpaid = await client.post(
        "/api/v1/expenses", json={**base, "status": "unpaid"}, headers=headers
    )
    assert unpaid.status_code == 201, unpaid.text
    marked = await client.patch(
        f"/api/v1/expenses/{unpaid.json()['id']}", json={"status": "paid"}, headers=headers
    )
    assert marked.status_code == 400

    ok = await client.patch(
        f"/api/v1/expenses/{unpaid.json()['id']}",
        json={"status": "paid", "payment_method": "Cash"},
        headers=headers,
    )
    assert ok.status_code == 200, ok.text
    # Once it has a method, an edit that does not resend it is still fine.
    renamed = await client.patch(
        f"/api/v1/expenses/{unpaid.json()['id']}", json={"payee": "Wapda"}, headers=headers
    )
    assert renamed.status_code == 200, renamed.text


async def test_an_explicit_payment_date_is_kept(client: AsyncClient, admin_token: str) -> None:
    """Invoice dated one day, paid another: sending both keeps both."""
    from datetime import date

    headers = _auth(admin_token)
    today = date.fromisoformat(_today())
    created = await client.post(
        "/api/v1/expenses",
        json={
            "expense_date": (today - timedelta(days=5)).isoformat(),
            "payee": "Landlord",
            "amount_minor": 100_000,
            "status": "paid",
            "payment_method": "Cash",
            "paid_on": (today - timedelta(days=5)).isoformat(),
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    moved = await client.patch(
        f"/api/v1/expenses/{created.json()['id']}",
        json={
            "expense_date": (today - timedelta(days=6)).isoformat(),
            "paid_on": (today - timedelta(days=2)).isoformat(),
        },
        headers=headers,
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["expense_date"] == (today - timedelta(days=6)).isoformat()
    assert moved.json()["paid_on"] == (today - timedelta(days=2)).isoformat()
