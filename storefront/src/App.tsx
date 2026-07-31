import { useEffect, useState } from "react";
import { SHOP } from "./data/menu";
import { formatGBP } from "./lib/money";
import { isOpenNow } from "./lib/delivery";
import { itemCountOf, subtotalOf, useCart } from "./store/cart";
import { useMenu } from "./store/menu";
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

export default function App() {
  const [view, setView] = useState<View>("menu");
  const [cartOpen, setCartOpen] = useState(false);
  const [placed, setPlaced] = useState<ApiOrderResponse | null>(null);
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
      setPlaced(restored);
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
      {/* Testing-mode notice. Sits above the header inside one sticky wrapper so
          it stays visible on every view (menu, checkout, confirmation) until
          Malik removes it — this is not tied to open/closed or ordering state. */}
      <div className="sticky top-0 z-50">
        <div className="bg-ember text-ink px-4 py-2.5 text-center border-b-2 border-ink">
          <p className="font-bold text-sm sm:text-base leading-snug">
            This website is under testing — please do not place an order here.
          </p>
          <p className="text-xs sm:text-sm mt-0.5">
            To place an order now, call us directly on{" "}
            <a href="tel:07719566889" className="underline font-semibold">
              07719 566 889
            </a>
            . Website ordering will be live shortly.
          </p>
        </div>
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
            {!open && (
              <p className="mt-4 card p-3 text-sm text-ember">
                We're closed right now — but you can still order. Open daily{" "}
                {SHOP.openTime}–{SHOP.closeTime}; we'll confirm your pre-order
                when we open.
              </p>
            )}
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
          onPlaced={(order) => {
            setPlaced(order);
            setView("done");
          }}
        />
      )}

      {view === "done" && placed && (
        <OrderConfirmation
          order={placed}
          cardAuthorised={cardAuthorised}
          onDone={() => {
            setPlaced(null);
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
