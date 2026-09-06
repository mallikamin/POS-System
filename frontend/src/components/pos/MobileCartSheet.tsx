/**
 * The order panel as a bottom sheet on a phone (Martin M12).
 *
 * > "How it looks on the phone still bad" -- with a screenshot of the Takeaway
 * >  till: a tall empty white column on the left and the cart crushed into a
 * >  strip down the right.
 *
 * The cause is one line, repeated on all three till screens: the page is a flex
 * ROW with a fixed `w-80` right column. On a 1024px+ screen that is the right
 * layout. On a 360px phone it leaves the menu 40px of usable width, which is
 * exactly what he photographed.
 *
 * So below `lg` the right column stops being a column. The menu gets the whole
 * screen, and this renders a fixed bar at the bottom that opens the same panel
 * full height. At `lg` and up nothing changes at all -- the desktop and tablet
 * tills are untouched.
 *
 * 🔴 The bar shows an item COUNT and no money. The total on the cart can carry
 * a delivery fee and a service charge that this component knows nothing about,
 * and a summary bar quietly disagreeing with the panel it opens is worse than a
 * bar that never quotes a number.
 */

import { useEffect, useState, type ReactNode } from "react";
import { ShoppingCart, X } from "lucide-react";
import { useCartStore, EMPTY_CART, type Cart } from "@/stores/cartStore";
import { cn } from "@/lib/utils";

interface MobileCartSheetProps {
  /** The whole right-hand column: the cart panel and anything above it. */
  children: ReactNode;
  /** Width of the desktop column. Matches what the page used before. */
  className?: string;
}

export function MobileCartSheet({ children, className }: MobileCartSheetProps) {
  const cart: Cart = useCartStore((s) => s.carts[s.activeCartId]) ?? EMPTY_CART;
  const itemCount = cart.lines.reduce((sum, l) => sum + l.quantity, 0);
  const [open, setOpen] = useState(false);

  // The sheet is a phone affordance. Rotating a tablet to landscape crosses
  // `lg`, where the panel is on screen permanently; leaving the sheet open
  // would then paint a second copy of it over the page.
  useEffect(() => {
    const query = window.matchMedia("(min-width: 1024px)");
    const close = () => {
      if (query.matches) setOpen(false);
    };
    close();
    query.addEventListener("change", close);
    return () => query.removeEventListener("change", close);
  }, []);

  // The body must not scroll behind an open sheet, or a flick on the backdrop
  // scrolls the menu underneath it.
  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [open]);

  return (
    <>
      {/* Desktop and landscape tablet: the column, exactly as before. */}
      <div
        className={cn(
          "hidden shrink-0 border-l border-secondary-200 lg:flex lg:flex-col",
          className ?? "lg:w-80",
        )}
      >
        {children}
      </div>

      {/* Phone: a bar at the bottom. `pb-safe` keeps it clear of the iOS home
          indicator, which otherwise sits on top of the button. */}
      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-secondary-200 bg-white p-3 pb-[calc(0.75rem+env(safe-area-inset-bottom))] shadow-[0_-2px_10px_rgba(0,0,0,0.06)] lg:hidden">
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="flex min-h-[56px] w-full items-center justify-center gap-2 rounded-lg bg-primary-600 px-4 font-semibold text-white active:bg-primary-700"
        >
          <ShoppingCart className="h-5 w-5" />
          {itemCount === 0
            ? "Open order"
            : `View order · ${itemCount} item${itemCount === 1 ? "" : "s"}`}
        </button>
      </div>

      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-black/40"
            onClick={() => setOpen(false)}
            aria-hidden="true"
          />
          <div className="absolute inset-x-0 bottom-0 top-10 flex flex-col overflow-hidden rounded-t-2xl bg-white">
            <div className="flex items-center justify-between border-b border-secondary-200 px-4 py-2">
              <span className="text-sm font-semibold text-secondary-800">
                Current order
              </span>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Close order panel"
                className="flex h-11 w-11 items-center justify-center rounded text-secondary-500"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
              {children}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
