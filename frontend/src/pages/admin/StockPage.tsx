import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  ClipboardList,
  Factory,
  Loader2,
  Package,
  RefreshCw,
  Search,
} from "lucide-react";
import { OpeningStockDialog } from "@/components/admin/OpeningStockDialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { useConfigStore } from "@/stores/configStore";
import { isModuleHidden } from "@/lib/modules";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import { Thumb } from "@/components/admin/Thumb";
import { formatMoney, getActiveCurrency } from "@/utils/currency";
import {
  adjustStock,
  fetchLocations,
  fetchStockMovements,
  fetchStockPosition,
  runProduction,
  setReorderLevel,
} from "@/services/locationsApi";
import { fetchIngredients, fetchRecipes } from "@/services/inventoryApi";
import { cn } from "@/lib/utils";
import type {
  Location,
  LocationStockRow,
  StockMovementRow,
} from "@/types/location";
import type { Ingredient, Recipe } from "@/types/inventory";
import { formatDateTime } from "@/utils/localDate";

/** Decimals arrive as strings from the API. Anything unparseable reads as 0. */
/**
 * Decimal fields arrive from the API as JSON **numbers** (`Num` in
 * `schemas/location.py`). Older endpoints and form inputs still hand over
 * strings, so this accepts both. `Number()` copes with either; the signature
 * was the only thing that was wrong, and it hid the mismatch behind F51.
 */
function toNumber(value: string | number | null | undefined): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatQty(value: string | number | null | undefined): string {
  return toNumber(value).toLocaleString(undefined, {
    maximumFractionDigits: 3,
  });
}

/**
 * The Recipe type does not yet declare `produces_ingredient_id`, but the
 * backend returns it on every recipe (exactly one of menu_item_id or
 * produces_ingredient_id is set). Read it through an `in` guard so this stays
 * type-safe without an assertion.
 */
function producedIngredientId(recipe: Recipe): string | null {
  if (!("produces_ingredient_id" in recipe)) return null;
  const value = recipe.produces_ingredient_id;
  return typeof value === "string" && value.length > 0 ? value : null;
}

function errorMessage(err: unknown, fallback: string): string {
  if (typeof err !== "object" || err === null || !("response" in err)) {
    return fallback;
  }
  const response = err.response;
  if (typeof response !== "object" || response === null || !("data" in response)) {
    return fallback;
  }
  const data = response.data;
  if (typeof data !== "object" || data === null || !("detail" in data)) {
    return fallback;
  }
  const detail = data.detail;
  return typeof detail === "string" && detail.length > 0 ? detail : fallback;
}

/** One stock row is one ingredient at one location. */
function rowKey(row: LocationStockRow): string {
  return `${row.location_id}:${row.ingredient_id}`;
}

/**
 * Stock on Hand: a list, and one item's detail beside it (below `lg`, one or
 * the other, with Back). Malik, 2026-09-27: the old table put Adjust, History
 * and Reorder behind a sideways scroll on a phone. Same pattern as the Recipe
 * Builder: tap an item, everything about it is on one screen.
 */
