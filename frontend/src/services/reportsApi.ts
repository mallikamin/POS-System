import api from "@/lib/axios";
import type {
  SalesSummary,
  ItemPerformance,
  HourlyBreakdown,
  VoidReport,
  PaymentMethodReport,
  TableSizeReport,
  WaiterPerformanceReport,
} from "@/types/order";

/** `compare` adds the previous period's figures (D-55). */
export async function fetchSalesSummary(
  dateFrom: string,
  dateTo: string,
  compare = false
): Promise<SalesSummary> {
  const { data } = await api.get<SalesSummary>("/reports/sales-summary", {
    params: { date_from: dateFrom, date_to: dateTo, compare },
  });
  return data;
}

export async function fetchItemPerformance(
  dateFrom: string,
  dateTo: string,
  compare = false
): Promise<ItemPerformance> {
  const { data } = await api.get<ItemPerformance>("/reports/item-performance", {
    params: { date_from: dateFrom, date_to: dateTo, compare },
  });
  return data;
}

/** The whole range, summed by hour of day (D-53: it used to take one date). */
export async function fetchHourlyBreakdown(
  dateFrom: string,
  dateTo: string
): Promise<HourlyBreakdown> {
  const { data } = await api.get<HourlyBreakdown>("/reports/hourly-breakdown", {
    params: { date_from: dateFrom, date_to: dateTo },
  });
  return data;
}

export async function fetchTableSizeReport(
  dateFrom: string,
  dateTo: string
): Promise<TableSizeReport> {
  const { data } = await api.get<TableSizeReport>("/reports/table-size", {
    params: { date_from: dateFrom, date_to: dateTo },
  });
  return data;
}

export async function fetchVoidReport(
  dateFrom: string,
  dateTo: string
): Promise<VoidReport> {
  const { data } = await api.get<VoidReport>("/reports/void-report", {
    params: { date_from: dateFrom, date_to: dateTo },
  });
  return data;
}

export async function fetchPaymentMethodReport(
  dateFrom: string,
  dateTo: string
): Promise<PaymentMethodReport> {
  const { data } = await api.get<PaymentMethodReport>("/reports/payment-method", {
    params: { date_from: dateFrom, date_to: dateTo },
  });
  return data;
}

export async function fetchWaiterPerformance(
  dateFrom: string,
  dateTo: string
): Promise<WaiterPerformanceReport> {
  const { data } = await api.get<WaiterPerformanceReport>("/reports/waiter-performance", {
    params: { date_from: dateFrom, date_to: dateTo },
  });
  return data;
}

export async function downloadSalesCsv(
  dateFrom: string,
  dateTo: string
): Promise<void> {
  const response = await api.get("/reports/sales-summary/csv", {
    params: { date_from: dateFrom, date_to: dateTo },
    responseType: "blob",
  });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = url;
  link.download = `sales_${dateFrom}_${dateTo}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}
