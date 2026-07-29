import { useEffect, useState } from "react";
import { SHOP } from "../data/menu";
import { formatGBP } from "../lib/money";
import { fetchOrderStatus } from "../lib/api";
import { orderTiming } from "../lib/delivery";
import type { ApiOrderResponse, ApiOrderStatus } from "../lib/api";

interface Props {
  order: ApiOrderResponse;
  onDone: () => void;
}

/** How often to ask the shop whether they have answered yet. */
const POLL_INTERVAL_MS = 10_000;

/**
 * Stop polling after this long.
 *
 * An order nobody answers is a phone call, not an infinite loop. Twenty minutes
 * is well past the shop's own busiest-case response time and stops a tab left
 * open overnight hitting the API every ten seconds until the battery dies.
 */
const POLL_WINDOW_MS = 20 * 60 * 1000;

/**
 * Once the shop has accepted, keep watching for longer.
 *
 * The twenty-minute window above answers "has anyone looked at this yet". After
 * an accept the remaining question is "has it left the shop", and the shop can
 * legitimately promise up to 90 minutes. Giving up at 20 would blank the page
 * exactly when the customer starts checking it.
 */
const ACCEPTED_POLL_WINDOW_MS = 2 * 60 * 60 * 1000;

/**
 * What the customer sees after placing an order.
 *
 * The order is real by this point: it exists in the POS and is sitting on the
 * shop's tablet awaiting accept or reject. What is NOT yet known is whether the
 * shop has taken it, so this screen polls
 * `GET /public/{tenant}/orders/{id}/status` and says only what is true at the
 * time — "received", then "confirmed, about 45 minutes", or the shop's own
 * reason for turning it down.
 *
 * It deliberately never claims payment has been taken. Orders are created
 * unpaid and settled in the shop until Stripe exists.
 */
