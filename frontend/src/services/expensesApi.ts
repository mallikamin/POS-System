/**
 * Operating expenses API (Martin M10).
 *
 * Everything is mounted under `/expenses` on the backend, categories and
 * attachments included.
 */

import api from "@/lib/axios";
import type {
  Expense,
  ExpenseAttachment,
  ExpenseCategory,
  ExpenseCreate,
  ExpenseSummary,
  ExpenseUpdate,
} from "@/types/expense";

// ==========================================================================
// CATEGORIES
// ==========================================================================

export async function fetchExpenseCategories(
  includeInactive = false,
): Promise<ExpenseCategory[]> {
  const { data } = await api.get<ExpenseCategory[]>("/expenses/categories", {
    params: { include_inactive: includeInactive },
  });
  return data;
}

export async function createExpenseCategory(
  name: string,
): Promise<ExpenseCategory> {
  const { data } = await api.post<ExpenseCategory>("/expenses/categories", {
    name,
  });
  return data;
}

export async function renameExpenseCategory(
  id: string,
  name: string,
): Promise<ExpenseCategory> {
  const { data } = await api.patch<ExpenseCategory>(
    `/expenses/categories/${id}`,
    { name },
  );
  return data;
}

export async function deleteExpenseCategory(id: string): Promise<void> {
  await api.delete(`/expenses/categories/${id}`);
}

// ==========================================================================
// EXPENSES
// ==========================================================================

export async function fetchExpenses(params?: {
  date_from?: string;
  date_to?: string;
  category_id?: string;
  location_id?: string;
  status?: string;
  search?: string;
  limit?: number;
}): Promise<Expense[]> {
  const { data } = await api.get<Expense[]>("/expenses", { params });
  return data;
}

export async function fetchExpense(id: string): Promise<Expense> {
  const { data } = await api.get<Expense>(`/expenses/${id}`);
  return data;
}

export async function createExpense(body: ExpenseCreate): Promise<Expense> {
  const { data } = await api.post<Expense>("/expenses", body);
  return data;
}

export async function updateExpense(
  id: string,
  body: ExpenseUpdate,
): Promise<Expense> {
  const { data } = await api.patch<Expense>(`/expenses/${id}`, body);
  return data;
}

export async function deleteExpense(id: string): Promise<void> {
  await api.delete(`/expenses/${id}`);
}

export async function fetchExpenseSummary(params?: {
  date_from?: string;
  date_to?: string;
  location_id?: string;
}): Promise<ExpenseSummary> {
  const { data } = await api.get<ExpenseSummary>("/expenses/summary", {
    params,
  });
  return data;
}

// ==========================================================================
// ATTACHMENTS
// ==========================================================================

export async function uploadExpenseAttachment(
  expenseId: string,
  file: File,
): Promise<ExpenseAttachment> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post<ExpenseAttachment>(
    `/expenses/${expenseId}/attachments`,
    form,
    // Deliberately NOT setting Content-Type: the browser has to add the
    // multipart boundary itself, and naming the header here strips it.
  );
  return data;
}

export async function deleteExpenseAttachment(
  expenseId: string,
  attachmentId: string,
): Promise<void> {
  await api.delete(`/expenses/${expenseId}/attachments/${attachmentId}`);
}

/**
 * Open an attachment in a new tab.
 *
 * 🔴 The attachment route needs a bearer token, so the URL cannot simply be put
 * in an `<a href>` -- the browser would send no Authorization header and get a
 * 401. It is fetched as a blob through the same axios instance that already
 * carries the token, then handed to the tab as an object URL.
 *
 * The object URL is revoked on a timer rather than immediately: revoking it in
 * the same tick races the new tab's own load and shows a blank page.
 */
export async function openExpenseAttachment(
  attachment: ExpenseAttachment,
): Promise<void> {
  const { data } = await api.get<Blob>(
    attachment.url.replace(/^\/api\/v1/, ""),
    { responseType: "blob" },
  );
  const blob = new Blob([data], { type: attachment.content_type });
  const objectUrl = URL.createObjectURL(blob);
  window.open(objectUrl, "_blank", "noopener,noreferrer");
  setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
}
