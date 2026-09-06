/**
 * Production (Martin M9).
 *
 * > "There is no production menu where I can produce subrecipes (example,
 * >  producing tomato sauce or dough or anything) and then this will be added
 * >  as stock (+ sauce) and at same time the ingredient reduced (-tomato raw
 * >  item)"
 *
 * The engine already did exactly that. What was missing was a place to find it:
 * `run_production` was reachable only through a button on the Stock screen, the
 * word "Production" appeared nowhere in the admin menu, and a finished run left
 * two stock movements that nothing listed.
 *
 * So this screen is three things:
 *
 *  1. **A menu entry.** It is what Martin went looking for.
 *  2. **A preview before the button.** He thinks "make 1600 g of sauce", not
 *     "run the recipe twice", and the preview is computed on the SERVER so the
 *     numbers shown are the numbers that will move. Both quantity and batches
 *     are accepted here; whichever he types, the other follows.
 *  3. **A history.** "What did we make yesterday" had no answer before.
 *
 * Built mobile-first (M12): the run panel and the history stack on a phone, and
 * the history is a card list below `sm` rather than a table nobody can read.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  Factory,
  Loader2,
  RefreshCw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { formatMoney, getActiveCurrency } from "@/utils/currency";
import {
  fetchLocations,
  fetchProductionRuns,
  previewProduction,
  runProduction,
} from "@/services/locationsApi";
import { fetchRecipes } from "@/services/inventoryApi";
import { cn } from "@/lib/utils";
import type {
  Location,
  ProductionPreview,
  ProductionRun,
} from "@/types/location";
import type { Recipe } from "@/types/inventory";

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
 * Exactly one of `menu_item_id` and `produces_ingredient_id` is set on every
 * recipe. Only the second kind can be produced into stock: a burger is made to
 * order and sold, not produced onto a shelf.
 */
function producedIngredientId(recipe: Recipe): string | null {
  if (!("produces_ingredient_id" in recipe)) return null;
  const value = recipe.produces_ingredient_id;
  return typeof value === "string" && value.length > 0 ? value : null;
}

