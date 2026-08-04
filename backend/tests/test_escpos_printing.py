"""Tests for ESC/POS ticket generation.

These exist because the printer is 6000 km away in a Scottish kitchen and we
cannot iterate against it. The bytes have to be right before they are sent.

Deliberately no database and no fixtures: ticket rendering is a pure function
from order data to bytes, and keeping it that way is what makes it testable at
all.
"""

from __future__ import annotations

import base64
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models.order import Order, OrderItem, OrderItemModifier
from app.services import escpos
from app.services.escpos import Ticket
from app.services.print_service import (
    build_online_order_ticket,
    money,
    to_rawbt_url,
)


# ---------------------------------------------------------------------------
# Encoding
# ---------------------------------------------------------------------------


def test_pound_sign_is_a_single_cp437_byte():
    """The client is in the UK. Every ticket carries a pound sign.

    UTF-8 would send 0xC2 0xA3 and print two junk characters on every money
    line. CP437 has it at 0x9C.
    """
    assert escpos.encode("£") == b"\x9c"


def test_encoding_never_raises_on_characters_the_printer_lacks():
    # A mangled character is recoverable. An exception loses the order.
    out = escpos.encode("Peri Peri — Half ‘Chicken’ 你好")
    assert isinstance(out, bytes)
    # The typographic dash and quotes are transliterated, not replaced.
    assert b"-" in out
    assert b"'" in out


def test_non_breaking_space_becomes_a_real_space():
    # Menu text pasted from a website is full of these.
    assert escpos.encode("Half Chicken") == b"Half Chicken"


# ---------------------------------------------------------------------------
# Wrapping
# ---------------------------------------------------------------------------


def test_wrap_never_exceeds_the_paper_width():
    text = "Peri Peri Half Chicken with Spicy Rice and Two Regular Sides"
    for line in escpos.wrap(text, 24):
        assert len(line) <= 24


def test_wrap_hard_breaks_a_word_longer_than_the_paper():
    """A single unbroken token must not silently overflow the line.

    This is the specific case textwrap gets wrong by default, and an
    overflowing line on a thermal printer is truncated, not wrapped.
    """
    lines = escpos.wrap("A" * 60, 20)
    assert all(len(line) <= 20 for line in lines)
    assert "".join(lines) == "A" * 60


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


def test_columns_right_aligns_the_amount():
    out = Ticket(width=24).columns("Subtotal", "£24.50").preview()
    line = out.splitlines()[0]
    assert len(line) == 24
    assert line.endswith("£24.50")
    assert line.startswith("Subtotal")


def test_columns_truncates_the_label_not_the_amount():
    """If something must be lost it must not be the money."""
    out = Ticket(width=20).columns("A" * 40, "£1,234.56").preview()
    assert out.splitlines()[0].endswith("£1,234.56")


def test_field_labels_form_a_column():
    """Regression: `wrap` collapses runs of spaces, so padding done with
    literal spaces in the string silently disappeared and the labels did not
    line up."""
    out = Ticket(width=48).field("Name", "Ahmed Khan").field("Phone", "07909").preview()
    name, phone = out.splitlines()[:2]
    assert name == "Name   Ahmed Khan"
    assert phone == "Phone  07909"


def test_wrapped_field_value_hangs_under_itself_not_under_the_label():
    out = Ticket(width=24).field("Addr", "Flat 4 128 Marchmont Crescent").preview()
    lines = out.splitlines()
    assert lines[0].startswith("Addr   ")
    assert lines[1].startswith(" " * 7)


def test_indented_text_keeps_its_indent():
    """Regression: a modifier printed hard against the left margin no longer
    reads as belonging to the item above it."""
    out = Ticket(width=48).text("    - Hot").preview()
    assert out.splitlines()[0] == "    - Hot"


def test_bold_text_also_keeps_its_indent():
    out = Ticket(width=48).bold("    ** no salt").preview()
    assert out.splitlines()[0] == "    ** no salt"


def test_indent_is_carried_onto_wrapped_continuation_lines():
    out = Ticket(width=20).text("    - extra hot with garlic mayo").preview()
    assert all(line.startswith("    ") for line in out.splitlines() if line)


def test_ticket_starts_with_an_init_command():
    # Without ESC @ the ticket inherits whatever mode the previous job left
    # the printer in, which is how you get a whole slip in double height.
    assert Ticket().bytes().startswith(escpos.INIT)


def test_ticket_ends_with_a_cut():
    assert Ticket().cut().bytes().endswith(escpos.CUT)


