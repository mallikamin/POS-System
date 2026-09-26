import { useEffect, useMemo, useState } from "react";
import { isAxiosError } from "axios";
import { Loader2, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Thumb } from "@/components/admin/Thumb";
import { useToast } from "@/hooks/use-toast";
import { fetchStockPosition, saveOpeningCount } from "@/services/locationsApi";
import { formatMoney, getActiveCurrency, paisaToRupees, rupeesToPaisa } from "@/utils/currency";
import type { Ingredient } from "@/types/inventory";
import type { Location } from "@/types/location";

/**
 * The go-live stock count (Danny's D-61): every active ingredient on one
 * screen, count typed in, one save.
 *
 * Each box starts at what the system holds now, so the owner only overwrites
 * what differs, and only changed rows are sent. The server books the
 * difference as an "opening" movement, so saving the same figures twice moves
 * nothing and the count can be finished over several sittings.
 *
 * Cost is editable only for an ingredient bought in its stocking unit: a
 * produced one is costed by its recipe, and one bought by the can derives its
 * cost from the can price. The server skips those too.
 */
interface OpeningStockDialogProps {
  open: boolean;
  onClose: () => void;
  locations: Location[];
  ingredients: Ingredient[];
  defaultLocationId: string;
  onSaved: () => void;
}

interface CountRow {
  ingredient: Ingredient;
  initialCount: string;
  initialCost: string;
  costEditable: boolean;
}

function asInput(value: number): string {
  return String(Number(value.toFixed(3)));
}

