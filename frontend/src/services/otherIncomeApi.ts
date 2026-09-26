/** Other income API (Danny's D-63). Mounted under `/other-income`. */

import api from "@/lib/axios";
import type {
  IncomeCategory,
  IncomeMethod,
  OpeningBalance,
  OtherIncome,
  OtherIncomeInput,
} from "@/types/otherIncome";

export async function fetchIncomeCategories(): Promise<IncomeCategory[]> {
  const { data } = await api.get<IncomeCategory[]>("/other-income/categories");
  return data;
}

export async function createIncomeCategory(name: string): Promise<IncomeCategory> {
  const { data } = await api.post<IncomeCategory>("/other-income/categories", { name });
  return data;
}

export async function fetchOtherIncome(params: {
  date_from?: string;
  date_to?: string;
  method?: IncomeMethod;
}): Promise<OtherIncome[]> {
  const { data } = await api.get<OtherIncome[]>("/other-income", { params });
  return data;
}

export async function createOtherIncome(body: OtherIncomeInput): Promise<OtherIncome> {
  const { data } = await api.post<OtherIncome>("/other-income", body);
  return data;
}

export async function updateOtherIncome(
  id: string,
  body: Partial<OtherIncomeInput>,
): Promise<OtherIncome> {
  const { data } = await api.patch<OtherIncome>(`/other-income/${id}`, body);
  return data;
}

export async function deleteOtherIncome(id: string): Promise<void> {
  await api.delete(`/other-income/${id}`);
}

/** D-62. Null when no opening balance has been recorded. */
export async function fetchOpeningBalance(): Promise<OpeningBalance | null> {
  const { data } = await api.get<OpeningBalance | null>("/opening-balance");
  return data;
}

export async function saveOpeningBalance(body: {
  as_of: string;
  cash_minor: number;
  notes?: string | null;
}): Promise<OpeningBalance> {
  const { data } = await api.put<OpeningBalance>("/opening-balance", body);
  return data;
}
