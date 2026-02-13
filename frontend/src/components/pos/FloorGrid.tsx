import { useEffect } from "react";
import { Loader2 } from "lucide-react";
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

  useEffect(() => {
    loadFloors();
  }, [loadFloors]);

  const activeFloor = floors.find((f) => f.id === selectedFloorId);
  const activeTables = activeFloor?.tables.filter((t) => t.is_active) ?? [];

  function handleTableClick(tableId: string) {
    setSelectedTable(tableId);
    onTableSelect(tableId);
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