export function OpeningStockDialog({
  open,
  onClose,
  locations,
  ingredients,
  defaultLocationId,
  onSaved,
}: OpeningStockDialogProps) {
  const { toast } = useToast();
  const currency = getActiveCurrency();
  const [locationId, setLocationId] = useState(defaultLocationId);
  const [rows, setRows] = useState<CountRow[]>([]);
  const [counts, setCounts] = useState<Record<string, string>>({});
  const [costs, setCosts] = useState<Record<string, string>>({});
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setLocationId(defaultLocationId);
      setSearch("");
    }
  }, [open, defaultLocationId]);

  useEffect(() => {
    if (!open || !locationId) return;
    let cancelled = false;
    setLoading(true);
    fetchStockPosition({ location_id: locationId })
      .then((stock) => {
        if (cancelled) return;
        const onHand = new Map(stock.map((s) => [s.ingredient_id, Number(s.quantity)]));
        const built = [...ingredients]
          .sort((a, b) => a.name.localeCompare(b.name))
          .map((ingredient) => ({
            ingredient,
            initialCount: asInput(onHand.get(ingredient.id) ?? 0),
            initialCost: String(paisaToRupees(Number(ingredient.cost_per_unit))),
            costEditable: !ingredient.is_produced && !ingredient.purchase_unit,
          }));
        setRows(built);
        setCounts(Object.fromEntries(built.map((r) => [r.ingredient.id, r.initialCount])));
        setCosts(Object.fromEntries(built.map((r) => [r.ingredient.id, r.initialCost])));
      })
      .catch(() => {
        // The global axios interceptor raises the toast.
        if (!cancelled) setRows([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, locationId, ingredients]);

  const changed = useMemo(
    () =>
      rows.filter(
        (r) =>
          counts[r.ingredient.id] !== r.initialCount ||
          (r.costEditable && costs[r.ingredient.id] !== r.initialCost),
      ),
    [rows, counts, costs],
  );

  const invalid = useMemo(
    () =>
      changed.filter((r) => {
        const count = Number(counts[r.ingredient.id]);
        const cost = Number(costs[r.ingredient.id]);
        return (
          counts[r.ingredient.id]?.trim() === "" ||
          !Number.isFinite(count) ||
          count < 0 ||
          (r.costEditable && (!Number.isFinite(cost) || cost < 0))
        );
      }),
    [changed, counts, costs],
  );

  const stockValue = rows.reduce((sum, r) => {
    const count = Number(counts[r.ingredient.id]);
    const cost = r.costEditable
      ? rupeesToPaisa(Number(costs[r.ingredient.id]))
      : Number(r.ingredient.cost_per_unit);
    return Number.isFinite(count) && Number.isFinite(cost) ? sum + count * cost : sum;
  }, 0);

  const needle = search.trim().toLowerCase();
  const visible = needle
    ? rows.filter((r) => r.ingredient.name.toLowerCase().includes(needle))
    : rows;

  async function handleSave() {
    if (changed.length === 0 || invalid.length > 0) return;
    setSaving(true);
    try {
      const result = await saveOpeningCount({
        location_id: locationId,
        lines: changed.map((r) => ({
          ingredient_id: r.ingredient.id,
          counted_quantity: Number(counts[r.ingredient.id]),
          ...(r.costEditable && costs[r.ingredient.id] !== r.initialCost
            ? { unit_cost: rupeesToPaisa(Number(costs[r.ingredient.id])) }
            : {}),
        })),
      });
      toast({
        title: "Opening stock saved",
        description: `${result.lines_counted} item${result.lines_counted === 1 ? "" : "s"} at ${
          result.location_name
        }: ${result.movements} stock change${result.movements === 1 ? "" : "s"}, ${
          result.costs_updated
        } cost${result.costs_updated === 1 ? "" : "s"} updated. Reference ${result.reference_number}.`,
        variant: "success",
      });
      onSaved();
      onClose();
    } catch (err) {
      // The global interceptor toasts only 403 and 5xx; a 400 carries the
      // reason in `detail` and would otherwise fail silently.
      const detail = isAxiosError(err) ? err.response?.data?.detail : undefined;
      toast({
        title: "Opening stock not saved",
        description: typeof detail === "string" ? detail : "Nothing was changed. Please try again.",
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
    >
      <DialogContent className="max-w-4xl">
        <DialogHeader>
          <DialogTitle>Opening Stock</DialogTitle>
          <DialogDescription>
            Type what is on the shelf now for each item. Only the rows you change are saved,
            and saving the same count again changes nothing.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-wrap items-end gap-4">
          {locations.length > 1 && (
            <div className="space-y-2 min-w-[200px]">
              <Label>Location</Label>
              <Select value={locationId} onChange={(e) => setLocationId(e.target.value)}>
                {locations.map((loc) => (
                  <option key={loc.id} value={loc.id}>
                    {loc.name}
                  </option>
                ))}
              </Select>
            </div>
          )}
          <div className="space-y-2 min-w-[220px] flex-1">
            <Label htmlFor="opening-search">Search</Label>
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-secondary-400" />
              <Input
                id="opening-search"
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Ingredient name"
                className="pl-9"
              />
            </div>
          </div>
        </div>

        {loading ? (
          <div className="flex justify-center py-10">
            <Loader2 className="h-6 w-6 animate-spin text-secondary-400" />
          </div>
        ) : (
          <div className="max-h-[55vh] overflow-y-auto scrollbar-visible">
            <table className="w-full text-pos-sm">
              <thead className="sticky top-0 z-10 bg-white">
                <tr className="border-b border-secondary-200 text-left text-secondary-500">
                  <th className="px-3 py-2 font-medium">Ingredient</th>
                  <th className="px-3 py-2 text-right font-medium">In system</th>
                  <th className="px-3 py-2 font-medium">Counted</th>
                  <th className="px-3 py-2 font-medium">Cost per unit</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((r) => {
                  const id = r.ingredient.id;
                  const isChanged = changed.includes(r);
                  const isInvalid = invalid.includes(r);
                  return (
                    <tr
                      key={id}
                      className={isChanged ? "border-b border-secondary-100 bg-primary-50" : "border-b border-secondary-100"}
                    >
                      <td className="px-3 py-2">
                        <div className="flex items-center gap-2">
                          <Thumb src={r.ingredient.image_url} alt={r.ingredient.name} />
                          <span className="font-medium text-secondary-900">{r.ingredient.name}</span>
                        </div>
                      </td>
                      <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums text-secondary-500">
                        {r.initialCount} {r.ingredient.unit}
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex items-center gap-2">
                          <Input
                            type="number"
                            inputMode="decimal"
                            min={0}
                            step="any"
                            aria-label={`Counted ${r.ingredient.name}`}
                            value={counts[id] ?? ""}
                            onChange={(e) => setCounts((c) => ({ ...c, [id]: e.target.value }))}
                            className={isInvalid ? "w-28 border-danger-500" : "w-28"}
                          />
                          <span className="text-secondary-500">{r.ingredient.unit}</span>
                        </div>
                      </td>
                      <td className="px-3 py-2">
                        {r.costEditable ? (
                          <Input
                            type="number"
                            inputMode="decimal"
                            min={0}
                            step="any"
                            aria-label={`Cost per ${r.ingredient.unit} of ${r.ingredient.name}`}
                            value={costs[id] ?? ""}
                            onChange={(e) => setCosts((c) => ({ ...c, [id]: e.target.value }))}
                            className="w-28"
                          />
                        ) : (
                          <span
                            className="text-secondary-500"
                            title={
                              r.ingredient.is_produced
                                ? "Costed by its recipe"
                                : `Set from the ${r.ingredient.purchase_unit} price`
                            }
                          >
                            {formatMoney(Number(r.ingredient.cost_per_unit), currency)}
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <DialogFooter className="items-center gap-3 sm:justify-between">
          <p className="text-pos-sm text-secondary-600">
            {changed.length} changed
            {invalid.length > 0 && (
              <span className="text-danger-600"> · {invalid.length} need a number of 0 or more</span>
            )}
            {" · "}Stock value {formatMoney(Math.round(stockValue), currency)}
          </p>
          <div className="flex gap-2">
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button
              onClick={() => void handleSave()}
              disabled={saving || loading || changed.length === 0 || invalid.length > 0}
            >
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : "Save Opening Stock"}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
