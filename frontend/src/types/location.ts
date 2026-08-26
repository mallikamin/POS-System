/**
 * Multi-location: sites, per-location stock, transfers, channels, profit.
 *
 * Mirrors `backend/app/schemas/location.py`. Money is in minor units
 * (integers) and percentages in basis points, exactly as the backend stores
 * them. Converting on the wire is how rounding bugs get in.
 */

export type LocationType = "production" | "delivery" | "retail";
export type InvoiceFormat = "a4_tax_invoice" | "thermal_ticket";
export type TransferStatus = "draft" | "in_transit" | "received" | "cancelled";

export interface Location {
  id: string;
  tenant_id: string;
  name: string;
  code: string;
  location_type: LocationType;
  legal_name: string | null;
  tax_registration_number: string | null;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  country: string | null;
  phone: string | null;
  email: string | null;
  invoice_format: InvoiceFormat;
  invoice_prefix: string;
  is_active: boolean;
  is_default: boolean;
  notes: string | null;
  created_at: string;
}

export interface LocationCreate {
  name: string;
  code: string;
  location_type: LocationType;
  legal_name?: string | null;
  tax_registration_number?: string | null;
  address_line1?: string | null;
  address_line2?: string | null;
  city?: string | null;
  country?: string | null;
  phone?: string | null;
  email?: string | null;
  invoice_format: InvoiceFormat;
  invoice_prefix?: string;
  is_active?: boolean;
  is_default?: boolean;
  notes?: string | null;
}

export type LocationUpdate = Partial<Omit<LocationCreate, "code">>;

export interface SalesChannel {
  id: string;
  tenant_id: string;
  name: string;
  code: string;
  /** Basis points. 1500 = 15.00%. */
  commission_bps: number;
  /** Flat per-order fee in minor units. */
  fixed_fee_minor: number;
  is_active: boolean;
  notes: string | null;
  created_at: string;
}

export interface SalesChannelCreate {
  name: string;
  code: string;
  commission_bps: number;
  fixed_fee_minor: number;
  is_active?: boolean;
  notes?: string | null;
}

export type SalesChannelUpdate = Partial<Omit<SalesChannelCreate, "code">>;

export interface LocationStockRow {
  location_id: string;
  location_name: string;
  ingredient_id: string;
  ingredient_name: string;
  unit: string;
  quantity: string;
  reorder_point: string;
  reorder_quantity: string;
  cost_per_unit: string;
  is_produced: boolean;
  is_low: boolean;
}

export interface TransferItem {
  id: string;
  ingredient_id: string;
  ingredient_name: string;
  quantity_sent: string;
  quantity_received: string | null;
  unit: string;
  unit_cost: string;
}

export interface Transfer {
  id: string;
  transfer_number: string;
  from_location_id: string;
  from_location_name: string;
  to_location_id: string;
  to_location_name: string;
  status: TransferStatus;
  notes: string | null;
  sent_at: string | null;
  received_at: string | null;
  created_at: string;
  items: TransferItem[];
}

export interface TransferCreate {
  from_location_id: string;
  to_location_id: string;
  lines: { ingredient_id: string; quantity: number }[];
  notes?: string | null;
}

export interface ProductionRunResult {
  reference_number: string;
  recipe_id: string;
  recipe_name: string;
  location_id: string;
  location_name: string;
  batches: string;
  produced_ingredient_id: string;
  produced_quantity: string;
  unit_cost: string;
  consumed: { ingredient_id: string; quantity: string }[];
}

export interface ProfitBucket {
  name: string;
  orders: number;
  revenue_minor: number;
  product_cost_minor: number;
  commission_minor: number;
  net_profit_minor: number;
  net_margin_pct: number;
}

export interface ProfitabilityReport {
  totals: ProfitBucket;
  by_channel: ProfitBucket[];
  by_location: ProfitBucket[];
}

export interface LocationOrderRow {
  id: string;
  order_number: string;
  order_type: string;
  status: string;
  payment_status: string;
  total_minor: number;
  channel_name: string | null;
  customer_name: string | null;
  created_at: string;
}

/** A4 VAT tax invoice. Mirrors `backend/app/schemas/tax_invoice.py`. */
export interface TaxInvoiceParty {
  name: string;
  trn: string | null;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  country: string | null;
  phone: string | null;
  email: string | null;
}

export interface TaxInvoiceLine {
  description: string;
  quantity: number;
  unit_price_net_minor: number;
  line_net_minor: number;
  vat_rate_bps: number;
  vat_amount_minor: number;
  line_gross_minor: number;
}

export interface TaxInvoiceData {
  document_title: string;
  invoice_number: string;
  order_number: string;
  issue_date: string;
  issued_at: string;
  supplier: TaxInvoiceParty;
  recipient: TaxInvoiceParty | null;
  currency: string;
  lines: TaxInvoiceLine[];
  subtotal_net_minor: number;
  discount_minor: number;
  vat_total_minor: number;
  total_gross_minor: number;
  vat_rate_bps: number;
  prices_include_vat: boolean;
  location_id: string | null;
  location_name: string | null;
  payment_status: string;
  notes: string | null;
}
