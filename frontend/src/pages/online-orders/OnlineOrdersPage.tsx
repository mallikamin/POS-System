import { useCallback, useEffect, useRef, useState } from "react";
import {
  acceptOnlineOrder,
  completeOnlineOrder,
  listOnlineOrders,
  markOnlineOrderPaid,
  markOnlineOrderReady,
  printTicket,
  rejectOnlineOrder,
  type OnlineOrder,
  type OnlineOrderState,
} from "@/services/onlineOrdersApi";
import { formatMoney } from "@/utils/currency";
import { useToast } from "@/hooks/use-toast";

/**
 * The order-queue tablet — the screen the client believes he is buying.
 *
 * He described it himself, and the scope is exactly his words and nothing
 * more: *"the exact same tablet, which is connected [to a] printer. When an
 * order comes in he either accepts or rejects, and he can change the lead time
 * for the delivery, or the time for collection."*
 *
 * Design constraints that are not arbitrary:
 *   - **Standalone and fullscreen**, like the KDS. This runs on a tablet
 *     propped up in a takeaway, not inside the POS chrome.
 *   - **Accept fires the print.** No unattended background job, therefore no
 *     Android Doze problem. See `onlineOrdersApi.printTicket`.
 *   - **Buttons are big.** 56px minimum per the project's touch-target rule;
 *     the accept/reject pair are larger still because they are pressed with a
 *     thumb, in a hurry, sometimes with greasy hands.
 *   - **Unpaid is shouted, not whispered.** A driver who assumes an order is
 *     prepaid does not come back with the money.
 *   - **An order must be able to finish.** Accept alone left every order in the
 *     Active tab forever and the day's takings never settled. The card now
 *     carries the rest of the life: made → handed over, and paid. The handover
 *     button settles an unpaid order in the same tap, and says so on its face
 *     rather than doing it quietly.
 */

const POLL_MS = 10_000;
const ETA_CHOICES = [15, 20, 30, 45, 60, 90];

const REJECT_REASONS = [
  "Too busy right now",
  "Item unavailable",
  "Outside delivery area",
  "Closing soon",
];

/** Made, and either on its way or waiting on the counter. */
const MADE = ["ready", "served"];
/** Off the queue for good. */
const CLOSED = ["completed", "voided"];

function minutesSince(iso: string): number {
  return Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 60000));
}

/**
 * Anything older than this was placed while the shop was shut.
 *
 * We take orders around the clock rather than turning customers away, so the
 * queue legitimately contains orders placed overnight. Measuring their age
 * from when they were placed would paint them solid red and shout "660 min
 * ago" next to a genuinely late five-minute-old order — training staff to
 * ignore the one signal that matters. A pre-order is not a late order.
 */
const PRE_ORDER_AFTER_MINUTES = 3 * 60;

/** "23:14, 28 Jul" — an absolute time is more use than "660 min ago". */
function placedAt(iso: string): string {
  return new Date(iso).toLocaleString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "short",
  });
}

function isPaid(order: OnlineOrder): boolean {
  return ["paid", "refunded"].includes((order.payment_status || "").toLowerCase());
}

/**
 * One button, two meanings — and the order's own service type decides which,
 * never the person tapping. A collecting customer must never be told their
 * food is driving to them.
 */
function readyLabel(order: OnlineOrder): string {
  return order.service_type === "delivery"
    ? "Out for delivery"
    : "Ready for collection";
}

function handoverLabel(order: OnlineOrder): string {
  return order.service_type === "delivery" ? "Delivered" : "Collected";
}

/** Where the order actually is now, rather than what was promised when it was accepted. */
function stageLabel(order: OnlineOrder): string {
  if (order.status === "voided") return "Voided";
  if (order.status === "completed") return handoverLabel(order);
  if (MADE.includes(order.status)) return readyLabel(order);
  return order.eta_minutes ? `Accepted · ${order.eta_minutes} min` : "Accepted";
}

/** Older than this and the card starts shouting. A waiting customer is a lost one. */
function urgency(minutes: number): string {
  // A pre-order placed overnight is not an emergency, and colouring it as one
  // devalues the colour for every real order beside it.
  if (minutes >= PRE_ORDER_AFTER_MINUTES) return "border-blue-400 bg-blue-50";
  if (minutes >= 10) return "border-red-500 bg-red-50";
  if (minutes >= 5) return "border-amber-500 bg-amber-50";
  return "border-secondary-200 bg-white";
}

