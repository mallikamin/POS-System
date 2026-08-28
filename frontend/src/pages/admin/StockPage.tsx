import { useEffect, useState } from "react";
import { Factory, Loader2, Package, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
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

function StockPage() {
  const { toast } = useToast();
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

  // Adjust dialog
  const [adjustRow, setAdjustRow] = useState<LocationStockRow | null>(null);
  const [adjustDelta, setAdjustDelta] = useState("");
  const [adjustReason, setAdjustReason] = useState("");

  // Reorder dialog
  const [reorderRow, setReorderRow] = useState<LocationStockRow | null>(null);
  const [historyRow, setHistoryRow] = useState<LocationStockRow | null>(null);
  const [history, setHistory] = useState<StockMovementRow[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [reorderPoint, setReorderPoint] = useState("");
  const [reorderQuantity, setReorderQuantity] = useState("");

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

  function ingredientName(id: string): string {
    return ingredients.find((i) => i.id === id)?.name ?? "ingredient";
  }

  function ingredientUnit(id: string): string {
    return ingredients.find((i) => i.id === id)?.unit ?? "";
  }

  function openAdjust(row: LocationStockRow) {
    setAdjustRow(row);
    setAdjustDelta("");
    setAdjustReason("");
  }

  async function openHistory(row: LocationStockRow) {
    setHistoryRow(row);
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

  function openReorder(row: LocationStockRow) {
    setReorderRow(row);
    setReorderPoint(String(toNumber(row.reorder_point)));
    setReorderQuantity(String(toNumber(row.reorder_quantity)));
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
    Number.isFinite(adjustDeltaValue) &&
    adjustDeltaValue !== 0 &&
    adjustReason.trim().length > 0;

  const reorderPointValue = Number(reorderPoint);
  const reorderQuantityValue = Number(reorderQuantity);
  const reorderValid =
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
    if (!adjustRow || !adjustValid) return;
    setSaving(true);
    try {
      await adjustStock({
        ingredient_id: adjustRow.ingredient_id,
        location_id: adjustRow.location_id,
        quantity_delta: adjustDeltaValue,
        reason: adjustReason.trim(),
      });
      toast({
        title: "Stock adjusted",
        description: `${adjustDeltaValue > 0 ? "+" : ""}${adjustDeltaValue} ${
          adjustRow.unit
        } of ${adjustRow.ingredient_name} at ${adjustRow.location_name}.`,
        variant: "success",
      });
      setAdjustRow(null);
      await loadStock();
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
    if (!reorderRow || !reorderValid) return;
    setSaving(true);
    try {
      await setReorderLevel({
        ingredient_id: reorderRow.ingredient_id,
        location_id: reorderRow.location_id,
        reorder_point: reorderPointValue,
        reorder_quantity: reorderQuantityValue,
      });
      toast({
        title: "Reorder level saved",
        description: `${reorderRow.ingredient_name} reorders at ${reorderPointValue} ${reorderRow.unit}.`,
        variant: "success",
      });
      setReorderRow(null);
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

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Package className="h-7 w-7 text-primary-600" />
          <h1 className="text-pos-2xl font-bold text-secondary-900">
            Stock on Hand
          </h1>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={() => void loadStock()}
            disabled={refreshing}
            className="gap-2 min-h-[48px]"
          >
            <RefreshCw
              className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>
          <Button
            onClick={openProduction}
            disabled={subRecipes.length === 0}
            className="gap-2 min-h-[48px]"
          >
            <Factory className="h-4 w-4" />
            Run Production
          </Button>
        </div>
      </div>

      <Card>
        <CardContent className="flex flex-wrap items-end gap-6 pt-4">
          <div className="space-y-2 min-w-[240px]">
            <Label>Location</Label>
            <Select
              value={locationFilter}
              onChange={(e) => setLocationFilter(e.target.value)}
            >
              <option value="">All locations</option>
              {locations.map((loc) => (
                <option key={loc.id} value={loc.id}>
                  {loc.name}
                </option>
              ))}
            </Select>
          </div>
          <div className="flex items-center gap-2 pb-2">
            <Switch checked={lowOnly} onCheckedChange={setLowOnly} />
            <span className="text-sm text-secondary-600">Low stock only</span>
          </div>
        </CardContent>
      </Card>

      {rows.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-secondary-400">
            {lowOnly
              ? "Nothing is below its reorder point right now."
              : "No stock records for this selection."}
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-secondary-200 text-left text-secondary-500">
                  <th className="px-4 py-3 font-medium">Location</th>
                  <th className="px-4 py-3 font-medium">Ingredient</th>
                  <th className="px-4 py-3 font-medium text-right">Quantity</th>
                  <th className="px-4 py-3 font-medium text-right">
                    Reorder point
                  </th>
                  <th className="px-4 py-3 font-medium text-right">
                    Cost per unit
                  </th>
                  <th className="px-4 py-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr
                    key={`${row.location_id}:${row.ingredient_id}`}
                    className="border-b border-secondary-100 last:border-0"
                  >
                    <td className="px-4 py-3 text-secondary-700">
                      {row.location_name}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Thumb
                          src={row.ingredient_image_url}
                          alt={row.ingredient_name}
                          size="lg"
                        />
                        <span className="font-medium text-secondary-900">
                          {row.ingredient_name}
                        </span>
                        {row.is_produced && (
                          <Badge variant="secondary">Produced</Badge>
                        )}
                        {row.is_low && <Badge variant="warning">LOW</Badge>}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-secondary-900">
                      {formatQty(row.quantity)} {row.unit}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-secondary-600">
                      {formatQty(row.reorder_point)} {row.unit}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-secondary-600">
                      {formatMoney(toNumber(row.cost_per_unit), currency)}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => openAdjust(row)}
                        >
                          Adjust Stock
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openHistory(row)}
                        >
                          History
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openReorder(row)}
                        >
                          Set Reorder Level
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {/* Adjust Stock Dialog */}
      <Dialog
        open={adjustRow !== null}
        onOpenChange={(open) => {
          if (!open) setAdjustRow(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Adjust Stock</DialogTitle>
            <DialogDescription>
              {adjustRow
                ? `${adjustRow.ingredient_name} at ${adjustRow.location_name}. On hand: ${formatQty(adjustRow.quantity)} ${adjustRow.unit}.`
                : ""}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Quantity change ({adjustRow?.unit ?? "unit"})</Label>
              <Input
                type="number"
                step="any"
                value={adjustDelta}
                onChange={(e) => setAdjustDelta(e.target.value)}
                placeholder="e.g. 5 to add, -5 to remove"
              />
              <p className="text-xs text-secondary-500">
                Positive adds stock, negative removes it.
              </p>
            </div>
            <div className="space-y-2">
              <Label>Reason (required)</Label>
              <Textarea
                value={adjustReason}
                onChange={(e) => setAdjustReason(e.target.value)}
                placeholder="e.g. Spoilage, stock count correction, supplier shortfall"
              />
              <p className="text-xs text-secondary-500">
                This reason is recorded on the stock movement log against your
                user, so it stays auditable.
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAdjustRow(null)}>
              Cancel
            </Button>
            <Button
              onClick={() => void handleAdjust()}
              disabled={saving || !adjustValid}
            >
              {saving ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                "Save Adjustment"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Movement History Dialog
          Why the stock figure is what it is. Every movement this system has ever
          written for this ingredient at this site, newest first, with who did it
          and the reason they gave.

          🔴 This ledger has been written since the module shipped and had no
          reader at all until 2026-08-27: no endpoint, no screen. The mandatory
          reason on a manual adjustment went into the database and could never be
          seen again, which made "stock never changes without an explanation" a
          claim a customer had to take on trust. */}
      <Dialog
        open={historyRow !== null}
        onOpenChange={(open) => {
          if (!open) {
            setHistoryRow(null);
            setHistory([]);
          }
        }}
      >
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>Movement History</DialogTitle>
            <DialogDescription>
              {historyRow
                ? `Every change to ${historyRow.ingredient_name} at ${historyRow.location_name}, newest first.`
                : ""}
            </DialogDescription>
          </DialogHeader>

          {historyLoading ? (
            <div className="flex justify-center py-10">
              <Loader2 className="h-6 w-6 animate-spin text-secondary-400" />
            </div>
          ) : history.length === 0 ? (
            <p className="py-8 text-center text-pos-sm text-secondary-500">
              No movements recorded yet for this item at this location.
            </p>
          ) : (
            <div className="max-h-[60vh] overflow-y-auto">
              <table className="w-full text-pos-sm">
                <thead className="sticky top-0 bg-white">
                  <tr className="border-b border-secondary-200 text-left text-secondary-500">
                    <th className="px-3 py-2 font-medium">When</th>
                    <th className="px-3 py-2 font-medium">Type</th>
                    <th className="px-3 py-2 text-right font-medium">Change</th>
                    <th className="px-3 py-2 text-right font-medium">Balance</th>
                    {/* F43: the price paid on each movement was stored and
                        returned by the API all along, and shown nowhere. */}
                    <th className="px-3 py-2 text-right font-medium">
                      Unit price
                    </th>
                    <th className="px-3 py-2 text-right font-medium">Value</th>
                    <th className="px-3 py-2 font-medium">Who</th>
                    <th className="px-3 py-2 font-medium">Why</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((m) => {
                    const delta = toNumber(m.quantity);
                    return (
                      <tr
                        key={m.id}
                        className="border-b border-secondary-100 align-top"
                      >
                        <td className="whitespace-nowrap px-3 py-2 text-secondary-600">
                          {new Date(m.transaction_date).toLocaleString()}
                        </td>
                        <td className="px-3 py-2">
                          <Badge variant="secondary">
                            {m.transaction_type.replace(/_/g, " ")}
                          </Badge>
                        </td>
                        {/* Signed and colour-coded: the single most-read number
                            here is "did this go up or down". */}
                        <td
                          className={cn(
                            "whitespace-nowrap px-3 py-2 text-right tabular-nums font-medium",
                            delta < 0 ? "text-danger-600" : "text-success-600",
                          )}
                        >
                          {delta > 0 ? "+" : ""}
                          {formatQty(m.quantity)} {m.unit}
                        </td>
                        <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums text-secondary-700">
                          {formatQty(m.balance_after)} {m.unit}
                        </td>
                        {/* What this movement was actually valued at, rather
                            than what the ingredient costs today. A purchase
                            made at 3.50 stays 3.50 here after a later delivery
                            at 3.75. */}
                        <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums text-secondary-700">
                          {toNumber(m.unit_cost) > 0 ? (
                            formatMoney(toNumber(m.unit_cost), currency)
                          ) : (
                            <span className="text-secondary-300">--</span>
                          )}
                        </td>
                        <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums text-secondary-700">
                          {toNumber(m.total_cost) > 0 ? (
                            formatMoney(toNumber(m.total_cost), currency)
                          ) : (
                            <span className="text-secondary-300">--</span>
                          )}
                        </td>
                        {/* A null performer is the system, not a gap in the
                            record: consumption from an online order has no
                            human behind it. Say so rather than showing a dash
                            that reads as missing data. */}
                        <td className="px-3 py-2 text-secondary-600">
                          {m.performed_by_name ?? (
                            <span className="italic text-secondary-400">
                              System
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-2 text-secondary-600">
                          {m.notes ?? m.reference_number ?? (
                            <span className="text-secondary-300">--</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setHistoryRow(null)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reorder Level Dialog */}
      <Dialog
        open={reorderRow !== null}
        onOpenChange={(open) => {
          if (!open) setReorderRow(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Set Reorder Level</DialogTitle>
            <DialogDescription>
              {reorderRow
                ? `${reorderRow.ingredient_name} at ${reorderRow.location_name}. Flagged as low once stock falls below the reorder point.`
                : ""}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Reorder point ({reorderRow?.unit ?? "unit"})</Label>
              <Input
                type="number"
                min={0}
                step="any"
                value={reorderPoint}
                onChange={(e) => setReorderPoint(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>Reorder quantity ({reorderRow?.unit ?? "unit"})</Label>
              <Input
                type="number"
                min={0}
                step="any"
                value={reorderQuantity}
                onChange={(e) => setReorderQuantity(e.target.value)}
              />
              <p className="text-xs text-secondary-500">
                How much to buy or produce when the reorder point is hit.
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setReorderRow(null)}>
              Cancel
            </Button>
            <Button
              onClick={() => void handleReorder()}
              disabled={saving || !reorderValid}
            >
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : "Save"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

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
