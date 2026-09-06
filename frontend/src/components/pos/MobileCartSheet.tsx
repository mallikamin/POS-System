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
 * screen, and this renders a fixed bar at the bottom that slides the same panel
 * up over the page. At `lg` and up nothing changes at all -- the desktop and
 * tablet tills are untouched.
 *
 * 🔴 `children` is rendered EXACTLY ONCE and is never unmounted. The first cut
 * of this component rendered it twice, in a desktop column and again inside the
 * sheet, which mounted two CartPanels at the same time and threw away anything
 * typed into the sheet (a delivery fee, a customer name) the moment it closed.
 * The panel is one instance whose POSITIONING changes; only CSS moves.
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
  // `lg`, where the panel is on screen permanently; leaving `open` set would
  // then keep the backdrop painted over a page that no longer needs it.
  useEffect(() => {
    const query = window.matchMedia("(min-width: 1024px)");
    const close = () => {
      if (query.matches) setOpen(false);
    };
    close();
    query.addEventListener("change", close);
    return () => query.removeEventListener("change", close);
  }, []);

  // The page must not scroll behind an open sheet, or a flick on the backdrop
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
      {/* Backdrop. Phone only, and only while the sheet is up. */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/40 lg:hidden"
          onClick={() => setOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* The panel itself. ONE instance.
          At `lg`: a normal in-flow column, exactly as before.
          Below `lg`: a fixed sheet, translated off the bottom until opened. */}
      <div
        className={cn(
          "flex flex-col border-secondary-200 bg-white",
          // Phone: the sheet.
          "fixed inset-x-0 bottom-0 top-10 z-50 overflow-hidden rounded-t-2xl shadow-2xl transition-transform duration-200",
          !open && "translate-y-full",
          // Laptop and landscape tablet: back into the row, untransformed.
          "lg:static lg:z-auto lg:translate-y-0 lg:rounded-none lg:border-l lg:shadow-none",
          "lg:shrink-0",
          className ?? "lg:w-80",
        )}
        // A sheet that is slid off-screen is still in the DOM, so it has to be
        // hidden from a screen reader and from tab order as well as from view.
        // `inert` is not typed on React 18's JSX, hence the attribute form.
        {...(!open ? { "aria-hidden": true } : {})}
      >
        <div className="flex items-center justify-between border-b border-secondary-200 px-4 py-2 lg:hidden">
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
        <div className="flex min-h-0 flex-1 flex-col overflow-y-auto lg:overflow-visible">
          {children}
        </div>
      </div>

      {/* Phone: the bar that opens it. `env(safe-area-inset-bottom)` keeps it
          clear of the iOS home indicator, which otherwise sits on the button. */}
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
    </>
  );
}
