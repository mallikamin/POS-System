import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Bell, BellOff, BarChart3, Pause, Play } from "lucide-react";
import {
  acceptOnlineOrder,
  completeOnlineOrder,
  fetchTicketUrl,
  getOrderingPaused,
  listOnlineOrders,
  markOnlineOrderPaid,
  markOnlineOrderReady,
  printTicket,
  rejectOnlineOrder,
  sendToPrinter,
  saveOrderingPaused,
  type OnlineOrder,
  type OnlineOrderSort,
  type OnlineOrderState,
} from "@/services/onlineOrdersApi";
import { formatMoney } from "@/utils/currency";
import { useToast } from "@/hooks/use-toast";
import { useConfigStore } from "@/stores/configStore";
import {
  dipTubLabel,
  dipTubTotals,
  isDipTub,
  placedAt,
  shopTime,
} from "@/lib/orderDisplay";

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
/** OI-57: a fixed page size, small enough that "Next" is a real, useful control on a tablet grid. */
const PAGE_SIZE = 24;

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

/*
 * Clock times (OI-70) and the dip-tub roll-up (OI-71) live in `lib/
 * orderDisplay` rather than here, so they can be bundled and run for real —
 * this project has no frontend test runner, and a helper buried in a page
 * component with React and store imports cannot be exercised standalone.
 */

function isPaid(order: OnlineOrder): boolean {
  return ["paid", "refunded"].includes((order.payment_status || "").toLowerCase());
}

/**
 * Stripe has APPROVED this card and is holding the money; only the capture is
 * outstanding, and that happens on Accept.
 *
 * Since OI-65 an unapproved card order cannot reach this tablet at all -- the
 * server excludes it from every queue state -- so a card order on screen that
 * is not yet `paid` is always an approved authorisation, never an unknown.
 * Treating it as "unpaid" is what caused a real double-charge on 2026-08-02
 * (OI-61); calling it "processing" caused a live scare on 2026-08-04. It is
 * approved money and must be stated as such.
 */
function isCardProcessing(order: OnlineOrder): boolean {
  return order.is_card_order && !isPaid(order);
}