export default function OrderConfirmation({ order, onDone }: Props) {
  const [status, setStatus] = useState<ApiOrderStatus | null>(null);
  const [gaveUp, setGaveUp] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;
    let accepted = false;
    const startedAt = Date.now();

    async function poll(): Promise<void> {
      try {
        const next = await fetchOrderStatus(order.id);
        if (cancelled) return;
        setStatus(next);

        // Only rejection and completion are terminal. Accept is NOT: the order
        // still has to be made and handed over, and those are the updates the
        // customer actually waits for.
        if (next.rejected || next.completed) return;

        accepted = next.accepted;
      } catch {
        // A failed poll is not worth showing the customer: their order was
        // accepted by the server, only this status check failed. Keep trying.
        if (cancelled) return;
      }

      const budget = accepted ? ACCEPTED_POLL_WINDOW_MS : POLL_WINDOW_MS;
      if (Date.now() - startedAt > budget) {
        // Only ever surfaced while still unanswered. Once accepted, the last
        // known state stays on screen rather than being replaced by a warning.
        if (!accepted) setGaveUp(true);
        return;
      }
      timer = window.setTimeout(() => void poll(), POLL_INTERVAL_MS);
    }

    void poll();

    return () => {
      cancelled = true;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [order.id]);

  // A pre-order is not a slow order. Placed while the shop is shut, it will not
  // be answered until they open — so this page must never tell the customer it
  // is "taking longer than usual" and send them to ring a closed shop.
  const preOrder = !orderTiming().immediate;

  const collecting = order.service_type !== "delivery";
  const accepted = status?.accepted === true;
  const rejected = status?.rejected === true;
  const eta = status?.eta_minutes ?? order.eta_minutes;

  // The shop has made the food: it is on the counter, or with the driver.
  const ready = status?.ready === true;
  const completed = status?.completed === true;

  return (
    <div className="px-4 py-16 max-w-md mx-auto text-center space-y-5">
      <div className="text-5xl">{rejected ? "😔" : "🍗"}</div>

      <h1 className="font-display text-2xl">
        {rejected
          ? "We couldn't take this one"
          : completed
            ? collecting
              ? "Enjoy your food"
              : "Delivered"
            : ready
              ? collecting
                ? "Ready to collect"
                : "On its way"
              : accepted
                ? "Order confirmed"
                : "Order received"}
      </h1>

      <p className="text-cream/70">
        Your order number is{" "}
        <strong className="text-flame-light">{order.order_number}</strong>.
      </p>

      {rejected ? (
        <div className="card p-4 space-y-2 border-ember/40 text-left">
          <p className="text-sm text-cream/80">
            {status?.rejection_reason?.trim()
              ? status.rejection_reason
              : "The shop is unable to take this order right now."}
          </p>
          <p className="text-sm text-cream/60">
            Nothing has been charged. Give us a ring and we'll sort it out.
          </p>
        </div>
      ) : completed ? (
        <div className="card p-4 border-emerald-500/40">
          <p className="font-semibold text-emerald-400">
            {collecting ? "Collected — thanks!" : "Delivered — thanks!"}
          </p>
          <p className="text-sm text-cream/60 mt-1">
            We hope it was good. See you again soon.
          </p>
        </div>
      ) : ready ? (
        <div className="card p-4 border-emerald-500/40">
          <p className="font-semibold text-emerald-400">
            {collecting
              ? "Your order is ready and waiting"
              : "Your order has left the shop"}
          </p>
          <p className="text-sm text-cream/60 mt-1">
            {collecting
              ? `Come to ${SHOP.addressLines.join(", ")}.`
              : "The driver is on the way to the address you gave us."}
          </p>
        </div>
      ) : accepted ? (
        <div className="card p-4 border-emerald-500/40">
          {/* "Confirmed", never "ready" — the food has not been made yet. Telling
              a customer their order is ready and having it not be there is worse
              than telling them nothing at all. */}
          <p className="font-semibold text-emerald-400">
            Confirmed
            {eta
              ? ` — ${collecting ? "ready to collect" : "with you"} in about ${eta} minutes`
              : ""}
          </p>
          <p className="text-sm text-cream/60 mt-1">
            {collecting
              ? `We'll let you know when it's ready. Come to ${SHOP.addressLines.join(", ")}.`
              : "We'll let you know the moment it leaves the shop."}
          </p>
        </div>
      ) : (
        <div className="card p-4">
          <p className="font-semibold">
            {preOrder
              ? "Pre-order received"
              : "The shop is confirming your order"}
          </p>
          <p className="text-sm text-cream/60 mt-1">
            {preOrder ? (
              <>
                We've got it. The shop is closed at the moment and will confirm
                your order when we open at{" "}
                <strong className="text-cream">{SHOP.openTime}</strong>. Nothing
                more for you to do — keep your order number safe.
              </>
            ) : gaveUp ? (
              "This is taking longer than usual. Please give us a ring to check."
            ) : (
              `This usually takes a minute or two. We'll show your ${
                collecting ? "collection" : "delivery"
              } time here as soon as it's confirmed.`
            )}
          </p>
        </div>
      )}

      {/* Server totals, not the basket's. If the two ever disagreed, this is
          the one the shop will charge. */}
      <div className="card p-4 text-left space-y-2">
        {order.lines.map((line, index) => (
          <div
            key={`${line.name}-${index}`}
            className="flex justify-between gap-4 text-sm"
          >
            <span className="text-cream/70">
              {line.quantity} × {line.name}
              {line.modifiers.length > 0 && (
                <span className="block text-xs text-cream/45">
                  {line.modifiers.join(", ")}
                </span>
              )}
            </span>
            <span className="text-cream/70 shrink-0">{formatGBP(line.total)}</span>
          </div>
        ))}
        {order.delivery_fee > 0 && (
          <div className="flex justify-between text-sm text-cream/70 pt-2 border-t border-ink-line">
            <span>Delivery</span>
            <span>{formatGBP(order.delivery_fee)}</span>
          </div>
        )}
        <div className="flex justify-between font-display text-lg pt-2 border-t border-ink-line">
          <span>Total</span>
          <span>{formatGBP(order.total)}</span>
        </div>
        <p className="text-xs text-cream/45">
          Payable on {collecting ? "collection" : "delivery"}.
        </p>
      </div>

      <p className="text-sm text-cream/50">Any problems, call {SHOP.phones[0]}.</p>

      <button onClick={onDone} className="btn-ghost tap h-12">
        Back to menu
      </button>
    </div>
  );
}
