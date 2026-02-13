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
  reason?: string
): Promise<OrderResponse> {
  const { data } = await api.post<OrderResponse>(`/orders/${id}/void`, {
    reason,
  });
  return data;
}
