import api from "@/lib/axios";
import type {
  CashDrawerAttachment,
  CashDrawerCloseRequest,
  CashDrawerOpenRequest,
  CashDrawerSessionResponse,
  CashDrawerSummary,
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

export async function fetchDrawerSummary(): Promise<CashDrawerSummary | null> {
  const { data } = await api.get<CashDrawerSummary | null>("/payments/drawer/summary");
  return data;
}

/** Pin a photo or PDF to a drawer session at close (D-78). */
export async function uploadDrawerAttachment(
  sessionId: string,
  file: File,
): Promise<CashDrawerAttachment> {
  const form = new FormData();
  form.append("file", file);
  // No Content-Type header: the browser must add the multipart boundary.
  const { data } = await api.post<CashDrawerAttachment>(
    `/payments/drawer/${sessionId}/attachments`,
    form,
  );
  return data;
}

/** Open a drawer attachment in a new tab. The route needs the auth header, so
 *  it is fetched as a blob, as expense attachments are. */
export async function openDrawerAttachment(url: string): Promise<void> {
  const { data } = await api.get<Blob>(url.replace(/^\/api\/v1/, ""), {
    responseType: "blob",
  });
  const objectUrl = URL.createObjectURL(data);
  window.open(objectUrl, "_blank", "noopener,noreferrer");
  setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
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
