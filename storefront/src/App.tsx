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

type View = "menu" | "checkout" | "done";

export default function App() {
  const [view, setView] = useState<View>("menu");
  const [cartOpen, setCartOpen] = useState(false);
  const [placed, setPlaced] = useState<ApiOrderResponse | null>(null);

  const lines = useCart((s) => s.lines);
  const reconcile = useCart((s) => s.reconcile);
  const count = itemCountOf(lines);
  const subtotal = subtotalOf(lines);
  const open = isOpenNow();

  const loadMenu = useMenu((s) => s.load);
  const menuItems = useMenu((s) => s.items);
  const menuSource = useMenu((s) => s.source);

  // Fetch the live menu once on mount. Until it arrives the hardcoded menu is
  // on screen and ordering is off, so there is no window where a customer can
  // build a basket the server would reject.
  useEffect(() => {
    void loadMenu();
  }, [loadMenu]);

  // The basket is persisted to localStorage, so it can hold items from before
  // the menu changed — or from another environment entirely. Prune it against
  // whatever menu is now live, and refresh the prices of what survives.
  useEffect(() => {
    if (menuSource === "api") reconcile(menuItems);
  }, [menuSource, menuItems, reconcile]);

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 bg-ink/95 backdrop-blur border-b border-ink-line">
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
                We're closed right now. Open daily {SHOP.openTime}–{SHOP.closeTime}
                {" "}— build your order now and place it from {SHOP.orderFromTime}.
              </p>
            )}
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
          onDone={() => {
            setPlaced(null);
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
