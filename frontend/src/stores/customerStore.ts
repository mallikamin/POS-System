import { create } from "zustand";
import type {
  CustomerResponse,
  CustomerCreate,
  CustomerUpdate,
  CustomerOrderHistoryItem,
} from "@/types/customer";
import * as customerApi from "@/services/customerApi";

interface CustomerState {
  selectedCustomer: CustomerResponse | null;
  searchResults: CustomerResponse[];
  orderHistory: CustomerOrderHistoryItem[];
  isLoading: boolean;
  isSearching: boolean;
  isCreating: boolean;
  isUpdating: boolean;
  isLoadingHistory: boolean;
  error: string | null;
}

interface CustomerActions {
  searchByPhone: (phone: string) => Promise<void>;
  selectCustomer: (customer: CustomerResponse | null) => void;
  createCustomer: (data: CustomerCreate) => Promise<CustomerResponse>;
  updateCustomer: (id: string, data: CustomerUpdate) => Promise<CustomerResponse>;
  loadOrderHistory: (customerId: string) => Promise<void>;
  setError: (message: string | null) => void;
  clearError: () => void;
  reset: () => void;
}

type CustomerStore = CustomerState & CustomerActions;

const initialState: CustomerState = {
  selectedCustomer: null,
  searchResults: [],
  orderHistory: [],
  isLoading: false,
  isSearching: false,
  isCreating: false,
  isUpdating: false,
  isLoadingHistory: false,
  error: null,
};

export const useCustomerStore = create<CustomerStore>()((set, get) => ({
  ...initialState,

  searchByPhone: async (phone: string) => {
    if (!phone || phone.trim().length < 3) {
      set({ searchResults: [], isSearching: false });
      return;
    }

    set({ isSearching: true, error: null });
    try {
      const results = await customerApi.searchCustomers(phone.trim(), 10);
      set({ searchResults: results, isSearching: false });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to search customers";
      set({ error: message, searchResults: [], isSearching: false });
    }
  },

  selectCustomer: (customer: CustomerResponse | null) => {
    set({ selectedCustomer: customer });
    if (customer) {
      get().loadOrderHistory(customer.id);
    } else {
      set({ orderHistory: [] });
    }
  },

  createCustomer: async (data: CustomerCreate) => {
    set({ isCreating: true, error: null });
    try {
      const customer = await customerApi.createCustomer(data);
      set({ isCreating: false, selectedCustomer: customer });
      // Auto-load order history for new customer
      await get().loadOrderHistory(customer.id);
      return customer;
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to create customer";
      set({ error: message, isCreating: false });
      throw err;
    }
  },

  updateCustomer: async (id: string, data: CustomerUpdate) => {
    set({ isUpdating: true, error: null });
    try {
      const customer = await customerApi.updateCustomer(id, data);
      set({
        isUpdating: false,
        selectedCustomer: customer,
        // Update in search results if present
        searchResults: get().searchResults.map((c) =>
          c.id === id ? customer : c
        ),
      });
      return customer;
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to update customer";
      set({ error: message, isUpdating: false });
      throw err;
    }
  },

  loadOrderHistory: async (customerId: string) => {
    set({ isLoadingHistory: true, error: null });
    try {
      const history = await customerApi.getCustomerOrderHistory(customerId, 20);
      set({ orderHistory: history, isLoadingHistory: false });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to load order history";
      set({ error: message, isLoadingHistory: false });
    }
  },

  setError: (message: string | null) => {
    set({ error: message });
  },

  clearError: () => {
    set({ error: null });
  },

  reset: () => {
    set(initialState);
  },
}));

