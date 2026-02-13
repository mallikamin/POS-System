/* ==========================================================================
   Floor plan domain types (matches backend schemas/floor.py)
   ========================================================================== */

export type TableStatus = "available" | "occupied" | "reserved" | "cleaning";
export type TableShape = "square" | "round" | "rectangle";

export interface TableResponse {
  id: string;
  floor_id: string;
  number: number;
  label: string | null;
  capacity: number;
  pos_x: number;
  pos_y: number;
  width: number;
  height: number;
  rotation: number;
  shape: TableShape;
  status: TableStatus;
  is_active: boolean;
}

export interface FloorResponse {
  id: string;
  name: string;
  display_order: number;
  is_active: boolean;
}

export interface FloorWithTables extends FloorResponse {
  tables: TableResponse[];
}

export interface FloorStatusBoard {
  floors: FloorWithTables[];
}

// ---------------------------------------------------------------------------
// Create / Update types
// ---------------------------------------------------------------------------

export interface FloorCreate {
  name: string;
  display_order?: number;
  is_active?: boolean;
}

export interface FloorUpdate {
  name?: string;
  display_order?: number;
  is_active?: boolean;
}

export interface TableCreate {
  floor_id: string;
  number: number;
  label?: string | null;
  capacity?: number;
  pos_x?: number;
  pos_y?: number;
  width?: number;
  height?: number;
  rotation?: number;
  shape?: TableShape;
  is_active?: boolean;
}

export interface TableUpdate {
  number?: number;
  label?: string | null;
  capacity?: number;
  pos_x?: number;
  pos_y?: number;
  width?: number;
  height?: number;
  rotation?: number;
  shape?: TableShape;
  status?: TableStatus;
  is_active?: boolean;
}

export interface TablePositionUpdate {
  id: string;
  pos_x: number;
  pos_y: number;
  width: number;
  height: number;
  rotation: number;
}

export interface BulkTablePositionUpdate {
  tables: TablePositionUpdate[];
}
