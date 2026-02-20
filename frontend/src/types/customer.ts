/* Customer types matching backend schemas/customer.py */

export interface CustomerCreate {
  name: string;
  phone: string; // digits only, 7-20 chars
  email?: string | null;
  default_address?: string | null;
  notes?: string | null;
}

export interface CustomerUpdate {
  name?: string | null;
  phone?: string | null;
  email?: string | null;
  default_address?: string | null;
  notes?: string | null;
}

export interface CustomerResponse {
  id: string;
  name: string;
  phone: string;
  email?: string | null;
  default_address?: string | null;
  notes?: string | null;
  order_count: number;
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
  created_at: string;
}

