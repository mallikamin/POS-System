/**
 * "We want to make this much this week. What do we need to buy?"
 *
 * 🔴 Every number on this screen is COMPUTED on the server: the production
 * target is exploded through the recipe tree down to raw ingredients, what is
 * already in stock and already on order is subtracted, and the remainder is
 * rounded up to whole packs. No model invents a quantity. The optional AI
 * review reads the finished plan and adds judgement it cannot act on.
 *
 * Money is MINOR UNITS end to end; `formatMoney` divides by 100 itself.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ChefHat,
  Info,
  Loader2,
  Plus,
  Sparkles,
  Trash2,
  Truck,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/hooks/use-toast";
import { useConfigStore } from "@/stores/configStore";
import { formatMoney } from "@/utils/currency";
import {
  createPurchaseOrder,
  suggestOrder,
} from "@/services/procurementApi";
import { fetchLocations } from "@/services/locationsApi";
import { fetchRecipes } from "@/services/inventoryApi";
import type { SuggestionResponse } from "@/types/procurement";
import type { Location } from "@/types/location";
import type { Recipe } from "@/types/inventory";

interface TargetRow {
  uid: string;
  recipe_id: string;
  batches: string;
}

let targetCounter = 0;
function newTarget(): TargetRow {
  targetCounter += 1;
  return { uid: `target-${targetCounter}`, recipe_id: "", batches: "" };
}

function minor(value: string | null | undefined): number {
  const n = Number(value ?? 0);
  return Number.isFinite(n) ? n : 0;
}

function num(value: string | null | undefined): number {
  const n = Number(value ?? 0);
  return Number.isFinite(n) ? n : 0;
}

function errorDetail(error: unknown, fallback = "Please try again."): string {
  return (
    (error as { response?: { data?: { detail?: string } } })?.response?.data
      ?.detail ?? fallback
  );
}

function recipeLabel(recipe: Recipe): string {
  return (
    recipe.menu_item_name ||
    recipe.produces_ingredient_name ||
    "Untitled recipe"
  );
}

function OrderPlannerPage() {
  const { toast } = useToast();
  const config = useConfigStore((s) => s.config);
  const currency = config?.currency ?? "AED";

  const [locations, setLocations] = useState<Location[]>([]);
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [locationId, setLocationId] = useState("");
  const [targets, setTargets] = useState<TargetRow[]>([newTarget()]);
  const [daysUntil, setDaysUntil] = useState("7");
  const [wantAdvice, setWantAdvice] = useState(true);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [raising, setRaising] = useState<string | null>(null);
  const [plan, setPlan] = useState<SuggestionResponse | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [locs, recipeRows] = await Promise.all([
        fetchLocations(),
        fetchRecipes(),
      ]);
      setLocations(locs);
      setRecipes(recipeRows.filter((r) => r.is_active !== false));
      setLocationId(locs.find((l) => l.is_default)?.id ?? locs[0]?.id ?? "");
    } catch {
      toast({ title: "Could not load the planner", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  // A target is something you decide to MAKE. Sub-recipes are reachable too --
  // "make 40 kg of dough" is a legitimate week's plan on its own.
  const sellable = useMemo(
    () => recipes.filter((r) => !!r.menu_item_id),
    [recipes],
  );
  const subRecipes = useMemo(
    () => recipes.filter((r) => !r.menu_item_id),
    [recipes],
  );

  async function run() {
    const usable = targets.filter(
      (t) => t.recipe_id && Number(t.batches) > 0,
    );
    if (usable.length === 0) {
      toast({
        title: "Set a target first",
        description: "Pick what you are making and how much.",
        variant: "destructive",
      });
      return;
    }
    setRunning(true);
    try {
      const result = await suggestOrder({
        location_id: locationId || null,
        days_until_production: daysUntil === "" ? null : Number(daysUntil),
        include_advice: wantAdvice,
        targets: usable.map((t) => ({
          recipe_id: t.recipe_id,
          batches: t.batches,
        })),
      });
      setPlan(result);
      if (wantAdvice && result.advice_error) {
        // Said out loud rather than silently omitted: the plan is complete,
        // only the commentary is missing, and the reason matters.
        toast({
          title: "Plan ready, without the AI review",
          description: result.advice_error,
        });
      }
    } catch (error) {
      toast({
        title: "Could not work out the plan",
        description: errorDetail(error),
        variant: "destructive",
      });
    } finally {
      setRunning(false);
    }
  }

  async function raiseOrder(basketIndex: number) {
    if (!plan) return;
    const basket = plan.baskets[basketIndex];
    if (!basket) return;
    setRaising(basket.supplier_id);
    try {
      const po = await createPurchaseOrder({
        supplier_id: basket.supplier_id,
        location_id: plan.location_id,
        tax_bps: config?.default_tax_rate ?? 0,
        lines: basket.lines.map((line) => ({
          ingredient_id: line.ingredient_id,
          quantity_ordered: line.suggested_quantity,
          unit_price_minor: line.unit_price_minor,
        })),
        notes: `Raised from the ordering plan for ${plan.location_name}.`,
      });
      toast({
        title: `${po.po_number} drafted`,
        description: `${basket.supplier_name}. Review and send it from Purchase Orders.`,
      });
    } catch (error) {
      toast({
        title: "Could not raise the order",
        description: errorDetail(error),
        variant: "destructive",
      });
    } finally {
      setRaising(null);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-secondary-900">Order planner</h1>
        <p className="text-sm text-secondary-500">
          Say what you are making this week. It works out what to buy from your
          recipes, your stock and what is already on order.
        </p>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16 text-secondary-500">
          <Loader2 className="mr-2 h-5 w-5 animate-spin" />
          Loading
        </div>
      ) : recipes.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-16 text-center">
            <ChefHat className="h-10 w-10 text-secondary-300" />
            <p className="text-secondary-600">No recipes yet.</p>
            <p className="max-w-md text-sm text-secondary-500">
              The planner works out what to buy by exploding your recipes down
              to raw ingredients. Build a recipe first and it will have
              something to work from.
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* --------------------------------------------------- the target */}
          <Card>
            <CardContent className="space-y-4 p-4">
              <div className="grid gap-4 md:grid-cols-3">
                <div>
                  <Label>Making it at</Label>
                  <Select
                    value={locationId}
                    onChange={(e) => setLocationId(e.target.value)}
                  >
                    {locations.map((l) => (
                      <option key={l.id} value={l.id}>
                        {l.name}
                      </option>
                    ))}
                  </Select>
                </div>
                <div>
                  <Label>Production starts in (days)</Label>
                  <Input
                    type="number"
                    min={0}
                    value={daysUntil}
                    onChange={(e) => setDaysUntil(e.target.value)}
                  />
                  <p className="mt-1 text-xs text-secondary-500">
                    Used to judge supplier lead times.
                  </p>
                </div>
                <div className="flex items-end">
                  <label className="flex items-center gap-2 pb-2 text-sm text-secondary-600">
                    <input
                      type="checkbox"
                      className="h-4 w-4"
                      checked={wantAdvice}
                      onChange={(e) => setWantAdvice(e.target.checked)}
                    />
                    Add an AI review of the plan
                  </label>
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>What are you making?</Label>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setTargets([...targets, newTarget()])}
                  >
                    <Plus className="mr-1 h-4 w-4" />
                    Add
                  </Button>
                </div>
                {targets.map((target, index) => (
                  <div key={target.uid} className="grid gap-2 md:grid-cols-12">
                    <div className="md:col-span-8">
                      <Select
                        value={target.recipe_id}
                        onChange={(e) => {
                          const next = [...targets];
                          next[index] = {
                            ...target,
                            recipe_id: e.target.value,
                          };
                          setTargets(next);
                        }}
                      >
                        <option value="">Select what you are making</option>
                        {sellable.length > 0 && (
                          <optgroup label="Products">
                            {sellable.map((r) => (
                              <option key={r.id} value={r.id}>
                                {recipeLabel(r)}
                              </option>
                            ))}
                          </optgroup>
                        )}
                        {subRecipes.length > 0 && (
                          <optgroup label="Sub-recipes (made in-house)">
                            {subRecipes.map((r) => (
                              <option key={r.id} value={r.id}>
                                {recipeLabel(r)}
                              </option>
                            ))}
                          </optgroup>
                        )}
                      </Select>
                    </div>
                    <div className="md:col-span-3">
                      <Input
                        type="number"
                        step="0.001"
                        min={0}
                        placeholder="How many"
                        value={target.batches}
                        onChange={(e) => {
                          const next = [...targets];
                          next[index] = { ...target, batches: e.target.value };
                          setTargets(next);
                        }}
                      />
                    </div>
                    <div className="md:col-span-1 flex items-center">
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={targets.length === 1}
                        onClick={() =>
                          setTargets(
                            targets.filter((t) => t.uid !== target.uid),
                          )
                        }
                      >
                        <Trash2 className="h-4 w-4 text-danger-600" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>

              <Button disabled={running} onClick={() => void run()}>
                {running && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Work out what to buy
              </Button>
            </CardContent>
          </Card>

          {plan && (
            <>
              {/* ------------------------------------------------ the advice */}
              {plan.advice && (
                <Card className="border-primary-200 bg-primary-50">
                  <CardContent className="space-y-2 p-4">
                    <div className="flex items-center gap-2 text-sm font-medium text-secondary-900">
                      <Sparkles className="h-4 w-4" />
                      AI review of this plan
                    </div>
                    <p className="text-sm text-secondary-700">
                      {plan.advice.summary}
                    </p>
                    {plan.advice.risks.length > 0 && (
                      <ul className="ml-5 list-disc text-sm text-secondary-700">
                        {plan.advice.risks.map((risk, i) => (
                          <li key={i}>{risk}</li>
                        ))}
                      </ul>
                    )}
                    {plan.advice.order_first.length > 0 && (
                      <p className="text-sm text-secondary-700">
                        Send first: {plan.advice.order_first.join(", ")}
                      </p>
                    )}
                    <p className="text-xs text-secondary-500">
                      Commentary only. Every quantity below was calculated from
                      your recipes and stock, not written by the AI.
                    </p>
                  </CardContent>
                </Card>
              )}
              {plan.advice_error && (
                <Card className="border-warning-200 bg-warning-50">
                  <CardContent className="flex gap-2 p-4 text-sm text-secondary-700">
                    <Info className="mt-0.5 h-4 w-4 shrink-0" />
                    <span>
                      The plan below is complete. The AI review is missing:{" "}
                      {plan.advice_error}
                    </span>
                  </CardContent>
                </Card>
              )}

              {/* -------------------------------------------- what to make */}
              {plan.production_plan.length > 0 && (
                <Card>
                  <CardContent className="p-4">
                    <p className="mb-2 text-sm font-medium text-secondary-900">
                      To make in-house
                    </p>
                    <p className="mb-3 text-xs text-secondary-500">
                      These are produced from your own recipes, so they are not
                      bought. Their raw ingredients are in the shopping list
                      below instead.
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {plan.production_plan.map((row) => (
                        <Badge key={row.ingredient_id} variant="secondary">
                          {row.ingredient_name} · {num(row.quantity_to_make)}{" "}
                          {row.unit}
                        </Badge>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* ------------------------------------------------- baskets */}
              {plan.baskets.map((basket, index) => (
                <Card key={basket.supplier_id}>
                  <CardContent className="p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2 font-semibold text-secondary-900">
                          <Truck className="h-4 w-4" />
                          {basket.supplier_name}
                        </div>
                        <div className="text-xs text-secondary-500">
                          {basket.lines.length} item
                          {basket.lines.length === 1 ? "" : "s"}
                          {basket.lead_time_days !== null &&
                            ` · ${basket.lead_time_days} day lead time`}
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-lg font-semibold">
                          {formatMoney(
                            minor(basket.estimated_total_minor),
                            currency,
                          )}
                        </span>
                        <Button
                          size="sm"
                          disabled={raising === basket.supplier_id}
                          onClick={() => void raiseOrder(index)}
                        >
                          {raising === basket.supplier_id && (
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          )}
                          Draft this order
                        </Button>
                      </div>
                    </div>

                    <table className="mt-3 w-full text-sm">
                      <thead className="text-left text-xs uppercase tracking-wide text-secondary-500">
                        <tr>
                          <th className="py-1">Item</th>
                          <th className="py-1 text-right">Needed</th>
                          <th className="py-1 text-right">In stock</th>
                          <th className="py-1 text-right">On order</th>
                          <th className="py-1 text-right">Order</th>
                          <th className="py-1 text-right">Cost</th>
                        </tr>
                      </thead>
                      <tbody>
                        {basket.lines.map((line) => (
                          <tr
                            key={line.ingredient_id}
                            className="border-t border-secondary-100"
                          >
                            <td className="py-2">
                              {line.ingredient_name}
                              {num(line.pack_size) > 0 && (
                                <span className="ml-2 text-xs text-secondary-500">
                                  {num(line.pack_size)} {line.unit} packs
                                </span>
                              )}
                            </td>
                            <td className="py-2 text-right">
                              {num(line.required)} {line.unit}
                            </td>
                            <td className="py-2 text-right">
                              {num(line.on_hand)}
                            </td>
                            <td className="py-2 text-right">
                              {num(line.on_order)}
                            </td>
                            <td className="py-2 text-right font-medium">
                              {num(line.suggested_quantity)} {line.unit}
                            </td>
                            <td className="py-2 text-right">
                              {formatMoney(
                                minor(line.estimated_cost_minor),
                                currency,
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </CardContent>
                </Card>
              ))}

              {/* ----------------------------------------------- unsourced */}
              {plan.unsourced.length > 0 && (
                <Card className="border-warning-200">
                  <CardContent className="p-4">
                    <div className="mb-2 flex items-center gap-2 text-sm font-medium text-warning-700">
                      <AlertTriangle className="h-4 w-4" />
                      Needed, but no supplier on file
                    </div>
                    <p className="mb-3 text-xs text-secondary-500">
                      These cannot be turned into a purchase order until you add
                      a supplier who sells them.
                    </p>
                    <ul className="space-y-1 text-sm text-secondary-700">
                      {plan.unsourced.map((line) => (
                        <li key={line.ingredient_id}>
                          {line.ingredient_name} ·{" "}
                          {num(line.suggested_quantity)} {line.unit}
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              )}

              {plan.baskets.length === 0 && plan.unsourced.length === 0 && (
                <Card>
                  <CardContent className="py-10 text-center text-secondary-600">
                    Nothing needs ordering. Stock on hand and what is already on
                    order cover this production target.
                  </CardContent>
                </Card>
              )}

              <div className="text-right text-sm text-secondary-600">
                {/* F45: supplier prices are ex VAT; the purchase order this
                    becomes adds VAT on top, so say so or the two totals look
                    like a bug next to each other (693.75 here, 728.44 there). */}
                Estimated total, before VAT{" "}
                <span className="text-lg font-semibold text-secondary-900">
                  {formatMoney(minor(plan.estimated_total_minor), currency)}
                </span>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}

export default OrderPlannerPage;
