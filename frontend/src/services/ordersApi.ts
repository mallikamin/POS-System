import api from "@/lib/axios";
import type {
  OrderCreateRequest,
  OrderResponse,
  PaginatedOrders,
} from "@/types/order";

export async function createOrder(body: OrderCreateRequest): Promise<OrderResponse> {
  const { data } = await api.post<OrderResponse>("/orders", body);
  return data;
}

export async function fetchOrders(params?: {
  status?: string;
  type?: string;
  active_only?: boolean;
  page?: number;
  page_size?: number;
}): Promise<PaginatedOrders> {
  const { data } = await api.get<PaginatedOrders>("/orders", { params });
  return data;
}

export async function fetchOrder(id: string): Promise<OrderResponse> {
  const { data } = await api.get<OrderResponse>(`/orders/${id}`);
  return data;
}

export async function transitionOrder(
  id: string,
  status: string
): Promise<OrderResponse> {
  const { data } = await api.patch<OrderResponse>(`/orders/${id}/status`, {
    status,
  });
  return data;
}

export async function voidOrder(
  id: string,
  reason: string,
  auth_token?: string
): Promise<OrderResponse> {
  const { data } = await api.post<OrderResponse>(`/orders/${id}/void`, {
    reason,
    auth_token,
  });
  return data;
}

export interface PaymentPreview {
  order_id: string;
  subtotal: number;
  cash_tax_rate_bps: number;
  cash_tax_amount: number;
  cash_total: number;
  card_tax_rate_bps: number;
  card_tax_amount: number;
  card_total: number;
}

export async function fetchPaymentPreview(orderId: string): Promise<PaymentPreview> {
  const { data } = await api.get<PaymentPreview>(`/orders/${orderId}/payment-preview`);
  return data;
}

export async function verifyPassword(password: string): Promise<{ auth_token: string }> {
  const { data } = await api.post<{ auth_token: string }>("/auth/verify-password", { password });
  return data;
}
