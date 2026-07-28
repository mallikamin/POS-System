import { useMemo, useState } from "react";
import { SHOP } from "../data/menu";
import type { ServiceType } from "../types";
import { formatGBP } from "../lib/money";
import { checkDelivery, collectionOffered, deliveryOffered } from "../lib/delivery";
import { orderLinesOf, subtotalOf, useCart } from "../store/cart";
import { canOrder, useMenu } from "../store/menu";
import { ApiError, placeOrder } from "../lib/api";
import type { ApiOrderResponse } from "../lib/api";

interface Props {
  onBack: () => void;
  onPlaced: (order: ApiOrderResponse) => void;
}

type PaymentMethod = "card" | "cash";

export default function Checkout({ onBack, onPlaced }: Props) {
  const lines = useCart((s) => s.lines);
  const clear = useCart((s) => s.clear);
  const reconcile = useCart((s) => s.reconcile);
  const subtotal = subtotalOf(lines);

  const menuItems = useMenu((s) => s.items);
  const menuSource = useMenu((s) => s.source);
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
  const [notes, setNotes] = useState("");
  // Card is only offered once Stripe exists. Until then the order is created
  // unpaid and settled in the shop, so cash is not merely the default, it is
  // the only truthful option. See the Payment section below.
  const [payment, setPayment] = useState<PaymentMethod>(
    SHOP.cardPaymentEnabled ? "card" : "cash",
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const delivery = useMemo(
    () => (service === "delivery" ? checkDelivery(areaId, subtotal) : null),
    [service, areaId, subtotal],
  );

  const deliveryFee = delivery?.ok ? delivery.fee : 0;
  const total = subtotal + deliveryFee;

  const contactOk = name.trim().length > 1 && phone.trim().length >= 7;
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

      clear();
      setSubmitting(false);
      onPlaced(order);
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
          placeholder="Email (for your receipt)"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          type="email"
          autoComplete="email"
        />
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
        {/* Card is hidden, not merely unselected, until Stripe is built. The
            order endpoint creates every order `unpaid` and there is no payment
            step behind it, so offering "Pay now by card" would take no money
            while telling the customer it had. Showing one honest option is
            better than two where one is a lie. */}
        {SHOP.cardPaymentEnabled ? (
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
        />
      </section>

      <section className="card p-4 space-y-2">
        <div className="flex justify-between text-cream/70">
          <span>Subtotal</span>
          <span>{formatGBP(subtotal)}</span>
        </div>
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
        <button onClick={place} disabled={!canPlace} className="btn-primary tap w-full h-14">
          {submitting
            ? "Placing order…"
            : payment === "card"
              ? `Pay ${formatGBP(total)}`
              : `Place order · ${formatGBP(total)}`}
        </button>
      ) : (
        /* Online ordering not switched on yet. Never imply an order was placed —
           send them to the phone with their basket total in hand. */
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

      <p className="text-xs text-cream/45 leading-relaxed card p-3">
        <strong className="text-cream/70">Allergens.</strong> {SHOP.allergenNotice}
      </p>

      <p className="text-xs text-cream/40 text-center">
        {SHOP.name} · {SHOP.addressLines.join(", ")}, {SHOP.postcode} ·{" "}
        {SHOP.phones[0]}
      </p>
    </div>
  );
}
