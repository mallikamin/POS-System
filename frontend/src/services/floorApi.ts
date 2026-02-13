import api from "@/lib/axios";
import type {
  FloorWithTables,
  FloorStatusBoard,
  FloorCreate,
  FloorUpdate,
  TableResponse,
  TableCreate,
  TableUpdate,
  BulkTablePositionUpdate,
} from "@/types/floor";

// ---------------------------------------------------------------------------
// Status Board (POS dine-in)
// ---------------------------------------------------------------------------

export async function fetchStatusBoard(): Promise<FloorStatusBoard> {
  const { data } = await api.get<FloorStatusBoard>("/floors/status-board");
  return data;
}

// ---------------------------------------------------------------------------
// Floors
// ---------------------------------------------------------------------------

export async function fetchFloors(activeOnly = false): Promise<FloorWithTables[]> {
  const { data } = await api.get<FloorWithTables[]>("/floors", {
    params: { active_only: activeOnly },
  });
  return data;
}

export async function fetchFloor(id: string): Promise<FloorWithTables> {
  const { data } = await api.get<FloorWithTables>(`/floors/${id}`);
  return data;
}

export async function createFloor(body: FloorCreate): Promise<FloorWithTables> {
  const { data } = await api.post<FloorWithTables>("/floors", body);
  return data;
}

export async function updateFloor(
  id: string,
  body: FloorUpdate
): Promise<FloorWithTables> {
  const { data } = await api.patch<FloorWithTables>(`/floors/${id}`, body);
  return data;
}

export async function deleteFloor(id: string): Promise<void> {
  await api.delete(`/floors/${id}`);
}

// ---------------------------------------------------------------------------
// Tables
// ---------------------------------------------------------------------------

export async function fetchTables(
  floorId: string,
  activeOnly = false
): Promise<TableResponse[]> {
  const { data } = await api.get<TableResponse[]>(`/floors/${floorId}/tables`, {
    params: { active_only: activeOnly },
  });
  return data;
}

export async function createTable(body: TableCreate): Promise<TableResponse> {
  const { data } = await api.post<TableResponse>("/floors/tables", body);
  return data;
}

export async function updateTable(
  id: string,
  body: TableUpdate
): Promise<TableResponse> {
  const { data } = await api.patch<TableResponse>(`/floors/tables/${id}`, body);
  return data;
}

export async function deleteTable(id: string): Promise<void> {
  await api.delete(`/floors/tables/${id}`);
}

export async function bulkUpdatePositions(
  body: BulkTablePositionUpdate
): Promise<TableResponse[]> {
  const { data } = await api.put<TableResponse[]>(
    "/floors/tables/positions",
    body
  );
  return data;
}

export async function updateTableStatus(
  id: string,
  status: string
): Promise<TableResponse> {
  const { data } = await api.patch<TableResponse>(
    `/floors/tables/${id}/status`,
    { status }
  );
  return data;
}
