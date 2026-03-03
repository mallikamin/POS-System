import api from "@/lib/axios";
import type {
  CashDrawerCloseRequest,
  CashDrawerOpenRequest,
  CashDrawerSessionResponse,
  PaymentCreateRequest,
  PaymentMethodResponse,
  PaymentSummary,
  RefundCreateRequest,
  SessionPaymentCreateRequest,
  SessionPaymentPreview,
  SessionPaymentSummary,
  SessionSplitPaymentCreateRequest,
  SplitPaymentCreateRequest,
} from "@/types/payment";

export async function fetchPaymentMethods(): Promise<PaymentMethodResponse[]> {
  const { data } = await api.get<PaymentMethodResponse[]>("/payments/methods");
  return data;
}

export async function fetchOrderPaymentSummary(orderId: string): Promise<PaymentSummary> {
  const { data } = await api.get<PaymentSummary>(`/payments/orders/${orderId}/summary`);
  return data;
}

export async function createPayment(body: PaymentCreateRequest): Promise<PaymentSummary> {
  const { data } = await api.post<PaymentSummary>("/payments", body);
  return data;
}

export async function splitPayment(body: SplitPaymentCreateRequest): Promise<PaymentSummary> {
  const { data } = await api.post<PaymentSummary>("/payments/split", body);
  return data;
}

export async function refundPayment(body: RefundCreateRequest): Promise<PaymentSummary> {
  const { data } = await api.post<PaymentSummary>("/payments/refund", body);
  return data;
}

export async function fetchDrawerSession(): Promise<CashDrawerSessionResponse | null> {
  const { data } = await api.get<CashDrawerSessionResponse | null>("/payments/drawer/session");
  return data;
}

export async function openDrawer(body: CashDrawerOpenRequest): Promise<CashDrawerSessionResponse> {
  const { data } = await api.post<CashDrawerSessionResponse>("/payments/drawer/open", body);
  return data;
}

export async function closeDrawer(body: CashDrawerCloseRequest): Promise<CashDrawerSessionResponse> {
  const { data } = await api.post<CashDrawerSessionResponse>("/payments/drawer/close", body);
  return data;
}

// Session Payment APIs (P2)

export async function fetchSessionPaymentPreview(sessionId: string): Promise<SessionPaymentPreview> {
  const { data } = await api.get<SessionPaymentPreview>(`/payments/table-sessions/${sessionId}/payment-preview`);
  return data;
}

export async function fetchSessionPaymentSummary(sessionId: string): Promise<SessionPaymentSummary> {
  const { data } = await api.get<SessionPaymentSummary>(`/payments/table-sessions/${sessionId}/summary`);
  return data;
}

export async function createSessionPayment(sessionId: string, body: SessionPaymentCreateRequest): Promise<SessionPaymentSummary> {
  const { data } = await api.post<SessionPaymentSummary>(`/payments/table-sessions/${sessionId}/pay`, body);
  return data;
}

export async function splitSessionPayment(sessionId: string, body: SessionSplitPaymentCreateRequest): Promise<SessionPaymentSummary> {
  const { data } = await api.post<SessionPaymentSummary>(`/payments/table-sessions/${sessionId}/split`, body);
  return data;
}
