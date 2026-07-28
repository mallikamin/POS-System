import { useMemo, useState } from "react";
import { SHOP } from "../data/menu";
import type { ServiceType } from "../types";
import { formatGBP } from "../lib/money";
import { checkDelivery, collectionOffered, deliveryOffered } from "../lib/delivery";
import { subtotalOf, useCart } from "../store/cart";

interface Props {
  onBack: () => void;
  onPlaced: (ref: string) => void;
}

type PaymentMethod = "card" | "cash";

export default function Checkout({ onBack, onPlaced }: Props) {
  const lines = useCart((s) => s.lines);
  const clear = useCart((s) => s.clear);
  const subtotal = subtotalOf(lines);

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
  const [payment, setPayment] = useState<PaymentMethod>("card");
  const [submitting, setSubmitting] = useState(false);

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
    setSubmitting(true);
    // NOT WIRED TO THE BACKEND YET. Items 3-4 of the build add the public order
    // endpoint and Stripe. Until then this is a front-end preview only — no
    // order is created, no payment is taken. Do not present this as working.
    await new Promise((r) => setTimeout(r, 600));
    const ref = `CS${Date.now().toString().slice(-6)}`;
    clear();
    setSubmitting(false);
    onPlaced(ref);
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

      {SHOP.orderingEnabled ? (
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
