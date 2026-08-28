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

/**
 * Decimal fields on these interfaces are JSON **numbers**, not strings.
 * The backend serialises them through `Num` (`schemas/location.py`), which was
 * introduced precisely so the wire matches what this client already assumed.
 * Typing one of them as `string` is what took `/admin/ingredients` down (F14)
 * and `/admin/transfers` down (F51, `n.trim is not a function`). If you add a
 * field here, check the backend annotation before you type it.
 */
export interface LocationStockRow {
  location_id: string;
  location_name: string;
  ingredient_id: string;
  ingredient_name: string;
  unit: string;
  quantity: number;
  reorder_point: number;
  reorder_quantity: number;
  cost_per_unit: number;
  is_produced: boolean;
  is_low: boolean;
  ingredient_image_url: string | null;
}

/**
 * One line of the stock ledger: what changed, by how much, who did it and why.
 *
 * `location_name` and `performed_by_name` are nullable and both nulls carry
 * meaning. No location means the movement predates the multi-site model. No
 * performer means the system did it rather than a person, which is what
 * consumption from an online order looks like. Render those as words, not as an
 * empty cell that reads like missing data.
 */
export interface StockMovementRow {
  id: string;
  ingredient_id: string;
  ingredient_name: string;
  location_id: string | null;
  location_name: string | null;
  transaction_type: string;
  quantity: number;
  unit: string;
  balance_after: number;
  unit_cost: number;
  total_cost: number;
  transaction_date: string;
  performed_by_name: string | null;
  notes: string | null;
  reference_number: string | null;
  order_id: string | null;
}

export interface TransferItem {
  id: string;
  ingredient_id: string;
  ingredient_name: string;
  quantity_sent: number;
  quantity_received: number | null;
  unit: string;
  unit_cost: number;
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
  batches: number;
  produced_ingredient_id: string;
  produced_quantity: number;
  unit_cost: number;
  consumed: { ingredient_id: string; quantity: number }[];
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
