/**
 * Operating expenses (Martin M10).
 *
 * 🔴 Every `*_minor` field is INTEGER MINOR UNITS, like the rest of this
 * codebase: 850 is AED 8.50. Format with `formatMoney`, never by dividing here.
 *
 * `amount_minor` is the WHOLE invoice, VAT included. `tax_minor` is the part of
 * it that is VAT, and `net_minor` is the difference, computed on the server so
 * three screens cannot each arrive at their own answer.
 */

export type ExpenseStatus = "draft" | "unpaid" | "paid";

export interface ExpenseCategory {
  id: string;
  name: string;
  sort_order: number;
  is_active: boolean;
  notes: string | null;
  expense_count: number;
}

export interface ExpenseAttachment {
  id: string;
  media_id: string;
  filename: string | null;
  content_type: string;
  size_bytes: number;
  /**
   * Path on the API, not a public URL. It needs a bearer token, so it is
   * fetched as a blob rather than dropped into an `<img>` or an `<a href>`.
   */
  url: string;
}

export interface Expense {
  id: string;
  expense_date: string;
  payee: string;
  description: string | null;
  reference_number: string | null;
  amount_minor: number;
  tax_minor: number;
  net_minor: number;
  status: ExpenseStatus;
  payment_method: string | null;
  paid_on: string | null;
  notes: string | null;
  category_id: string | null;
  category_name: string | null;
  location_id: string | null;
  location_name: string | null;
  recorded_by: string | null;
  recorded_by_name: string | null;
  created_at: string;
  attachments: ExpenseAttachment[];
}

export interface ExpenseCreate {
  expense_date: string;
  payee: string;
  amount_minor: number;
  tax_minor?: number;
  category_id?: string | null;
  location_id?: string | null;
  description?: string | null;
  reference_number?: string | null;
  status?: ExpenseStatus;
  payment_method?: string | null;
  paid_on?: string | null;
  notes?: string | null;
}

export type ExpenseUpdate = Partial<ExpenseCreate>;

export interface ExpenseCategoryTotal {
  category_id: string | null;
  category_name: string;
  total_minor: number;
  expense_count: number;
}

export interface ExpenseSummary {
  date_from: string | null;
  date_to: string | null;
  location_id: string | null;
  total_minor: number;
  tax_total_minor: number;
  net_minor: number;
  unpaid_minor: number;
  expense_count: number;
  by_category: ExpenseCategoryTotal[];
}
