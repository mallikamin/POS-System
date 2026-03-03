import api from "@/lib/axios";

export interface DiscountType {
  id: string;
  tenant_id: string;
  code: string;
  name: string;
  kind: "percent" | "fixed";
  value: number;
  is_active: boolean;
  created_at: string;
}

export interface OrderDiscount {
  id: string;
  order_id?: string;
  table_session_id?: string;
  discount_type_id?: string;
  label: string;
  source_type: string;
  amount: number;
  percent_bps: number;
  note?: string;
  applied_by: string;
  created_at: string;
}

export interface DiscountBreakdown {
  order_id: string;
  discounts: OrderDiscount[];
  total_discount: number;
}

// Discount type CRUD
export async function fetchDiscountTypes(active_only = false): Promise<DiscountType[]> {
  const { data } = await api.get<DiscountType[]>("/discounts/types", {
    params: { active_only },
  });
  return data;
}

export async function createDiscountType(body: {
  code: string;
  name: string;
  kind: "percent" | "fixed";
  value: number;
  is_active?: boolean;
}): Promise<DiscountType> {
  const { data } = await api.post<DiscountType>("/discounts/types", body);
  return data;
}

export async function updateDiscountType(
  id: string,
  body: Partial<{ name: string; kind: string; value: number; is_active: boolean }>
): Promise<DiscountType> {
  const { data } = await api.patch<DiscountType>(`/discounts/types/${id}`, body);
  return data;
}

export async function deleteDiscountType(id: string): Promise<void> {
  await api.delete(`/discounts/types/${id}`);
}

// Apply / remove discounts
export async function applyDiscount(body: {
  order_id?: string;
  table_session_id?: string;
  discount_type_id?: string;
  label?: string;
  source_type?: string;
  amount?: number;
  note?: string;
}): Promise<OrderDiscount> {
  const { data } = await api.post<OrderDiscount>("/discounts/apply", body);
  return data;
}

export async function removeDiscount(discountId: string): Promise<void> {
  await api.delete(`/discounts/${discountId}`);
}

export async function fetchOrderDiscounts(orderId: string): Promise<DiscountBreakdown> {
  const { data } = await api.get<DiscountBreakdown>(`/discounts/orders/${orderId}`);
  return data;
}
