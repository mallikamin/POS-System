import { useState, useEffect, useCallback, useLayoutEffect } from "react";
import {
  Phone,
  Search,
  UserPlus,
  User,
  Loader2,
  X,
  RotateCcw,
  AlertTriangle,
  MapPin,
  Clock,
  ShoppingBag,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import { MenuGrid } from "@/components/pos/MenuGrid";
import { CartPanel } from "@/components/pos/CartPanel";
import { OrderTicker } from "@/components/pos/OrderTicker";
import { useCartStore } from "@/stores/cartStore";
import { useUIStore } from "@/stores/uiStore";
import { useCustomerStore } from "@/stores/customerStore";
import { useMenuStore } from "@/stores/menuStore";
import { fetchOrder } from "@/services/ordersApi";
import { formatPKR } from "@/utils/currency";
import type { CartItem } from "@/types/cart";
import type { MenuItem } from "@/types/menu";
import type { SelectedModifier } from "@/types/cart";

// Debounce hook
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
}

// Status badge colors
function getStatusColor(status: string): string {
  switch (status) {
    case "completed":
      return "bg-green-100 text-green-700";
    case "voided":
      return "bg-red-100 text-red-700";
    case "in_kitchen":
      return "bg-amber-100 text-amber-700";
    case "ready":
      return "bg-blue-100 text-blue-700";
    case "confirmed":
      return "bg-gray-100 text-gray-600";
    case "served":
      return "bg-teal-100 text-teal-700";
    default:
      return "bg-gray-100 text-gray-600";
  }
}

function getPaymentColor(status: string): string {
  switch (status) {
    case "paid":
      return "bg-green-100 text-green-700";
    case "refunded":
      return "bg-orange-100 text-orange-700";
    default:
      return "bg-red-100 text-red-700";
  }
}

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays} days ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
  return `${Math.floor(diffDays / 30)} months ago`;
}

