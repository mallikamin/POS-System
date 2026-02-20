import { useState, useEffect } from "react";
import { Minus, Plus, ShoppingCart, ChefHat, X, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import { formatPKR } from "@/utils/currency";
import { useCartStore, type CartLine, type Cart, EMPTY_CART } from "@/stores/cartStore";
import { useOrderStore } from "@/stores/orderStore";
import { useUIStore } from "@/stores/uiStore";
import { useCustomerStore } from "@/stores/customerStore";

const TAX_BPS = 1600; // 16.00% in basis points (integer math)

export function CartPanel() {
  // Direct property selectors — stable references, no method calls
  const cart: Cart = useCartStore((s) => s.carts[s.activeCartId]) ?? EMPTY_CART;
  const activeCartId = useCartStore((s) => s.activeCartId);
  const updateQuantity = useCartStore((s) => s.updateQuantity);
  const removeItem = useCartStore((s) => s.removeItem);
  const clearCart = useCartStore((s) => s.clearCart);
  const isSending = useOrderStore((s) => s.isSending);
  const orderError = useOrderStore((s) => s.error);
  const currentChannel = useUIStore((s) => s.currentChannel);
  const selectedCustomer = useCustomerStore((s) => s.selectedCustomer);

  const [clearConfirmOpen, setClearConfirmOpen] = useState(false);
  const [sentSuccess, setSentSuccess] = useState(false);
  const [orderNumber, setOrderNumber] = useState<string | null>(null);
  const [displayError, setDisplayError] = useState<string | null>(null);

  // Sync orderError to displayError
  useEffect(() => {
    if (orderError) {
      setDisplayError(orderError);
    }
  }, [orderError]);

  const subtotal = cart.lines.reduce((sum, l) => sum + l.unitPrice * l.quantity, 0);
  const itemCount = cart.lines.reduce((sum, l) => sum + l.quantity, 0);
  const tax = Math.round(subtotal * TAX_BPS / 10000); // integer math
  const total = subtotal + tax;

  async function handleSendToKitchen() {
    if (cart.lines.length === 0 || isSending) return;

    const orderType = currentChannel || "takeaway";
    const tableId = activeCartId.startsWith("table-")
      ? activeCartId.replace("table-", "")
      : undefined;

    try {
      setDisplayError(null);
      const customerName =
        orderType === "call_center" && selectedCustomer ? selectedCustomer.name : undefined;
      const customerPhone =
        orderType === "call_center" && selectedCustomer ? selectedCustomer.phone : undefined;
      const order = await useOrderStore.getState().createOrderFromCart(
        orderType,
        tableId,
        customerName,
        customerPhone
      );
      setOrderNumber(order.order_number);
      setSentSuccess(true);
      setTimeout(() => {
        setSentSuccess(false);
        setOrderNumber(null);
      }, 4000);
    } catch {
      // Error is stored in orderStore.error and will be displayed via useEffect
    }
  }

  function handleClearCart() {
    clearCart();
    setClearConfirmOpen(false);
  }

  return (
    <div className="flex h-full flex-col bg-white">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-secondary-200 px-4 py-3">
        <div className="flex items-center gap-2">
          <ShoppingCart className="h-5 w-5 text-primary-600" />
          <h2 className="font-semibold text-secondary-900">Current Order</h2>
        </div>
        {itemCount > 0 && (
          <Badge variant="default">{itemCount} item{itemCount !== 1 && "s"}</Badge>
        )}
      </div>

      {/* Cart Lines */}
      <div className="flex-1 overflow-y-auto">
        {sentSuccess && (
          <div className="mx-4 mt-3 flex items-center gap-2 rounded-lg bg-success-50 px-3 py-2 text-sm text-success-700">
            <ChefHat className="h-4 w-4" />
            Order #{orderNumber} sent to kitchen!
          </div>
        )}
        {displayError && (
          <div className="mx-4 mt-3 flex items-center justify-between rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">
            <span>{displayError}</span>
            <button
              onClick={() => setDisplayError(null)}
              className="ml-2 rounded p-0.5 hover:bg-danger-100"
              aria-label="Dismiss error"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}

        {cart.lines.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 py-16 px-4">
            <ShoppingCart className="h-10 w-10 text-secondary-200" />
            <p className="text-sm text-secondary-400 text-center">
              Tap menu items to add them here
            </p>
          </div>
        ) : (
          <div className="divide-y divide-secondary-100">
            {cart.lines.map((line) => (
              <CartLineItem
                key={line.lineId}
                line={line}
                onUpdateQty={(qty) => updateQuantity(line.lineId, qty)}
                onRemove={() => removeItem(line.lineId)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Totals + Actions */}
      {cart.lines.length > 0 && (
        <div className="border-t border-secondary-200 p-4 space-y-3">
          {/* Totals */}
          <div className="space-y-1 text-sm">
            <div className="flex justify-between text-secondary-600">
              <span>Subtotal</span>
              <span>{formatPKR(subtotal)}</span>
            </div>
            <div className="flex justify-between text-secondary-600">
              <span>Tax (16% GST)</span>
              <span>{formatPKR(tax)}</span>
            </div>
            <div className="flex justify-between font-bold text-secondary-900 text-base pt-1 border-t border-secondary-100">
              <span>Total</span>
              <span>{formatPKR(total)}</span>
            </div>
          </div>

          {/* Action buttons */}
          <div className="space-y-2">
            <Button
              onClick={handleSendToKitchen}
              className="w-full gap-2"
              size="pos"
              disabled={isSending}
            >
              {isSending ? (
                <Loader2 className="h-5 w-5 animate-spin" />
              ) : (
                <ChefHat className="h-5 w-5" />
              )}
              {isSending ? "Sending..." : "Send to Kitchen"}
            </Button>
            <Button
              variant="ghost"
              onClick={() => setClearConfirmOpen(true)}
              className="w-full text-danger-600 hover:text-danger-700 hover:bg-danger-50"
              size="sm"
            >
              Clear Order
            </Button>
          </div>
        </div>
      )}

      {/* Clear Confirmation */}
      <Dialog open={clearConfirmOpen} onOpenChange={setClearConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Clear Order</DialogTitle>
            <DialogDescription>
              Remove all items from the current order?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setClearConfirmOpen(false)} className="min-h-touch">
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleClearCart} className="min-h-touch">
              Clear All
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/* ==========================================================================
   Cart Line Item
   ========================================================================== */

interface CartLineItemProps {
  line: CartLine;
  onUpdateQty: (qty: number) => void;
  onRemove: () => void;
}

function CartLineItem({ line, onUpdateQty, onRemove }: CartLineItemProps) {
  const lineTotal = line.unitPrice * line.quantity;

  return (
    <div className="px-4 py-3 space-y-2">
      <div className="flex items-start gap-2">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-secondary-900 leading-tight">
            {line.menuItem.name}
          </p>
          {line.modifiers.length > 0 && (
            <div className="mt-0.5 flex flex-wrap gap-1">
              {line.modifiers.map((mod) => (
                <span
                  key={mod.modifier_option_id}
                  className="text-[11px] text-secondary-500 bg-secondary-50 rounded px-1.5 py-0.5"
                >
                  {mod.name}
                  {mod.price_adjustment !== 0 && (
                    <span className={mod.price_adjustment > 0 ? "text-secondary-400" : "text-success-600"}>
                      {" "}
                      {mod.price_adjustment > 0 ? "+" : "-"}
                      {formatPKR(Math.abs(mod.price_adjustment))}
                    </span>
                  )}
                </span>
              ))}
            </div>
          )}
        </div>
        <button
          onClick={onRemove}
          aria-label="Remove item"
          className="mt-0.5 rounded p-1 text-secondary-300 hover:text-danger-500 hover:bg-danger-50 transition-colors"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="flex items-center justify-between">
        {/* Quantity controls */}
        <div className="flex items-center gap-1">
          <button
            onClick={() => onUpdateQty(line.quantity - 1)}
            aria-label="Decrease quantity"
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-secondary-200 text-secondary-600 hover:bg-secondary-50 active:bg-secondary-100 transition-colors"
          >
            <Minus className="h-3.5 w-3.5" />
          </button>
          <span className="w-8 text-center text-sm font-semibold text-secondary-900">
            {line.quantity}
          </span>
          <button
            onClick={() => onUpdateQty(line.quantity + 1)}
            aria-label="Increase quantity"
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-secondary-200 text-secondary-600 hover:bg-secondary-50 active:bg-secondary-100 transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
          </button>
        </div>

        {/* Line total */}
        <span className="text-sm font-semibold text-secondary-900">
          {formatPKR(lineTotal)}
        </span>
      </div>
    </div>
  );
}