function recipeLabel(recipe: Recipe): string {
  if ("produces_ingredient_name" in recipe && recipe.produces_ingredient_name) {
    return String(recipe.produces_ingredient_name);
  }
  return "Sub-recipe";
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

function ProductionPage() {
  const { toast } = useToast();
  const currency = getActiveCurrency();

  const [locations, setLocations] = useState<Location[]>([]);
  const [subRecipes, setSubRecipes] = useState<Recipe[]>([]);
  const [runs, setRuns] = useState<ProductionRun[]>([]);

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [running, setRunning] = useState(false);

  const [recipeId, setRecipeId] = useState("");
  const [locationId, setLocationId] = useState("");
  const [batches, setBatches] = useState("1");
  const [reference, setReference] = useState("");

  const [preview, setPreview] = useState<ProductionPreview | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const selectedRecipe = useMemo(
    () => subRecipes.find((r) => r.id === recipeId) ?? null,
    [subRecipes, recipeId],
  );

  const batchesValue = toNumber(batches);
  const canRun =
    recipeId.length > 0 && locationId.length > 0 && batchesValue > 0;

  const loadRuns = useCallback(async () => {
    const rows = await fetchProductionRuns({ limit: 50 });
    setRuns(rows);
  }, []);

  useEffect(() => {
    void (async () => {
      try {
        const [sites, recipes] = await Promise.all([
          fetchLocations(),
          fetchRecipes(),
        ]);
        setLocations(sites);
        const producible = recipes.filter(
          (r) => producedIngredientId(r) !== null,
        );
        setSubRecipes(producible);

        const preferred = sites.find((s) => s.is_default) ?? sites[0];
        if (preferred) setLocationId(preferred.id);
        const first = producible[0];
        if (first) setRecipeId(first.id);

        await loadRuns();
      } catch (err) {
        toast({
          title: "Could not load production",
          description: errorMessage(err, "Sites and recipes are unavailable."),
          variant: "destructive",
        });
      } finally {
        setLoading(false);
      }
    })();
  }, [loadRuns, toast]);

  /*
   * The preview is debounced rather than fired on every keystroke: typing "12"
   * would otherwise ask the server about 1 batch and then 12, and the two
   * answers can arrive out of order.
   */
  useEffect(() => {
    if (!canRun) {
      setPreview(null);
      setPreviewError(null);
      return;
    }
    let cancelled = false;
    setPreviewing(true);
    const timer = setTimeout(() => {
      void (async () => {
        try {
          const result = await previewProduction({
            recipe_id: recipeId,
            batches: batchesValue,
            location_id: locationId,
          });
          if (!cancelled) {
            setPreview(result);
            setPreviewError(null);
          }
        } catch (err) {
          if (!cancelled) {
            setPreview(null);
            setPreviewError(
              errorMessage(err, "This recipe cannot be produced into stock."),
            );
          }
        } finally {
          if (!cancelled) setPreviewing(false);
        }
      })();
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [recipeId, locationId, batchesValue, canRun]);

  /**
   * Type the amount you want to make, and the batch count follows.
   *
   * A chef asks for 5 kg of sauce; the recipe happens to yield 800 g a batch.
   * Doing the division for him is the difference between a screen he uses and
   * one he works around. The batch count is left as a fraction rather than
   * rounded, because the server is happy to run 6.25 batches and rounding would
   * quietly make more sauce than he asked for.
   */
  function setFromOutput(rawOutput: string) {
    const output = toNumber(rawOutput);
    const perBatch = preview
      ? toNumber(preview.yield_per_batch)
      : toNumber(selectedRecipe?.yield_servings);
    if (perBatch <= 0 || output <= 0) return;
    setBatches(String(Number((output / perBatch).toFixed(4))));
  }

  async function handleRefresh() {
    setRefreshing(true);
    try {
      await loadRuns();
    } catch (err) {
      toast({
        title: "Could not refresh",
        description: errorMessage(err, "The run history is unavailable."),
        variant: "destructive",
      });
    } finally {
      setRefreshing(false);
    }
  }

  async function handleRun() {
    if (!canRun || running) return;
    setRunning(true);
    try {
      const result = await runProduction({
        recipe_id: recipeId,
        batches: batchesValue,
        location_id: locationId,
        ...(reference.trim() ? { reference_number: reference.trim() } : {}),
      });
      toast({
        title: `Produced ${formatQty(result.produced_quantity)} ${
          preview?.produced_unit ?? ""
        } of ${result.recipe_name}`.trim(),
        description: `${result.consumed.length} ingredient(s) came off the shelf at ${result.location_name}. Reference ${result.reference_number}.`,
        variant: "success",
      });
      setReference("");
      await loadRuns();
    } catch (err) {
      toast({
        title: "Nothing was produced",
        description: errorMessage(err, "No stock was moved."),
        variant: "destructive",
      });
    } finally {
      setRunning(false);
    }
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    );
  }

  return (
    <div className="space-y-4 sm:space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-secondary-900 sm:text-2xl">
            Production
          </h1>
          <p className="mt-1 text-sm text-secondary-500">
            Make a batch of something you produce in-house. The output goes onto
            the shelf and the ingredients come off it.
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() => void handleRefresh()}
          disabled={refreshing}
          className="min-h-[44px] gap-2"
        >
          <RefreshCw className={cn("h-4 w-4", refreshing && "animate-spin")} />
          Refresh
        </Button>
      </div>

      {subRecipes.length === 0 ? (
        <Card>
          <CardContent className="p-6 text-center">
            <Factory className="mx-auto h-10 w-10 text-secondary-300" />
            <p className="mt-3 font-medium text-secondary-800">
              Nothing is made in-house yet
            </p>
            <p className="mt-1 text-sm text-secondary-500">
              Mark an ingredient as "Made in-house" on the Ingredients screen,
              then build the recipe that makes it. It will appear here.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {/* ---- Make a batch ------------------------------------------ */}
          <Card>
            <CardContent className="space-y-4 p-4 sm:p-6">
              <h2 className="font-semibold text-secondary-900">Make a batch</h2>

              <div className="space-y-2">
                <Label htmlFor="prod-recipe">What are you making?</Label>
                <Select
                  id="prod-recipe"
                  value={recipeId}
                  onChange={(e) => setRecipeId(e.target.value)}
                  className="min-h-[48px]"
                >
                  {subRecipes.map((recipe) => (
                    <option key={recipe.id} value={recipe.id}>
                      {recipeLabel(recipe)}
                    </option>
                  ))}
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="prod-site">Where</Label>
                <Select
                  id="prod-site"
                  value={locationId}
                  onChange={(e) => setLocationId(e.target.value)}
                  className="min-h-[48px]"
                >
                  {locations.map((site) => (
                    <option key={site.id} value={site.id}>
                      {site.name}
                    </option>
                  ))}
                </Select>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="prod-output">
                    How much do you want{preview ? ` (${preview.produced_unit})` : ""}?
                  </Label>
                  <Input
                    id="prod-output"
                    type="number"
                    inputMode="decimal"
                    min="0"
                    value={
                      preview ? String(toNumber(preview.produced_quantity)) : ""
                    }
                    onChange={(e) => setFromOutput(e.target.value)}
                    className="min-h-[48px]"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="prod-batches">Batches</Label>
                  <Input
                    id="prod-batches"
                    type="number"
                    inputMode="decimal"
                    min="0"
                    step="0.25"
                    value={batches}
                    onChange={(e) => setBatches(e.target.value)}
                    className="min-h-[48px]"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="prod-ref">Reference (optional)</Label>
                <Input
                  id="prod-ref"
                  value={reference}
                  onChange={(e) => setReference(e.target.value)}
                  placeholder="Left blank, one is generated"
                  className="min-h-[48px]"
                />
              </div>

              <Button
                onClick={() => void handleRun()}
                disabled={!canRun || running || previewing || !preview}
                className="min-h-[52px] w-full gap-2"
              >
                {running ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                  <Factory className="h-5 w-5" />
                )}
                {running ? "Producing..." : "Produce"}
              </Button>
            </CardContent>
          </Card>

          {/* ---- What will happen -------------------------------------- */}
          <Card>
            <CardContent className="space-y-4 p-4 sm:p-6">
              <h2 className="font-semibold text-secondary-900">
                What this will do
              </h2>

              {previewError && (
                <p className="rounded-lg bg-danger-50 p-3 text-sm text-danger-700">
                  {previewError}
                </p>
              )}

              {previewing && !preview && (
                <div className="flex items-center gap-2 text-sm text-secondary-500">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Working it out...
                </div>
              )}

              {preview && (
                <div className="space-y-4">
                  <div className="rounded-lg bg-success-50 p-3">
                    <p className="text-xs font-medium uppercase tracking-wide text-success-700">
                      Onto the shelf
                    </p>
                    <p className="mt-1 text-lg font-semibold text-success-900">
                      + {formatQty(preview.produced_quantity)}{" "}
                      {preview.produced_unit} {preview.produced_ingredient_name}
                    </p>
                    <p className="mt-1 text-xs text-success-700">
                      Worth {formatMoney(toNumber(preview.total_cost), currency)}{" "}
                      at {formatMoney(toNumber(preview.unit_cost), currency)} per{" "}
                      {preview.produced_unit}
                    </p>
                  </div>

                  <div>
                    <p className="text-xs font-medium uppercase tracking-wide text-secondary-500">
                      Off the shelf
                    </p>
                    <ul className="mt-2 space-y-2">
                      {preview.consumes.map((line) => (
                        <li
                          key={line.ingredient_id}
                          className={cn(
                            "flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 rounded-lg p-2 text-sm",
                            toNumber(line.shortfall) > 0
                              ? "bg-danger-50"
                              : "bg-secondary-50",
                          )}
                        >
                          <span className="font-medium text-secondary-900">
                            {line.ingredient_name}
                          </span>
                          <span className="tabular-nums text-secondary-700">
                            &minus; {formatQty(line.quantity)} {line.unit}
                          </span>
                          <span className="w-full text-xs text-secondary-500">
                            {formatQty(line.available)} {line.unit} on hand
                            {toNumber(line.shortfall) > 0 && (
                              <span className="ml-1 font-medium text-danger-700">
                                &mdash; {formatQty(line.shortfall)} {line.unit}{" "}
                                short
                              </span>
                            )}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  {preview.has_shortfall && (
                    <p className="flex items-start gap-2 rounded-lg bg-warning-50 p-3 text-sm text-warning-800">
                      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                      <span>
                        There is not enough on hand for this batch. Producing it
                        anyway is allowed and will leave a negative balance, so
                        the shortage is visible rather than hidden.
                      </span>
                    </p>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* ---- History -------------------------------------------------- */}
      <div>
        <h2 className="mb-3 font-semibold text-secondary-900">
          Recent production
        </h2>
        {runs.length === 0 ? (
          <Card>
            <CardContent className="p-6 text-center text-sm text-secondary-500">
              Nothing has been produced yet.
            </CardContent>
          </Card>
        ) : (
          <>
            {/* Phone: one card per run. A seven-column table on a 360px
                screen is unreadable however it scrolls (M12). */}
            <div className="space-y-3 sm:hidden">
              {runs.map((run) => (
                <Card key={`${run.reference_number}-${run.produced_at}`}>
                  <CardContent className="space-y-2 p-4">
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="font-medium text-secondary-900">
                        {run.produced_ingredient_name}
                      </span>
                      <span className="tabular-nums font-semibold text-success-700">
                        + {formatQty(run.quantity)} {run.unit}
                      </span>
                    </div>
                    <p className="text-xs text-secondary-500">
                      {new Date(run.produced_at).toLocaleString()} &middot;{" "}
                      {run.location_name ?? "No site"}
                      {run.performed_by_name && ` · ${run.performed_by_name}`}
                    </p>
                    <p className="text-xs text-secondary-600">
                      {run.consumed
                        .map(
                          (line) =>
                            `${line.ingredient_name} ${formatQty(line.quantity)} ${line.unit}`,
                        )
                        .join(", ") || "No inputs recorded"}
                    </p>
                    <p className="text-xs text-secondary-500">
                      {formatMoney(toNumber(run.total_cost), currency)} &middot;{" "}
                      {run.reference_number}
                    </p>
                  </CardContent>
                </Card>
              ))}
            </div>

            {/* Tablet and up: the table, with a real minimum width so its
                scroller actually scrolls instead of crushing the columns. */}
            <Card className="hidden sm:block">
              <CardContent className="overflow-x-auto p-0">
                <table className="w-full min-w-[46rem] text-sm">
                  <thead className="border-b border-secondary-200 bg-secondary-50 text-left text-xs uppercase tracking-wide text-secondary-500">
                    <tr>
                      <th className="px-4 py-3 font-medium">When</th>
                      <th className="px-4 py-3 font-medium">Produced</th>
                      <th className="px-4 py-3 font-medium">Quantity</th>
                      <th className="px-4 py-3 font-medium">Consumed</th>
                      <th className="px-4 py-3 font-medium">Cost</th>
                      <th className="px-4 py-3 font-medium">Site</th>
                      <th className="px-4 py-3 font-medium">Reference</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-secondary-100">
                    {runs.map((run) => (
                      <tr key={`${run.reference_number}-${run.produced_at}`}>
                        <td className="whitespace-nowrap px-4 py-3 text-secondary-600">
                          {new Date(run.produced_at).toLocaleString()}
                        </td>
                        <td className="px-4 py-3 font-medium text-secondary-900">
                          {run.produced_ingredient_name}
                        </td>
                        <td className="whitespace-nowrap px-4 py-3 tabular-nums text-success-700">
                          + {formatQty(run.quantity)} {run.unit}
                        </td>
                        <td className="px-4 py-3 text-secondary-600">
                          {run.consumed.length === 0 ? (
                            <span className="text-secondary-400">&mdash;</span>
                          ) : (
                            <ul className="space-y-0.5">
                              {run.consumed.map((line) => (
                                <li key={line.ingredient_id}>
                                  <ArrowRight className="mr-1 inline h-3 w-3 text-secondary-400" />
                                  {line.ingredient_name}{" "}
                                  {formatQty(line.quantity)} {line.unit}
                                </li>
                              ))}
                            </ul>
                          )}
                        </td>
                        <td className="whitespace-nowrap px-4 py-3 tabular-nums text-secondary-700">
                          {formatMoney(toNumber(run.total_cost), currency)}
                        </td>
                        <td className="px-4 py-3 text-secondary-600">
                          {run.location_name ?? "—"}
                        </td>
                        <td className="whitespace-nowrap px-4 py-3 text-xs text-secondary-500">
                          {run.reference_number}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </div>
  );
}

export default ProductionPage;
