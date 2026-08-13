import { useCallback, useEffect, useRef, useState } from "react";
import { SHOP } from "./data/menu";
import { formatGBP } from "./lib/money";
import { isOpenNow } from "./lib/delivery";
import type { OrderTiming } from "./lib/delivery";
import { itemCountOf, subtotalOf, useCart } from "./store/cart";
import { DEFAULT_PAUSED_MESSAGE, useMenu } from "./store/menu";
import type { ApiOrderResponse } from "./lib/api";
import MenuBrowser from "./components/MenuBrowser";
import CartPanel from "./components/CartPanel";
import Checkout from "./components/Checkout";
import OrderConfirmation from "./components/OrderConfirmation";
import {
  returnFromStripe,
  stripReturnParams,
  takePendingOrder,
} from "./lib/pendingOrder";

type View = "menu" | "checkout" | "done";

/**
 * Gaps between automatic menu retries, in milliseconds (OI-78).
 *
 * Widening rather than fixed, and deliberately short at the start: the common
 * case is a signal blip of a second or two while the page is still loading, and
 * recovering from that before the customer notices is the whole point. Four
 * attempts then stop, so a genuinely offline phone is not left retrying for
 * ever — the Retry button and the browser's own `online` event both take over
 * from there.
 */
const MENU_RETRY_DELAYS = [2_000, 5_000, 12_000, 30_000] as const;