function StockPage() {
  const { toast } = useToast();
  const config = useConfigStore((s) => s.config);
  const currency = getActiveCurrency();

  const [locations, setLocations] = useState<Location[]>([]);
  const [ingredients, setIngredients] = useState<Ingredient[]>([]);
  const [subRecipes, setSubRecipes] = useState<Recipe[]>([]);
  const [rows, setRows] = useState<LocationStockRow[]>([]);

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState(false);

  const [locationFilter, setLocationFilter] = useState("");
  const [lowOnly, setLowOnly] = useState(false);
  // Find one ingredient in a 70-row list without scrolling (Danny's D-49).
  const [search, setSearch] = useState("");

  // The item whose detail is open. Kept as the row itself, refreshed from each
  // reload, so an item that leaves the list (no longer low under "Low stock
  // only") stays open instead of snapping back to the list mid-task.
  const [selected, setSelected] = useState<LocationStockRow | null>(null);
  const detailRef = useRef<HTMLDivElement>(null);

  // Adjust form
  const [adjustDelta, setAdjustDelta] = useState("");
  const [adjustReason, setAdjustReason] = useState("");

  // Reorder form
  const [reorderPoint, setReorderPoint] = useState("");
  const [reorderQuantity, setReorderQuantity] = useState("");

  // Movement history
  const [history, setHistory] = useState<StockMovementRow[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  // Opening stock count (D-61)
  const [showOpening, setShowOpening] = useState(false);

  // Production dialog
  const [showProduction, setShowProduction] = useState(false);
  const [prodRecipeId, setProdRecipeId] = useState("");
  const [prodLocationId, setProdLocationId] = useState("");
  const [prodBatches, setProdBatches] = useState("1");

  useEffect(() => {
    void loadReferenceData();
  }, []);

  useEffect(() => {
    void loadStock();
  }, [locationFilter, lowOnly]);

  const selectedKey = selected ? rowKey(selected) : null;

  // A newly opened item: fresh forms, its own history, and on a phone the
  // detail brought to the top of the screen.
  useEffect(() => {
    if (!selected) return;
    setAdjustDelta("");
    setAdjustReason("");
    setReorderPoint(String(toNumber(selected.reorder_point)));
    setReorderQuantity(String(toNumber(selected.reorder_quantity)));
    void loadHistory(selected);
    if (window.innerWidth < 1024) {
      detailRef.current?.scrollIntoView({ block: "start" });
    }
    // Keyed on the item, not the row object, which each reload replaces.
  }, [selectedKey]);

  async function loadReferenceData() {
    try {
      const [locationList, recipeList, ingredientList] = await Promise.all([
        fetchLocations(),
        fetchRecipes({ is_active: true }),
        fetchIngredients({ is_active: true }),
      ]);
      setLocations(locationList);
      setIngredients(ingredientList);
      setSubRecipes(recipeList.filter((r) => producedIngredientId(r) !== null));
    } catch (err) {
      toast({
        title: "Failed to load locations and recipes",
        description: errorMessage(err, "Production options are unavailable."),
        variant: "destructive",
      });
    }
  }

  async function loadStock() {
    try {
      setRefreshing(true);
      const data = await fetchStockPosition({
        ...(locationFilter ? { location_id: locationFilter } : {}),
        ...(lowOnly ? { low_only: true } : {}),
      });
      setRows(data);
      setSelected((prev) =>
        prev ? (data.find((r) => rowKey(r) === rowKey(prev)) ?? prev) : null,
      );
    } catch (err) {
      toast({
        title: "Failed to load stock position",
        description: errorMessage(err, "Please try again."),
        variant: "destructive",
      });
    } finally {
      setRefreshing(false);
      setLoading(false);
    }
  }

  async function loadHistory(row: LocationStockRow) {
    setHistory([]);
    setHistoryLoading(true);
    try {
      // Scoped to this ingredient AND this location. The tenant-wide history of
      // an ingredient is a different question, and mixing two sites' movements
      // in one list makes the running balance column nonsense.
      setHistory(
        await fetchStockMovements({
          ingredient_id: row.ingredient_id,
          location_id: row.location_id,
          limit: 200,
        }),
      );
    } catch {
      // The global axios interceptor raises the toast. Leaving the list empty
      // shows the honest "no movements" state rather than a stale one.
      setHistory([]);
    } finally {
      setHistoryLoading(false);
    }
  }

  function ingredientName(id: string): string {
    return ingredients.find((i) => i.id === id)?.name ?? "ingredient";
  }

  function ingredientUnit(id: string): string {
    return ingredients.find((i) => i.id === id)?.unit ?? "";
  }

  function openProduction() {
    const firstRecipe = subRecipes[0];
    const defaultLocation =
      locations.find((l) => l.is_default) ?? locations[0];
    setProdRecipeId(firstRecipe ? firstRecipe.id : "");
    setProdLocationId(
      locationFilter || (defaultLocation ? defaultLocation.id : ""),
    );
    setProdBatches("1");
    setShowProduction(true);
  }

  const adjustDeltaValue = Number(adjustDelta);
  const adjustValid =
    adjustDelta.trim().length > 0 &&
    Number.isFinite(adjustDeltaValue) &&
    adjustDeltaValue !== 0 &&
    adjustReason.trim().length > 0;

  const reorderPointValue = Number(reorderPoint);
  const reorderQuantityValue = Number(reorderQuantity);
  const reorderValid =
    reorderPoint.trim().length > 0 &&
    Number.isFinite(reorderPointValue) &&
    reorderPointValue >= 0 &&
    Number.isFinite(reorderQuantityValue) &&
    reorderQuantityValue >= 0;

  const batchesValue = Number(prodBatches);
  const productionValid =
    prodRecipeId.length > 0 &&
    prodLocationId.length > 0 &&
    Number.isFinite(batchesValue) &&
    batchesValue > 0;

  async function handleAdjust() {
    if (!selected || !adjustValid) return;
    const row = selected;
    setSaving(true);
    try {
      await adjustStock({
        ingredient_id: row.ingredient_id,
        location_id: row.location_id,
        quantity_delta: adjustDeltaValue,
        reason: adjustReason.trim(),
      });
      toast({
        title: "Stock adjusted",
        description: `${adjustDeltaValue > 0 ? "+" : ""}${adjustDeltaValue} ${
          row.unit
        } of ${row.ingredient_name} at ${row.location_name}.`,
        variant: "success",
      });
      setAdjustDelta("");
      setAdjustReason("");
      await loadStock();
      await loadHistory(row);
    } catch (err) {
      toast({
        title: "Adjustment failed",
        description: errorMessage(err, "The stock was not changed."),
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  }

  async function handleReorder() {
    if (!selected || !reorderValid) return;
    const row = selected;
    setSaving(true);
    try {
      await setReorderLevel({
        ingredient_id: row.ingredient_id,
        location_id: row.location_id,
        reorder_point: reorderPointValue,
        reorder_quantity: reorderQuantityValue,
      });
      toast({
        title: "Reorder level saved",
        description: `${row.ingredient_name} reorders at ${reorderPointValue} ${row.unit}.`,
        variant: "success",
      });
      await loadStock();
    } catch (err) {
      toast({
        title: "Failed to save reorder level",
        description: errorMessage(err, "Please try again."),
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  }

  async function handleProduction() {
    if (!productionValid) return;
    setSaving(true);
    try {
      const result = await runProduction({
        recipe_id: prodRecipeId,
        location_id: prodLocationId,
        batches: batchesValue,
      });
      const producedName = ingredientName(result.produced_ingredient_id);
      const unit = ingredientUnit(result.produced_ingredient_id);
      toast({
        title: `Produced ${formatQty(result.produced_quantity)} ${unit} of ${producedName}`.trim(),
        description: `${result.consumed.length} ingredient(s) consumed at ${result.location_name}. Reference ${result.reference_number}.`,
        variant: "success",
      });
      setShowProduction(false);
      await loadStock();
    } catch (err) {
      toast({
        title: "Production run failed",
        description: errorMessage(err, "No stock was moved."),
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  }

  const needle = search.trim().toLowerCase();
  const visibleRows = needle
    ? rows.filter((row) => row.ingredient_name.toLowerCase().includes(needle))
    : rows;
  // The location only needs saying when the list can hold more than one.
  const showLocation = !locationFilter && locations.length > 1;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    );
  }

  return (
    <div className="space-y-4 sm:space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Package className="h-7 w-7 text-primary-600" />
          <h1 className="text-pos-2xl font-bold text-secondary-900">
            Stock on Hand
          </h1>
        </div>
        <div className={cn("flex flex-wrap items-center gap-2", selected && "hidden lg:flex")}>
          <Button
            variant="outline"
            onClick={() => void loadStock()}
            disabled={refreshing}
            aria-label="Refresh"
            className="gap-2 min-h-[48px]"
          >
            <RefreshCw
              className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`}
            />
            <span className="hidden sm:inline">Refresh</span>
          </Button>
          <Button
            variant="outline"
            onClick={() => setShowOpening(true)}
            disabled={locations.length === 0}
            className="gap-2 min-h-[48px]"
          >
            <ClipboardList className="h-4 w-4" />
            Opening Stock
          </Button>
          {/* Not offered to a tenant that makes nothing in-house (Danny's). */}
          {!isModuleHidden(config, "production") && (
            <Button
              onClick={openProduction}
              disabled={subRecipes.length === 0}
              className="gap-2 min-h-[48px]"
            >
              <Factory className="h-4 w-4" />
              Run Production
            </Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* LEFT: the list */}
        <Card className={cn("lg:col-span-1", selected && "hidden lg:block")}>
          <CardContent className="space-y-3 px-4 pt-4 sm:px-6">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-secondary-400" />
              <Input
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search ingredients"
                aria-label="Search ingredients"
                className="min-h-[48px] pl-9"
              />
            </div>
            {locations.length > 1 && (
              <Select
                value={locationFilter}
                onChange={(e) => setLocationFilter(e.target.value)}
                aria-label="Location"
                className="min-h-[48px]"
              >
                <option value="">All locations</option>
                {locations.map((loc) => (
                  <option key={loc.id} value={loc.id}>
                    {loc.name}
                  </option>
                ))}
              </Select>
            )}
            <label className="flex items-center gap-2">
              <Switch checked={lowOnly} onCheckedChange={setLowOnly} />
              <span className="text-sm text-secondary-600">Low stock only</span>
            </label>

            {visibleRows.length === 0 ? (
              <div className="py-8 text-center text-pos-sm text-secondary-500">
                {needle && rows.length > 0
                  ? `No ingredient matches "${search.trim()}".`
                  : lowOnly
                    ? "Nothing is below its reorder point right now."
                    : "No stock records for this selection."}
              </div>
            ) : (
              <div className="space-y-2">
                {visibleRows.map((row) => {
                  const isSelected = selectedKey === rowKey(row);
                  return (
                    <button
                      key={rowKey(row)}
                      type="button"
                      onClick={() => setSelected(row)}
                      className={cn(
                        "flex w-full items-center gap-3 rounded-lg border px-3 py-2 text-left transition-colors",
                        isSelected
                          ? "border-primary-500 bg-primary-50"
                          : "border-secondary-200 hover:bg-secondary-50",
                      )}
                    >
                      <Thumb src={row.ingredient_image_url} alt={row.ingredient_name} />
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-pos-sm font-medium text-secondary-900">
                          {row.ingredient_name}
                        </div>
                        {showLocation && (
                          <div className="truncate text-pos-xs text-secondary-500">
                            {row.location_name}
                          </div>
                        )}
                      </div>
                      <div className="shrink-0 text-right">
                        <div
                          className={cn(
                            "text-pos-sm tabular-nums font-medium",
                            row.is_low ? "text-danger-600" : "text-secondary-900",
                          )}
                        >
                          {formatQty(row.quantity)} {row.unit}
                        </div>
                        {row.is_low && <Badge variant="warning">LOW</Badge>}
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>

        {/* RIGHT: one item */}
        <Card
          ref={detailRef}
          // Desktop: pinned beside a 70-row list, scrolling on its own, so an
          // item picked far down the list is not opened off-screen at the top.
          className={cn(
            "scroll-mt-4 lg:sticky lg:top-4 lg:col-span-2 lg:max-h-[calc(100vh-6rem)] lg:self-start lg:overflow-y-auto",
            !selected && "hidden lg:block",
          )}
        >
          <CardHeader className="px-4 pb-3 sm:px-6">
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSelected(null)}
                className="min-h-[44px] gap-1 lg:hidden"
              >
                <ArrowLeft className="h-4 w-4" />
                Back
              </Button>
              <CardTitle className="text-pos-lg">Stock item</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="px-4 sm:px-6">
            {!selected ? (
              <div className="py-12 text-center text-secondary-500">
                Select an ingredient to see its stock, adjust it, set its reorder
                level, or read its history.
              </div>
            ) : (
              <div className="space-y-6">
                {/* Identity */}
                <div className="flex items-center gap-3 rounded-lg border border-secondary-200 bg-secondary-50 p-3">
                  <Thumb
                    src={selected.ingredient_image_url}
                    alt={selected.ingredient_name}
                    size="lg"
                  />
                  <div className="min-w-0 flex-1">
                    <div className="text-pos-base font-semibold text-secondary-900">
                      {selected.ingredient_name}
                    </div>
                    <div className="text-pos-sm text-secondary-600">
                      {selected.location_name}
                    </div>
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1">
                    {selected.is_produced && <Badge variant="secondary">Produced</Badge>}
                    {selected.is_low && <Badge variant="warning">LOW</Badge>}
                  </div>
                </div>

                {/* The three numbers */}
                <div className="grid grid-cols-3 gap-2 sm:gap-3">
                  <div className="rounded-lg border border-secondary-200 p-3">
                    <div className="text-pos-xs text-secondary-500">On hand</div>
                    <div
                      className={cn(
                        "text-pos-base font-semibold tabular-nums",
                        selected.is_low ? "text-danger-600" : "text-secondary-900",
                      )}
                    >
                      {formatQty(selected.quantity)} {selected.unit}
                    </div>
                  </div>
                  <div className="rounded-lg border border-secondary-200 p-3">
                    <div className="text-pos-xs text-secondary-500">Reorder at</div>
                    <div className="text-pos-base font-semibold tabular-nums text-secondary-900">
                      {formatQty(selected.reorder_point)} {selected.unit}
                    </div>
                    {toNumber(selected.reorder_quantity) > 0 && (
                      <div className="text-pos-xs text-secondary-500">
                        buy {formatQty(selected.reorder_quantity)} {selected.unit}
                      </div>
                    )}
                  </div>
                  <div className="rounded-lg border border-secondary-200 p-3">
                    <div className="text-pos-xs text-secondary-500">Cost / {selected.unit}</div>
                    <div className="text-pos-base font-semibold tabular-nums text-secondary-900">
                      {formatMoney(toNumber(selected.cost_per_unit), currency)}
                    </div>
                    <div className="text-pos-xs text-secondary-500">
                      worth{" "}
                      {formatMoney(
                        toNumber(selected.quantity) * toNumber(selected.cost_per_unit),
                        currency,
                      )}
                    </div>
                  </div>
                </div>

                {/* Adjust stock */}
                <section className="space-y-3">
                  <h2 className="text-pos-base font-semibold text-secondary-900">
                    Adjust stock
                  </h2>
                  <div className="space-y-2">
                    <Label htmlFor="adjust-delta">
                      Quantity change ({selected.unit})
                    </Label>
                    <Input
                      id="adjust-delta"
                      type="number"
                      step="any"
                      inputMode="decimal"
                      value={adjustDelta}
                      onChange={(e) => setAdjustDelta(e.target.value)}
                      placeholder="e.g. 5 to add, -5 to remove"
                      className="min-h-[48px]"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="adjust-reason">Reason (required)</Label>
                    <Textarea
                      id="adjust-reason"
                      rows={2}
                      value={adjustReason}
                      onChange={(e) => setAdjustReason(e.target.value)}
                      placeholder="e.g. Spoilage, stock count correction, supplier shortfall"
                    />
                    <p className="text-xs text-secondary-500">
                      Recorded on the history against your name, so it stays
                      auditable.
                    </p>
                  </div>
                  <Button
                    onClick={() => void handleAdjust()}
                    disabled={saving || !adjustValid}
                    className="min-h-[48px] w-full sm:w-auto"
                  >
                    {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : "Save adjustment"}
                  </Button>
                </section>

                {/* Reorder level */}
                <section className="space-y-3 border-t border-secondary-200 pt-6">
                  <h2 className="text-pos-base font-semibold text-secondary-900">
                    Reorder level
                  </h2>
                  <p className="text-xs text-secondary-500">
                    Flagged as low once stock falls below the reorder point.
                  </p>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-2">
                      <Label htmlFor="reorder-point">Reorder point ({selected.unit})</Label>
                      <Input
                        id="reorder-point"
                        type="number"
                        min={0}
                        step="any"
                        inputMode="decimal"
                        value={reorderPoint}
                        onChange={(e) => setReorderPoint(e.target.value)}
                        className="min-h-[48px]"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="reorder-qty">Buy quantity ({selected.unit})</Label>
                      <Input
                        id="reorder-qty"
                        type="number"
                        min={0}
                        step="any"
                        inputMode="decimal"
                        value={reorderQuantity}
                        onChange={(e) => setReorderQuantity(e.target.value)}
                        className="min-h-[48px]"
                      />
                    </div>
                  </div>
                  <Button
                    variant="outline"
                    onClick={() => void handleReorder()}
                    disabled={saving || !reorderValid}
                    className="min-h-[48px] w-full sm:w-auto"
                  >
                    {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : "Save reorder level"}
                  </Button>
                </section>

                {/* Movement history
                    Why the stock figure is what it is. Every movement this system
                    has ever written for this ingredient at this site, newest
                    first, with who did it and the reason they gave.

                    🔴 This ledger has been written since the module shipped and
                    had no reader at all until 2026-08-27: no endpoint, no screen.
                    The mandatory reason on a manual adjustment went into the
                    database and could never be seen again, which made "stock
                    never changes without an explanation" a claim a customer had
                    to take on trust. */}
                <section className="space-y-3 border-t border-secondary-200 pt-6">
                  <h2 className="text-pos-base font-semibold text-secondary-900">
                    History
                  </h2>
                  {historyLoading ? (
                    <div className="flex justify-center py-8">
                      <Loader2 className="h-6 w-6 animate-spin text-secondary-400" />
                    </div>
                  ) : history.length === 0 ? (
                    <p className="py-6 text-center text-pos-sm text-secondary-500">
                      No movements recorded yet for this item at this location.
                    </p>
                  ) : (
                    <div className="divide-y divide-secondary-100 rounded-lg border border-secondary-200">
                      {history.map((m) => {
                        const delta = toNumber(m.quantity);
                        return (
                          <div key={m.id} className="space-y-1 px-3 py-2">
                            <div className="flex items-center justify-between gap-2">
                              <Badge variant="secondary">
                                {m.transaction_type.replace(/_/g, " ")}
                              </Badge>
                              <span className="text-pos-xs text-secondary-500">
                                {formatDateTime(m.transaction_date)}
                              </span>
                            </div>
                            {/* Signed and colour-coded: the single most-read
                                number here is "did this go up or down". */}
                            <div className="flex flex-wrap items-baseline gap-x-3 text-pos-sm tabular-nums">
                              <span
                                className={cn(
                                  "font-medium",
                                  delta < 0 ? "text-danger-600" : "text-success-600",
                                )}
                              >
                                {delta > 0 ? "+" : ""}
                                {formatQty(m.quantity)} {m.unit}
                              </span>
                              <span className="text-secondary-700">
                                balance {formatQty(m.balance_after)} {m.unit}
                              </span>
                              {/* F43: what this movement was valued at, rather
                                  than what the ingredient costs today. */}
                              {toNumber(m.total_cost) > 0 && (
                                <span className="text-secondary-500">
                                  {formatMoney(toNumber(m.total_cost), currency)}
                                  {toNumber(m.unit_cost) > 0 &&
                                    ` @ ${formatMoney(toNumber(m.unit_cost), currency)}`}
                                </span>
                              )}
                            </div>
                            {/* A null performer is the system, not a gap in the
                                record: consumption from an online order has no
                                human behind it. */}
                            <div className="text-pos-xs text-secondary-500">
                              {m.performed_by_name ?? <span className="italic">System</span>}
                              {(m.notes ?? m.reference_number) && (
                                <> · {m.notes ?? m.reference_number}</>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </section>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <OpeningStockDialog
        open={showOpening}
        onClose={() => setShowOpening(false)}
        locations={locations}
        ingredients={ingredients}
        defaultLocationId={
          locationFilter ||
          (locations.find((l) => l.is_default) ?? locations[0])?.id ||
          ""
        }
        onSaved={() => void loadStock()}
      />

      {/* Run Production Dialog */}
      <Dialog open={showProduction} onOpenChange={setShowProduction}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Run Production</DialogTitle>
            <DialogDescription>
              Makes a sub-recipe batch. Raw ingredients are consumed and the
              produced ingredient is added to the chosen location.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Sub-recipe</Label>
              <Select
                value={prodRecipeId}
                onChange={(e) => setProdRecipeId(e.target.value)}
              >
                {subRecipes.map((recipe) => {
                  const producedId = producedIngredientId(recipe);
                  return (
                    <option key={recipe.id} value={recipe.id}>
                      {producedId ? ingredientName(producedId) : "Sub-recipe"}
                      {` (yield ${recipe.yield_servings})`}
                    </option>
                  );
                })}
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Location</Label>
              <Select
                value={prodLocationId}
                onChange={(e) => setProdLocationId(e.target.value)}
              >
                {locations.map((loc) => (
                  <option key={loc.id} value={loc.id}>
                    {loc.name}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Batches</Label>
              <Input
                type="number"
                min={1}
                step="any"
                value={prodBatches}
                onChange={(e) => setProdBatches(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowProduction(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => void handleProduction()}
              disabled={saving || !productionValid}
            >
              {saving ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                "Run Production"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default StockPage;
