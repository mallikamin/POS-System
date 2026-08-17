"""One-off win-back campaign: email everyone who ordered exactly once (OI-83).

Deliberately a script, not a feature. It runs inside the running backend
container against production, so nothing is deployed and the droplet is never
recreated during service.

    # 1. see who would get it, send nothing
    python -m app.scripts.winback_email --dry-run

    # 2. render recipient #1's real email and send it to one address
    python -m app.scripts.winback_email --test someone@example.com

    # 3. fire, paced
    python -m app.scripts.winback_email --send

Safety properties, in order of how much they matter:

* `--send` is the only mode that mails customers. Everything else is inert.
* Every successful send is appended to SENT_LOG *before* the next one starts,
  and addresses already in that file are skipped. A crash halfway through is
  therefore resumable and can never double-email anybody. This is the poor
  man's version of the atomic claim the review worker does in Postgres, and it
  is enough because exactly one copy of this script ever runs at a time.
* Addresses in OPTOUT_FILE are never mailed, checked at send time.
* The pace is one email every PACE_SECONDS. The Brevo API allows 1000/second;
  this is throttled for the receiving side, not the sending one. A domain that
  has only ever sent one-to-one transactional mail suddenly emitting 84
  near-identical messages in ten seconds is what Gmail scores as a new bulk
  sender.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from html import escape as html_escape
from pathlib import Path

import httpx
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import async_session_factory
from app.models.order import Order, OrderItem
from app.services.email_normalise import normalise_email
from app.services.email_service import (
    _C_BODY_TEXT,
    _C_CREAM,
    _C_FLAME,
    _C_INK,
    _C_LINE,
    _C_MUTED,
    _C_PAGE_BG,
    _FONT_STACK,
    _first_name,
    _html_items_table,
    _money,
)

# Chick Shack. Hardcoded on purpose: this is a one-off for one client, and a
# tenant slug lookup would invite running it against the wrong shop.
TENANT_ID = "8b2b6223-7db9-443b-8ace-34dd115a9275"
SHOP_NAME = "Chick Shack"
CURRENCY = "GBP"
MENU_URL = "https://chickshackg84.com/"

PACE_SECONDS = 7.5  # 8 emails/minute -> 85 recipients in about 10.5 minutes
SENT_LOG = Path("/tmp/winback_sent.log")
OPTOUT_FILE = Path("/tmp/winback_optout.txt")

# ⚠️ SUPERSEDED by OI-86 and kept empty on purpose rather than deleted.
#
# This used to hold {"gmail.con", "gmail.cim"} and SKIP those recipients, because
# mailing a domain that does not exist earns a hard bounce. That was the right
# call when the only alternative was a bounce -- but it was treating the symptom.
# `normalise_email` now repairs the domain before sending, so those customers are
# reachable instead of skipped, and the skip would silently exclude the very
# people the fix was written for.
#
# Anything genuinely undeliverable (a misspelt NAME, which nothing can detect)
# still hard-bounces and is auto-suppressed by Brevo.
BAD_DOMAINS: set[str] = set()

BREVO_ENDPOINT = "https://api.brevo.com/v3/smtp/email"

# One order per person, most recent first, for everyone whose whole history is
# a single real order. Predicate is order_visibility.is_real_order() plus
# rejected/voided removed -- identical to email-cohorts_queries.sql and to the
# OI-82 analysis, so the count reconciles with both.
COHORT_SQL = text(
    """
    SELECT (array_agg(o.id ORDER BY o.created_at DESC))[1] AS order_id
    FROM orders o
    WHERE o.tenant_id = :tid
      AND (o.stripe_checkout_session_id IS NULL
           OR o.payment_authorized_at IS NOT NULL
           OR o.accepted_at IS NOT NULL
           OR o.rejected_at IS NOT NULL)
      AND o.rejected_at IS NULL
      AND o.status <> 'voided'
      AND o.customer_email IS NOT NULL
      AND btrim(o.customer_email) <> ''
    GROUP BY lower(btrim(o.customer_email))
    HAVING count(*) = 1
    ORDER BY min(o.created_at)
    """
)


def _unsub_address() -> str:
    return (settings.EMAIL_REPLY_TO or settings.EMAIL_FROM or "").strip()


def _subject(order: Order) -> str:
    return f"Fancy the same again, {_first_name(order)}?"


def _order_date(order: Order) -> str:
    # "Saturday 2 August". The order is the whole point of the email, so the
    # date has to be recognisable rather than an ISO stamp.
    return order.created_at.strftime("%A %-d %B")


def _text_body(order: Order) -> str:
    lines = [f"Hi {_first_name(order)},", ""]
    lines.append(
        f"This is what you had on {_order_date(order)}. Everything on it is "
        "still on the menu, and the fryers are on from 4pm."
    )
    lines.append("")
    for item in order.items:
        mods = ", ".join(m.name for m in item.modifiers)
        suffix = f" ({mods})" if mods else ""
        lines.append(
            f"  {item.quantity} x {item.name}{suffix}"
            f"  {_money(item.total, CURRENCY)}"
        )
    lines.append(f"  Total  {_money(order.subtotal, CURRENCY)}")
    lines.append("")
    lines.append(f"Order again: {MENU_URL}")
    lines.append("")
    lines.append(f"{SHOP_NAME}, Garelochhead. Open 4pm to 10pm, every day.")
    lines.append(
        f"Don't want these? Reply to this email with STOP, or write to "
        f"{_unsub_address()}, and you are off the list."
    )
    return "\n".join(lines)


def _html_body(order: Order) -> str:
    """The campaign email.

    Not built on `_html_shell` from email_service: that footer escapes its
    string and so cannot carry a link, and a marketing email needs a visible
    opt-out in it. Everything else -- the wordmark, the palette, the items
    table -- is imported from there so the two cannot drift apart.
    """
    name = html_escape(_first_name(order))
    unsub = html_escape(_unsub_address())
    total = html_escape(_money(order.subtotal, CURRENCY))

    return f"""<!doctype html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0; padding:0; background-color:{_C_PAGE_BG}; font-family:{_FONT_STACK};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:{_C_PAGE_BG};">
<tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px; width:100%; background-color:#ffffff; border-radius:10px; overflow:hidden;">
<tr>
<td style="background-color:{_C_INK}; padding:28px 32px; text-align:center;">
<div style="font-family:{_FONT_STACK}; font-weight:800; font-size:26px; letter-spacing:1px; text-transform:uppercase;">
<span style="color:{_C_CREAM};">CHICK&nbsp;</span><span style="color:{_C_FLAME};">SHACK</span>
</div>
<div style="display:inline-block; margin-top:14px; padding:6px 16px; border-radius:999px; background-color:{_C_FLAME}; color:#ffffff; font-weight:700; font-size:12px; letter-spacing:1px; text-transform:uppercase;">
Order again
</div>
</td>
</tr>
<tr>
<td style="padding:28px 32px;">
<p style="margin:0 0 16px 0; font-size:22px; line-height:1.2; color:{_C_INK}; font-weight:800;">{name}, fancy the same again?</p>
<p style="margin:0 0 20px 0; font-size:15px; line-height:1.55; color:{_C_BODY_TEXT};">This is what you had on {html_escape(_order_date(order))}. Everything on it is still on the menu, and the fryers are on from 4pm.</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid {_C_LINE}; border-radius:8px;">
<tr><td style="padding:16px 18px;">
{_html_items_table(order, CURRENCY)}
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:8px; border-top:1px solid {_C_LINE};">
<tr>
<td style="padding:10px 0 0 0; font-size:15px; font-weight:800; color:{_C_INK};">Total</td>
<td style="padding:10px 0 0 0; font-size:15px; font-weight:800; color:{_C_INK}; text-align:right;">{total}</td>
</tr>
</table>
</td></tr>
</table>
<table role="presentation" cellpadding="0" cellspacing="0" style="margin:22px 0 0 0;">
<tr>
<td style="border-radius:6px; background-color:{_C_FLAME};">
<a href="{MENU_URL}" style="display:inline-block; padding:13px 26px; font-size:14px; font-weight:700; color:#ffffff; text-decoration:none; border-radius:6px;">Go to the menu</a>
</td>
</tr>
</table>
<p style="margin:14px 0 0 0; font-size:13px; color:{_C_MUTED};">Takes about a minute to build again.</p>
</td>
</tr>
<tr>
<td style="padding:18px 32px; background-color:{_C_PAGE_BG}; border-top:1px solid {_C_LINE};">
<p style="margin:0 0 6px 0; font-size:12px; color:{_C_MUTED};">{SHOP_NAME}, Garelochhead &middot; Open 4pm to 10pm, every day</p>
<p style="margin:0; font-size:12px; color:{_C_MUTED};">You are getting this because you ordered from us online. Don't want these? <a href="mailto:{unsub}?subject=Unsubscribe" style="color:{_C_MUTED};">Reply with STOP</a> and you are off the list.</p>
</td>
</tr>
</table>
</td></tr>
</table>
</body>
</html>"""


async def _send(to: str, subject: str, text_body: str, html: str) -> None:
    """Post one email to Brevo. Raises on anything that is not a 2xx."""
    sender: dict[str, str] = {"email": settings.EMAIL_FROM}
    if settings.EMAIL_FROM_NAME:
        sender["name"] = settings.EMAIL_FROM_NAME
    unsub = _unsub_address()
    payload = {
        "sender": sender,
        "to": [{"email": to}],
        "subject": subject,
        "textContent": text_body,
        "htmlContent": html,
        "replyTo": {"email": unsub},
        # Gmail and Outlook both look for this on bulk mail. Without it a
        # marketing send from a domain that has only done transactional gets
        # scored worse than it deserves.
        "headers": {"List-Unsubscribe": f"<mailto:{unsub}?subject=Unsubscribe>"},
    }
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            BREVO_ENDPOINT,
            json=payload,
            headers={"api-key": settings.BREVO_API_KEY, "accept": "application/json"},
        )
    response.raise_for_status()


def _already_sent() -> set[str]:
    if not SENT_LOG.exists():
        return set()
    return {
        line.split("\t")[0].strip().lower()
        for line in SENT_LOG.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


def _opted_out() -> set[str]:
    if not OPTOUT_FILE.exists():
        return set()
    return {
        line.strip().lower()
        for line in OPTOUT_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


async def _load_recipients() -> list[Order]:
    async with async_session_factory() as db:
        rows = await db.execute(COHORT_SQL, {"tid": TENANT_ID})
        order_ids = [row[0] for row in rows]
        if not order_ids:
            return []
        result = await db.execute(
            select(Order)
            .where(Order.id.in_(order_ids))
            .options(selectinload(Order.items).selectinload(OrderItem.modifiers))
            .order_by(Order.created_at)
        )
        return list(result.scalars().unique())


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="list recipients, send nothing")
    group.add_argument("--test", metavar="EMAIL", help="send recipient #1's real email to one address")
    group.add_argument("--send", action="store_true", help="mail every recipient, paced")
    parser.add_argument(
        "--sample",
        metavar="ORDER_NUMBER",
        help="with --test, render this order instead of the first pending one",
    )
    args = parser.parse_args()

    if not settings.BREVO_API_KEY or not settings.EMAIL_FROM:
        print("Email is not configured on this container. Nothing sent.")
        return 1

    orders = await _load_recipients()
    sent = _already_sent()
    optout = _opted_out()

    pending = []
    undeliverable = []
    for order in orders:
        address = (order.customer_email or "").strip().lower()
        if address in sent or address in optout:
            continue
        if address.rsplit("@", 1)[-1] in BAD_DOMAINS:
            undeliverable.append(order)
            continue
        pending.append(order)

    print(f"cohort:        {len(orders)} people who ordered exactly once")
    print(f"already sent:  {len(sent)}")
    print(f"opted out:     {len(optout)}")
    print(f"undeliverable: {len(undeliverable)} "
          f"({', '.join(sorted({(o.customer_email or '').rsplit('@', 1)[-1] for o in undeliverable})) or 'none'})")
    print(f"to send now:   {len(pending)}")
    print(f"pace:          one every {PACE_SECONDS}s "
          f"(~{60 / PACE_SECONDS:.0f}/min, ~{len(pending) * PACE_SECONDS / 60:.1f} min total)")
    print(f"from:          {settings.EMAIL_FROM_NAME or ''} <{settings.EMAIL_FROM}>")
    print(f"reply/unsub:   {_unsub_address()}")
    print()

    if args.dry_run:
        for i, order in enumerate(pending, 1):
            items = ", ".join(f"{it.quantity}x {it.name}" for it in order.items)
            print(
                f"{i:3}. {_first_name(order):12} {order.order_number}  "
                f"{_money(order.subtotal, CURRENCY):>8}  {order.created_at:%d %b}  {items[:60]}"
            )
        print("\nDRY RUN. Nothing was sent.")
        return 0

    if args.test:
        if not pending:
            print("No pending recipients, so there is nothing to render.")
            return 1
        sample = pending[0]
        if args.sample:
            matches = [o for o in pending if o.order_number == args.sample]
            if not matches:
                print(f"No pending recipient has order {args.sample}.")
                return 1
            sample = matches[0]
        subject = _subject(sample)
        print(f"Rendering {_first_name(sample)}'s order {sample.order_number} "
              f"and sending it to {args.test}")
        print(f"Subject: {subject}")
        await _send(args.test, subject, _text_body(sample), _html_body(sample))
        print("TEST SENT. No customer was emailed.")
        return 0

    # --send
    print(f"SENDING to {len(pending)} customers. Ctrl-C is safe, progress is logged.\n")
    failures = 0
    for i, order in enumerate(pending, 1):
        # Repair an obvious domain typo before sending (OI-86). The stored
        # address is untouched; only what we hand Brevo changes.
        to, _repaired = normalise_email(order.customer_email)
        try:
            await _send(to, _subject(order), _text_body(order), _html_body(order))
        except Exception as exc:  # noqa: BLE001 - one bad address must not stop the run
            failures += 1
            print(f"{i:3}/{len(pending)}  FAILED  {to}  {exc}", flush=True)
        else:
            with SENT_LOG.open("a", encoding="utf-8") as handle:
                handle.write(f"{to.lower()}\t{order.order_number}\n")
            print(f"{i:3}/{len(pending)}  sent    {to}", flush=True)
        if i < len(pending):
            await asyncio.sleep(PACE_SECONDS)

    print(f"\nDone. {len(pending) - failures} sent, {failures} failed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
