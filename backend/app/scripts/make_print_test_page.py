"""Generate a self-contained print test page for the shop tablet.

Why self-contained
------------------
This page is handed to the client to prove one link in the chain:

    web page in Chrome on Android  ->  RawBT  ->  TCP:9100  ->  printer

Nothing else. So it deliberately has **no backend, no login, no API call and no
network dependency**: the ESC/POS payload is baked in as base64 at build time.
If it needed our API, a failure would be ambiguous -- was it the API, the
token, CORS, or the printer? A static page makes a failure mean exactly one
thing, which is the entire point of a test.

Usage
-----
    docker exec pos-system-backend-1 python -m app.scripts.make_print_test_page \
        > storefront/public/print-test.html

Then deploy the storefront, or send him the file directly. It works opened from
a downloaded file too, which is a useful fallback if the deploy has not gone
out.
"""

from __future__ import annotations

import base64
import html
import uuid
from datetime import datetime, timedelta, timezone

from app.models.order import Order, OrderItem, OrderItemModifier
from app.services import escpos
from app.services.print_service import build_online_order_ticket, to_rawbt_url

SHOP_NAME = "Chick Shack"


def sample_order() -> Order:
    """A realistic ticket, not a "hello world".

    Deliberately includes the things most likely to print wrong: a pound sign,
    an ampersand in an area name, a multi-line address, item modifiers, an item
    note, and the unpaid-cash-on-delivery banner.
    """
    placed = datetime(2026, 7, 27, 18, 42, tzinfo=timezone.utc)

    def line(name: str, qty: int, mods: tuple[str, ...] = (), notes: str | None = None):
        item = OrderItem(
            id=uuid.uuid4(), name=name, quantity=qty,
            unit_price=0, total=0, notes=notes,
        )
        item.modifiers = [
            OrderItemModifier(id=uuid.uuid4(), name=m, price_adjustment=0)
            for m in mods
        ]
        return item

    order = Order(
        id=uuid.uuid4(),
        order_number="TEST-001",
        order_type="online",
        status="in_kitchen",
        payment_status="unpaid",
        customer_name="Test Customer",
        customer_phone="07700 900123",
        subtotal=2450,
        tax_amount=0,
        discount_amount=0,
        delivery_fee=400,
        total=2850,
        service_type="delivery",
        delivery_address="12 Shore Road",
        delivery_area="Mambeg, Clynder & Rahane",
        created_at=placed,
        accepted_at=placed + timedelta(minutes=1),
        eta_minutes=45,
        notes="This is a test ticket. No food needed.",
    )
    order.items = [
        line("Peri Peri Half Chicken", 2, ("Hot",), "no salt"),
        line("Chips", 1, ("Large",)),
        line("Rubicon Passionfruit", 3),
    ]
    return order


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Printer test</title>
<style>
  :root {{ color-scheme: light dark; }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 24px;
    font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    line-height: 1.5; max-width: 640px; margin-inline: auto;
  }}
  h1 {{ font-size: 1.4rem; margin: 0 0 4px; }}
  p.sub {{ margin: 0 0 24px; opacity: .7; }}
  button {{
    width: 100%; min-height: 72px; font-size: 1.25rem; font-weight: 600;
    border: 0; border-radius: 12px; background: #c81e1e; color: #fff;
    cursor: pointer; margin-bottom: 12px;
  }}
  button:active {{ opacity: .8; }}
  button.secondary {{ background: #374151; min-height: 56px; font-size: 1rem; }}
  ol {{ padding-left: 20px; }}
  li {{ margin-bottom: 10px; }}
  pre {{
    background: #111; color: #eee; padding: 14px; border-radius: 10px;
    overflow-x: auto; font-size: 12px; line-height: 1.35;
  }}
  .note {{
    border-left: 4px solid #c81e1e; padding: 10px 14px; margin: 20px 0;
    background: rgba(200,30,30,.08); border-radius: 0 8px 8px 0;
  }}

  /* Route 3 only: what Android's own print dialog renders. Sized for 80mm
     paper, which is 72mm of printable width. Everything else is hidden so the
     print is the slip and nothing else. */
  #slip {{ display: none; }}
  @media print {{
    body > *:not(#slip) {{ display: none !important; }}
    #slip {{
      display: block; white-space: pre; font-family: "Courier New", monospace;
      font-size: 11pt; line-height: 1.25; color: #000;
    }}
    @page {{ size: 72mm auto; margin: 0; }}
  }}
</style>
</head>
<body>

<h1>Printer test</h1>
<p class="sub">{shop} online orders</p>

<div class="note">
  <strong>Before you tap the button:</strong> open the RawBT app once and add
  your printer. Choose the network or WiFi option, enter the printer's IP
  address, and set the port to <strong>9100</strong>. Do a test print from
  inside RawBT first. If that works, come back here.
</div>

<button onclick="printTicket()">1 &nbsp;Print test ticket</button>
<button class="secondary" onclick="printViaIntent()">
  2 &nbsp;Did nothing? Try this
</button>
<button class="secondary" onclick="window.print()">
  3 &nbsp;Still nothing? Try this
</button>
<p style="opacity:.7;font-size:.9rem;margin-top:-4px;">
  Try them in order. Button 3 opens the normal Android print box, where you
  pick RawBT from the printer list.
</p>

<div id="slip">{preview}</div>

<h2 style="font-size:1.05rem;margin-top:28px;">What should come out</h2>
<pre>{preview}</pre>

<h2 style="font-size:1.05rem;">If nothing prints</h2>
<ol>
  <li>Does a test print from inside the RawBT app itself work? If not, the
      problem is the printer or the network, not this page.</li>
  <li>Is the tablet on the shop WiFi rather than mobile data?</li>
  <li>Work down the three buttons. They reach the printer three different
      ways, and knowing which one works tells us how to build it.</li>
  <li>Send us a photo of whatever the printer does produce, even if it looks
      like nonsense. That tells us a lot.</li>
  <li>Send the printer's make and model. There is a chance it can print with
      no app at all, and that would be the simplest answer of the lot.</li>
</ol>

<p style="opacity:.7;font-size:.9rem;">
  Tell us which button worked. That is the only result we need.
</p>

<script>
  // Built at generation time by app/scripts/make_print_test_page.py so this
  // page needs no server. Two ways to hand the job to RawBT: the rawbt:
  // scheme, and an intent: URL naming the package explicitly. Chrome on
  // Android handles them differently depending on version, so both are here.
  var PAYLOAD = "{payload}";

  function printTicket() {{
    window.location.href = "rawbt:base64," + PAYLOAD;
  }}

  function printViaIntent() {{
    window.location.href =
      "intent:base64," + PAYLOAD +
      "#Intent;scheme=rawbt;package=ru.a402d.rawbtprinter;end;";
  }}
</script>

</body>
</html>
"""


def main() -> None:
    payload = build_online_order_ticket(
        sample_order(), shop_name=SHOP_NAME, currency="GBP", width=48,
        utc_offset_minutes=60,
    )
    print(
        TEMPLATE.format(
            shop=html.escape(SHOP_NAME),
            preview=html.escape(escpos.preview(payload).rstrip()),
            payload=base64.b64encode(payload).decode("ascii"),
        )
    )
    # to_rawbt_url is the same construction the live tablet uses; referenced
    # here so the two cannot drift apart unnoticed.
    assert to_rawbt_url(payload).endswith(
        base64.b64encode(payload).decode("ascii")
    )


if __name__ == "__main__":
    main()
