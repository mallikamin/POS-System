export type PaymentMethodCode = "cash" | "card" | "mobile_wallet" | "bank_transfer";

export interface PaymentMethodResponse {
  id: string;
  code: PaymentMethodCode;
  display_name: string;
  is_active: boolean;
  requires_reference: boolean;
  sort_order: number;
}

export interface PaymentResponse {
  id: string;
  order_id: string;
  method_id: string;
  parent_payment_id?: string;
  kind: "payment" | "refund";
  status: "pending" | "completed" | "failed";
  amount: number;
  tendered_amount?: number;
  change_amount: number;
  reference?: string;
  note?: string;
  processed_by: string;
  processed_at: string;
  created_at: string;
  method?: PaymentMethodResponse;
}

export interface PaymentSummary {
  order_id: string;
  order_number: string;
  order_total: number;
  paid_amount: number;
  refunded_amount: number;
  due_amount: number;
  payment_status: "unpaid" | "partial" | "paid" | "refunded";
  payments: PaymentResponse[];
}

export interface PaymentCreateRequest {
  order_id: string;
  method_code: PaymentMethodCode;
  amount: number;
  tendered_amount?: number;
  reference?: string;
  note?: string;
}

export interface SplitPaymentAllocation {
  method_code: PaymentMethodCode;
  amount: number;
  tendered_amount?: number;
  reference?: string;
}

export interface SplitPaymentCreateRequest {
  order_id: string;
  allocations: SplitPaymentAllocation[];
  note?: string;
}

export interface RefundCreateRequest {
  payment_id: string;
  amount: number;
  note?: string;
}

export interface CashDrawerSessionResponse {
  id: string;
  status: "open" | "closed";
  opened_by: string;
  opened_at: string;
  opening_float: number;
  closed_by?: string;
  closed_at?: string;
  closing_balance_expected?: number;
  closing_balance_counted?: number;
  note?: string;
}

/** The open drawer and what should be in it now (D-73). Same figure the
 *  Z-Report shows for this drawer (D-68). */
export interface CashDrawerSummary {
  id: string;
  opened_by: string;
  opened_by_name: string | null;
  opened_at: string;
  opening_float: number;
  cash_taken: number;
  cash_refunds: number;
  cash_paid_out: number;
  other_cash_in: number;
  expected_in_drawer: number;
}

export interface CashDrawerOpenRequest {
  opening_float: number;
  note?: string;
}

export interface CashDrawerCloseRequest {
  closing_balance_counted: number;
  note?: string;
}

// Session Payment types (P2)

export interface SessionPaymentOrderDue {
  order_id: string;
  order_number: string;
  order_total: number;
  paid_amount: number;
  due_amount: number;
  payment_status: string;
}

export interface SessionPaymentSummary {
  session_id: string;
  table_id: string;
  table_label?: string;
  order_count: number;
  subtotal: number;
  tax_amount: number;
  discount_amount: number;
  total: number;
  paid_amount: number;
  due_amount: number;
  payment_status: string;
  orders: SessionPaymentOrderDue[];
}

export interface SessionPaymentPreview {
  session_id: string;
  subtotal: number;
  cash_tax_rate_bps: number;
  cash_tax_amount: number;
  cash_total: number;
  card_tax_rate_bps: number;
  card_tax_amount: number;
  card_total: number;
}

export interface SessionPaymentCreateRequest {
  method_code: PaymentMethodCode;
  amount: number;
  tendered_amount?: number;
  reference?: string;
  note?: string;
}

export interface SessionSplitPaymentCreateRequest {
  allocations: SplitPaymentAllocation[];
  note?: string;
}