export default function OnlineOrdersPage() {
  const { toast } = useToast();
  const [state, setState] = useState<OnlineOrderState>("pending");
  const [orders, setOrders] = useState<OnlineOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [etaFor, setEtaFor] = useState<string | null>(null);
  const [rejectFor, setRejectFor] = useState<string | null>(null);

  // Used only to decide whether to chime. Comparing against the rendered list
  // would re-chime on every poll that returns the same orders.
  const knownIds = useRef<Set<string>>(new Set());
  const firstLoad = useRef(true);

  const chime = useCallback(() => {
    try {
      const Ctx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext })
          .webkitAudioContext;
      const ctx = new Ctx();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.frequency.value = 880;
      gain.gain.setValueAtTime(0.25, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.6);
      osc.start();
      osc.stop(ctx.currentTime + 0.6);
    } catch {
      // A tablet that refuses to make noise is not a reason to stop working.
    }
  }, []);

  const refresh = useCallback(
    async (which: OnlineOrderState) => {
      try {
        const next = await listOnlineOrders(which);
        setOrders(next);

        if (which === "pending") {
          const incoming = next.filter((o) => !knownIds.current.has(o.id));
          if (incoming.length > 0 && !firstLoad.current) chime();
          knownIds.current = new Set(next.map((o) => o.id));
          firstLoad.current = false;
        }
      } catch {
        // Deliberately silent. A dropped poll on a shop wifi is normal and a
        // toast every 10 seconds would train them to ignore all toasts.
      } finally {
        setLoading(false);
      }
    },
    [chime],
  );

  useEffect(() => {
    setLoading(true);
    void refresh(state);
    const id = window.setInterval(() => void refresh(state), POLL_MS);
    return () => window.clearInterval(id);
  }, [state, refresh]);

  async function onAccept(order: OnlineOrder, eta: number) {
    setBusyId(order.id);
    setEtaFor(null);
    try {
      await acceptOnlineOrder(order.id, eta);
      toast({
        title: `Order ${order.order_number} accepted`,
        description: `${eta} minutes. Sending to the printer…`,
      });

      // The print is a separate step on purpose. If it fails the order stays
      // accepted -- the customer has already been told yes, and that must not
      // be undone by a printer problem. It can be reprinted from Active.
      const printed = await printTicket(order.id);
      if (!printed) {
        toast({
          title: "Could not reach the printer",
          description:
            "The order is accepted. Open it under Active and print again.",
          variant: "destructive",
        });
      }
      await refresh(state);
    } catch (err) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Could not accept this order.";
      toast({ title: "Not accepted", description: detail, variant: "destructive" });
      await refresh(state);
    } finally {
      setBusyId(null);
    }
  }

  async function onReject(order: OnlineOrder, reason: string) {
    setBusyId(order.id);
    setRejectFor(null);
    try {
      await rejectOnlineOrder(order.id, reason);
      toast({ title: `Order ${order.order_number} rejected`, description: reason });
      await refresh(state);
    } catch (err) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Could not reject this order.";
      toast({ title: "Not rejected", description: detail, variant: "destructive" });
      await refresh(state);
    } finally {
      setBusyId(null);
    }
  }

  /**
   * Shared plumbing for the three lifecycle taps.
   *
   * They differ only in which call they make and what they say afterwards.
   * Three copies of the same try/catch/refresh would drift apart the first time
   * one of them changed.
   *
   * The refresh runs on failure as well as success, deliberately: if the server
   * refused the move, our card is showing a status the server disagrees with,
   * and that is exactly when a stale view is most dangerous.
   */
  async function runLifecycle(
    order: OnlineOrder,
    action: () => Promise<unknown>,
    success: { title: string; description?: string },
    failTitle: string,
  ) {
    setBusyId(order.id);
    try {
      await action();
      toast(success);
    } catch (err) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Please try again.";
      toast({ title: failTitle, description: detail, variant: "destructive" });
    } finally {
      await refresh(state);
      setBusyId(null);
    }
  }

  function onReady(order: OnlineOrder) {
    return runLifecycle(
      order,
      () => markOnlineOrderReady(order.id),
      { title: `Order ${order.order_number} — ${readyLabel(order).toLowerCase()}` },
      "Could not update this order",
    );
  }

  /**
   * The handover tap. For an unpaid order this also settles it in cash, because
   * at a door the money and the food change hands in the same movement — but
   * the button says so rather than doing it quietly.
   */
  function onHandover(order: OnlineOrder) {
    const settle = !isPaid(order);
    return runLifecycle(
      order,
      () => completeOnlineOrder(order.id, settle),
      {
        title: `Order ${order.order_number} ${handoverLabel(order).toLowerCase()}`,
        description: settle
          ? `${formatMoney(order.total, order.currency)} recorded as cash.`
          : "Order closed.",
      },
      "Could not close this order",
    );
  }

  /** For the driver who comes back with the cash after the order was closed. */
  function onMarkPaid(order: OnlineOrder) {
    return runLifecycle(
      order,
      () => markOnlineOrderPaid(order.id),
      {
        title: `Order ${order.order_number} marked paid`,
        description: `${formatMoney(order.total, order.currency)} recorded as cash.`,
      },
      "Could not mark this order paid",
    );
  }

  return (
    <div className="min-h-screen bg-secondary-100 p-4">
      <header className="mb-4 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-secondary-900">Online orders</h1>
          <p className="text-sm text-secondary-500">
            {state === "pending"
              ? "Waiting for you to accept or reject"
              : state === "active"
                ? "Accepted and being prepared"
                : "Everything, including rejected"}
          </p>
        </div>

        <div className="flex gap-2">
          {(["pending", "active", "all"] as OnlineOrderState[]).map((s) => (
            <button
              key={s}
              onClick={() => setState(s)}
              className={`h-14 min-w-[7rem] rounded-xl px-5 text-base font-semibold capitalize transition ${
                state === s
                  ? "bg-primary-600 text-white shadow"
                  : "bg-white text-secondary-700 border border-secondary-200"
              }`}
            >
              {s}
              {s === "pending" && orders.length > 0 && state === "pending" ? (
                <span className="ml-2 rounded-full bg-white/25 px-2 py-0.5 text-sm">
                  {orders.length}
                </span>
              ) : null}
            </button>
          ))}
        </div>
      </header>

      {loading ? (
        <p className="p-8 text-center text-secondary-500">Loading…</p>
      ) : orders.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-secondary-300 bg-white p-16 text-center">
          <p className="text-xl font-medium text-secondary-700">
            {state === "pending" ? "No orders waiting" : "Nothing here"}
          </p>
          <p className="mt-1 text-secondary-500">
            {state === "pending"
              ? "New online orders will appear here automatically."
              : "Accepted orders show under Active."}
          </p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {orders.map((order) => {
            const waited = minutesSince(order.placed_at);
            const unpaid = !isPaid(order);
            const isPending = !order.accepted_at && !order.rejected_at;
            const closed = CLOSED.includes(order.status);
            const made = MADE.includes(order.status);
            const isPreOrder = isPending && waited >= PRE_ORDER_AFTER_MINUTES;

            return (
              <article
                key={order.id}
                className={`rounded-2xl border-2 p-4 shadow-sm ${
                  isPending ? urgency(waited) : "border-secondary-200 bg-white"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-xl font-bold text-secondary-900">
                      {order.order_number}
                    </p>
                    <p className="text-sm text-secondary-500">
                      {isPreOrder
                        ? `Pre-order · placed ${placedAt(order.placed_at)}`
                        : waited === 0
                          ? "just now"
                          : `${waited} min ago`}
                    </p>
                  </div>
                  <span
                    className={`rounded-lg px-3 py-1 text-sm font-bold uppercase ${
                      order.service_type === "delivery"
                        ? "bg-blue-100 text-blue-800"
                        : "bg-purple-100 text-purple-800"
                    }`}
                  >
                    {order.service_type}
                  </span>
                </div>

                {unpaid ? (
                  <p className="mt-3 rounded-lg bg-red-600 px-3 py-2 text-center text-base font-bold text-white">
                    NOT PAID — COLLECT {formatMoney(order.total, order.currency)}
                  </p>
                ) : null}

                <div className="mt-3 text-sm">
                  <p className="font-semibold text-secondary-900">
                    {order.customer_name}
                  </p>
                  {order.customer_phone ? (
                    <a
                      href={`tel:${order.customer_phone.replace(/\s+/g, "")}`}
                      className="text-primary-600 underline"
                    >
                      {order.customer_phone}
                    </a>
                  ) : null}
                  {order.service_type === "delivery" ? (
                    <p className="mt-1 text-secondary-700">
                      {order.delivery_address}
                      {order.delivery_area ? (
                        <span className="block font-semibold">
                          {order.delivery_area}
                        </span>
                      ) : null}
                    </p>
                  ) : null}
                </div>

                <ul className="mt-3 space-y-1 border-t border-secondary-200 pt-3 text-sm">
                  {order.lines.map((line, i) => (
                    <li key={i}>
                      <div className="flex justify-between gap-2">
                        <span className="font-medium">
                          {line.quantity} × {line.name}
                        </span>
                        <span>{formatMoney(line.total, order.currency)}</span>
                      </div>
                      {line.modifiers.length > 0 ? (
                        <p className="pl-4 text-secondary-500">
                          {line.modifiers.join(", ")}
                        </p>
                      ) : null}
                    </li>
                  ))}
                </ul>

                {order.notes ? (
                  <p className="mt-2 rounded-lg bg-amber-100 p-2 text-sm text-amber-900">
                    <span className="font-bold">Note: </span>
                    {order.notes}
                  </p>
                ) : null}

                <div className="mt-3 border-t border-secondary-200 pt-2 text-sm">
                  {order.delivery_fee > 0 ? (
                    <div className="flex justify-between text-secondary-600">
                      <span>Delivery</span>
                      <span>{formatMoney(order.delivery_fee, order.currency)}</span>
                    </div>
                  ) : null}
                  <div className="flex justify-between text-lg font-bold">
                    <span>Total</span>
                    <span>{formatMoney(order.total, order.currency)}</span>
                  </div>
                </div>

                {order.accepted_at ? (
                  <div className="mt-3 space-y-2">
                    <div
                      className={`flex items-center justify-between rounded-lg px-3 py-2 ${
                        closed ? "bg-secondary-200" : "bg-green-100"
                      }`}
                    >
                      <span
                        className={`font-semibold ${
                          closed ? "text-secondary-700" : "text-green-900"
                        }`}
                      >
                        {stageLabel(order)}
                      </span>
                      <button
                        onClick={() => void printTicket(order.id)}
                        className="h-11 rounded-lg bg-white px-4 font-semibold text-secondary-800 shadow-sm"
                      >
                        Print again
                      </button>
                    </div>

                    {closed ? null : made ? (
                      <button
                        disabled={busyId === order.id}
                        onClick={() => void onHandover(order)}
                        className="h-16 w-full rounded-xl bg-green-700 text-lg font-bold text-white disabled:opacity-50"
                      >
                        {handoverLabel(order)}
                        {unpaid ? (
                          <span className="block text-sm font-normal">
                            take {formatMoney(order.total, order.currency)}
                          </span>
                        ) : null}
                      </button>
                    ) : (
                      <button
                        disabled={busyId === order.id}
                        onClick={() => void onReady(order)}
                        className="h-16 w-full rounded-xl bg-blue-600 text-lg font-bold text-white disabled:opacity-50"
                      >
                        {readyLabel(order)}
                      </button>
                    )}

                    {unpaid ? (
                      <button
                        disabled={busyId === order.id}
                        onClick={() => void onMarkPaid(order)}
                        className="h-14 w-full rounded-xl border-2 border-secondary-300 font-semibold text-secondary-700 disabled:opacity-50"
                      >
                        Mark paid
                      </button>
                    ) : null}
                  </div>
                ) : order.rejected_at ? (
                  <p className="mt-3 rounded-lg bg-secondary-200 px-3 py-2 text-sm text-secondary-700">
                    Rejected — {order.rejection_reason}
                  </p>
                ) : etaFor === order.id ? (
                  <div className="mt-3">
                    <p className="mb-2 text-sm font-semibold text-secondary-700">
                      How long will it take?
                    </p>
                    <div className="grid grid-cols-3 gap-2">
                      {ETA_CHOICES.map((eta) => (
                        <button
                          key={eta}
                          disabled={busyId === order.id}
                          onClick={() => void onAccept(order, eta)}
                          className="h-16 rounded-xl bg-green-600 text-lg font-bold text-white disabled:opacity-50"
                        >
                          {eta}
                          <span className="block text-xs font-normal">min</span>
                        </button>
                      ))}
                    </div>
                    <button
                      onClick={() => setEtaFor(null)}
                      className="mt-2 h-12 w-full rounded-xl border border-secondary-300 font-medium"
                    >
                      Cancel
                    </button>
                  </div>
                ) : rejectFor === order.id ? (
                  <div className="mt-3">
                    <p className="mb-2 text-sm font-semibold text-secondary-700">
                      Why are you rejecting it?
                    </p>
                    <div className="space-y-2">
                      {REJECT_REASONS.map((reason) => (
                        <button
                          key={reason}
                          disabled={busyId === order.id}
                          onClick={() => void onReject(order, reason)}
                          className="h-14 w-full rounded-xl bg-red-600 font-semibold text-white disabled:opacity-50"
                        >
                          {reason}
                        </button>
                      ))}
                    </div>
                    <button
                      onClick={() => setRejectFor(null)}
                      className="mt-2 h-12 w-full rounded-xl border border-secondary-300 font-medium"
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <div className="mt-3 grid grid-cols-3 gap-2">
                    <button
                      disabled={busyId === order.id}
                      onClick={() => setEtaFor(order.id)}
                      className="col-span-2 h-16 rounded-xl bg-green-600 text-lg font-bold text-white disabled:opacity-50"
                    >
                      Accept
                    </button>
                    <button
                      disabled={busyId === order.id}
                      onClick={() => setRejectFor(order.id)}
                      className="h-16 rounded-xl border-2 border-red-500 text-lg font-bold text-red-600 disabled:opacity-50"
                    >
                      Reject
                    </button>
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