# ---------------------------------------------------------------------------
# Money
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "minor,currency,expected",
    [
        (2450, "GBP", "£24.50"),
        (300, "GBP", "£3.00"),
        (0, "GBP", "£0.00"),
        (123456, "GBP", "£1,234.56"),
        (850, "PKR", "Rs.8.50"),
        (999, "XYZ", "XYZ 9.99"),
    ],
)
def test_money_formatting(minor, currency, expected):
    assert money(minor, currency) == expected


def test_money_never_loses_a_penny_to_float_rounding():
    # 8.50 is the case that rendered as 9 in the storefront formatter bug.
    assert money(850, "GBP") == "£8.50"
    assert money(845, "GBP") == "£8.45"


# ---------------------------------------------------------------------------
# The ticket itself
# ---------------------------------------------------------------------------


def _order(**overrides) -> Order:
    """A representative accepted online order, transient (no DB)."""
    now = datetime(2026, 7, 27, 17, 42, tzinfo=timezone.utc)
    item = OrderItem(
        id=uuid.uuid4(),
        name="Peri Peri Half Chicken",
        quantity=2,
        unit_price=850,
        total=1700,
        notes=None,
    )
    item.modifiers = [
        OrderItemModifier(id=uuid.uuid4(), name="Hot", price_adjustment=0)
    ]
    order = Order(
        id=uuid.uuid4(),
        order_number="260727-001",
        order_type="online",
        status="in_kitchen",
        payment_status="unpaid",
        customer_name="Ahmed Khan",
        customer_phone="07909313456",
        subtotal=1700,
        tax_amount=0,
        discount_amount=0,
        delivery_fee=0,
        total=1700,
        service_type="collection",
        created_at=now,
        accepted_at=now + timedelta(minutes=2),
        eta_minutes=30,
    )
    order.items = [item]
    for key, value in overrides.items():
        setattr(order, key, value)
    return order


def _preview(order: Order, **kwargs) -> str:
    payload = build_online_order_ticket(order, shop_name="Chick Shack", **kwargs)
    return escpos.preview(payload)


def test_collection_ticket_says_collection():
    out = _preview(_order())
    assert "COLLECTION" in out
    assert "DELIVERY" not in out


def test_delivery_ticket_carries_the_address_and_area():
    order = _order(
        service_type="delivery",
        delivery_address="12 Shore Road",
        delivery_area="Arrochar",
        delivery_fee=1500,
        total=3200,
    )
    out = _preview(order)
    assert "DELIVERY" in out
    assert "12 Shore Road" in out
    assert "Arrochar" in out
    assert "£15.00" in out  # the delivery fee line


def test_service_fee_prints_as_its_own_line():
    out = _preview(_order(service_fee=70, total=1770))
    assert "Service Fee" in out
    assert "£0.70" in out


def test_zero_service_fee_prints_no_line():
    out = _preview(_order(service_fee=0))
    assert "Service Fee" not in out


def test_ready_time_is_computed_not_left_as_minutes():
    """The kitchen must not have to add 30 minutes in their head mid-rush."""
    out = _preview(_order(), utc_offset_minutes=60)
    # Accepted 17:44 UTC + 30 min = 18:14 UTC = 19:14 at UTC+1.
    assert "19:14" in out
    assert "READY AT" in out


def test_delivery_ticket_says_deliver_by_not_ready_at():
    out = _preview(_order(service_type="delivery"))
    assert "DELIVER BY" in out


def test_timestamps_are_shown_in_shop_local_time():
    """Server is in Singapore, shop is in Scotland. A ticket showing UTC
    during a rush is worse than no ticket."""
    out = _preview(_order(), utc_offset_minutes=60)
    assert "Placed 18:42" in out  # 17:42 UTC -> 18:42 BST


def test_unpaid_order_shouts_the_amount_to_collect():
    """A driver who assumes an order is prepaid does not come back with
    the money. This is the most expensive thing to get wrong."""
    out = _preview(_order(payment_status="unpaid", total=3200))
    assert "NOT PAID" in out
    assert "COLLECT £32.00" in out


def test_paid_order_does_not_ask_for_money():
    out = _preview(_order(payment_status="paid"))
    assert "PAID ONLINE" in out
    assert "NOT PAID" not in out
    # Not a bare "COLLECT" check: the heading on a collection order is
    # "COLLECTION", which contains it.
    assert "COLLECT £" not in out


