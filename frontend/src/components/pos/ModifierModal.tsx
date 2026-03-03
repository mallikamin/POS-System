import { useState, useEffect, useCallback } from "react";
import { Minus, Plus } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import { formatPKR } from "@/utils/currency";
import type { MenuItem, ModifierGroup } from "@/types/menu";
import type { SelectedModifier } from "@/types/cart";

interface ModifierModalProps {
  item: MenuItem | null;
  open: boolean;
  onClose: () => void;
  onConfirm: (modifiers: SelectedModifier[]) => void;
}

// Track quantities per modifier option: modifier_id -> quantity
type ModifierQuantities = Record<string, number>;

export function ModifierModal({
  item,
  open,
  onClose,
  onConfirm,
}: ModifierModalProps) {
  const [quantities, setQuantities] = useState<ModifierQuantities>({});

  // Reset when item changes
  useEffect(() => {
    if (item) {
      setQuantities({});
    }
  }, [item]);

  const getQty = (modId: string) => quantities[modId] || 0;

  const changeQty = useCallback(
    (group: ModifierGroup, modId: string, delta: number) => {
      setQuantities((prev) => {
        const current = prev[modId] || 0;
        const next = Math.max(0, current + delta);

        // For single-select groups (max_selections === 1), clear others in group
        if (group.max_selections === 1 && next > 0) {
          const cleared = { ...prev };
          for (const mod of group.modifiers) {
            if (mod.id !== modId) cleared[mod.id] = 0;
          }
          return { ...cleared, [modId]: Math.min(next, 1) };
        }

        // For multi-select with max, check total count in group
        if (group.max_selections > 1) {
          let groupTotal = 0;
          for (const mod of group.modifiers) {
            groupTotal += mod.id === modId ? next : (prev[mod.id] || 0);
          }
          if (groupTotal > group.max_selections) return prev;
        }

        return { ...prev, [modId]: next };
      });
    },
    []
  );

  // Validate all required groups have sufficient selections
  const isValid = useCallback(() => {
    if (!item) return false;
    for (const group of item.modifier_groups || []) {
      let groupCount = 0;
      for (const mod of group.modifiers) {
        groupCount += quantities[mod.id] || 0;
      }
      if (group.required && groupCount < group.min_selections) {
        return false;
      }
    }
    return true;
  }, [item, quantities]);

  function handleConfirm() {
    if (!item || !isValid()) return;

    const modifiers: SelectedModifier[] = [];
    for (const group of item.modifier_groups || []) {
      for (const mod of group.modifiers) {
        const qty = quantities[mod.id] || 0;
        if (qty > 0) {
          modifiers.push({
            modifier_option_id: mod.id,
            name: mod.name,
            price_adjustment: mod.price_adjustment,
            group_id: group.id,
            quantity: qty,
          });
        }
      }
    }
    onConfirm(modifiers);
  }

  // Calculate total modifier price adjustment
  const totalAdjustment = (() => {
    let total = 0;
    if (!item) return total;
    for (const group of item.modifier_groups || []) {
      for (const mod of group.modifiers) {
        const qty = quantities[mod.id] || 0;
        total += mod.price_adjustment * qty;
      }
    }
    return total;
  })();

  if (!item) return null;

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{item.name}</DialogTitle>
          <DialogDescription>
            {formatPKR(item.price)}
            {totalAdjustment !== 0 && (
              <span className={cn("ml-2", totalAdjustment > 0 ? "text-primary-600" : "text-success-600")}>
                {totalAdjustment > 0 ? "+" : "-"} {formatPKR(Math.abs(totalAdjustment))}
              </span>
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5 max-h-[60vh] overflow-y-auto">
          {(item.modifier_groups || []).map((group) => (
            <div key={group.id} className="space-y-2">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold text-secondary-900">
                  {group.name}
                </h3>
                {group.required && (
                  <Badge variant="warning" className="text-[10px]">
                    Required
                  </Badge>
                )}
                <span className="text-xs text-secondary-400">
                  {group.max_selections === 1
                    ? "Choose 1"
                    : group.max_selections <= 0
                      ? "Choose any"
                      : `Choose up to ${group.max_selections}`}
                </span>
              </div>

              <div className="space-y-1">
                {group.modifiers
                  .filter((m) => m.is_available)
                  .map((mod) => {
                    const qty = getQty(mod.id);
                    const isSelected = qty > 0;
                    const isSingleSelect = group.max_selections === 1;
                    return (
                      <div
                        key={mod.id}
                        className={cn(
                          "flex w-full items-center gap-3 rounded-lg border p-3 transition-colors min-h-touch",
                          isSelected
                            ? "border-primary-400 bg-primary-50"
                            : "border-secondary-200 bg-white"
                        )}
                      >
                        <span className="flex-1 text-sm text-secondary-700">
                          {mod.name}
                        </span>
                        {mod.price_adjustment !== 0 && (
                          <span className={cn("text-sm font-medium whitespace-nowrap", mod.price_adjustment > 0 ? "text-secondary-500" : "text-success-600")}>
                            {mod.price_adjustment > 0 ? "+" : "-"}{formatPKR(Math.abs(mod.price_adjustment))}
                          </span>
                        )}
                        {isSingleSelect ? (
                          /* Single-select: simple toggle button */
                          <button
                            onClick={() => changeQty(group, mod.id, isSelected ? -1 : 1)}
                            className={cn(
                              "flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 transition-colors",
                              isSelected
                                ? "border-primary-600 bg-primary-600 text-white"
                                : "border-secondary-300 hover:border-secondary-400"
                            )}
                          >
                            {isSelected && <span className="text-xs font-bold">&#10003;</span>}
                          </button>
                        ) : (
                          /* Multi-select: quantity stepper */
                          <div className="flex items-center gap-1 shrink-0">
                            <button
                              onClick={() => changeQty(group, mod.id, -1)}
                              disabled={qty === 0}
                              className={cn(
                                "flex h-8 w-8 items-center justify-center rounded-full border-2 transition-colors",
                                qty > 0
                                  ? "border-primary-400 bg-primary-50 text-primary-700 hover:bg-primary-100"
                                  : "border-secondary-200 text-secondary-300 cursor-not-allowed"
                              )}
                            >
                              <Minus className="h-4 w-4" />
                            </button>
                            <span className="w-6 text-center text-sm font-semibold text-secondary-800">
                              {qty}
                            </span>
                            <button
                              onClick={() => changeQty(group, mod.id, 1)}
                              className="flex h-8 w-8 items-center justify-center rounded-full border-2 border-primary-400 bg-primary-50 text-primary-700 hover:bg-primary-100 transition-colors"
                            >
                              <Plus className="h-4 w-4" />
                            </button>
                          </div>
                        )}
                      </div>
                    );
                  })}
              </div>
            </div>
          ))}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={onClose}
            className="min-h-touch-lg"
          >
            Cancel
          </Button>
          <Button
            onClick={handleConfirm}
            disabled={!isValid()}
            size="pos"
          >
            Add to Order &middot;{" "}
            {formatPKR(item.price + totalAdjustment)}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
