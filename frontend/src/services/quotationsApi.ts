/** Back-office quotations: raise, send, decide, convert. */

import api from "@/lib/axios";
import type {
  Quotation,
  QuotationConversion,
  QuotationCreate,
  QuotationDisplayStatus,
  QuotationSendRequest,
  QuotationSendResult,
  QuotationUpdate,
} from "@/types/quotation";

export async function fetchQuotations(
  status?: QuotationDisplayStatus,
): Promise<Quotation[]> {
  const { data } = await api.get<Quotation[]>("/quotations", {
    params: { status },
  });
  return data;
}

export async function fetchQuotation(id: string): Promise<Quotation> {
  const { data } = await api.get<Quotation>(`/quotations/${id}`);
  return data;
}

export async function createQuotation(
  body: QuotationCreate,
): Promise<Quotation> {
  const { data } = await api.post<Quotation>("/quotations", body);
  return data;
}

export async function updateQuotation(
  id: string,
  body: QuotationUpdate,
): Promise<Quotation> {
  const { data } = await api.patch<Quotation>(`/quotations/${id}`, body);
  return data;
}

export async function sendQuotation(
  id: string,
  body: QuotationSendRequest = {},
): Promise<QuotationSendResult> {
  const { data } = await api.post<QuotationSendResult>(
    `/quotations/${id}/send`,
    body,
  );
  return data;
}

export async function decideQuotation(
  id: string,
  accepted: boolean,
  reason?: string | null,
): Promise<Quotation> {
  const { data } = await api.post<Quotation>(`/quotations/${id}/decide`, {
    accepted,
    reason: reason ?? null,
  });
  return data;
}

export async function convertQuotation(
  id: string,
): Promise<QuotationConversion> {
  const { data } = await api.post<QuotationConversion>(
    `/quotations/${id}/convert`,
  );
  return data;
}

/**
 * The printable quotation. Fetched rather than linked to directly, because a
 * plain `<a href>` would not carry the JWT and the endpoint would reject it.
 */
export async function fetchQuotationDocument(id: string): Promise<string> {
  const { data } = await api.get<string>(`/quotations/${id}/document`, {
    responseType: "text",
  });
  return data;
}
