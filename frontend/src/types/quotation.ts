/**
 * Back-office quotations.
 *
 * 🔴 Money here is INTEGER MINOR UNITS as a NUMBER (sales-side convention,
 * like orders), not the decimal strings the procurement types use. Prices
 * INCLUDE VAT: `tax_minor` is the tax contained in `total_minor`, not an
 * amount added to it. `formatMoney` takes minor units directly.
 */

export type QuotationStatus =
  | "draft"
  | "sent"
  | "accepted"
  | "declined"
  | "converted";

/** What a human is shown. `expired` is derived from the date, never stored. */
export type QuotationDisplayStatus = QuotationStatus | "expired";

export interface QuotationItem {
  id: string;
  menu_item_id: string | null;
  name: string;
  description: string | null;
  quantity: number;
  unit_price_minor: number;
  line_total_minor: number;
  display_order: number;
}

export interface Quotation {
  id: string;
  quote_number: string;
  status: QuotationStatus;
  display_status: QuotationDisplayStatus;
  location_id: string | null;
  location_name: string | null;
  customer_id: string | null;
  customer_name: string;
  customer_phone: string | null;
  customer_email: string | null;
  customer_address: string | null;
  customer_trn: string | null;
  issue_date: string;
  valid_until: string;
  tax_rate_bps: number;
  subtotal_minor: number;
  discount_minor: number;
  tax_minor: number;
  total_minor: number;
  notes: string | null;
  terms: string | null;
  sent_at: string | null;
  sent_to_email: string | null;
  email_send_count: number;
  last_email_error: string | null;
  decided_at: string | null;
  decline_reason: string | null;
  converted_order_id: string | null;
  converted_at: string | null;
  created_at: string;
  items: QuotationItem[];
}

export interface QuotationLineCreate {
  menu_item_id?: string | null;
  name?: string | null;
  description?: string | null;
  quantity: number;
  unit_price_minor?: number | null;
}

export interface QuotationCreate {
  customer_name: string;
  lines: QuotationLineCreate[];
  location_id?: string | null;
  customer_phone?: string | null;
  customer_email?: string | null;
  customer_address?: string | null;
  customer_trn?: string | null;
  valid_until?: string | null;
  tax_rate_bps?: number | null;
  discount_minor?: number;
  notes?: string | null;
  terms?: string | null;
}

export interface QuotationUpdate {
  customer_name?: string;
  customer_phone?: string | null;
  customer_email?: string | null;
  customer_address?: string | null;
  customer_trn?: string | null;
  location_id?: string | null;
  valid_until?: string | null;
  tax_rate_bps?: number | null;
  discount_minor?: number | null;
  notes?: string | null;
  terms?: string | null;
  lines?: QuotationLineCreate[];
}

export interface QuotationSendRequest {
  to?: string | null;
  message?: string | null;
  skip_email?: boolean;
}

export interface QuotationSendResult {
  quotation: Quotation;
  email_sent: boolean;
  sent_to: string | null;
  error: string | null;
}

export interface QuotationConversion {
  quotation: Quotation;
  order_id: string;
  order_number: string;
}