/** Nothing is coming from Stripe for this order -- cash is genuinely owed. */
function isCashOwed(order: OnlineOrder): boolean {
  return !order.is_card_order && !isPaid(order);
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

/**
 * Notification-style ascending 3-tone chime, reused from the (already
 * noise-tested) pattern in `C:\FBAI\bilal-app\src\worker.js`'s `playChime()`
 * -- built specifically because a single quiet beep didn't carry across a
 * busy office.
 *
 * Still too quiet on this restaurant floor even with the tablet's own media
 * volume already maxed (Malik, 2026-08-01, after the first louder-gain pass).
 * A sine oscillator's own peak is 1.0, so more gain was never available --
 * genuine loudness needed a different technique, not a bigger number:
 *   - square wave, not sine: far more harmonic energy at the same peak
 *     amplitude, and reads as an alarm rather than a pleasant beep -- correct
 *     for a noisy floor.
 *   - two unison oscillators per tone (one an octave up): more simultaneous
 *     acoustic energy hitting the ear than any single oscillator.
 *   - a short attack + a near-peak hold instead of a smooth exponential
 *     ramp, which spends much of the tone quiet.
 *   - a DynamicsCompressorNode shared by every oscillator in the sequence:
 *     this is what actually lets the extra energy from layering come out
 *     louder instead of just clipping into distortion sooner.
 *   - three passes, not two -- Malik: "need to increase at least 2-3x".
 */
function playAlertTones(ctx: AudioContext): void {
  const now = ctx.currentTime;

  const compressor = ctx.createDynamicsCompressor();
  compressor.threshold.setValueAtTime(-24, now);
  compressor.knee.setValueAtTime(12, now);
  compressor.ratio.setValueAtTime(12, now);
  compressor.attack.setValueAtTime(0.003, now);
  compressor.release.setValueAtTime(0.15, now);
  compressor.connect(ctx.destination);

  const tone = (freq: number, start: number, dur: number, peak: number) => {
    for (const f of [freq, freq * 2]) {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "square";
      osc.frequency.setValueAtTime(f, now + start);
      gain.gain.setValueAtTime(0.0001, now + start);
      gain.gain.exponentialRampToValueAtTime(peak, now + start + 0.008);
      gain.gain.setValueAtTime(peak, now + start + Math.max(0.008, dur - 0.03));
      gain.gain.exponentialRampToValueAtTime(0.0001, now + start + dur);
      osc.connect(gain);
      gain.connect(compressor);
      osc.start(now + start);
      osc.stop(now + start + dur + 0.02);
    }
  };
  const sequence = (offset: number) => {
    tone(987.8, offset + 0.0, 0.22, 0.9); // B5
    tone(1318.5, offset + 0.18, 0.22, 0.9); // E6
    tone(1568.0, offset + 0.36, 0.4, 0.95); // G6 -- slightly longer tail
  };
  sequence(0);
  sequence(0.85);
  sequence(1.7); // third pass
}

/**
 * A native OS notification for a new order -- its own sound, appears even if
 * the tablet's screen is dim or Chrome is briefly backgrounded. A second,
 * independent channel alongside the Web Audio chime, not a replacement for
 * it. Reused from `C:\FBAI\bilal-app`'s `showOSNotification`.
 */
function showNewOrderNotification(order: OnlineOrder): void {
  if (!("Notification" in window) || Notification.permission !== "granted") return;
  try {
    const n = new Notification("New online order", {
      body: `${order.order_number} — ${formatMoney(order.total, order.currency)}`,
      tag: `online-order-${order.id}`,
      requireInteraction: false,
    });
    n.onclick = () => {
      window.focus();
      n.close();
    };
  } catch {
    // Notifications are best-effort; the chime is the primary alert.
  }
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

  // OI-70: the shop's own timezone drives every clock time on this page. Same
  // reason OnlineReportsPage fetches config here — this route is mounted
  // outside POSLayout, so a hard refresh straight onto it (bookmarked, which
  // is exactly how the tablet opens) never runs POSLayout's fetchConfig().
  const config = useConfigStore((s) => s.config);
  const fetchConfig = useConfigStore((s) => s.fetchConfig);
  const shopTz = config?.timezone;

  const [state, setState] = useState<OnlineOrderState>("pending");
  const [orders, setOrders] = useState<OnlineOrder[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [etaFor, setEtaFor] = useState<string | null>(null);
  const [rejectFor, setRejectFor] = useState<string | null>(null);

  // OI-57: date filter, pagination and sort. `dateFilter` is Pending/Active's
  // single-day override ("" = today, the backend's own default); `dateFrom`/
  // `dateTo` are All's range, shared across the tab (both empty = All stays
  // the full unscoped log). `sortOverride` is undefined until the toggle is
  // used, so each tab's own default (asc for Pending, desc for Active/All)
  // holds until a staff member explicitly flips it; `effectiveSort` mirrors
  // back whatever the server actually applied, including that default, so the
  // toggle's label is always honest even before it's been touched.
  const [dateFilter, setDateFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [sortOverride, setSortOverride] = useState<OnlineOrderSort | undefined>(
    undefined,
  );
  const [effectiveSort, setEffectiveSort] = useState<OnlineOrderSort>("asc");
  const [page, setPage] = useState(0);

  function changeTab(next: OnlineOrderState) {
    setState(next);
    setPage(0);
    // A sort flipped on one tab silently carrying over to another (with a
    // different default) would be confusing -- start each tab fresh. The date
    // filters are left alone: picking "look at the 28th" is a deliberate
    // choice worth keeping while flipping between Pending and Active for the
    // same day.
    setSortOverride(undefined);
  }

  function changeDateFilter(next: string) {
    setDateFilter(next);
    setPage(0);
  }

  function changeDateRange(from: string, to: string) {
    setDateFrom(from);
    setDateTo(to);
    setPage(0);
  }

  function toggleSort() {
    setSortOverride(effectiveSort === "asc" ? "desc" : "asc");
    setPage(0);
  }

  // Used only to decide whether to chime. Comparing against the rendered list
  // would re-chime on every poll that returns the same orders.
  const knownIds = useRef<Set<string>>(new Set());
  const firstLoad = useRef(true);

  // Ticket jobs, fetched ahead of the tap. A ref rather than state, and that is
  // the whole point: the Print handler has to read the current value
  // SYNCHRONOUSLY, because any await before navigating ends the user gesture
  // and Chrome then drops the `rawbt:` handoff without a word. Nothing renders
  // from this, so it needs no re-render.
  const ticketUrls = useRef<Map<string, string>>(new Map());

  // What `payment_status` each cached ticket was last rendered against --
  // see `refresh`'s prefetch loop below. A plain `has(id)` check let a
  // ticket cached while an order was still `unpaid` survive forever even
  // after payment later landed via the Stripe webhook (reconcile_late_
  // authorization -- see OI-61), because nothing client-initiated ever
  // called `invalidateTicket` for that path. Tracking the signature lets the
  // ordinary poll notice the change itself and refetch, with no new server
  // event needed.
  const ticketSig = useRef<Map<string, string>>(new Map());

  // ⚠️ A cached ticket is a fully-rendered, one-shot ESC/POS payload -- see
  // `refresh` below -- and it goes stale the instant an order's payment
  // status actually changes (a card captured on Accept, cash settled on
  // Mark paid or handover). `refresh`'s own prefetch loop never re-fetches
  // an id it already has, so without this, whatever prints next -- the
  // automatic attempt or a later manual tap -- keeps printing the payment
  // state from *before* the money moved. This is exactly the bug that
  // printed "NOT PAID" on a genuinely captured card order (260731-003,
  // 2026-08-01): the ticket was prefetched while the order still sat
  // pending, and nothing ever told the cache the order had since been paid.
  // The re-fetch is never awaited here, on purpose -- this must not become
  // one more `await` standing between a tap and a `rawbt:` navigation.
  //
  // The signature is deliberately cleared, not set, here: the fetch below
  // races the next poll tick, and letting the poll's own signature-compare
  // (against fresh order data) decide what's current is safer than this
  // call guessing at a value it was never handed.
  const invalidateTicket = useCallback((orderId: string) => {
    ticketUrls.current.delete(orderId);
    ticketSig.current.delete(orderId);
    void fetchTicketUrl(orderId).then((url) => {
      if (url) ticketUrls.current.set(orderId, url);
    });
  }, []);

  // ⚠️ One AudioContext for the whole page's life, not a fresh one per chime.
  // Chrome -- Android especially, which is what this tablet runs -- creates
  // every new AudioContext `suspended` until it is resumed from inside a
  // genuine user gesture, and does this silently: no exception, just no
  // sound. A poll timer is never a gesture, so a context built fresh inside
  // one (the previous version of this code) can never actually play.
  // Same rule that already bit the `rawbt:` print navigation once before --
  // see the Print button below. Resuming ONE context on an explicit tap
  // keeps it usable for every later chime fired from a poll.
  const audioCtxRef = useRef<AudioContext | null>(null);
  const [audioReady, setAudioReady] = useState(false);
  // Imran's rush button. `orderingPaused` mirrors the server and is re-read on
  // every poll, never assumed from the last tap -- two tablets share one shop,
  // so a pause made on one must show on the other.
  const [orderingPaused, setOrderingPaused] = useState(false);
  const [pausingOrders, setPausingOrders] = useState(false);
  // Turning ordering OFF is confirmed first; turning it back ON is not.
  // The dangerous direction is the one that silently turns paying customers
  // away, and it is the one nobody notices they left on.
  const [confirmPause, setConfirmPause] = useState(false);

  const enableSound = useCallback(() => {
    try {
      const Ctx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext })
          .webkitAudioContext;
      if (!Ctx) return;
      if (!audioCtxRef.current) audioCtxRef.current = new Ctx();
      const ctx = audioCtxRef.current;
      ctx.resume().catch(() => {
        // Nothing to do; the button stays showing "Enable sound".
      });
      // A silent buffer, played right after resume -- belt-and-suspenders for
      // browsers that need actual playback (not just `.resume()`) inside the
      // gesture to consider the context genuinely unlocked.
      const silent = ctx.createBuffer(1, 1, 22050);
      const src = ctx.createBufferSource();
      src.buffer = silent;
      src.connect(ctx.destination);
      src.start(0);
      setAudioReady(true);
      // Confirm immediately, from inside this same tap. If this is silent,
      // it is the tablet's media volume or Chrome's per-site Sound setting,
      // not this page -- worth knowing before the real order comes in.
      playAlertTones(ctx);
      // Same tap arms the OS notification channel too -- one button, both
      // alerts, so staff never have to find a second permission prompt.
      if ("Notification" in window && Notification.permission === "default") {
        void Notification.requestPermission();
      }
    } catch {
      // A tablet that refuses to make noise is not a reason to stop working.
    }
  }, []);

  const chime = useCallback(() => {
    const ctx = audioCtxRef.current;
    if (!ctx) return; // sound was never enabled this session -- nothing to do
    try {
      // Defensive: a backgrounded tab can suspend an already-running context
      // again. Resuming an already-running context is a harmless no-op.
      void ctx.resume();
      playAlertTones(ctx);
    } catch {
      // A tablet that refuses to make noise is not a reason to stop working.
    }
  }, []);

  const refresh = useCallback(
    async (opts: {
      which: OnlineOrderState;
      pageIndex: number;
      sort?: OnlineOrderSort;
      date: string;
      dateFrom: string;
      dateTo: string;
    }) => {
      try {
        const resp = await listOnlineOrders({
          state: opts.which,
          limit: PAGE_SIZE,
          offset: opts.pageIndex * PAGE_SIZE,
          date: opts.which !== "all" ? opts.date || undefined : undefined,
          dateFrom: opts.which === "all" ? opts.dateFrom || undefined : undefined,
          dateTo: opts.which === "all" ? opts.dateTo || undefined : undefined,
          sort: opts.sort,
        });
        setOrders(resp.orders);
        setTotalCount(resp.total_count);
        setEffectiveSort(resp.sort);

        // Fetch every ticket URL up front, in the background.
        //
        // Not an optimisation -- a correctness requirement. Chrome on Android
        // only follows a custom scheme inside a real user gesture, and an
        // `await` inside the tap handler ends that gesture, so the print was
        // being dropped silently. Having the URL already in hand is what makes
        // the Print button navigate synchronously and actually reach RawBT.
        // Signature is just `payment_status` -- the one field the printed
        // PAID/PROCESSING/NOT-PAID line actually branches on (see
        // `print_service.py`). A cached ticket whose order hasn't moved
        // since it was fetched is left alone; one whose payment status has
        // moved on (typically the OI-61 late-capture case) is refetched here,
        // same as any never-before-seen order.
        void Promise.all(
          resp.orders.map(async (order) => {
            const sig = order.payment_status;
            if (
              ticketUrls.current.has(order.id) &&
              ticketSig.current.get(order.id) === sig
            ) {
              return;
            }
            const url = await fetchTicketUrl(order.id);
            if (url) {
              ticketUrls.current.set(order.id, url);
              ticketSig.current.set(order.id, sig);
            }
          }),
        );
      } catch {
        // Deliberately silent. A dropped poll on a shop wifi is normal and a
        // toast every 10 seconds would train them to ignore all toasts.
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  /** Re-fetches whatever the tablet is currently looking at -- same tab, page, date and sort. */
  function refreshCurrent() {
    return refresh({
      which: state,
      pageIndex: page,
      sort: sortOverride,
      date: dateFilter,
      dateFrom,
      dateTo,
    });
  }

  useEffect(() => {
    if (!config) void fetchConfig();
  }, [config, fetchConfig]);

  useEffect(() => {
    setLoading(true);
    const opts = {
      which: state,
      pageIndex: page,
      sort: sortOverride,
      date: dateFilter,
      dateFrom,
      dateTo,
    };
    void refresh(opts);
    const id = window.setInterval(() => void refresh(opts), POLL_MS);
    return () => window.clearInterval(id);
  }, [state, page, sortOverride, dateFilter, dateFrom, dateTo, refresh]);

  // Watches for new pending orders regardless of which tab is on screen --
  // switching to "Active" or "All" must not silence the alert for whatever
  // arrives next. Runs its own poll rather than reusing `refresh`'s tab-scoped
  // one, on purpose, so it keeps working no matter what's currently displayed.
  useEffect(() => {
    let cancelled = false;

    async function checkForNewOrders() {
      try {
        // Deliberately bare -- no date/sort/page override from whatever the
        // visible tab is showing. This watch always means "today's pending
        // queue, from the top", regardless of what a staff member is
        // currently browsing in the grid below.
        const pending = await listOnlineOrders({ state: "pending" });
        if (cancelled) return;
        const incoming = pending.orders.filter((o) => !knownIds.current.has(o.id));
        if (incoming.length > 0 && !firstLoad.current) {
          chime();
          // A second, independent alert channel -- fires the OS's own
          // notification sound and shows even if Chrome is briefly
          // backgrounded. Best-effort; the chime above is the primary alert.
          incoming.forEach(showNewOrderNotification);
        }
        knownIds.current = new Set(pending.orders.map((o) => o.id));
        firstLoad.current = false;
      } catch {
        // Same as the main poll: a dropped request on shop wifi is normal.
      }

      // Re-read the pause state from the server rather than trusting the last
      // tap on THIS tablet -- the shop may have a second one, and a stale
      // "Pause orders" button would be worse than none at all.
      try {
        const paused = await getOrderingPaused();
        if (!cancelled) setOrderingPaused(paused);
      } catch {
        // Leave the last known value; a dropped poll must not flip the button.
      }
    }

    void checkForNewOrders();
    const id = window.setInterval(() => void checkForNewOrders(), POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [chime]);

  async function onAccept(order: OnlineOrder, eta: number) {
    setBusyId(order.id);
    setEtaFor(null);
    try {
      await acceptOnlineOrder(order.id, eta);
      // See `invalidateTicket` -- a card order's cached ticket was rendered
      // before payment was captured and must not be trusted below.
      invalidateTicket(order.id);
      toast({
        title: `Order ${order.order_number} accepted`,
        description: `${eta} minutes. Sending to the printer…`,
      });

      // The print is a separate step on purpose. If it fails the order stays
      // accepted -- the customer has already been told yes, and that must not
      // be undone by a printer problem.
      //
      // ⚠️ This automatic attempt is BEST EFFORT and frequently will not fire.
      // Accepting means awaiting the API call above, which ends the user
      // gesture, and Chrome on Android then refuses the `rawbt:` navigation
      // without a word. That is exactly how the first live ticket vanished:
      // 200s in the log, nothing on paper.
      //
      // So the real print path is the Print ticket button on the card, which
      // navigates synchronously from the tap using a prefetched URL. If the
      // automatic attempt is dropped, the toast below sends them straight to it.
      const url = ticketUrls.current.get(order.id);
      if (url) {
        sendToPrinter(url);
      } else {
        const printed = await printTicket(order.id);
        if (!printed) {
          toast({
            title: "Now tap Print ticket",
            description:
              "The order is accepted. Tap the Print ticket button on the order to send it to the printer.",
            variant: "destructive",
          });
        }
      }
      await refreshCurrent();
    } catch (err) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Could not accept this order.";
      toast({ title: "Not accepted", description: detail, variant: "destructive" });
      await refreshCurrent();
    } finally {
      setBusyId(null);
    }
  }

  /**
   * Stop or resume online ordering (Imran, 2026-08-04).
   *
   * The server is the authority: this sets state from what the API returns,
   * never from what was requested, so a failed call cannot leave the button
   * claiming the shop is closed when it is still taking orders.
   */
  async function toggleOrdering() {
    // Pausing turns real, paying customers away, so it is confirmed first.
    // Resuming is the safe direction and stays one tap -- a shop that has
    // caught up should never have to argue with a dialog to reopen.
    if (!orderingPaused) {
      setConfirmPause(true);
      return;
    }
    await applyOrderingPaused(false);
  }

  async function applyOrderingPaused(next: boolean) {
    setConfirmPause(false);
    setPausingOrders(true);
    try {
      const now = await saveOrderingPaused(next);
      setOrderingPaused(now);
      toast({
        title: now ? "Online ordering PAUSED" : "Online ordering resumed",
        description: now
          ? "Customers are now told to phone the shop. Orders placed while paused are not saved."
          : "The website is taking collection and delivery orders again.",
      });
    } catch (err) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Could not change online ordering.";
      toast({ title: "Not changed", description: detail, variant: "destructive" });
    } finally {
      setPausingOrders(false);
    }
  }

  async function onReject(order: OnlineOrder, reason: string) {
    setBusyId(order.id);
    setRejectFor(null);
    try {
      await rejectOnlineOrder(order.id, reason);
      toast({ title: `Order ${order.order_number} rejected`, description: reason });
      await refreshCurrent();
    } catch (err) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Could not reject this order.";
      toast({ title: "Not rejected", description: detail, variant: "destructive" });
      await refreshCurrent();
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
      // Mark paid and a cash-settled handover can also flip payment_status --
      // same staleness risk as Accept. See `invalidateTicket`.
      invalidateTicket(order.id);
      toast(success);
    } catch (err) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Please try again.";
      toast({ title: failTitle, description: detail, variant: "destructive" });
    } finally {
      await refreshCurrent();
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
    // Only auto-settle as CASH when cash is genuinely owed. A card order
    // that's still processing must never be silently recorded as cash on
    // handover -- Stripe may capture the real payment moments later (or
    // already has), and this app would otherwise be the one place claiming
    // "cash" for money that was actually taken by card. See OI-61.
    const settle = isCashOwed(order);
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
      {/* Confirm before turning ordering OFF. Deliberately a blocking overlay
          rather than a toast-and-undo: by the time an "undo" is noticed the
          website has already been turning customers away. Uses the page's own
          inline-confirm pattern (see the ETA and reject panels) rather than
          window.confirm, which Chrome on this tablet renders inconsistently. */}
      {confirmPause && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
            <h2 className="text-xl font-bold text-secondary-900">
              Turn off online ordering?
            </h2>
            <p className="mt-3 text-base text-secondary-700">
              This will <strong>disable live orders</strong>. Customers will not
              be able to place or pay for an order on the website — they will be
              told to phone the shop instead.
            </p>
            <p className="mt-2 text-sm font-semibold text-red-700">
              Proceed with caution. Orders attempted while it is off are not
              saved.
            </p>
            <div className="mt-5 grid grid-cols-2 gap-3">
              <button
                onClick={() => setConfirmPause(false)}
                className="h-14 rounded-xl border-2 border-secondary-300 text-base font-bold text-secondary-700"
              >
                Keep taking orders
              </button>
              <button
                disabled={pausingOrders}
                onClick={() => void applyOrderingPaused(true)}
                className="h-14 rounded-xl bg-red-600 text-base font-bold text-white disabled:opacity-50"
              >
                Yes, turn off
              </button>
            </div>
          </div>
        </div>
      )}
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
          <Link
            to="/online-orders/reports"
            className="flex h-14 items-center gap-2 rounded-xl border border-secondary-200 bg-white px-4 text-base font-semibold text-secondary-700"
          >
            <BarChart3 className="h-5 w-5" />
            Reports
          </Link>
          {/* Imran's rush button (2026-08-04). Deliberately styled as the loud
              exception rather than another neutral tab: while it is on, the
              shop is turning real customers away, and nobody should be able to
              leave it on by accident after the rush passes. */}
          <button
            onClick={() => void toggleOrdering()}
            disabled={pausingOrders}
            title={
              orderingPaused
                ? "Online ordering is OFF. Customers are being told to phone the shop."
                : "Stop taking online orders (collection and delivery) during a rush"
            }
            className={`flex h-14 items-center gap-2 rounded-xl px-4 text-base font-bold disabled:opacity-50 ${
              orderingPaused
                ? "animate-pulse bg-red-600 text-white"
                : "bg-secondary-100 text-secondary-800"
            }`}
          >
            {orderingPaused ? (
              <Play className="h-5 w-5" />
            ) : (
              <Pause className="h-5 w-5" />
            )}
            {orderingPaused ? "Orders OFF — tap to resume" : "Pause orders"}
          </button>
          <button
            onClick={enableSound}
            title={
              audioReady
                ? "Sound + notifications are on for this session"
                : "Tap once to enable the new-order alert sound and notifications"
            }
            className={`flex h-14 items-center gap-2 rounded-xl px-4 text-base font-semibold ${
              audioReady
                ? "bg-green-100 text-green-800"
                : "animate-pulse bg-amber-100 text-amber-900"
            }`}
          >
            {audioReady ? (
              <Bell className="h-5 w-5" />
            ) : (
              <BellOff className="h-5 w-5" />
            )}
            {audioReady ? "Sound on" : "Enable sound"}
          </button>
          {(["pending", "active", "all"] as OnlineOrderState[]).map((s) => (
            <button
              key={s}
              onClick={() => changeTab(s)}
              className={`h-14 min-w-[7rem] rounded-xl px-5 text-base font-semibold capitalize transition ${
                state === s
                  ? "bg-primary-600 text-white shadow"
                  : "bg-white text-secondary-700 border border-secondary-200"
              }`}
            >
              {s}
              {/* `totalCount`, not `orders.length` -- since OI-57's pagination,
                  the visible page is often smaller than the real queue, and a
                  badge reading "24" while 31 orders wait would undersell it. */}
              {s === "pending" && state === "pending" && totalCount > 0 ? (
                <span className="ml-2 rounded-full bg-white/25 px-2 py-0.5 text-sm">
                  {totalCount}
                </span>
              ) : null}
            </button>
          ))}
        </div>
      </header>

      <div className="mb-4 flex flex-wrap items-center gap-3 rounded-2xl border border-secondary-200 bg-white p-3">
        {state !== "all" ? (
          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-secondary-700">Date</label>
            <input
              type="date"
              value={dateFilter}
              onChange={(e) => changeDateFilter(e.target.value)}
              className="h-11 rounded-lg border border-secondary-300 px-3 text-sm"
            />
            {dateFilter ? (
              <button
                onClick={() => changeDateFilter("")}
                className="h-11 rounded-lg border border-secondary-300 px-3 text-sm font-medium text-secondary-700"
              >
                Today
              </button>
            ) : (
              <span className="text-sm text-secondary-500">Showing today</span>
            )}
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-secondary-700">From</label>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => changeDateRange(e.target.value, dateTo)}
              className="h-11 rounded-lg border border-secondary-300 px-3 text-sm"
            />
            <label className="text-sm font-medium text-secondary-700">To</label>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => changeDateRange(dateFrom, e.target.value)}
              className="h-11 rounded-lg border border-secondary-300 px-3 text-sm"
            />
            {dateFrom || dateTo ? (
              <button
                onClick={() => changeDateRange("", "")}
                className="h-11 rounded-lg border border-secondary-300 px-3 text-sm font-medium text-secondary-700"
              >
                Clear
              </button>
            ) : (
              <span className="text-sm text-secondary-500">Showing everything</span>
            )}
          </div>
        )}

        {state !== "pending" ? (
          <button
            onClick={toggleSort}
            title="Pending's oldest-first queue order always stays the same -- this only reorders Active/All"
            className="h-11 rounded-lg border border-secondary-300 px-3 text-sm font-medium text-secondary-700"
          >
            Sort: {effectiveSort === "asc" ? "Oldest first" : "Newest first"} ⇅
          </button>
        ) : null}

        <div className="ml-auto flex items-center gap-2">
          <button
            disabled={page === 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            className="h-11 rounded-lg border border-secondary-300 px-3 text-sm font-medium text-secondary-700 disabled:opacity-40"
          >
            ← Prev
          </button>
          <span className="text-sm text-secondary-600">
            {totalCount === 0
              ? "0 of 0"
              : `${page * PAGE_SIZE + 1}–${Math.min(
                  totalCount,
                  (page + 1) * PAGE_SIZE,
                )} of ${totalCount}`}
          </span>
          <button
            disabled={(page + 1) * PAGE_SIZE >= totalCount}
            onClick={() => setPage((p) => p + 1)}
            className="h-11 rounded-lg border border-secondary-300 px-3 text-sm font-medium text-secondary-700 disabled:opacity-40"
          >
            Next →
          </button>
        </div>
      </div>

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
            const cashOwed = isCashOwed(order);
            const cardProcessing = isCardProcessing(order);
            const notPaidYet = cashOwed || cardProcessing;
            const isPending = !order.accepted_at && !order.rejected_at;
            const closed = CLOSED.includes(order.status);
            const made = MADE.includes(order.status);
            const isPreOrder = isPending && waited >= PRE_ORDER_AFTER_MINUTES;
            const dips = dipTubTotals(order);

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
                    {/* OI-70. Two facts, and they answer different questions.
                        The relative age is what justifies the red/amber border
                        on an order nobody has answered yet, so it leads while
                        the order is still waiting. The clock times are what you
                        reconcile against later — a phone call, an email, a
                        Stripe row — so they are always present and always in
                        the SHOP's timezone, identical on the tablet in
                        Garelochhead and on a screen in Pakistan. */}
                    <p className="text-sm text-secondary-500">
                      {isPreOrder
                        ? `Pre-order · placed ${placedAt(order.placed_at, shopTz)}`
                        : isPending
                          ? `${waited === 0 ? "just now" : `${waited} min ago`} · placed ${shopTime(order.placed_at, shopTz)}`
                          : `Placed ${shopTime(order.placed_at, shopTz)}`}
                      {order.accepted_at
                        ? ` · accepted ${shopTime(order.accepted_at, shopTz)}`
                        : order.rejected_at
                          ? ` · rejected ${shopTime(order.rejected_at, shopTz)}`
                          : ""}
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

                {cashOwed ? (
                  <p className="mt-3 rounded-lg bg-red-600 px-3 py-2 text-center text-base font-bold text-white">
                    NOT PAID — COLLECT {formatMoney(order.total, order.currency)}
                  </p>
                ) : cardProcessing ? (
                  // Stripe has ALREADY APPROVED this card and is holding the
                  // money -- since OI-65 an unapproved card order cannot reach
                  // this tablet at all, in any tab. The only thing outstanding
                  // is the capture, which happens the moment staff tap Accept.
                  //
                  // The old wording here said "PAYMENT PROCESSING", which read
                  // as "we don't know yet" and caused a live scare on
                  // 2026-08-04: two orders that were fully approved (and then
                  // captured) looked unresolved on the shop floor. Approved
                  // money must be stated as approved.
                  <p className="mt-3 rounded-lg bg-green-600 px-3 py-2 text-center text-base font-bold text-white">
                    CARD APPROVED — DO NOT COLLECT
                    <span className="block text-xs font-normal">
                      Stripe is holding {formatMoney(order.total, order.currency)}. It is
                      charged automatically when you accept.
                    </span>
                  </p>
                ) : (
                  <p className="mt-3 rounded-lg bg-green-100 px-3 py-1.5 text-center text-sm font-semibold text-green-800">
                    PAID · {order.is_card_order ? "CARD" : "CASH"}
                  </p>
                )}

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

                {/* OI-71: dip tubs first and counted, exactly as the printed
                    ticket does it. Whoever is packing may be reading the paper
                    or this screen, and the two must not disagree. */}
                {dips.length > 0 ? (
                  <div className="mt-3 rounded-lg border border-secondary-300 bg-secondary-50 px-3 py-2 text-sm">
                    <p className="font-bold uppercase tracking-wide text-secondary-900">
                      Dip tubs
                    </p>
                    {dips.map(([name, qty]) => (
                      <p key={name} className="text-secondary-700">
                        {qty} × {dipTubLabel(name)}
                      </p>
                    ))}
                  </div>
                ) : null}

                <ul className="mt-3 space-y-1 border-t border-secondary-200 pt-3 text-sm">
                  {order.lines.map((line, i) => {
                    // Counted above; repeating them here is the buried
                    // sub-line the roll-up exists to replace.
                    const rest = line.modifiers.filter((m) => !isDipTub(m));
                    return (
                      <li key={i}>
                        <div className="flex justify-between gap-2">
                          <span className="font-medium">
                            {line.quantity} × {line.name}
                          </span>
                          <span>{formatMoney(line.total, order.currency)}</span>
                        </div>
                        {rest.length > 0 ? (
                          <p className="pl-4 text-secondary-500">
                            {rest.join(", ")}
                          </p>
                        ) : null}
                      </li>
                    );
                  })}
                </ul>

                {order.notes ? (
                  <p className="mt-2 rounded-lg bg-amber-100 p-2 text-sm text-amber-900">
                    <span className="font-bold">Note: </span>
                    {order.notes}
                  </p>
                ) : null}

                <div className="mt-3 border-t border-secondary-200 pt-2 text-sm">
                  {order.service_fee > 0 ? (
                    <div className="flex justify-between text-secondary-600">
                      <span>Service Fee</span>
                      <span>{formatMoney(order.service_fee, order.currency)}</span>
                    </div>
                  ) : null}
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
                      {/* Synchronous on purpose: the URL is already in hand,
                          so the tap navigates straight to RawBT. Awaiting a
                          fetch here is what silently killed the first live
                          ticket. */}
                      <button
                        onClick={() => {
                          const url = ticketUrls.current.get(order.id);
                          if (url) {
                            sendToPrinter(url);
                            return;
                          }
                          // Not prefetched yet -- fall back and warn, because
                          // this path can be dropped by Chrome.
                          void printTicket(order.id).then((ok) => {
                            if (!ok) {
                              toast({
                                title: "Could not reach the printer",
                                description: "Wait a moment and tap Print again.",
                                variant: "destructive",
                              });
                            }
                          });
                        }}
                        className="h-12 rounded-lg bg-secondary-900 px-5 font-bold text-white shadow-sm"
                      >
                        🖨 Print ticket
                      </button>
                    </div>

                    {closed ? null : made ? (
                      <button
                        disabled={busyId === order.id}
                        onClick={() => void onHandover(order)}
                        className="h-16 w-full rounded-xl bg-green-700 text-lg font-bold text-white disabled:opacity-50"
                      >
                        {handoverLabel(order)}
                        {cashOwed ? (
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

                    {notPaidYet ? (
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
