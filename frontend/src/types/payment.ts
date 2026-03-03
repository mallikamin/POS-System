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
