/**
 * Multi-location API service: sites, stock, production, transfers, channels.
 *
 * Every path here is mounted under `/locations` on the backend, including the
 * stock and transfer sub-resources, so they all live in one module.
 */

import api from "@/lib/axios";
import type {
  Location,
  LocationCreate,
  LocationOrderRow,
  LocationStockRow,
  StockMovementRow,
  LocationUpdate,
  ProductionRunResult,
  ProfitabilityReport,
  SalesChannel,
  SalesChannelCreate,
  SalesChannelUpdate,
  TaxInvoiceData,
  Transfer,
  TransferCreate,
} from "@/types/location";

// ==========================================================================
// LOCATIONS
// ==========================================================================

export async function fetchLocations(
  includeInactive = false,
): Promise<Location[]> {
  const { data } = await api.get<Location[]>("/locations", {
    params: { include_inactive: includeInactive },
  });
  return data;
}

export async function createLocation(body: LocationCreate): Promise<Location> {
  const { data } = await api.post<Location>("/locations", body);
  return data;
}

export async function updateLocation(
  id: string,
  body: LocationUpdate,
): Promise<Location> {
  const { data } = await api.patch<Location>(`/locations/${id}`, body);
  return data;
}

// ==========================================================================
// SALES CHANNELS
// ==========================================================================

export async function fetchChannels(
  includeInactive = false,
): Promise<SalesChannel[]> {
  const { data } = await api.get<SalesChannel[]>("/locations/channels/all", {
    params: { include_inactive: includeInactive },
  });
  return data;
}

export async function createChannel(
  body: SalesChannelCreate,
): Promise<SalesChannel> {
  const { data } = await api.post<SalesChannel>("/locations/channels", body);
  return data;
}

export async function updateChannel(
  id: string,
  body: SalesChannelUpdate,
): Promise<SalesChannel> {
  const { data } = await api.patch<SalesChannel>(
    `/locations/channels/${id}`,
    body,
  );
  return data;
}

// ==========================================================================
// STOCK
// ==========================================================================

export async function fetchStockPosition(params?: {
  location_id?: string;
  low_only?: boolean;
}): Promise<LocationStockRow[]> {
  const { data } = await api.get<LocationStockRow[]>(
    "/locations/stock/position",
    { params },
  );
  return data;
}

/**
 * The movement ledger for an item: why the stock figure is what it is.
 *
 * Scope it to BOTH ingredient and location for a per-row history. The
 * `balance_after` column is that location's running balance, so mixing two
 * sites' movements into one list produces a balance column that jumps around
 * and means nothing.
 */
export async function fetchStockMovements(params: {
  ingredient_id?: string;
  location_id?: string;
  limit?: number;
  offset?: number;
}): Promise<StockMovementRow[]> {
  const { data } = await api.get<StockMovementRow[]>(
    "/locations/stock/movements",
    { params },
  );
  return data;
}

export async function adjustStock(body: {
  ingredient_id: string;
  location_id?: string;
  quantity_delta: number;
  reason: string;
}): Promise<LocationStockRow> {
  const { data } = await api.post<LocationStockRow>(
    "/locations/stock/adjust",
    body,
  );
  return data;
}

export async function setReorderLevel(body: {
  ingredient_id: string;
  location_id: string;
  reorder_point: number;
  reorder_quantity: number;
}): Promise<LocationStockRow> {
  const { data } = await api.post<LocationStockRow>(
    "/locations/stock/reorder-level",
    body,
  );
  return data;
}

// ==========================================================================
// PRODUCTION
// ==========================================================================

export async function runProduction(body: {
  recipe_id: string;
  batches: number;
  location_id?: string;
  reference_number?: string;
}): Promise<ProductionRunResult> {
  const { data } = await api.post<ProductionRunResult>(
    "/locations/production/run",
    body,
  );
  return data;
}

// ==========================================================================
// TRANSFERS
// ==========================================================================

export async function fetchTransfers(params?: {
  status?: string;
  location_id?: string;
}): Promise<Transfer[]> {
  const { data } = await api.get<Transfer[]>("/locations/transfers/all", {
    params,
  });
  return data;
}

export async function createTransfer(body: TransferCreate): Promise<Transfer> {
  const { data } = await api.post<Transfer>("/locations/transfers", body);
  return data;
}

export async function sendTransfer(id: string): Promise<Transfer> {
  const { data } = await api.post<Transfer>(`/locations/transfers/${id}/send`);
  return data;
}

export async function receiveTransfer(
  id: string,
  lines?: { item_id: string; quantity_received: number }[],
): Promise<Transfer> {
  const { data } = await api.post<Transfer>(
    `/locations/transfers/${id}/receive`,
    { lines: lines ?? [] },
  );
  return data;
}

export async function cancelTransfer(id: string): Promise<Transfer> {
  const { data } = await api.post<Transfer>(
    `/locations/transfers/${id}/cancel`,
  );
  return data;
}

// ==========================================================================
// PROFITABILITY
// ==========================================================================

export async function fetchProfitability(params?: {
  date_from?: string;
  date_to?: string;
}): Promise<ProfitabilityReport> {
  const { data } = await api.get<ProfitabilityReport>(
    "/locations/reports/profitability",
    { params },
  );
  return data;
}

// ==========================================================================
// TAX INVOICES
// ==========================================================================

export async function fetchLocationOrders(
  locationId: string,
  limit = 100,
): Promise<LocationOrderRow[]> {
  const { data } = await api.get<LocationOrderRow[]>(
    `/locations/${locationId}/orders`,
    { params: { limit } },
  );
  return data;
}

export async function fetchTaxInvoice(orderId: string): Promise<TaxInvoiceData> {
  const { data } = await api.get<TaxInvoiceData>(
    `/receipts/orders/${orderId}/tax-invoice`,
  );
  return data;
}
