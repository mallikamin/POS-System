import { cn } from "@/lib/utils";
import { Users } from "lucide-react";
import type { TableResponse, TableStatus } from "@/types/floor";

interface TableCardProps {
  table: TableResponse;
  isSelected: boolean;
  onClick: () => void;
}

const STATUS_STYLES: Record<TableStatus, { bg: string; border: string; text: string; badge: string }> = {
  available: {
    bg: "bg-success-50 hover:bg-success-100",
    border: "border-success-300",
    text: "text-success-700",
    badge: "bg-success-500",
  },
  occupied: {
    bg: "bg-danger-50 hover:bg-danger-100",
    border: "border-danger-300",
    text: "text-danger-700",
    badge: "bg-danger-500",
  },
  reserved: {
    bg: "bg-warning-50 hover:bg-warning-100",
    border: "border-warning-300",
    text: "text-warning-700",
    badge: "bg-warning-500",
  },
  cleaning: {
    bg: "bg-secondary-50 hover:bg-secondary-100",
    border: "border-secondary-300",
    text: "text-secondary-500",
    badge: "bg-secondary-400",
  },
};

export function TableCard({ table, isSelected, onClick }: TableCardProps) {
  const style = STATUS_STYLES[table.status];
  const displayName = table.label || `T${table.number}`;

  return (
    <button
      onClick={onClick}
      aria-label={`Table ${displayName}, ${table.status}, seats ${table.capacity}`}
      className={cn(
        "relative flex flex-col items-center justify-center gap-1 border-2 transition-all active:scale-95",
        style.bg,
        style.border,
        isSelected && "ring-2 ring-primary-500 ring-offset-2",
        table.shape === "round" ? "rounded-full" : "rounded-xl",
        // Fixed sizes for the grid layout
        "w-20 h-20 min-h-touch-lg"
      )}
    >
      {/* Status dot */}
      <span
        className={cn(
          "absolute top-1.5 right-1.5 h-2 w-2 rounded-full",
          style.badge
        )}
      />

      {/* Table number */}
      <span className={cn("text-sm font-bold", style.text)}>
        {displayName}
      </span>

      {/* Capacity */}
      <span className={cn("flex items-center gap-0.5 text-[10px]", style.text)}>
        <Users className="h-2.5 w-2.5" />
        {table.capacity}
      </span>
    </button>
  );
}
