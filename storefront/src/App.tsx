import { useState } from "react";
import { SHOP } from "./data/menu";
import { formatGBP } from "./lib/money";
import { isOpenNow } from "./lib/delivery";
import { itemCountOf, subtotalOf, useCart } from "./store/cart";
import MenuBrowser from "./components/MenuBrowser";
import CartPanel from "./components/CartPanel";
import Checkout from "./components/Checkout";

type View = "menu" | "checkout" | "done";

export default function App() {
  const [view, setView] = useState<View>("menu");
  const [cartOpen, setCartOpen] = useState(false);
  const [reference, setReference] = useState("");

  const lines = useCart((s) => s.lines);
  const count = itemCountOf(lines);
  const subtotal = subtotalOf(lines);
  const open = isOpenNow();

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
                — you can still build your order.
              </p>
            )}
          </section>
          <MenuBrowser />
        </>
      )}

      {view === "checkout" && (
        <Checkout
          onBack={() => setView("menu")}
          onPlaced={(ref) => {
            setReference(ref);
            setView("done");
          }}
        />
      )}

      {view === "done" && (
        <div className="px-4 py-20 max-w-md mx-auto text-center space-y-4">
          <div className="text-5xl">🍗</div>
          <h1 className="font-display text-2xl">Order received</h1>
          <p className="text-cream/70">
            Your reference is <strong className="text-flame-light">{reference}</strong>.
            We'll confirm your order and text you a collection time shortly.
          </p>
          <p className="text-sm text-cream/50">
            Any problems, call {SHOP.phones[0]}.
          </p>
          <button onClick={() => setView("menu")} className="btn-ghost tap h-12">
            Back to menu
          </button>
        </div>
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
