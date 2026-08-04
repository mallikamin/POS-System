/**
 * Client for the POS public storefront API.
 *
 * Three calls, and only three:
 *   GET  /public/{tenant}/menu                 what can be ordered right now
 *   POST /public/{tenant}/orders               place it
 *   GET  /public/{tenant}/orders/{id}/status   has the shop accepted it yet
 *
 * ⚠️ THE BROWSER NEVER SENDS A PRICE.
 *
 * `PublicOrderItemRequest` on the server sets `extra="forbid"`, so posting a
 * `unit_price` is a 422 rather than a silently ignored field. That is by design
 * and this module must not "helpfully" start sending totals. Every amount on
 * the order is recomputed server-side from its own menu rows, including the
 * delivery fee, which is why we send `delivery_area_id` and never a fee.
 *
 * Prices held in the basket are for DISPLAY ONLY. If the browser and the server
 * disagree, the server is right and the customer sees the server's total on the
 * confirmation screen.
 */

import type { Pence, ServiceType } from "../types";

const DEFAULT_API_BASE = "https://eats.sitaratech.info/api/v1";
const DEFAULT_TENANT_SLUG = "chick-shack";

/** No trailing slash, so path concatenation below stays predictable. */
export const API_BASE = (import.meta.env.VITE_API_URL ?? DEFAULT_API_BASE).replace(
  /\/+$/,
  "",
);

export const TENANT_SLUG = import.meta.env.VITE_TENANT_SLUG ?? DEFAULT_TENANT_SLUG;

// ---------------------------------------------------------------------------
// Wire types — these mirror `backend/app/schemas/public_order.py` exactly.
// snake_case is deliberate: it is what the server sends, and renaming it here
// would hide the correspondence. The adapter converts to storefront types.
// ---------------------------------------------------------------------------

export interface ApiModifier {
  id: string;
  name: string;
  price_adjustment: Pence;
}

export interface ApiModifierGroup {
  id: string;
  name: string;
  required: boolean;
  min_selections: number;
  /** 0 means unlimited, per the menu engine's convention. */
  max_selections: number;
  modifiers: ApiModifier[];
}

export interface ApiMenuItem {
  id: string;
  name: string;
  description: string | null;
  price: Pence;
  image_url: string | null;
  modifier_groups: ApiModifierGroup[];
}

export interface ApiCategory {
  id: string;
  name: string;
  description: string | null;
  display_order: number;
  items: ApiMenuItem[];
}

export interface ApiMenuResponse {
  currency: string;
  categories: ApiCategory[];
  /** The shop has paused online ordering during a rush (Imran, 2026-08-04). */
  ordering_paused?: boolean;
  ordering_paused_message?: string | null;
}

export interface ApiOrderLineRequest {
  menu_item_id: string;
  quantity: number;
  modifier_ids: string[];
  notes?: string | null;
}

export interface ApiOrderRequest {
  service_type: ServiceType;
  customer_name: string;
  customer_phone: string;
  customer_email?: string | null;
  items: ApiOrderLineRequest[];
  notes?: string | null;
  /** The area CODE, e.g. "arrochar". The server looks the fee up from it. */
  delivery_area_id?: string | null;
  delivery_address?: string | null;
  /**
   * The customer's chosen payment method, sent so the "order received" email
   * -- which goes out immediately, before Stripe Checkout even starts -- can
   * say "prepaid" for a card order instead of the misleading default
   * "payable on delivery". Never used server-side to decide whether money
   * actually moves; that is Stripe's own state, checked separately.
   */
  payment_method?: "cash" | "card";
}

export interface ApiOrderLine {
  name: string;
  quantity: number;
  unit_price: Pence;
  total: Pence;
  modifiers: string[];
}

export interface ApiOrderResponse {
  id: string;
  order_number: string;
  status: string;
  payment_status: string;
  service_type: string;
  customer_name: string;
  lines: ApiOrderLine[];
  subtotal: Pence;
  tax_amount: Pence;
  service_fee: Pence;
  delivery_fee: Pence;
  total: Pence;
  currency: string;
  eta_minutes: number | null;
  created_at: string;
}

