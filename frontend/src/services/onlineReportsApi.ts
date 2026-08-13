import api from "@/lib/axios";

/**
 * OI-58: reports specific to online-ordering tenants. Daily Sales has no
 * function here on purpose -- it reuses `reportsApi.fetchSalesSummary` /
 * `downloadSalesCsv`, which OI-58a already fixed to expose
 * `online_revenue`/`online_orders`.
 */

export interface PrepaidVsCodReport {
  date_from: string;
  date_to: string;
  prepaid_revenue: number;
  prepaid_orders: number;
  cod_revenue: number;
  cod_orders: number;
  /** OI-81: tips, split by the same prepaid/COD rule as the revenue. */
  prepaid_tips: number;
  cod_tips: number;
}

export interface RejectedOrderEntry {
  order_number: string;
  customer_name: string | null;
  rejected_at: string;
  rejection_reason: string;
  total: number;
}

export interface RejectedOrdersReport {
  date_from: string;
  date_to: string;
  count: number;
  total_value: number;
  orders: RejectedOrderEntry[];
}

export interface StripeReconciliationRow {
  order_number: string;
  db_payment_status: string;
  db_captured_amount: number;
  stripe_status: string | null;
  stripe_amount_received: number | null;
  matches: boolean;
  error: string | null;
}

export interface StripeReconciliationReport {
  date_from: string;
  date_to: string;
  checked: number;
  mismatches: number;
  rows: StripeReconciliationRow[];
}

function downloadBlob(data: BlobPart, filename: string): void {
  const url = window.URL.createObjectURL(new Blob([data]));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

export async function fetchPrepaidVsCod(
  dateFrom: string,
  dateTo: string,
): Promise<PrepaidVsCodReport> {
  const { data } = await api.get<PrepaidVsCodReport>(
    "/reports/online/prepaid-vs-cod",
    { params: { date_from: dateFrom, date_to: dateTo } },
  );
  return data;
}

export async function downloadPrepaidVsCodCsv(
  dateFrom: string,
  dateTo: string,
): Promise<void> {
  const response = await api.get("/reports/online/prepaid-vs-cod/csv", {
    params: { date_from: dateFrom, date_to: dateTo },
    responseType: "blob",
  });
  downloadBlob(response.data, `prepaid_vs_cod_${dateFrom}_${dateTo}.csv`);
}

export async function fetchRejectedOrders(
  dateFrom: string,
  dateTo: string,
): Promise<RejectedOrdersReport> {
  const { data } = await api.get<RejectedOrdersReport>(
    "/reports/online/rejected-orders",
    { params: { date_from: dateFrom, date_to: dateTo } },
  );
  return data;
}

export async function downloadRejectedOrdersCsv(
  dateFrom: string,
  dateTo: string,
): Promise<void> {
  const response = await api.get("/reports/online/rejected-orders/csv", {
    params: { date_from: dateFrom, date_to: dateTo },
    responseType: "blob",
  });
  downloadBlob(response.data, `rejected_orders_${dateFrom}_${dateTo}.csv`);
}

export async function fetchStripeReconciliation(
  dateFrom: string,
  dateTo: string,
): Promise<StripeReconciliationReport> {
  const { data } = await api.get<StripeReconciliationReport>(
    "/reports/online/stripe-reconciliation",
    { params: { date_from: dateFrom, date_to: dateTo } },
  );
  return data;
}

export async function downloadStripeReconciliationCsv(
  dateFrom: string,
  dateTo: string,
): Promise<void> {
  const response = await api.get("/reports/online/stripe-reconciliation/csv", {
    params: { date_from: dateFrom, date_to: dateTo },
    responseType: "blob",
  });
  downloadBlob(response.data, `stripe_reconciliation_${dateFrom}_${dateTo}.csv`);
}
