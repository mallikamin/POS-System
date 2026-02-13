import { useState, useEffect, useCallback } from "react";
import { Check } from "lucide-react";
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

// Track selections per group: group_id -> set of modifier option ids
type GroupSelections = Record<string, Set<string>>;

export function ModifierModal({
  item,
  open,
  onClose,
  onConfirm,
}: ModifierModalProps) {
  const [selections, setSelections] = useState<GroupSelections>({});

  // Reset selections when item changes
  useEffect(() => {
    if (item) {
      const initial: GroupSelections = {};
      for (const group of item.modifier_groups || []) {
        initial[group.id] = new Set();
      }
      setSelections(initial);
    }
  }, [item]);

  const toggleOption = useCallback(
    (group: ModifierGroup, optionId: string) => {
      setSelections((prev) => {
        const current = new Set(prev[group.id] || []);

        if (current.has(optionId)) {
          current.delete(optionId);
        } else {
          // If at max, either replace (single-select) or block
          if (group.max_selections === 1) {
            current.clear();
            current.add(optionId);
          } else if (group.max_selections <= 0 || current.size < group.max_selections) {
            // max_selections <= 0 means unlimited
            current.add(optionId);
          }
        }

        return { ...prev, [group.id]: current };
      });
    },
    []
  );

  // Validate all required groups have sufficient selections
  const isValid = useCallback(() => {
    if (!item) return false;
    for (const group of item.modifier_groups || []) {
      const selected = selections[group.id]?.size || 0;
      if (group.required && selected < group.min_selections) {
        return false;
      }
      if (selected > 0 && selected < group.min_selections) {
        return false;
      }
    }
    return true;
  }, [item, selections]);

  function handleConfirm() {
    if (!item || !isValid()) return;

    const modifiers: SelectedModifier[] = [];
    for (const group of item.modifier_groups || []) {
      const selectedIds = selections[group.id] || new Set();
      for (const mod of group.modifiers) {
        if (selectedIds.has(mod.id)) {
          modifiers.push({
            modifier_option_id: mod.id,
            name: mod.name,
            price_adjustment: mod.price_adjustment,
            group_id: group.id,
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
      const selectedIds = selections[group.id] || new Set();
      for (const mod of group.modifiers) {
        if (selectedIds.has(mod.id)) {
          total += mod.price_adjustment;
        }
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
          {(item.modifier_groups || []).map((group) => {
            const selectedIds = selections[group.id] || new Set<string>();
            return (
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
                        : `Choose ${group.min_selections}-${group.max_selections}`}
                  </span>
                </div>

                <div className="space-y-1">
                  {group.modifiers
                    .filter((m) => m.is_available)
                    .map((mod) => {
                      const isSelected = selectedIds.has(mod.id);
                      return (
                        <button
                          key={mod.id}
                          onClick={() => toggleOption(group, mod.id)}
                          className={cn(
                            "flex w-full items-center gap-3 rounded-lg border p-3 text-left transition-colors min-h-touch",
                            isSelected
                              ? "border-primary-400 bg-primary-50"
                              : "border-secondary-200 bg-white hover:border-secondary-300"
                          )}
                        >
                          <div
                            className={cn(
                              "flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 transition-colors",
                              isSelected
                                ? "border-primary-600 bg-primary-600"
                                : "border-secondary-300"
                            )}
                          >
                            {isSelected && (
                              <Check className="h-3 w-3 text-white" />
                            )}
                          </div>
                          <span className="flex-1 text-sm text-secondary-700">
                            {mod.name}
                          </span>
                          {mod.price_adjustment !== 0 && (
                            <span className={cn("text-sm font-medium", mod.price_adjustment > 0 ? "text-secondary-500" : "text-success-600")}>
                              {mod.price_adjustment > 0 ? "+" : "-"}{formatPKR(Math.abs(mod.price_adjustment))}
                            </span>
                          )}
                        </button>
                      );
                    })}
                </div>
              </div>
            );
          })}
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
