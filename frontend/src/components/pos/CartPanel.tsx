import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Minus, Plus, ShoppingCart, ChefHat, X, Loader2, CreditCard, User, Search, RotateCcw } from "lucide-react";
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
import { useConfigStore } from "@/stores/configStore";
import { searchCustomers } from "@/services/customerApi";
import type { CustomerResponse } from "@/types/customer";

const DEFAULT_TAX_BPS = 1600; // 16.00% in basis points (integer math)

interface CartPanelProps {
  waiterId?: string;
  onOrderCreated?: () => void;
}

export function CartPanel({ waiterId, onOrderCreated }: CartPanelProps = {}) {
  const navigate = useNavigate();
  // Direct property selectors — stable references, no method calls
  const cart: Cart = useCartStore((s) => s.carts[s.activeCartId]) ?? EMPTY_CART;
  const activeCartId = useCartStore((s) => s.activeCartId);
  const updateQuantity = useCartStore((s) => s.updateQuantity);
  const removeItem = useCartStore((s) => s.removeItem);
  const clearCart = useCartStore((s) => s.clearCart);
  const isSending = useOrderStore((s) => s.isSending);
  const orderError = useOrderStore((s) => s.error);
  const currentChannel = useUIStore((s) => s.currentChannel);
  const paymentFlow = useConfigStore((s) => s.config?.payment_flow);
  const configTaxRate = useConfigStore((s) => s.config?.default_tax_rate);
  const TAX_BPS = configTaxRate ?? DEFAULT_TAX_BPS;
  const selectedCustomer = useCustomerStore((s) => s.selectedCustomer);
  const isPayFirst = paymentFlow === "pay_first";

  const [clearConfirmOpen, setClearConfirmOpen] = useState(false);
  const [sentSuccess, setSentSuccess] = useState(false);
  const [orderNumber, setOrderNumber] = useState<string | null>(null);
  const [displayError, setDisplayError] = useState<string | null>(null);

  // Customer lookup for dine-in / takeaway
  const [customerName, setCustomerName] = useState("Walk-in Customer");
  const [customerPhone, setCustomerPhone] = useState("");
  const [linkedCustomer, setLinkedCustomer] = useState<CustomerResponse | null>(null);
  const [phoneQuery, setPhoneQuery] = useState("");
  const [searchResults, setSearchResults] = useState<CustomerResponse[]>([]);
  const [searching, setSearching] = useState(false);
  const [customerExpanded, setCustomerExpanded] = useState(false);
  const searchTimeout = useRef<ReturnType<typeof setTimeout>>();

  // Debounced phone search
  useEffect(() => {
    if (phoneQuery.length < 3) { setSearchResults([]); return; }
    clearTimeout(searchTimeout.current);
    searchTimeout.current = setTimeout(async () => {
      setSearching(true);
      try {
        const results = await searchCustomers(phoneQuery, 5);
        setSearchResults(results.filter((c) => c.phone !== "0000000000"));
      } catch { setSearchResults([]); }
      finally { setSearching(false); }
    }, 300);
    return () => clearTimeout(searchTimeout.current);
  }, [phoneQuery]);

  function selectCustomer(c: CustomerResponse) {
    setLinkedCustomer(c);
    setCustomerName(c.name);
    setCustomerPhone(c.phone);
    setPhoneQuery("");
    setSearchResults([]);
    setCustomerExpanded(false);
  }

  function resetCustomer() {
    setLinkedCustomer(null);
    setCustomerName("Walk-in Customer");
    setCustomerPhone("");
    setPhoneQuery("");
    setSearchResults([]);
  }

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
      let custName: string | undefined;
      let custPhone: string | undefined;
      if (orderType === "call_center" && selectedCustomer) {
        custName = selectedCustomer.name;
        custPhone = selectedCustomer.phone;
      } else {
        // dine_in / takeaway: use linked customer or manual name
        const name = customerName.trim();
        if (name && name !== "Walk-in Customer") custName = name;
        if (customerPhone.trim()) custPhone = customerPhone.trim();
      }
      const order = await useOrderStore.getState().createOrderFromCart(
        orderType,
        tableId,
        custName,
        custPhone,
        waiterId
      );
      onOrderCreated?.();
      if (isPayFirst) {
        // Pay-first: redirect to payment page
        navigate(`/payment/${order.id}`);
      } else {
        setOrderNumber(order.order_number);
        setSentSuccess(true);
        setTimeout(() => {
          setSentSuccess(false);
          setOrderNumber(null);
        }, 4000);
      }
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

      {/* Customer selector (dine-in / takeaway only) */}
      {currentChannel !== "call_center" && (
        <div className="border-b border-secondary-200">
          <button
            type="button"
            onClick={() => setCustomerExpanded(!customerExpanded)}
            className="flex w-full items-center gap-2 px-4 py-2 text-xs hover:bg-secondary-50 transition-colors"
          >
            <User className="h-3.5 w-3.5 text-secondary-400" />
            <span className="font-medium text-secondary-700">{customerName}</span>
            {customerPhone && (
              <span className="text-secondary-400">({customerPhone})</span>
            )}
            {linkedCustomer && (
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); resetCustomer(); }}
                className="ml-auto rounded p-0.5 text-secondary-400 hover:text-danger-500"
                aria-label="Reset to walk-in"
              >
                <RotateCcw className="h-3 w-3" />
              </button>
            )}
          </button>
          {customerExpanded && (
            <div className="px-4 pb-3 space-y-2">
              <div className="relative">
                <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-secondary-400" />
                <input
                  type="tel"
                  placeholder="Search by phone..."
                  value={phoneQuery}
                  onChange={(e) => setPhoneQuery(e.target.value)}
                  className="w-full rounded border border-secondary-200 py-1.5 pl-7 pr-2 text-xs focus:border-primary-400 focus:outline-none"
                />
              </div>
              {searching && <p className="text-[10px] text-secondary-400">Searching...</p>}
              {searchResults.length > 0 && (
                <div className="max-h-28 overflow-y-auto rounded border border-secondary-200 divide-y divide-secondary-100">
                  {searchResults.map((c) => (
                    <button
                      key={c.id}
                      type="button"
                      onClick={() => selectCustomer(c)}
                      className="flex w-full items-center justify-between px-3 py-1.5 text-xs hover:bg-primary-50 transition-colors"
                    >
                      <span className="font-medium text-secondary-800">{c.name}</span>
                      <span className="text-secondary-400">{c.phone}</span>
                    </button>
                  ))}
                </div>
              )}
              {!linkedCustomer && (
                <input
                  type="text"
                  placeholder="Or type customer name..."
                  value={customerName === "Walk-in Customer" ? "" : customerName}
                  onChange={(e) => setCustomerName(e.target.value || "Walk-in Customer")}
                  className="w-full rounded border border-secondary-200 py-1.5 px-2 text-xs focus:border-primary-400 focus:outline-none"
                />
              )}
            </div>
          )}
        </div>
      )}

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
              <span>Tax ({TAX_BPS / 100}% GST)</span>
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
              ) : isPayFirst ? (
                <CreditCard className="h-5 w-5" />
              ) : (
                <ChefHat className="h-5 w-5" />
              )}
              {isSending ? "Sending..." : isPayFirst ? "Pay & Send" : "Send to Kitchen"}
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
                  {(mod.quantity || 1) > 1 ? `${mod.quantity}x ` : ""}{mod.name}
                  {mod.price_adjustment !== 0 && (
                    <span className={mod.price_adjustment > 0 ? "text-secondary-400" : "text-success-600"}>
                      {" "}
                      {mod.price_adjustment > 0 ? "+" : "-"}
                      {formatPKR(Math.abs(mod.price_adjustment * (mod.quantity || 1)))}
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
            className="flex h-12 w-12 items-center justify-center rounded-lg border border-secondary-200 text-secondary-600 hover:bg-secondary-50 active:bg-secondary-100 transition-colors"
          >
            <Minus className="h-3.5 w-3.5" />
          </button>
          <span className="w-8 text-center text-sm font-semibold text-secondary-900">
            {line.quantity}
          </span>
          <button
            onClick={() => onUpdateQty(line.quantity + 1)}
            aria-label="Increase quantity"
            className="flex h-12 w-12 items-center justify-center rounded-lg border border-secondary-200 text-secondary-600 hover:bg-secondary-50 active:bg-secondary-100 transition-colors"
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
