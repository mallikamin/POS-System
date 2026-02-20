import { useState, useEffect, useRef, useCallback } from "react";
import {
  Plus,
  Save,
  Trash2,
  LayoutGrid,
  Loader2,
  Circle,
  Square,
  RectangleHorizontal,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import type {
  FloorWithTables,
  TableResponse,
  TableShape,
  TableCreate,
} from "@/types/floor";
import * as floorApi from "@/services/floorApi";

type DragState = {
  tableId: string;
  offsetX: number;
  offsetY: number;
} | null;

function FloorEditorPage() {
  const [floors, setFloors] = useState<FloorWithTables[]>([]);
  const [activeFloorId, setActiveFloorId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedTableId, setSelectedTableId] = useState<string | null>(null);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showFloorDialog, setShowFloorDialog] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [dragState, setDragState] = useState<DragState>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // New table form
  const [newTableNumber, setNewTableNumber] = useState("");
  const [newTableCapacity, setNewTableCapacity] = useState("4");
  const [newTableShape, setNewTableShape] = useState<TableShape>("square");
  const [newTableLabel, setNewTableLabel] = useState("");

  // New floor form
  const [newFloorName, setNewFloorName] = useState("");

  const canvasRef = useRef<HTMLDivElement>(null);

  function showSuccess(msg: string) {
    setSuccessMessage(msg);
    setTimeout(() => setSuccessMessage(null), 3000);
  }

  const activeFloor = floors.find((f) => f.id === activeFloorId);
  const selectedTable = activeFloor?.tables.find((t) => t.id === selectedTableId);

  // Load floors
  useEffect(() => {
    loadFloors();
  }, []);

  async function loadFloors() {
    setIsLoading(true);
    setError(null);
    try {
      const data = await floorApi.fetchFloors();
      setFloors(data);
      if (data.length > 0 && !activeFloorId) {
        setActiveFloorId(data[0]!.id);
      }
    } catch {
      setError("Failed to load floors");
    } finally {
      setIsLoading(false);
    }
  }

  // Drag handlers
  const handleMouseDown = useCallback(
    (e: React.MouseEvent, table: TableResponse) => {
      e.preventDefault();
      const rect = canvasRef.current?.getBoundingClientRect();
      if (!rect) return;
      setDragState({
        tableId: table.id,
        offsetX: e.clientX - rect.left - table.pos_x,
        offsetY: e.clientY - rect.top - table.pos_y,
      });
      setSelectedTableId(table.id);
    },
    []
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!dragState || !canvasRef.current) return;
      const rect = canvasRef.current.getBoundingClientRect();
      const newX = Math.max(0, e.clientX - rect.left - dragState.offsetX);
      const newY = Math.max(0, e.clientY - rect.top - dragState.offsetY);

      setFloors((prev) =>
        prev.map((floor) =>
          floor.id === activeFloorId
            ? {
                ...floor,
                tables: floor.tables.map((t) =>
                  t.id === dragState.tableId
                    ? { ...t, pos_x: Math.round(newX), pos_y: Math.round(newY) }
                    : t
                ),
              }
            : floor
        )
      );
      setHasChanges(true);
    },
    [dragState, activeFloorId]
  );

  const handleMouseUp = useCallback(() => {
    setDragState(null);
  }, []);

  // Save positions
  async function handleSave() {
    if (!activeFloor) return;
    setIsSaving(true);
    try {
      await floorApi.bulkUpdatePositions({
        tables: activeFloor.tables.map((t) => ({
          id: t.id,
          pos_x: t.pos_x,
          pos_y: t.pos_y,
          width: t.width,
          height: t.height,
          rotation: t.rotation,
        })),
      });
      setHasChanges(false);
      showSuccess("Layout saved");
    } catch {
      setError("Failed to save positions");
    } finally {
      setIsSaving(false);
    }
  }

  // Add table
  async function handleAddTable() {
    if (!activeFloorId || !newTableNumber) return;
    try {
      const body: TableCreate = {
        floor_id: activeFloorId,
        number: parseInt(newTableNumber, 10),
        capacity: parseInt(newTableCapacity, 10) || 4,
        shape: newTableShape,
        label: newTableLabel || undefined,
        pos_x: 100,
        pos_y: 100,
        width: newTableShape === "rectangle" ? 140 : 90,
        height: 90,
      };
      const table = await floorApi.createTable(body);
      setFloors((prev) =>
        prev.map((f) =>
          f.id === activeFloorId
            ? { ...f, tables: [...f.tables, table] }
            : f
        )
      );
      setShowAddDialog(false);
      setNewTableNumber("");
      setNewTableCapacity("4");
      setNewTableShape("square");
      setNewTableLabel("");
      showSuccess("Table added");
    } catch {
      setError("Failed to create table");
    }
  }

  // Delete table
  async function handleDeleteTable() {
    if (!selectedTableId) return;
    try {
      await floorApi.deleteTable(selectedTableId);
      setFloors((prev) =>
        prev.map((f) =>
          f.id === activeFloorId
            ? { ...f, tables: f.tables.filter((t) => t.id !== selectedTableId) }
            : f
        )
      );
      setSelectedTableId(null);
      setShowDeleteConfirm(false);
      showSuccess("Table deleted");
    } catch {
      setError("Failed to delete table");
    }
  }

  // Update selected table property
  async function handleUpdateTableProp(field: string, value: number | string) {
    if (!selectedTableId) return;
    try {
      const updated = await floorApi.updateTable(selectedTableId, {
        [field]: value,
      });
      setFloors((prev) =>
        prev.map((f) =>
          f.id === activeFloorId
            ? {
                ...f,
                tables: f.tables.map((t) =>
                  t.id === selectedTableId ? updated : t
                ),
              }
            : f
        )
      );
      // Mark changes for properties that affect layout (pos, size, rotation)
      if (field === "pos_x" || field === "pos_y" || field === "width" || field === "height" || field === "rotation") {
        setHasChanges(true);
      }
    } catch {
      setError("Failed to update table");
    }
  }

  // Add floor
  async function handleAddFloor() {
    if (!newFloorName) return;
    try {
      const floor = await floorApi.createFloor({
        name: newFloorName,
        display_order: floors.length,
      });
      setFloors((prev) => [...prev, floor]);
      setActiveFloorId(floor.id);
      setShowFloorDialog(false);
      setNewFloorName("");
      showSuccess("Floor created");
    } catch {
      setError("Failed to create floor");
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* Toolbar */}
      <div className="flex items-center justify-between border-b border-secondary-200 bg-white px-4 py-2.5">
        <div className="flex items-center gap-3">
          <LayoutGrid className="h-5 w-5 text-primary-600" />
          <h1 className="font-semibold text-secondary-900">Floor Editor</h1>

          {/* Floor tabs */}
          <div className="flex items-center gap-1.5 ml-4">
            {floors.map((floor) => (
              <button
                key={floor.id}
                onClick={() => {
                  setActiveFloorId(floor.id);
                  setSelectedTableId(null);
                }}
                className={cn(
                  "rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
                  floor.id === activeFloorId
                    ? "bg-primary-600 text-white"
                    : "bg-secondary-100 text-secondary-600 hover:bg-secondary-200"
                )}
              >
                {floor.name}
              </button>
            ))}
            <button
              onClick={() => setShowFloorDialog(true)}
              className="rounded-lg px-2 py-1.5 text-xs text-secondary-400 hover:bg-secondary-100"
              aria-label="Add floor"
            >
              <Plus className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => setShowAddDialog(true)}
            disabled={!activeFloorId}
          >
            <Plus className="h-4 w-4 mr-1" />
            Add Table
          </Button>
          <Button
            size="sm"
            onClick={handleSave}
            disabled={!hasChanges || isSaving}
          >
            {isSaving ? (
              <Loader2 className="h-4 w-4 mr-1 animate-spin" />
            ) : (
              <Save className="h-4 w-4 mr-1" />
            )}
            Save Layout
          </Button>
        </div>
      </div>

      {error && (
        <div className="bg-danger-50 px-4 py-2 text-sm text-danger-700">
          {error}
          <button
            onClick={() => setError(null)}
            className="ml-2 underline"
          >
            dismiss
          </button>
        </div>
      )}

      {successMessage && (
        <div className="bg-success-50 px-4 py-2 text-sm text-success-700">
          {successMessage}
        </div>
      )}

      <div className="flex flex-1 overflow-hidden">
        {/* Canvas */}
        <div
          ref={canvasRef}
          className="flex-1 relative overflow-auto bg-secondary-50"
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          onClick={(e) => {
            if (e.target === e.currentTarget) setSelectedTableId(null);
          }}
        >
          {/* Grid dots background */}
          <div
            className="absolute inset-0"
            style={{
              backgroundImage:
                "radial-gradient(circle, #cbd5e1 1px, transparent 1px)",
              backgroundSize: "20px 20px",
            }}
          />

          {/* Empty state */}
          {floors.length === 0 && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
              <LayoutGrid className="h-12 w-12 text-secondary-300" />
              <p className="text-lg font-medium text-secondary-400">No floors yet</p>
              <p className="text-sm text-secondary-300">Create a floor to start designing your layout</p>
              <Button onClick={() => setShowFloorDialog(true)}>
                <Plus className="h-4 w-4 mr-1" />
                Add Floor
              </Button>
            </div>
          )}

          {/* Tables */}
          {activeFloor?.tables.map((table) => (
            <div
              key={table.id}
              onMouseDown={(e) => handleMouseDown(e, table)}
              className={cn(
                "absolute flex flex-col items-center justify-center cursor-move select-none border-2 transition-shadow",
                table.shape === "round" ? "rounded-full" : "rounded-lg",
                table.id === selectedTableId
                  ? "border-primary-500 bg-primary-50 shadow-lg z-10"
                  : "border-secondary-300 bg-white hover:border-secondary-400 shadow-sm"
              )}
              style={{
                left: table.pos_x,
                top: table.pos_y,
                width: table.width,
                height: table.height,
                transform: table.rotation ? `rotate(${table.rotation}deg)` : undefined,
              }}
            >
              <span className="text-xs font-bold text-secondary-700">
                {table.label || `T${table.number}`}
              </span>
              <span className="text-[10px] text-secondary-400">
                {table.capacity} seats
              </span>
            </div>
          ))}
        </div>

        {/* Properties Panel */}
        {selectedTable && (
          <div className="w-64 shrink-0 border-l border-secondary-200 bg-white p-4 space-y-4 overflow-y-auto">
            <h3 className="font-semibold text-secondary-900 text-sm">
              Table {selectedTable.label || `T${selectedTable.number}`}
            </h3>

            <div className="space-y-3">
              <div>
                <Label className="text-xs">Number</Label>
                <Input
                  type="number"
                  value={selectedTable.number}
                  min={1}
                  onChange={(e) =>
                    handleUpdateTableProp("number", parseInt(e.target.value, 10))
                  }
                />
              </div>
              <div>
                <Label className="text-xs">Label (optional)</Label>
                <Input
                  value={selectedTable.label || ""}
                  placeholder="e.g. VIP-1"
                  onChange={(e) =>
                    handleUpdateTableProp("label", e.target.value || "")
                  }
                />
              </div>
              <div>
                <Label className="text-xs">Capacity</Label>
                <Input
                  type="number"
                  value={selectedTable.capacity}
                  min={1}
                  max={50}
                  onChange={(e) =>
                    handleUpdateTableProp("capacity", parseInt(e.target.value, 10))
                  }
                />
              </div>
              <div>
                <Label className="text-xs">Shape</Label>
                <div className="flex gap-1.5 mt-1">
                  {(
                    [
                      { shape: "square" as const, icon: Square },
                      { shape: "round" as const, icon: Circle },
                      { shape: "rectangle" as const, icon: RectangleHorizontal },
                    ] as const
                  ).map(({ shape, icon: Icon }) => (
                    <button
                      key={shape}
                      onClick={() => handleUpdateTableProp("shape", shape)}
                      className={cn(
                        "flex h-9 w-9 items-center justify-center rounded-lg border-2 transition-colors",
                        selectedTable.shape === shape
                          ? "border-primary-500 bg-primary-50 text-primary-700"
                          : "border-secondary-200 text-secondary-400 hover:border-secondary-300"
                      )}
                      aria-label={shape}
                    >
                      <Icon className="h-4 w-4" />
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <Label className="text-xs">Rotation</Label>
                <div className="flex items-center gap-2 mt-1">
                  <input
                    type="range"
                    min={0}
                    max={359}
                    value={selectedTable.rotation}
                    onChange={(e) => {
                      const val = parseInt(e.target.value, 10);
                      setFloors((prev) =>
                        prev.map((f) =>
                          f.id === activeFloorId
                            ? {
                                ...f,
                                tables: f.tables.map((t) =>
                                  t.id === selectedTableId
                                    ? { ...t, rotation: val }
                                    : t
                                ),
                              }
                            : f
                        )
                      );
                      setHasChanges(true);
                    }}
                    className="flex-1"
                  />
                  <span className="text-xs text-secondary-500 w-8 text-right">
                    {selectedTable.rotation}°
                  </span>
                </div>
              </div>
            </div>

            <div className="pt-2 border-t border-secondary-100">
              <Button
                variant="ghost"
                size="sm"
                className="w-full text-danger-600 hover:text-danger-700 hover:bg-danger-50"
                onClick={() => setShowDeleteConfirm(true)}
              >
                <Trash2 className="h-4 w-4 mr-1" />
                Delete Table
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Add Table Dialog */}
      <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Add Table</DialogTitle>
            <DialogDescription>
              Add a new table to {activeFloor?.name}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>Table Number</Label>
              <Input
                type="number"
                min={1}
                value={newTableNumber}
                onChange={(e) => setNewTableNumber(e.target.value)}
                placeholder="e.g. 17"
              />
            </div>
            <div>
              <Label>Label (optional)</Label>
              <Input
                value={newTableLabel}
                onChange={(e) => setNewTableLabel(e.target.value)}
                placeholder="e.g. VIP-2"
              />
            </div>
            <div>
              <Label>Capacity</Label>
              <Input
                type="number"
                min={1}
                max={50}
                value={newTableCapacity}
                onChange={(e) => setNewTableCapacity(e.target.value)}
              />
            </div>
            <div>
              <Label>Shape</Label>
              <div className="flex gap-2 mt-1">
                {(
                  [
                    { shape: "square" as const, icon: Square, label: "Square" },
                    { shape: "round" as const, icon: Circle, label: "Round" },
                    { shape: "rectangle" as const, icon: RectangleHorizontal, label: "Rectangle" },
                  ] as const
                ).map(({ shape, icon: Icon, label }) => (
                  <button
                    key={shape}
                    onClick={() => setNewTableShape(shape)}
                    className={cn(
                      "flex items-center gap-1.5 rounded-lg border-2 px-3 py-2 text-xs transition-colors",
                      newTableShape === shape
                        ? "border-primary-500 bg-primary-50 text-primary-700"
                        : "border-secondary-200 text-secondary-500 hover:border-secondary-300"
                    )}
                  >
                    <Icon className="h-3.5 w-3.5" />
                    {label}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAddDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleAddTable} disabled={!newTableNumber}>
              Add Table
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Delete Table</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete Table{" "}
              {selectedTable?.label || `T${selectedTable?.number}`}? This
              action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowDeleteConfirm(false)}
            >
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDeleteTable}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Add Floor Dialog */}
      <Dialog open={showFloorDialog} onOpenChange={setShowFloorDialog}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Add Floor</DialogTitle>
            <DialogDescription>
              Create a new dining area or section.
            </DialogDescription>
          </DialogHeader>
          <div>
            <Label>Floor Name</Label>
            <Input
              value={newFloorName}
              onChange={(e) => setNewFloorName(e.target.value)}
              placeholder="e.g. Rooftop, Private Room"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowFloorDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleAddFloor} disabled={!newFloorName}>
              Create Floor
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default FloorEditorPage;