def test_paid_online_line_is_double_size_and_bold_like_not_paid():
    """"Unpaid is shouted, not whispered" was already this ticket's design
    principle -- paid now shouts too, at the same weight, so a driver reads it
    just as unmistakably (session N pending item 2, 2026-08-01)."""
    payload = build_online_order_ticket(
        _order(payment_status="paid"), shop_name="Chick Shack"
    )
    big_bold = (
        escpos.SIZE_DOUBLE + escpos.BOLD_ON + escpos.encode("*** PAID ONLINE ***") + b"\n"
    )
    assert big_bold in payload


def test_item_modifiers_and_notes_are_printed():
    order = _order()
    order.items[0].notes = "no salt"
    out = _preview(order)
    assert "2 x Peri Peri Half Chicken" in out
    assert "- Hot" in out
    assert "no salt" in out


# ---------------------------------------------------------------------------
# OI-61 -- card payment still processing is not the same as unpaid
# ---------------------------------------------------------------------------


def test_card_checkout_started_but_not_captured_says_approved_not_unpaid():
    """Stripe is holding the money; only the capture is outstanding.

    Printing "NOT PAID" here caused a real double-charge on 2026-08-02 (OI-61):
    staff read it and took payment again in person. Printing "CARD PROCESSING"
    then caused a live scare on 2026-08-04 -- it reads as "we don't know yet"
    about money that is actually secured. Since OI-65 an unapproved card order
    cannot reach the kitchen at all, so this state always means APPROVED.
    """
    out = _preview(
        _order(
            payment_status="unpaid",
            stripe_checkout_session_id="cs_test_123",
            total=3200,
        )
    )
    assert "CARD APPROVED" in out
    assert "PROCESSING" not in out
    assert "NOT PAID" not in out
    assert "COLLECT £32.00" not in out
    assert "DO NOT COLLECT CASH" in out


def test_genuinely_cash_order_still_shouts_not_paid():
    """No checkout session at all -- must not be softened by the new branch."""
    out = _preview(
        _order(payment_status="unpaid", stripe_checkout_session_id=None, total=3200)
    )
    assert "NOT PAID" in out
    assert "COLLECT £32.00" in out
    assert "CARD APPROVED" not in out


def test_captured_card_order_still_says_paid_online():
    """Once captured, the ticket says PAID regardless of how it got there."""
    out = _preview(
        _order(payment_status="paid", stripe_checkout_session_id="cs_test_123")
    )
    assert "PAID ONLINE" in out
    assert "CARD APPROVED" not in out
    assert "NOT PAID" not in out


# ---------------------------------------------------------------------------
# Dip tubs -- rolled up and printed first, not buried under whichever item
# they were chosen for (Imran, voice note 2026-08-03)
# ---------------------------------------------------------------------------


def test_dip_tub_modifiers_are_grouped_before_the_cook_list():
    order = _order()
    order.items[0].modifiers = [
        OrderItemModifier(id=uuid.uuid4(), name="Hot", price_adjustment=0),
        OrderItemModifier(
            id=uuid.uuid4(), name="Garlic Mayo (Dip Tub)", price_adjustment=0
        ),
    ]
    out = _preview(order)
    assert "DIP TUBS" in out
    dip_pos = out.index("DIP TUBS")
    cook_pos = out.index("2 x Peri Peri Half Chicken")
    assert dip_pos < cook_pos
    # Not printed a second time nested under the item.
    assert out.count("Garlic Mayo (Dip Tub)") == 1
    assert "- Hot" in out  # a non-dip modifier still prints where it always did


def test_dip_tubs_from_different_items_are_rolled_up_by_name():
    order = _order()
    second_item = OrderItem(
        id=uuid.uuid4(),
        name="Peri Peri Wings Meal",
        quantity=1,
        unit_price=999,
        total=999,
        notes=None,
    )
    second_item.modifiers = [
        OrderItemModifier(
            id=uuid.uuid4(), name="Garlic Mayo (Dip Tub)", price_adjustment=0
        )
    ]
    order.items[0].modifiers = [
        OrderItemModifier(
            id=uuid.uuid4(), name="Garlic Mayo (Dip Tub)", price_adjustment=0
        )
    ]
    order.items.append(second_item)
    out = _preview(order)
    # 2x from the first item's quantity (2) + 1x from the second's quantity (1).
    assert "3 x Garlic Mayo (Dip Tub)" in out


def test_standalone_dips_category_item_is_unaffected():
    """A dip sold as its own menu item (no modifier, no "(Dip Tub)" suffix
    on the item name itself) is not part of this grouping -- nothing was
    reported wrong there, only the nested-modifier case."""
    order = _order()
    dip_item = OrderItem(
        id=uuid.uuid4(),
        name="Peri Peri Sauce",
        quantity=2,
        unit_price=100,
        total=200,
        notes=None,
    )
    order.items.append(dip_item)
    out = _preview(order)
    assert "2 x Peri Peri Sauce" in out
    assert "DIP TUBS" not in out


