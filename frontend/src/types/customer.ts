/* Customer types matching backend schemas/customer.py */

export interface CustomerCreate {
  name: string;
  phone: string; // digits only, 7-20 chars
  email?: string | null;
  alt_contact?: string | null;
  default_address?: string | null;
  city?: string | null;
  alt_address?: string | null;
  alt_city?: string | null;
  notes?: string | null;
}

export interface CustomerUpdate {
  name?: string | null;
  phone?: string | null;
  email?: string | null;
  alt_contact?: string | null;
  default_address?: string | null;
  city?: string | null;
  alt_address?: string | null;
  alt_city?: string | null;
  notes?: string | null;
  risk_flag?: string | null;
}

export interface CustomerResponse {
  id: string;
  name: string;
  phone: string;
  email?: string | null;
  alt_contact?: string | null;
  default_address?: string | null;
  city?: string | null;
  alt_address?: string | null;
  alt_city?: string | null;
  notes?: string | null;
  order_count: number;
  total_spent: number; // paisa
  last_order_at?: string | null;
  risk_flag: string; // "normal" | "high" | "blocked"
  created_at: string;
  updated_at?: string | null;
}

export interface CustomerOrderHistoryItem {
  id: string;
  order_number: string;
  order_type: string;
  status: string;
  payment_status: string;
  total: number; // paisa
  items_count: number;
  created_at: string;
}
