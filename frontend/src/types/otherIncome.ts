/** Other income: money in that is not a sale (Danny's D-63). Money in minor units. */

export type IncomeMethod = "cash" | "bank";

export interface IncomeCategory {
  id: string;
  name: string;
  sort_order: number;
  is_active: boolean;
  income_count: number;
}

export interface OtherIncome {
  id: string;
  received_on: string;
  payer: string;
  amount_minor: number;
  method: IncomeMethod;
  category_id: string | null;
  category_name: string | null;
  location_id: string | null;
  location_name: string | null;
  description: string | null;
  reference_number: string | null;
  notes: string | null;
  recorded_by_name: string | null;
  created_at: string;
}

/** D-62: cash in hand at the START of `as_of`. Cash only. */
export interface OpeningBalance {
  as_of: string;
  cash_minor: number;
  notes: string | null;
  recorded_by_name: string | null;
  updated_at: string;
}

export interface OtherIncomeInput {
  received_on: string;
  payer: string;
  amount_minor: number;
  method: IncomeMethod;
  category_id: string | null;
  description: string | null;
  reference_number: string | null;
}