def test_every_line_fits_the_paper():
    """The single most common thermal-printing bug: content wider than the
    paper is truncated by the printer, silently."""
    order = _order(
        service_type="delivery",
        delivery_address="Flat 4, 128 Marchmont Crescent, Garelochhead",
        delivery_area="Mambeg, Clynder & Rahane",
        customer_name="Bartholomew Fitzgerald-Montgomery",
        delivery_fee=400,
        total=2100,
    )
    order.items[0].name = "Peri Peri Whole Chicken with Spicy Rice and Two Sides"
    for line in _preview(order, width=48).splitlines():
        # Double-width lines use half the columns, so 48 is the ceiling for
        # everything and generous for the centred headings.
        assert len(line) <= 48, f"line overflows the paper: {line!r}"


def test_ticket_is_cut_at_the_end():
    payload = build_online_order_ticket(_order(), shop_name="Chick Shack")
    assert payload.endswith(escpos.CUT)


def test_no_utf8_bytes_reach_the_printer():
    """Any byte sequence from UTF-8 encoding would print as garbage."""
    payload = build_online_order_ticket(
        _order(customer_name="Renée O’Brien"), shop_name="Chick Shack"
    )
    assert b"\xc2\xa3" not in payload  # UTF-8 pound
    assert b"\xe2\x80" not in payload  # UTF-8 typographic punctuation


# ---------------------------------------------------------------------------
# Copies and the daily number (OI-51 / OI-52)
# ---------------------------------------------------------------------------


def test_three_copies_ride_in_one_payload_each_with_its_own_cut():
    """Imran wants three slips per accepted order. The repeat lives in the
    payload so the tablet still makes exactly ONE rawbt: navigation — three
    navigations are three chances for Chrome to drop the handoff."""
    payload = build_online_order_ticket(_order(), shop_name="Chick Shack", copies=3)
    assert payload.count(escpos.CUT) == 3
    assert escpos.preview(payload).count("ORDER 260727-001") == 3


def test_copies_carry_no_copy_label():
    """Imran, 2026-08-01: remove "COPY n OF 3" entirely -- all three slips go
    to separate stations, none of them is "the extra one". The daily number
    above it is untouched (see the test below)."""
    out = _preview(_order(), copies=3)
    assert "COPY" not in out


def test_single_copy_carries_no_copy_label():
    out = _preview(_order())
    assert "COPY" not in out
    payload = build_online_order_ticket(_order(), shop_name="Chick Shack")
    assert payload.count(escpos.CUT) == 1


def test_daily_number_leads_every_copy_double_size_and_bold():
    """The kitchen works by the day's number, not the full order number. It
    must be the first thing on each slip, at the largest size this exact
    printer has proven on paper (double), and bold."""
    payload = build_online_order_ticket(_order(), shop_name="Chick Shack", copies=3)
    # center(big=True, bold=True) emits SIZE_DOUBLE then BOLD_ON then the text.
    big_number = escpos.SIZE_DOUBLE + escpos.BOLD_ON + escpos.encode("#001") + b"\n"
    assert payload.count(big_number) == 3
    assert escpos.preview(payload).splitlines()[0] == "#001"


def test_daily_number_is_extracted_from_the_order_number_not_recounted():
    # The numbering already exists and already resets daily (YYMMDD-NNN).
    # 260727-047 is the 47th order of that day; the slip must show #047.
    out = _preview(_order(order_number="260727-047"))
    assert "#047" in out


# ---------------------------------------------------------------------------
# The handoff to the tablet
# ---------------------------------------------------------------------------


def test_rawbt_url_is_a_valid_scheme_with_decodable_payload():
    payload = build_online_order_ticket(_order(), shop_name="Chick Shack")
    url = to_rawbt_url(payload)
    assert url.startswith("rawbt:base64,")
    assert base64.b64decode(url.removeprefix("rawbt:base64,")) == payload


def test_rawbt_url_stays_within_a_sane_url_length():
    """The payload rides in a URL the browser navigates to. A realistic
    ticket — even at three copies — must not approach browser or intent
    limits."""
    order = _order()
    order.items = order.items * 20  # a 20-line order, far beyond typical
    url = to_rawbt_url(
        build_online_order_ticket(order, shop_name="Chick Shack", copies=3)
    )
    assert len(url) < 32_000
