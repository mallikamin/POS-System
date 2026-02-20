import { useEffect, useState } from "react";
import { Loader2, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useFloorStore } from "@/stores/floorStore";
import { TableCard } from "./TableCard";

interface FloorGridProps {
  onTableSelect: (tableId: string) => void;
}

export function FloorGrid({ onTableSelect }: FloorGridProps) {
  const floors = useFloorStore((s) => s.floors);
  const selectedFloorId = useFloorStore((s) => s.selectedFloorId);
  const selectedTableId = useFloorStore((s) => s.selectedTableId);
  const isLoading = useFloorStore((s) => s.isLoading);
  const error = useFloorStore((s) => s.error);
  const loadFloors = useFloorStore((s) => s.loadFloors);
  const setSelectedFloor = useFloorStore((s) => s.setSelectedFloor);
  const setSelectedTable = useFloorStore((s) => s.setSelectedTable);
  const setTableStatus = useFloorStore((s) => s.setTableStatus);
  const [statusError, setStatusError] = useState<string | null>(null);

  useEffect(() => {
    loadFloors();
  }, [loadFloors]);

  const activeFloor = floors.find((f) => f.id === selectedFloorId);
  const activeTables = activeFloor?.tables.filter((t) => t.is_active) ?? [];
  const selectedTable = activeTables.find((t) => t.id === selectedTableId) ?? null;

  function handleTableClick(tableId: string) {
    setSelectedTable(tableId);
    onTableSelect(tableId);
  }

  async function handleSetTableStatus(tableId: string, status: "available" | "reserved" | "occupied" | "cleaning") {
    setStatusError(null);
    try {
      await setTableStatus(tableId, status);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to update table status";
      setStatusError(message);
      // Auto-dismiss after 5 seconds
      setTimeout(() => setStatusError(null), 5000);
    }
  }

  if (isLoading && floors.length === 0) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin text-primary-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center gap-2 py-8 px-4">
        <p className="text-sm text-danger-600">{error}</p>
        <button
          onClick={() => loadFloors()}
          className="text-sm text-primary-600 underline"
        >
          Retry
        </button>
      </div>
    );
  }

  if (floors.length === 0) {
    return (
      <div className="flex items-center justify-center py-8 px-4">
        <p className="text-sm text-secondary-400">No floors configured</p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* Floor tabs */}
      {floors.length > 1 && (
        <div className="flex gap-1.5 px-3 pt-3 pb-2">
          {floors.map((floor) => (
            <button
              key={floor.id}
              onClick={() => setSelectedFloor(floor.id)}
              className={cn(
                "rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
                floor.id === selectedFloorId
                  ? "bg-primary-600 text-white"
                  : "bg-secondary-100 text-secondary-600 hover:bg-secondary-200"
              )}
            >
              {floor.name}
            </button>
          ))}
        </div>
      )}

      {/* Tables grid */}
      <div className="flex-1 overflow-y-auto px-3 pb-3">
        {activeTables.length === 0 ? (
          <div className="flex items-center justify-center py-8">
            <p className="text-sm text-secondary-400">No tables on this floor</p>
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-2 pt-1">
            {activeTables.map((table) => (
              <TableCard
                key={table.id}
                table={table}
                isSelected={table.id === selectedTableId}
                onClick={() => handleTableClick(table.id)}
              />
            ))}
          </div>
        )}

        {selectedTable && (
          <div className="mt-3 rounded-lg border border-secondary-200 bg-white p-2">
            <p className="mb-2 text-xs font-medium text-secondary-600">
              {selectedTable.label || `Table ${selectedTable.number}`}
            </p>
            {statusError && (
              <div className="mb-2 flex items-center justify-between rounded-md bg-danger-50 px-2 py-1.5 text-xs text-danger-700">
                <span>{statusError}</span>
                <button
                  onClick={() => setStatusError(null)}
                  className="ml-2 rounded p-0.5 hover:bg-danger-100"
                  aria-label="Dismiss error"
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            )}
            <div className="flex gap-2">
              <button
                onClick={() =>
                  handleSetTableStatus(
                    selectedTable.id,
                    selectedTable.status === "reserved" ? "available" : "reserved"
                  )
                }
                className="rounded-md bg-warning-100 px-2.5 py-1.5 text-xs font-medium text-warning-800 hover:bg-warning-200"
              >
                {selectedTable.status === "reserved" ? "Unreserve" : "Reserve"}
              </button>
              <button
                onClick={() => handleSetTableStatus(selectedTable.id, "available")}
                className="rounded-md bg-success-100 px-2.5 py-1.5 text-xs font-medium text-success-800 hover:bg-success-200"
              >
                Mark Available
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="flex items-center justify-center gap-4 border-t border-secondary-200 px-3 py-2">
        <LegendDot color="bg-success-500" label="Open" />
        <LegendDot color="bg-danger-500" label="Busy" />
        <LegendDot color="bg-warning-500" label="Reserved" />
        <LegendDot color="bg-secondary-400" label="Cleaning" />
      </div>
    </div>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1">
      <span className={cn("h-2 w-2 rounded-full", color)} />
      <span className="text-[10px] text-secondary-500">{label}</span>
    </span>
  );
}
