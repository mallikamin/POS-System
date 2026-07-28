import { SHOP } from "../data/menu";
import { formatGBP } from "../lib/money";
import { subtotalOf, useCart } from "../store/cart";

interface Props {
  onClose: () => void;
  onCheckout: () => void;
}

export default function CartPanel({ onClose, onCheckout }: Props) {
  const lines = useCart((s) => s.lines);
  const setQuantity = useCart((s) => s.setQuantity);
  const subtotal = subtotalOf(lines);

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/70 backdrop-blur-sm"
      onClick={onClose}
    >
      <aside
        className="w-full sm:max-w-md bg-ink-soft border-l border-ink-line flex flex-col"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Your order"
      >
        <header className="flex items-center justify-between p-5 border-b border-ink-line">
          <h2 className="font-display text-xl">Your order</h2>
          <button
            onClick={onClose}
            aria-label="Close"
            className="w-9 h-9 rounded-full border border-ink-line text-cream/60 hover:text-cream"
          >
            ✕
          </button>
        </header>

        <div className="flex-1 overflow-y-auto p-5 space-y-3">
          {lines.length === 0 && (
            <p className="text-cream/50 text-center py-12">
              Your order is empty.
            </p>
          )}

          {lines.map((line) => (
            <div key={line.key} className="card p-4">
              <div className="flex justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="font-semibold leading-snug">{line.itemName}</h3>
                  {line.variantName && (
                    <p className="text-sm text-cream/55">{line.variantName}</p>
                  )}
                  {line.modifiers.length > 0 && (
                    <p className="text-sm text-cream/45 mt-0.5">
                      {line.modifiers.map((m) => m.name).join(", ")}
                    </p>
                  )}
                </div>
                <span className="font-semibold shrink-0">
                  {formatGBP(line.unitPrice * line.quantity)}
                </span>
              </div>

              <div className="flex items-center gap-1 mt-3">
                <button
                  onClick={() => setQuantity(line.key, line.quantity - 1)}
                  className="w-9 h-9 rounded-lg border border-ink-line"
                  aria-label={`Reduce ${line.itemName}`}
                >
                  −
                </button>
                <span className="w-8 text-center text-sm">{line.quantity}</span>
                <button
                  onClick={() => setQuantity(line.key, line.quantity + 1)}
                  className="w-9 h-9 rounded-lg border border-ink-line"
                  aria-label={`Add another ${line.itemName}`}
                >
                  +
                </button>
              </div>
            </div>
          ))}
        </div>

        {lines.length > 0 && (
          <footer className="p-5 border-t border-ink-line space-y-3">
            <div className="flex justify-between font-display text-lg">
              <span>Subtotal</span>
              <span>{formatGBP(subtotal)}</span>
            </div>
            <p className="text-xs text-cream/45">
              Delivery charge, if any, is added at checkout.
            </p>
            <button onClick={onCheckout} className="btn-primary tap w-full h-13 py-3">
              {SHOP.orderingEnabled ? "Go to checkout" : "Continue"}
            </button>
          </footer>
        )}
      </aside>
    </div>
  );
}