function CallCenterPage() {
  const addItem = useCartStore((s) => s.addItem);
  const setActiveCart = useCartStore((s) => s.setActiveCart);
  const setCurrentChannel = useUIStore((s) => s.setCurrentChannel);
  const {
    selectedCustomer,
    searchResults,
    orderHistory,
    isSearching,
    isCreating,
    isUpdating,
    isLoadingHistory,
    error,
    searchByPhone,
    selectCustomer,
    createCustomer: createCustomerAction,
    updateCustomer: updateCustomerAction,
    setError,
    clearError,
  } = useCustomerStore();
  const { categories, loadMenu } = useMenuStore();
  const resetCustomerStore = useCustomerStore((s) => s.reset);

  const [phoneInput, setPhoneInput] = useState("");
  const [showCustomerDialog, setShowCustomerDialog] = useState(false);
  const [isEditingCustomer, setIsEditingCustomer] = useState(false);
  const [customerForm, setCustomerForm] = useState({
    name: "",
    phone: "",
    email: "",
    alt_contact: "",
    default_address: "",
    city: "",
    alt_address: "",
    alt_city: "",
    notes: "",
  });
  const [repeatOrderLoading, setRepeatOrderLoading] = useState<string | null>(null);

  const debouncedPhone = useDebounce(phoneInput, 500);

  useEffect(() => {
    setCurrentChannel("call_center");
    return () => {
      resetCustomerStore();
    };
  }, [setCurrentChannel, resetCustomerStore]);

  useLayoutEffect(() => {
    setActiveCart("call-center");
  }, [setActiveCart]);

  // Search customers when debounced phone changes
  useEffect(() => {
    if (debouncedPhone.trim().length >= 3) {
      searchByPhone(debouncedPhone);
    } else {
      // Clear search results when phone is too short
      useCustomerStore.setState({ searchResults: [] });
    }
  }, [debouncedPhone, searchByPhone]);

  // Auto-select if single result
  useEffect(() => {
    if (searchResults.length === 1 && !selectedCustomer) {
      selectCustomer(searchResults[0]!);
      setPhoneInput(searchResults[0]!.phone);
    }
  }, [searchResults, selectedCustomer, selectCustomer]);

  const handleAddToCart = useCallback(
    (item: CartItem) => {
      addItem(item.menuItem, item.modifiers);
    },
    [addItem]
  );

  function handlePhoneChange(value: string) {
    // Strip non-digits
    const digits = value.replace(/\D/g, "");
    setPhoneInput(digits);
    if (selectedCustomer) {
      selectCustomer(null);
    }
  }

  function handleSelectCustomer(customer: typeof searchResults[0]) {
    if (!customer) return;
    selectCustomer(customer);
    setPhoneInput(customer.phone);
    useCustomerStore.setState({ searchResults: [] });
  }

  function handleNewCustomer() {
    setCustomerForm({
      name: "",
      phone: phoneInput,
      email: "",
      alt_contact: "",
      default_address: "",
      city: "",
      alt_address: "",
      alt_city: "",
      notes: "",
    });
    setIsEditingCustomer(false);
    setShowCustomerDialog(true);
  }

  function handleEditCustomer() {
    if (!selectedCustomer) return;
    setCustomerForm({
      name: selectedCustomer.name,
      phone: selectedCustomer.phone,
      email: selectedCustomer.email || "",
      alt_contact: selectedCustomer.alt_contact || "",
      default_address: selectedCustomer.default_address || "",
      city: selectedCustomer.city || "",
      alt_address: selectedCustomer.alt_address || "",
      alt_city: selectedCustomer.alt_city || "",
      notes: selectedCustomer.notes || "",
    });
    setIsEditingCustomer(true);
    setShowCustomerDialog(true);
  }

  async function handleSaveCustomer() {
    try {
      if (isEditingCustomer && selectedCustomer) {
        await updateCustomerAction(selectedCustomer.id, {
          name: customerForm.name || null,
          phone: customerForm.phone || null,
          email: customerForm.email || null,
          alt_contact: customerForm.alt_contact || null,
          default_address: customerForm.default_address || null,
          city: customerForm.city || null,
          alt_address: customerForm.alt_address || null,
          alt_city: customerForm.alt_city || null,
          notes: customerForm.notes || null,
        });
      } else {
        await createCustomerAction({
          name: customerForm.name,
          phone: customerForm.phone,
          email: customerForm.email || null,
          alt_contact: customerForm.alt_contact || null,
          default_address: customerForm.default_address || null,
          city: customerForm.city || null,
          alt_address: customerForm.alt_address || null,
          alt_city: customerForm.alt_city || null,
          notes: customerForm.notes || null,
        });
        setPhoneInput(customerForm.phone);
      }
      setShowCustomerDialog(false);
    } catch {
      // Error handled by store
    }
  }

  async function handleRepeatOrder(orderId: string) {
    setRepeatOrderLoading(orderId);
    try {
      await loadMenu();
      const order = await fetchOrder(orderId);

      // Clear current cart
      useCartStore.getState().clearCart("call-center");

      // Find menu items by ID and prefill cart
      const allMenuItems: MenuItem[] = [];
      categories.forEach((cat) => {
        cat.items.forEach((item) => {
          allMenuItems.push(item);
        });
      });

      for (const orderItem of order.items) {
        const menuItem = allMenuItems.find((m) => m.id === orderItem.menu_item_id);
        if (!menuItem) continue;

        // Convert order modifiers to selected modifiers
        const modifiers: SelectedModifier[] = orderItem.modifiers.map((m) => ({
          modifier_option_id: m.modifier_id,
          name: m.name,
          price_adjustment: m.price_adjustment,
          group_id: "",
          quantity: 1,
        }));

        // Add item to cart with same quantity
        for (let i = 0; i < orderItem.quantity; i++) {
          addItem(menuItem, modifiers);
        }
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load order";
      setError(message);
    } finally {
      setRepeatOrderLoading(null);
    }
  }

  // Compute void stats from order history
  const voidedCount = orderHistory.filter((o) => o.status === "voided").length;
  const totalOrders = orderHistory.length;
  const voidRate = totalOrders > 0 ? Math.round((voidedCount / totalOrders) * 100) : 0;

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-1 min-h-0">
        {/* Left: Customer panel */}
        <div className="w-80 shrink-0 border-r border-secondary-200 bg-secondary-50 flex flex-col">
          {/* Header */}
          <div className="border-b border-secondary-200 bg-white px-4 py-3">
            <div className="flex items-center gap-2 mb-3">
              <Phone className="h-5 w-5 text-primary-600" />
              <h2 className="font-semibold text-secondary-900">Call Center</h2>
            </div>

            {/* Phone search */}
            <div className="relative">
              <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-4 w-4 text-secondary-400" />
              <Input
                type="tel"
                placeholder="Enter phone number"
                value={phoneInput}
                onChange={(e) => handlePhoneChange(e.target.value)}
                className="pl-8 pr-8"
              />
              {isSearching && (
                <Loader2 className="absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4 animate-spin text-secondary-400" />
              )}
              {!isSearching && phoneInput && (
                <button
                  onClick={() => {
                    setPhoneInput("");
                    selectCustomer(null);
                    useCustomerStore.setState({ searchResults: [] });
                  }}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-0.5 rounded hover:bg-secondary-100 text-secondary-400"
                  aria-label="Clear search"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>

            {/* Search results */}
            {searchResults.length > 0 && !selectedCustomer && (
              <div className="mt-2 max-h-48 overflow-y-auto rounded-lg border border-secondary-200 bg-white">
                {searchResults.map((customer) => (
                  <button
                    key={customer.id}
                    onClick={() => handleSelectCustomer(customer)}
                    className="w-full px-3 py-2 text-left hover:bg-secondary-50 border-b border-secondary-100 last:border-b-0"
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="font-medium text-sm text-secondary-900">{customer.name}</div>
                        <div className="text-xs text-secondary-500">{customer.phone}</div>
                      </div>
                      {customer.risk_flag === "high" && (
                        <span className="px-1.5 py-0.5 text-[10px] font-bold rounded bg-red-100 text-red-700">
                          HIGH RISK
                        </span>
                      )}
                    </div>
                    {customer.order_count > 0 && (
                      <div className="text-xs text-secondary-400 mt-0.5">
                        {customer.order_count} order{customer.order_count !== 1 ? "s" : ""} | {formatPKR(customer.total_spent)}
                      </div>
                    )}
                  </button>
                ))}
              </div>
            )}

            {/* No results */}
            {debouncedPhone.length >= 3 && searchResults.length === 0 && !isSearching && (
              <div className="mt-2 text-center py-4">
                <p className="text-sm text-secondary-500 mb-2">No customer found</p>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleNewCustomer}
                  className="w-full"
                >
                  <UserPlus className="h-4 w-4 mr-1" />
                  Create New Customer
                </Button>
              </div>
            )}
          </div>

          {/* Selected customer */}
          {selectedCustomer && (
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {/* Customer info card */}
              <div className="bg-white rounded-lg border border-secondary-200 p-3">
                <div className="flex items-start justify-between mb-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold text-secondary-900 truncate">{selectedCustomer.name}</h3>
                      {selectedCustomer.risk_flag === "high" && (
                        <span className="shrink-0 inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[10px] font-bold rounded bg-red-100 text-red-700">
                          <AlertTriangle className="h-3 w-3" />
                          HIGH RISK
                        </span>
                      )}
                      {selectedCustomer.risk_flag === "blocked" && (
                        <span className="shrink-0 px-1.5 py-0.5 text-[10px] font-bold rounded bg-red-600 text-white">
                          BLOCKED
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-secondary-600">{selectedCustomer.phone}</p>
                  </div>
                  <button
                    onClick={handleEditCustomer}
                    className="p-1 rounded hover:bg-secondary-100 text-secondary-600"
                    aria-label="Edit customer"
                  >
                    <User className="h-4 w-4" />
                  </button>
                </div>

                {/* Alt contact */}
                {selectedCustomer.alt_contact && (
                  <div className="flex items-center gap-1 text-xs text-secondary-500 mb-1">
                    <Phone className="h-3 w-3" />
                    <span>Alt: {selectedCustomer.alt_contact}</span>
                  </div>
                )}

                {/* Email */}
                {selectedCustomer.email && (
                  <p className="text-xs text-secondary-500 mb-1">{selectedCustomer.email}</p>
                )}

                {/* Primary address */}
                {(selectedCustomer.default_address || selectedCustomer.city) && (
                  <div className="flex items-start gap-1 text-xs text-secondary-500 mb-1">
                    <MapPin className="h-3 w-3 mt-0.5 shrink-0" />
                    <span>
                      {selectedCustomer.default_address}
                      {selectedCustomer.city && `, ${selectedCustomer.city}`}
                    </span>
                  </div>
                )}

                {/* Alt address */}
                {(selectedCustomer.alt_address || selectedCustomer.alt_city) && (
                  <div className="flex items-start gap-1 text-xs text-secondary-400 mb-1">
                    <MapPin className="h-3 w-3 mt-0.5 shrink-0" />
                    <span>
                      {selectedCustomer.alt_address}
                      {selectedCustomer.alt_city && `, ${selectedCustomer.alt_city}`}
                    </span>
                  </div>
                )}

                {/* Stats row */}
                <div className="mt-2 pt-2 border-t border-secondary-100 flex flex-wrap gap-x-3 gap-y-1 text-xs text-secondary-500">
                  <span className="flex items-center gap-1">
                    <ShoppingBag className="h-3 w-3" />
                    {selectedCustomer.order_count} orders
                  </span>
                  <span className="font-medium text-secondary-700">
                    {formatPKR(selectedCustomer.total_spent)}
                  </span>
                  {selectedCustomer.last_order_at && (
                    <span className="flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {formatRelativeTime(selectedCustomer.last_order_at)}
                    </span>
                  )}
                </div>

                {/* Notes */}
                {selectedCustomer.notes && (
                  <div className="mt-2 pt-2 border-t border-secondary-100">
                    <p className="text-xs text-secondary-400 italic">{selectedCustomer.notes}</p>
                  </div>
                )}
              </div>

              {/* Order history */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-sm font-medium text-secondary-700">Order History</h4>
                  {voidedCount > 0 && (
                    <span className="text-[10px] font-medium text-red-600 bg-red-50 px-1.5 py-0.5 rounded">
                      {voidedCount} voided ({voidRate}%)
                    </span>
                  )}
                </div>
                {isLoadingHistory ? (
                  <div className="flex items-center justify-center py-4">
                    <Loader2 className="h-5 w-5 animate-spin text-primary-600" />
                  </div>
                ) : orderHistory.length === 0 ? (
                  <p className="text-xs text-secondary-400 text-center py-4">No previous orders</p>
                ) : (
                  <div className="space-y-2">
                    {orderHistory.map((order) => (
                      <div
                        key={order.id}
                        className={`bg-white rounded-lg border p-3 ${
                          order.status === "voided"
                            ? "border-red-200 bg-red-50/30"
                            : "border-secondary-200"
                        }`}
                      >
                        <div className="flex items-start justify-between mb-1">
                          <div>
                            <div className="font-medium text-sm text-secondary-900">
                              #{order.order_number}
                            </div>
                            <div className="text-xs text-secondary-500">
                              {new Date(order.created_at).toLocaleDateString()}
                            </div>
                          </div>
                          <div className="text-right space-y-1">
                            <div className="font-semibold text-sm text-secondary-900">
                              {formatPKR(order.total)}
                            </div>
                            <div className="flex gap-1 justify-end">
                              <span className={`px-1.5 py-0.5 text-[10px] font-medium rounded ${getStatusColor(order.status)}`}>
                                {order.status.replace("_", " ")}
                              </span>
                              <span className={`px-1.5 py-0.5 text-[10px] font-medium rounded ${getPaymentColor(order.payment_status)}`}>
                                {order.payment_status}
                              </span>
                            </div>
                          </div>
                        </div>
                        {order.items_count > 0 && (
                          <div className="text-xs text-secondary-400 mb-1">
                            {order.items_count} item{order.items_count !== 1 ? "s" : ""}
                          </div>
                        )}
                        {order.status !== "voided" && (
                          <Button
                            size="sm"
                            variant="outline"
                            className="w-full mt-2"
                            onClick={() => handleRepeatOrder(order.id)}
                            disabled={repeatOrderLoading === order.id}
                          >
                            {repeatOrderLoading === order.id ? (
                              <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                            ) : (
                              <RotateCcw className="h-3.5 w-3.5 mr-1" />
                            )}
                            Repeat Order
                          </Button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Error display */}
          {error && (
            <div className="border-t border-secondary-200 bg-danger-50 px-4 py-2 flex items-center justify-between">
              <span className="text-sm text-danger-700">{error}</span>
              <button
                onClick={clearError}
                className="ml-2 rounded p-0.5 hover:bg-danger-100"
                aria-label="Dismiss error"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          )}
        </div>

        {/* Center: Menu grid */}
        <div className="flex-1 min-w-0 p-4">
          {selectedCustomer ? (
            <MenuGrid onAddToCart={handleAddToCart} />
          ) : (
            <div className="flex flex-col items-center justify-center h-full gap-3">
              <Phone className="h-16 w-16 text-secondary-300" />
              <p className="text-lg font-medium text-secondary-400">
                Search for a customer to start ordering
              </p>
              <p className="text-sm text-secondary-300">
                Enter a phone number in the left panel
              </p>
            </div>
          )}
        </div>

        {/* Right: Cart panel */}
        <div className="w-80 shrink-0 border-l border-secondary-200">
          <CartPanel />
        </div>
      </div>

      {/* Bottom: Live order ticker */}
      <OrderTicker orderType="call_center" />

      {/* Customer create/edit dialog */}
      <Dialog open={showCustomerDialog} onOpenChange={setShowCustomerDialog}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {isEditingCustomer ? "Edit Customer" : "Create New Customer"}
            </DialogTitle>
            <DialogDescription>
              {isEditingCustomer
                ? "Update customer information"
                : "Add a new customer to the system"}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            {/* Contact section */}
            <div>
              <h4 className="text-xs font-semibold text-secondary-500 uppercase tracking-wider mb-2">Contact</h4>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>Name *</Label>
                  <Input
                    value={customerForm.name}
                    onChange={(e) => setCustomerForm({ ...customerForm, name: e.target.value })}
                    placeholder="Customer name"
                  />
                </div>
                <div>
                  <Label>Phone *</Label>
                  <Input
                    type="tel"
                    value={customerForm.phone}
                    onChange={(e) => {
                      const digits = e.target.value.replace(/\D/g, "");
                      setCustomerForm({ ...customerForm, phone: digits });
                    }}
                    placeholder="03001234567"
                  />
                </div>
                <div>
                  <Label>Email</Label>
                  <Input
                    type="email"
                    value={customerForm.email}
                    onChange={(e) => setCustomerForm({ ...customerForm, email: e.target.value })}
                    placeholder="customer@example.com"
                  />
                </div>
                <div>
                  <Label>Alt Contact</Label>
                  <Input
                    type="tel"
                    value={customerForm.alt_contact}
                    onChange={(e) => {
                      const digits = e.target.value.replace(/\D/g, "");
                      setCustomerForm({ ...customerForm, alt_contact: digits });
                    }}
                    placeholder="Alternative phone"
                  />
                </div>
              </div>
            </div>

            {/* Primary address section */}
            <div>
              <h4 className="text-xs font-semibold text-secondary-500 uppercase tracking-wider mb-2">Primary Address</h4>
              <div className="grid grid-cols-3 gap-3">
                <div className="col-span-2">
                  <Label>Address</Label>
                  <Input
                    value={customerForm.default_address}
                    onChange={(e) =>
                      setCustomerForm({ ...customerForm, default_address: e.target.value })
                    }
                    placeholder="Street address"
                  />
                </div>
                <div>
                  <Label>City</Label>
                  <Input
                    value={customerForm.city}
                    onChange={(e) => setCustomerForm({ ...customerForm, city: e.target.value })}
                    placeholder="Lahore"
                  />
                </div>
              </div>
            </div>

            {/* Alternative address section */}
            <div>
              <h4 className="text-xs font-semibold text-secondary-500 uppercase tracking-wider mb-2">Alternative Address</h4>
              <div className="grid grid-cols-3 gap-3">
                <div className="col-span-2">
                  <Label>Address</Label>
                  <Input
                    value={customerForm.alt_address}
                    onChange={(e) =>
                      setCustomerForm({ ...customerForm, alt_address: e.target.value })
                    }
                    placeholder="Office / other address"
                  />
                </div>
                <div>
                  <Label>City</Label>
                  <Input
                    value={customerForm.alt_city}
                    onChange={(e) => setCustomerForm({ ...customerForm, alt_city: e.target.value })}
                    placeholder="City"
                  />
                </div>
              </div>
            </div>

            {/* Notes */}
            <div>
              <Label>Notes</Label>
              <Input
                value={customerForm.notes}
                onChange={(e) => setCustomerForm({ ...customerForm, notes: e.target.value })}
                placeholder="Preferences, allergies, special instructions"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCustomerDialog(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleSaveCustomer}
              disabled={!customerForm.name || !customerForm.phone || isCreating || isUpdating}
            >
              {(isCreating || isUpdating) && (
                <Loader2 className="h-4 w-4 mr-1 animate-spin" />
              )}
              {isEditingCustomer ? "Update" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default CallCenterPage;
