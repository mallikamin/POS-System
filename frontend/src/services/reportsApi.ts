import api from "@/lib/axios";
import type {
  SalesSummary,
  ItemPerformance,
  HourlyBreakdown,
  VoidReport,
  PaymentMethodReport,
  WaiterPerformanceReport,
} from "@/types/order";

export async function fetchSalesSummary(
  dateFrom: string,
  dateTo: string
): Promise<SalesSummary> {
  const { data } = await api.get<SalesSummary>("/reports/sales-summary", {
    params: { date_from: dateFrom, date_to: dateTo },
  });
  return data;
}

export async function fetchItemPerformance(
  dateFrom: string,
  dateTo: string
): Promise<ItemPerformance> {
  const { data } = await api.get<ItemPerformance>("/reports/item-performance", {
    params: { date_from: dateFrom, date_to: dateTo },
  });
  return data;
}

export async function fetchHourlyBreakdown(
  date: string
): Promise<HourlyBreakdown> {
  const { data } = await api.get<HourlyBreakdown>("/reports/hourly-breakdown", {
    params: { date },
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