export default function App() {
  const [view, setView] = useState<View>("menu");
  const [cartOpen, setCartOpen] = useState(false);
  const [placed, setPlaced] = useState<ApiOrderResponse | null>(null);
  // Computed once at the moment of placing (Checkout knows the selected
  // service/area; nothing downstream should re-derive it and risk a
  // different answer if real time has moved on, e.g. during a Stripe trip).
  const [timing, setTiming] = useState<OrderTiming | null>(null);
  // True only when the customer has just returned from Stripe having paid. The
  // order itself cannot tell us — it was stashed before the redirect.
  const [cardAuthorised, setCardAuthorised] = useState(false);

  const lines = useCart((s) => s.lines);
  const reconcile = useCart((s) => s.reconcile);
  const count = itemCountOf(lines);
  const subtotal = subtotalOf(lines);
  const open = isOpenNow();

  const loadMenu = useMenu((s) => s.load);
  const menuItems = useMenu((s) => s.items);
  const menuSource = useMenu((s) => s.source);
  const orderingPaused = useMenu((s) => s.orderingPaused);
  const pausedMessage = useMenu((s) => s.pausedMessage);

  // Coming back from Stripe.
  //
  // This runs BEFORE the menu load below matters, because a customer returning
  // from a payment must see their confirmation immediately rather than a menu
  // that flickers into a confirmation a second later. The order was stashed
  // before the redirect, so nothing has to be re-fetched to draw the screen —
  // and `OrderConfirmation` starts polling the real status the moment it
  // mounts, so what is shown is the server's truth within one poll.
  //
  // Runs once, on mount only. The query parameters are stripped immediately so
  // a refresh cannot replay it.
  useEffect(() => {
    const back = returnFromStripe();
    if (!back) return;

    const restored = takePendingOrder(back.orderId);
    stripReturnParams();

    // No stash means a different browser, cleared storage, or a link someone
    // shared. The order is real and the shop can see it either way, so send
    // them to the menu rather than inventing a confirmation we cannot back up.
    if (restored) {
      setPlaced(restored.order);
      setTiming(restored.timing);
      setCardAuthorised(back.paid);
      setView("done");
    }
  }, []);

  // Fetch the live menu once on mount. Until it arrives the hardcoded menu is
  // on screen and ordering is off, so there is no window where a customer can
  // build a basket the server would reject.
  useEffect(() => {
    void loadMenu();
  }, [loadMenu]);

  // OI-78. One failed fetch used to end ordering for the entire session: the
  // menu was asked for once, on mount, and nothing ever asked again. A customer
  // whose signal dropped for a second browsed a full menu, built a basket, and
  // was only told at the checkout total. Rural Argyll is exactly where that
  // happens. Retry a few times with a widening gap, and immediately when the
  // browser tells us the connection is back.
  const retries = useRef(0);

  useEffect(() => {
    if (menuSource === "api") {
      retries.current = 0;
      return;
    }
    if (menuSource !== "fallback") return;
    if (retries.current >= MENU_RETRY_DELAYS.length) return;

    const delay = MENU_RETRY_DELAYS[retries.current]!;
    retries.current += 1;
    const timer = setTimeout(() => void loadMenu(), delay);
    return () => clearTimeout(timer);
  }, [menuSource, loadMenu]);

  // Sticky across retries. `source` flips fallback → loading → fallback on every
  // attempt, so keying the warning off `source` alone would blink it out of
  // existence each time we try again and make the page look broken twice over.
  const [menuFailed, setMenuFailed] = useState(false);
  useEffect(() => {
    if (menuSource === "fallback") setMenuFailed(true);
    else if (menuSource === "api") setMenuFailed(false);
  }, [menuSource]);

  // A manual tap always gets a fresh set of automatic attempts behind it.
  const retryMenu = useCallback(() => {
    retries.current = 0;
    void loadMenu();
  }, [loadMenu]);

  useEffect(() => {
    const onOnline = () => {
      retries.current = 0;
      void loadMenu();
    };
    window.addEventListener("online", onOnline);
    return () => window.removeEventListener("online", onOnline);
  }, [loadMenu]);

  // `view` swaps the whole screen in place rather than navigating to a new
  // route, so the browser keeps whatever scroll position the menu list was
  // at. Someone who had scrolled deep into the menu before checking out would
  // land on checkout already scrolled past the name/phone fields. Every view
  // change should start at the top.
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [view]);

  // The basket is persisted to localStorage, so it can hold items from before
  // the menu changed — or from another environment entirely. Prune it against
  // whatever menu is now live, and refresh the prices of what survives.
  useEffect(() => {
    if (menuSource === "api") reconcile(menuItems);
  }, [menuSource, menuItems, reconcile]);

  return (
    <div className="min-h-screen">
      <div className="sticky top-0 z-50">
        <header className="bg-ink/95 backdrop-blur border-b border-ink-line">
          <div className="flex items-center justify-between px-4 h-14 max-w-3xl mx-auto">
            <button
              onClick={() => setView("menu")}
              className="font-display text-lg tracking-tight"
            >
              CHICK <span className="text-flame">SHACK</span>
            </button>
            <span
              className={`text-xs font-semibold px-2.5 py-1 rounded-full border ${
                open
                  ? "border-emerald-500/40 text-emerald-400"
                  : "border-ink-line text-cream/50"
              }`}
            >
              {open ? "Open now" : `Opens ${SHOP.openTime}`}
            </span>
          </div>
        </header>
      </div>

      {view === "menu" && (
        <>
          <section className="px-4 pt-8 pb-2 max-w-3xl mx-auto">
            <h1 className="font-display text-3xl sm:text-4xl leading-tight">
              {SHOP.tagline}
            </h1>
            <p className="text-cream/60 mt-2">
              {SHOP.addressLines.join(", ")} · {SHOP.postcode}
            </p>
            {/* The shop has paused ordering during a rush (Imran, 2026-08-04).
                Said here, at the top of the menu, rather than only at checkout
                — a customer who builds a whole basket before being told to
                phone has been wasted, and this outranks the closed/pre-order
                notice below because it is the reason they cannot order at all. */}
            {orderingPaused ? (
              <p className="mt-4 card p-3 text-sm text-ember border-ember/40">
                {pausedMessage ?? DEFAULT_PAUSED_MESSAGE}
              </p>
            ) : menuFailed ? (
              /* OI-78. Say it here, not at the checkout total. The old
                 behaviour let someone browse the whole menu and build a basket
                 before discovering they could not order — and then told them
                 "coming very soon", which reads as "this shop has not launched"
                 rather than "your connection dropped". */
              <div className="mt-4 card p-3 border-flame/40 flex items-center justify-between gap-3">
                <p className="text-sm text-ember">
                  Your internet connection has dropped, so we can't load the
                  live menu. Check your signal, then tap Retry.
                </p>
                <button
                  onClick={retryMenu}
                  disabled={menuSource === "loading"}
                  className="btn-ghost tap h-10 shrink-0 text-sm"
                >
                  {menuSource === "loading" ? "Trying…" : "Retry"}
                </button>
              </div>
            ) : (
              !open && (
                <p className="mt-4 card p-3 text-sm text-ember">
                  We're closed right now — but you can still order. Open daily{" "}
                  {SHOP.openTime}–{SHOP.closeTime}; we'll confirm your pre-order
                  when we open.
                </p>
              )
            )}
            {/* Imran asked (2026-08-03) for last-order/delivery-window times
                to be visible on the site itself, not just shown reactively
                once a customer is already past a cut-off. Always shown, same
                card treatment as the Allergen Notice below. */}
            <div className="mt-4 card p-3 text-xs text-cream/70">
              <p className="font-bold uppercase tracking-wide text-cream/90">
                Hours
              </p>
              <p className="mt-1 leading-relaxed">
                Collection {SHOP.openTime}–{SHOP.closeTime} · Delivery{" "}
                {SHOP.deliveryOpenTime}–{SHOP.deliveryCloseTime}
                {SHOP.deliveryAreas.some((a) => a.closeTime) && (
                  <>
                    {" "}
                    (
                    {SHOP.deliveryAreas
                      .filter((a) => a.closeTime)
                      .map((a) => `${a.name} until ${a.closeTime}`)
                      .join(", ")}
                    )
                  </>
                )}
              </p>
            </div>
            {/* Same notice and styling as the one on Checkout — shown here too
                so it's visible before a customer starts choosing items, not
                only once they reach the end of ordering. */}
            <div className="mt-4 card p-3 border-ember/40 bg-ember/10">
              <p className="text-xs font-bold uppercase tracking-wide text-ember">
                Allergen Notice
              </p>
              <p className="text-xs text-cream/70 leading-relaxed mt-1">
                {SHOP.allergenNotice}
              </p>
            </div>
          </section>
          <MenuBrowser />
        </>
      )}

      {view === "checkout" && (
        <Checkout
          onBack={() => setView("menu")}
          onPlaced={(order, orderTiming) => {
            setPlaced(order);
            setTiming(orderTiming);
            setView("done");
          }}
        />
      )}

      {view === "done" && placed && timing && (
        <OrderConfirmation
          order={placed}
          timing={timing}
          cardAuthorised={cardAuthorised}
          onDone={() => {
            setPlaced(null);
            setTiming(null);
            setCardAuthorised(false);
            setView("menu");
          }}
        />
      )}

      {/* Persistent basket bar. Hidden once you're past the menu. */}
      {view === "menu" && count > 0 && (
        <div className="fixed bottom-0 inset-x-0 z-40 p-4 bg-gradient-to-t from-ink via-ink to-transparent">
          <button
            onClick={() => setCartOpen(true)}
            className="btn-primary tap w-full max-w-3xl mx-auto h-14 flex justify-between"
          >
            <span>
              {count} {count === 1 ? "item" : "items"}
            </span>
            <span>View order · {formatGBP(subtotal)}</span>
          </button>
        </div>
      )}

      {cartOpen && (
        <CartPanel
          onClose={() => setCartOpen(false)}
          onCheckout={() => {
            setCartOpen(false);
            setView("checkout");
          }}
        />
      )}
    </div>
  );
}
