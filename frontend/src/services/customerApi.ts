import api from "@/lib/axios";
import type {
  CustomerCreate,
  CustomerResponse,
  CustomerUpdate,
  CustomerOrderHistoryItem,
} from "@/types/customer";

/**
 * Search customers by phone number (partial match)
 */
export async function searchCustomers(
  phone: string,
  limit: number = 10
): Promise<CustomerResponse[]> {
  const { data } = await api.get<CustomerResponse[]>("/customers/search", {
    params: { phone, limit },
  });
  return data;
}

/**
 * Get customer by ID
 */
export async function getCustomer(id: string): Promise<CustomerResponse> {
  const { data } = await api.get<CustomerResponse>(`/customers/${id}`);
  return data;
}

/**
 * Create a new customer
 */
export async function createCustomer(
  body: CustomerCreate
): Promise<CustomerResponse> {
  const { data } = await api.post<CustomerResponse>("/customers", body);
  return data;
}

/**
 * Update an existing customer
 */
export async function updateCustomer(
  id: string,
  body: CustomerUpdate
): Promise<CustomerResponse> {
  const { data } = await api.patch<CustomerResponse>(`/customers/${id}`, body);
  return data;
}

/**
 * Get customer order history
 */
export async function getCustomerOrderHistory(
  customerId: string,
  limit: number = 20
): Promise<CustomerOrderHistoryItem[]> {
  const { data } = await api.get<CustomerOrderHistoryItem[]>(
    `/customers/${customerId}/orders`,
    {
      params: { limit },
    }
  );
  return data;
}

