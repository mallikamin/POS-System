/**
 * Procurement API service: suppliers, catalogue, purchase orders, receiving.
 *
 * Everything is mounted under `/procurement` on the backend, so it all lives
 * in one module.
 */

import api from "@/lib/axios";
import type {
  GoodsReceiptRequest,
  GoodsReceiptResult,
  PurchaseOrder,
  PurchaseOrderCreate,
  PurchaseOrderSendRequest,
  PurchaseOrderSendResult,
  PurchaseOrderStatus,
  PurchaseOrderUpdate,
  ReceivingHistoryRow,
  ScanResult,
  SuggestionRequest,
  SuggestionResponse,
  Supplier,
  SupplierCreate,
  SupplierItemRow,
  SupplierItemUpsert,
  SupplierPurchaseRow,
  SupplierUpdate,
} from "@/types/procurement";

// ==========================================================================
// SUPPLIERS
// ==========================================================================

export async function fetchSuppliers(
  includeInactive = false,
): Promise<Supplier[]> {
  const { data } = await api.get<Supplier[]>("/procurement/suppliers", {
    params: { include_inactive: includeInactive },
  });
  return data;
}

export async function createSupplier(body: SupplierCreate): Promise<Supplier> {
  const { data } = await api.post<Supplier>("/procurement/suppliers", body);
  return data;
}

export async function updateSupplier(
  id: string,
  body: SupplierUpdate,
): Promise<Supplier> {
  const { data } = await api.patch<Supplier>(
    `/procurement/suppliers/${id}`,
    body,
  );
  return data;
}

/** Deactivate, never delete: the purchase history hangs off the record. */
export async function deactivateSupplier(id: string): Promise<Supplier> {
  const { data } = await api.delete<Supplier>(`/procurement/suppliers/${id}`);
  return data;
}

export async function fetchSupplierHistory(
  id: string,
): Promise<SupplierPurchaseRow[]> {
  const { data } = await api.get<SupplierPurchaseRow[]>(
    `/procurement/suppliers/${id}/history`,
  );
  return data;
}

// ==========================================================================
// CATALOGUE
// ==========================================================================

export async function fetchCatalogue(params?: {
  supplierId?: string;
  ingredientId?: string;
  includeInactive?: boolean;
}): Promise<SupplierItemRow[]> {
  const { data } = await api.get<SupplierItemRow[]>("/procurement/catalogue", {
    params: {
      supplier_id: params?.supplierId,
      ingredient_id: params?.ingredientId,
      include_inactive: params?.includeInactive ?? false,
    },
  });
  return data;
}

export async function upsertCatalogueItem(
  supplierId: string,
  body: SupplierItemUpsert,
): Promise<SupplierItemRow> {
  const { data } = await api.post<SupplierItemRow>(
    `/procurement/suppliers/${supplierId}/items`,
    body,
  );
  return data;
}

export async function removeCatalogueItem(itemId: string): Promise<void> {
  await api.delete(`/procurement/catalogue/${itemId}`);
}

// ==========================================================================
// PURCHASE ORDERS
// ==========================================================================

export async function fetchPurchaseOrders(params?: {
  status?: PurchaseOrderStatus;
  supplierId?: string;
  locationId?: string;
}): Promise<PurchaseOrder[]> {
  const { data } = await api.get<PurchaseOrder[]>(
    "/procurement/purchase-orders",
    {
      params: {
        status: params?.status,
        supplier_id: params?.supplierId,
        location_id: params?.locationId,
      },
    },
  );
  return data;
}

export async function fetchPurchaseOrder(id: string): Promise<PurchaseOrder> {
  const { data } = await api.get<PurchaseOrder>(
    `/procurement/purchase-orders/${id}`,
  );
  return data;
}

export async function createPurchaseOrder(
  body: PurchaseOrderCreate,
): Promise<PurchaseOrder> {
  const { data } = await api.post<PurchaseOrder>(
    "/procurement/purchase-orders",
    body,
  );
  return data;
}

export async function updatePurchaseOrder(
  id: string,
  body: PurchaseOrderUpdate,
): Promise<PurchaseOrder> {
  const { data } = await api.patch<PurchaseOrder>(
    `/procurement/purchase-orders/${id}`,
    body,
  );
  return data;
}

export async function sendPurchaseOrder(
  id: string,
  body: PurchaseOrderSendRequest = {},
): Promise<PurchaseOrderSendResult> {
  const { data } = await api.post<PurchaseOrderSendResult>(
    `/procurement/purchase-orders/${id}/send`,
    body,
  );
  return data;
}

export async function receiveGoods(
  id: string,
  body: GoodsReceiptRequest,
): Promise<GoodsReceiptResult> {
  const { data } = await api.post<GoodsReceiptResult>(
    `/procurement/purchase-orders/${id}/receive`,
    body,
  );
  return data;
}

export async function cancelPurchaseOrder(
  id: string,
): Promise<PurchaseOrder> {
  const { data } = await api.post<PurchaseOrder>(
    `/procurement/purchase-orders/${id}/cancel`,
  );
  return data;
}

/**
 * The printable PO, fetched as HTML rather than linked to directly.
 *
 * A plain `<a href>` would not carry the JWT, so the document endpoint would
 * reject it. Fetching through the configured axios instance and opening the
 * result in a new window keeps the auth header where it belongs.
 */
export async function fetchPurchaseOrderDocument(
  id: string,
): Promise<string> {
  const { data } = await api.get<string>(
    `/procurement/purchase-orders/${id}/document`,
    { responseType: "text" },
  );
  return data;
}

// ==========================================================================
// ORDERING SUGGESTION
// ==========================================================================

/**
 * What to buy for a production target.
 *
 * The quantities come back computed from the recipe tree, current stock and
 * open orders. `include_advice` adds an AI review of that finished plan; if
 * the AI is unavailable the plan is returned in full anyway and
 * `advice_error` says why the commentary is missing.
 */
export async function suggestOrder(
  body: SuggestionRequest,
): Promise<SuggestionResponse> {
  const { data } = await api.post<SuggestionResponse>(
    "/procurement/suggest-order",
    body,
  );
  return data;
}

// ==========================================================================
// OCR GOODS RECEIVING
// ==========================================================================

/**
 * Read a delivery note into PROPOSED receipt lines. Changes no stock.
 *
 * The caller reviews and corrects the result, then confirms it through
 * `receiveGoods` -- the same endpoint manual receiving uses.
 */
export async function scanDeliveryNote(
  purchaseOrderId: string,
  file: File,
): Promise<ScanResult> {
  const form = new FormData();
  form.append("file", file);
  // The JSON default Content-Type is stripped for FormData in the axios
  // request interceptor, so the browser sets multipart with its own boundary.
  const { data } = await api.post<ScanResult>(
    `/procurement/purchase-orders/${purchaseOrderId}/scan-delivery-note`,
    form,
  );
  return data;
}

export async function fetchReceivingHistory(
  locationId?: string,
): Promise<ReceivingHistoryRow[]> {
  const { data } = await api.get<ReceivingHistoryRow[]>(
    "/procurement/receiving-history",
    { params: { location_id: locationId } },
  );
  return data;
}
