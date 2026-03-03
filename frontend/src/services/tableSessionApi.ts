import api from "@/lib/axios";

export interface TableSessionOrderSummary {
  id: string;
  order_number: string;
  status: string;
  payment_status: string;
  subtotal: number;
  tax_amount: number;
  discount_amount: number;
  total: number;
  created_at: string;
}

export interface TableSessionResponse {
  id: string;
  tenant_id: string;
  table_id: string;
  table_number?: number;
  table_label?: string;
  status: string;
  opened_by: string;
  opened_at: string;
  closed_by?: string;
  closed_at?: string;
  notes?: string;
  order_count: number;
  created_at: string;
}

export interface TableSessionDetail extends TableSessionResponse {
  orders: TableSessionOrderSummary[];
}

export interface TableSessionBillSummary {
  session_id: string;
  table_id: string;
  table_number?: number;
  table_label?: string;
  status: string;
  subtotal: number;
  tax_amount: number;
  discount_amount: number;
  total: number;
  paid_amount: number;
  due_amount: number;
  order_count: number;
  orders: TableSessionOrderSummary[];
}

export async function openTableSession(table_id: string, notes?: string): Promise<TableSessionResponse> {
  const { data } = await api.post<TableSessionResponse>("/table-sessions/open", { table_id, notes });
  return data;
}

export async function getTableSession(sessionId: string): Promise<TableSessionDetail> {
  const { data } = await api.get<TableSessionDetail>(`/table-sessions/${sessionId}`);
  return data;
}

export async function getActiveSessionForTable(tableId: string): Promise<TableSessionDetail | null> {
  const { data } = await api.get<TableSessionDetail | null>(`/table-sessions/table/${tableId}/active`);
  return data;
}

export async function closeTableSession(sessionId: string, notes?: string): Promise<TableSessionResponse> {
  const { data } = await api.post<TableSessionResponse>(`/table-sessions/${sessionId}/close`, { notes });
  return data;
}

export async function getSessionBillSummary(sessionId: string): Promise<TableSessionBillSummary> {
  const { data } = await api.get<TableSessionBillSummary>(`/table-sessions/${sessionId}/bill-summary`);
  return data;
}