export interface ApiOrderStatus {
  order_number: string;
  status: string;
  accepted: boolean;
  rejected: boolean;
  rejection_reason: string | null;
  eta_minutes: number | null;

  /** The rest of the journey, so the page can say "on its way" rather than
   *  sitting on "confirmed" until the food physically arrives. */
  service_type: string;
  ready: boolean;
  completed: boolean;
  paid: boolean;
}

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------

/**
 * A failed API call.
 *
 * `customerMessage` is the only string that should ever be rendered. The server
 * returns 409 with a sentence written for the customer ("We do not deliver to
 * that area.", "Minimum order for delivery is 5.00") and those are worth
 * showing verbatim. Everything else gets a generic line, because a 422 body or
 * a stack trace is noise to someone trying to buy chicken.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly customerMessage: string;

  constructor(message: string, status: number, customerMessage: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.customerMessage = customerMessage;
  }
}

const GENERIC_MESSAGE =
  "Something went wrong placing your order. Please try again, or give us a ring.";
const OFFLINE_MESSAGE =
  "We could not reach the shop. Check your connection and try again.";

/**
 * FastAPI's `detail` is a string for `HTTPException` but a list of objects for
 * a 422 validation failure. Only the string form is fit to show a customer.
 */
function detailString(body: unknown): string | null {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) return detail;
  }
  return null;
}

async function request<T>(
  path: string,
  init?: RequestInit,
  timeoutMs = 12_000,
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
  } catch {
    // Network failure, CORS rejection or our own timeout. Indistinguishable
    // from the browser, and the customer's next move is the same either way.
    throw new ApiError(`Request to ${path} failed`, 0, OFFLINE_MESSAGE);
  } finally {
    clearTimeout(timer);
  }

  if (!response.ok) {
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      // A non-JSON error body is not worth failing over; the status is enough.
    }
    const detail = detailString(body);
    // 409 is the server telling the customer something actionable about their
    // own basket. Every other status is our problem, not theirs.
    const customerMessage =
      response.status === 409 && detail ? detail : GENERIC_MESSAGE;
    throw new ApiError(
      `${response.status} from ${path}${detail ? `: ${detail}` : ""}`,
      response.status,
      customerMessage,
    );
  }

  return (await response.json()) as T;
}

// ---------------------------------------------------------------------------
// Calls
// ---------------------------------------------------------------------------

export function fetchMenu(): Promise<ApiMenuResponse> {
  return request<ApiMenuResponse>(`/public/${TENANT_SLUG}/menu`);
}

export function placeOrder(order: ApiOrderRequest): Promise<ApiOrderResponse> {
  return request<ApiOrderResponse>(`/public/${TENANT_SLUG}/orders`, {
    method: "POST",
    body: JSON.stringify(order),
  });
}

/**
 * Authorise the card for an order that has ALREADY been placed.
 *
 * Deliberately a second call, never part of placing the order. The order is
 * real before any payment page is shown, so a customer who abandons Stripe
 * leaves an ordinary unpaid order the shop can still see and chase — rather
 * than nothing at all, which is what would happen if payment came first.
 *
 * The money is only *held* here. It is taken when the shop accepts and released
 * if the shop rejects, which is the client's own rule: charge once accepted.
 */
export function createCheckoutSession(
  orderId: string,
): Promise<{ checkout_url: string; session_id: string }> {
  return request<{ checkout_url: string; session_id: string }>(
    `/public/${TENANT_SLUG}/orders/${orderId}/checkout-session`,
    { method: "POST" },
  );
}

export function fetchOrderStatus(orderId: string): Promise<ApiOrderStatus> {
  return request<ApiOrderStatus>(
    `/public/${TENANT_SLUG}/orders/${orderId}/status`,
    undefined,
    // Shorter than the default: this runs on a poll loop, and a request that
    // outlives its own interval would stack up behind the next one.
    8_000,
  );
}
