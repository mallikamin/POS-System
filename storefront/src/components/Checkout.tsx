import { useMemo, useState } from "react";
import { SHOP } from "../data/menu";
import type { ServiceType } from "../types";
import { formatGBP } from "../lib/money";
import {
  checkDelivery,
  collectionOffered,
  deliveryOffered,
  orderTiming,
} from "../lib/delivery";
import type { OrderTiming } from "../lib/delivery";
import { orderLinesOf, subtotalOf, useCart } from "../store/cart";
import { canOrder, useMenu } from "../store/menu";
import { ApiError, createCheckoutSession, placeOrder } from "../lib/api";
import type { ApiOrderResponse } from "../lib/api";
import { savePendingOrder } from "../lib/pendingOrder";
import { cardPaymentOffered } from "../lib/cardPayment";

interface Props {
  onBack: () => void;
  onPlaced: (order: ApiOrderResponse, timing: OrderTiming) => void;
}

type PaymentMethod = "card" | "cash";

export default function Checkout({ onBack, onPlaced }: Props) {
  const lines = useCart((s) => s.lines);
  const clear = useCart((s) => s.clear);
  const reconcile = useCart((s) => s.reconcile);
  const subtotal = subtotalOf(lines);
  // Lifted into the cart store (not local state here) so a per-item note
  // typed in ItemModal lands in this same box — see cart.ts `add()` — and
  // survives this component unmounting when the customer goes back to the
  // menu to add more.
  const notes = useCart((s) => s.orderNotes);
  const setNotes = useCart((s) => s.setOrderNotes);

  const menuItems = useMenu((s) => s.items);
  const menuSource = useMenu((s) => s.source);
  // Ordering is gated ONLY on the feature being on and the menu genuinely
  // having come from the API. The clock never refuses an order — it only
  // decides whether this is for now or a pre-order for the next service.
  const orderingLive = canOrder(menuSource);

  const [service, setService] = useState<ServiceType>(
    collectionOffered() ? "collection" : "delivery",
  );
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [address, setAddress] = useState("");
  const [areaId, setAreaId] = useState("");
  const [postcode, setPostcode] = useState("");

  // Delivery gets its own, earlier cut-off than the shop's general close
  // time (Imran, voice note 2026-08-02) — so this has to know which service
  // and area are currently selected, not just the shop-wide clock.
  const timing = orderTiming(new Date(), service, areaId);
  const preOrder = !timing.immediate;
  // Card is only offered once Stripe is wired and proven. Until then the order
  // is created unpaid and settled in the shop, so cash is not merely the
  // default, it is the only truthful option. See the Payment section below.
  const cardOffered = cardPaymentOffered();
  const [payment, setPayment] = useState<PaymentMethod>(
    cardOffered ? "card" : "cash",
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const delivery = useMemo(
    () => (service === "delivery" ? checkDelivery(areaId, subtotal) : null),
    [service, areaId, subtotal],
  );

  const deliveryFee = delivery?.ok ? delivery.fee : 0;
  const serviceFee = SHOP.serviceFee;
  const total = subtotal + deliveryFee + serviceFee;

  // Email is REQUIRED, not a nicety. It is the channel the shop uses to tell the
  // customer their order was accepted and how long it will be — and Imran's own
  // worked example is an order placed at 14:00 and accepted at 15:30, long after
  // the confirmation screen has stopped polling. Without an address that
  // customer never finds out. Deliberately a shape check only: anything
  // stricter rejects real addresses, and the real proof is the mail arriving.
  const emailOk = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
  const contactOk =
    name.trim().length > 1 && phone.trim().length >= 7 && emailOk;
  const addressOk =
    service === "collection" || (address.trim().length > 4 && delivery?.ok === true);
  const canPlace = lines.length > 0 && contactOk && addressOk && !submitting;

  async function place() {
    if (!canPlace) return;
    setSubmitting(true);
    setError(null);

    // Re-check the basket against the live menu before sending anything. The
    // basket is persisted and outlives the page, so this is the last point at
    // which a withdrawn item can be caught without the customer discovering it
    // as a failed order after they have typed their address.
    const dropped = reconcile(menuItems);
    if (dropped > 0) {
      setSubmitting(false);
      setError(
        dropped === 1
          ? "One item in your basket is no longer on the menu, so we've removed it. Please check your order before continuing."
          : `${dropped} items in your basket are no longer on the menu, so we've removed them. Please check your order before continuing.`,
      );
      return;
    }

    try {
      // IDs and quantities only. Every amount on the resulting order — line
      // prices, tax and the delivery fee — is recomputed by the server from
      // its own menu. Sending a price here is a 422 by design.
      const order = await placeOrder({
        service_type: service,
        customer_name: name.trim(),
        customer_phone: phone.trim(),
        ...(email.trim() ? { customer_email: email.trim() } : {}),
        items: orderLinesOf(useCart.getState().lines),
        payment_method: payment,
        ...(notes.trim() ? { notes: notes.trim() } : {}),
        ...(service === "delivery"
          ? {
              delivery_area_id: areaId,
              delivery_address: [address.trim(), postcode.trim().toUpperCase()]
                .filter(Boolean)
                .join(", "),
            }
          : {}),
      });

      // The order now EXISTS, whatever happens next. That is deliberate: a
      // customer who abandons the payment page leaves an ordinary unpaid order
      // the shop can see and chase, rather than nothing at all.
      clear();

      if (payment === "card") {
        try {
          const { checkout_url } = await createCheckoutSession(order.id);
          // Stash before leaving. Stripe returns the browser here as a fresh
          // page load, and without this the customer lands on an empty menu
          // having just paid. `timing` travels with it — service/area are
          // this component's state and won't exist after the round trip.
          savePendingOrder(order, timing);
          window.location.assign(checkout_url);
          // Deliberately leave `submitting` set. The page is being replaced,
          // and re-enabling the button invites a second tap on the way out.
          return;
        } catch {
          // Card could not be started -- Stripe unconfigured, unreachable, or
          // refusing. The order stands and is unpaid, so show the confirmation
          // rather than an error: telling someone their order failed when it
          // is sitting on the shop's tablet is worse than telling them nothing.
          setSubmitting(false);
          onPlaced(order, timing);
          return;
        }
      }

      setSubmitting(false);
      onPlaced(order, timing);
    } catch (cause) {
      // A 409 carries a sentence written for the customer ("We do not deliver
      // to that area."). Anything else gets the generic line.
      setError(
        cause instanceof ApiError
          ? cause.customerMessage
          : "Something went wrong placing your order. Please try again, or give us a ring.",
      );
      setSubmitting(false);
    }
  }

  function deliveryMessage() {
    if (!delivery) return null;
    if (delivery.ok) {
      return (
        <p className="text-sm text-emerald-400 mt-2">
          Delivery to {delivery.area.name} — {formatGBP(delivery.fee)}
        </p>
      );
    }
    if (delivery.reason === "below_minimum")
      return (
        <p className="text-sm text-ember mt-2">
          Add {formatGBP(delivery.shortfall)} more to reach the delivery minimum.
        </p>
      );
    return null;
  }

  return (
    <div className="px-4 pb-32 pt-6 max-w-xl mx-auto space-y-6">
      <button onClick={onBack} className="text-sm text-cream/60 hover:text-cream">
        ← Back to menu
      </button>

      <h1 className="font-display text-2xl">Checkout</h1>

      {/* Collection / delivery */}
      {collectionOffered() && deliveryOffered() && (
        <section>
          <h2 className="label">How would you like it?</h2>
          <div className="grid grid-cols-2 gap-2">
            {(["collection", "delivery"] as ServiceType[]).map((s) => (
              <button
                key={s}
                onClick={() => setService(s)}
                className={`rounded-xl border py-3 font-semibold capitalize
                  ${service === s ? "border-flame bg-flame/10" : "border-ink-line"}`}
              >
                {s}
                <span className="block text-xs font-normal text-cream/50">
                  ~
                  {s === "collection"
                    ? SHOP.collectionMinutes
                    : SHOP.deliveryMinutes}{" "}
                  mins
                </span>
              </button>
            ))}
          </div>
        </section>
      )}

      <section className="space-y-3">
        <h2 className="label">Your details</h2>
        <div>
          <input
            className="field"
            placeholder="Full name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoComplete="name"
          />
        </div>
        <input
          className="field"
          placeholder="Mobile number"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          type="tel"
          autoComplete="tel"
        />
        <input
          className="field"
          placeholder="Email address"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          type="email"
          autoComplete="email"
          required
          aria-invalid={email.trim().length > 0 && !emailOk}
        />
        <p className="text-xs text-white/60">
          We'll email you when the shop confirms your order and how long it will be.
        </p>
      </section>

      {service === "delivery" && (
        <section className="space-y-3">
          <h2 className="label">Delivery address</h2>
          <input
            className="field"
            placeholder="House number and street"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            autoComplete="street-address"
          />
          <input
            className="field uppercase"
            placeholder="Postcode"
            value={postcode}
            onChange={(e) => setPostcode(e.target.value)}
            autoComplete="postal-code"
          />
          <div>
            {/* Priced by village, exactly as the shop's own menu lists it. */}
            <select
              className="field"
              value={areaId}
              onChange={(e) => setAreaId(e.target.value)}
              aria-label="Delivery area"
            >
              <option value="">Choose your area…</option>
              {SHOP.deliveryAreas.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name} — {formatGBP(a.fee)}
                </option>
              ))}
            </select>
            {deliveryMessage()}
            <p className="text-xs text-cream/40 mt-2">
              Don't see your area? Give us a ring on {SHOP.phones[0]}.
            </p>
          </div>
        </section>
      )}

      <section>
        <h2 className="label">Payment</h2>
        {/* Same wording as the printed menu board's "Delivery Charges" box.
            Delivery-only: a service fee for long-distance delivery has
            nothing to say to a customer collecting in person. */}
        {service === "delivery" && (
          <p className="text-xs text-cream/50 mb-3">
            A service fee may be applied for long distance deliveries.
          </p>
        )}
        {/* Card is hidden, not merely unselected, until it is proven end to
            end. Offering "Pay now by card" while the server holds test keys
            would decline every real customer's real card for no reason they
            could understand. Showing one honest option is better than two where
            one is a lie. See `lib/cardPayment.ts` for the `?card=1` override
            that lets us test on the live site without exposing it. */}
        {cardOffered ? (
          <div className="space-y-2">
            <button
              onClick={() => setPayment("card")}
              className={`w-full rounded-xl border px-4 py-3 text-left
                ${payment === "card" ? "border-flame bg-flame/10" : "border-ink-line"}`}
            >
              <span className="font-semibold">Pay now by card</span>
              <span className="block text-xs text-cream/50">
                Secure payment by Stripe
              </span>
            </button>
            <button
              onClick={() => setPayment("cash")}
              className={`w-full rounded-xl border px-4 py-3 text-left
                ${payment === "cash" ? "border-flame bg-flame/10" : "border-ink-line"}`}
            >
              <span className="font-semibold">
                Pay on {service === "delivery" ? "delivery" : "collection"}
              </span>
              <span className="block text-xs text-cream/50">Cash</span>
            </button>
          </div>
        ) : (
          <div className="card p-4">
            <p className="font-semibold">
              Pay on {service === "delivery" ? "delivery" : "collection"}
            </p>
            <p className="text-sm text-cream/60 mt-1">
              Cash, or card in the shop. Online card payment is coming soon.
            </p>
          </div>
        )}
      </section>

      <section>
        <h2 className="label">Notes for the kitchen</h2>
        <textarea
          className="field min-h-[80px]"
          placeholder="Allergies, no salad, extra napkins…"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          maxLength={500}
        />
      </section>

      <section className="card p-4 space-y-2">
        <div className="flex justify-between text-cream/70">
          <span>Subtotal</span>
          <span>{formatGBP(subtotal)}</span>
        </div>
        {serviceFee > 0 && (
          <div className="flex justify-between text-cream/70">
            <span>Service Fee</span>
            <span>{formatGBP(serviceFee)}</span>
          </div>
        )}
        {service === "delivery" && (
          <div className="flex justify-between text-cream/70">
            <span>Delivery</span>
            <span>{deliveryFee > 0 ? formatGBP(deliveryFee) : "—"}</span>
          </div>
        )}
        <div className="flex justify-between font-display text-lg pt-2 border-t border-ink-line">
          <span>Total</span>
          <span>{formatGBP(total)}</span>
        </div>
      </section>

      {error && (
        <p
          role="alert"
          className="card p-3 text-sm text-ember border-ember/40"
        >
          {error}
        </p>
      )}

      {orderingLive ? (
        <div className="space-y-3">
          {/* Say it BEFORE they commit, not after. A customer who finds out
              their 3am order is not coming for hours only once they reach the
              confirmation screen has been misled, however technically true it
              was. */}
          {preOrder && (
            <p className="card p-3 text-sm text-ember border-ember/40">
              {timing.closedReason === "delivery_cutoff" ? (
                <>
                  Online delivery has finished for tonight, so this will be a{" "}
                  <strong className="text-cream">pre-order</strong>. We'll take
                  it now and it'll be accepted when we open at{" "}
                  <strong className="text-cream">{timing.opensAt}</strong> —
                  you'll get a confirmation email then too.
                </>
              ) : (
                <>
                  We're closed at the moment, so this will be a{" "}
                  <strong className="text-cream">pre-order</strong>. We'll take
                  it now and it'll be accepted when we open at{" "}
                  <strong className="text-cream">{timing.opensAt}</strong> —
                  you'll get a confirmation email then too.
                </>
              )}
            </p>
          )}
          <button onClick={place} disabled={!canPlace} className="btn-primary tap w-full h-14">
            {submitting
              ? "Placing order…"
              : payment === "card"
                ? `Pay ${formatGBP(total)}`
                : preOrder
                  ? `Place pre-order · ${formatGBP(total)}`
                  : `Place order · ${formatGBP(total)}`}
          </button>
        </div>
      ) : (
        /* Either ordering is not switched on yet, or the shop is shut for the
           night. Never imply an order was placed — send them to the phone with
           their basket total in hand. */
        <div className="card p-4 space-y-3 border-ember/40">
          <p className="font-semibold text-ember">
            Online ordering is coming very soon
          </p>
          <p className="text-sm text-cream/70">
            We're not taking online payments just yet. Give us a ring and we'll
            get this order started — your total is{" "}
            <strong className="text-cream">{formatGBP(total)}</strong>.
          </p>
          <div className="grid gap-2">
            {SHOP.phones.map((p) => (
              <a
                key={p}
                href={`tel:${p.replace(/\s+/g, "")}`}
                className="btn-primary tap h-13 py-3 w-full"
              >
                Call {p}
              </a>
            ))}
          </div>
          <p className="text-xs text-cream/45">
            Open daily {SHOP.openTime}–{SHOP.closeTime}.
          </p>
        </div>
      )}

      <div className="card p-3 border-ember/40 bg-ember/10">
        <p className="text-xs font-bold uppercase tracking-wide text-ember">
          Allergen Notice
        </p>
        <p className="text-xs text-cream/70 leading-relaxed mt-1">
          {SHOP.allergenNotice}
        </p>
      </div>

      <p className="text-xs text-cream/40 text-center">
        {SHOP.name} · {SHOP.addressLines.join(", ")}, {SHOP.postcode} ·{" "}
        {SHOP.phones[0]}
      </p>
    </div>
  );
}
