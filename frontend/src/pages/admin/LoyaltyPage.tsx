/**
 * Danny's D-99: visit loyalty, admin side. The rules (on/off, visits per
 * reward, which menu item is the reward) and the member list. The counter
 * screen opens from here.
 */
import { useEffect, useMemo, useState } from "react";
import { ExternalLink, Gift, Loader2, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { toast } from "@/hooks/use-toast";
import api from "@/lib/axios";
import { useConfigStore } from "@/stores/configStore";
import { useMenuStore } from "@/stores/menuStore";
import { fetchMembers, type LoyaltyProgress } from "@/services/loyaltyApi";

export default function LoyaltyPage() {
  const config = useConfigStore((s) => s.config);
  const categories = useMenuStore((s) => s.categories);
  const [enabled, setEnabled] = useState(false);
  const [visits, setVisits] = useState(5);
  // Visits one customer can earn per day; "" = no limit (sent as 0).
  const [perDay, setPerDay] = useState("1");
  const [rewardItemId, setRewardItemId] = useState("");
  const [label, setLabel] = useState("");
  const [saving, setSaving] = useState(false);
  const [members, setMembers] = useState<LoyaltyProgress[] | null>(null);

  useEffect(() => {
    void useMenuStore.getState().loadMenu();
    fetchMembers().then(setMembers).catch(() => setMembers([]));
  }, []);

  useEffect(() => {
    if (!config) return;
    setEnabled(config.loyalty_enabled);
    setVisits(config.loyalty_visits_required || 5);
    setPerDay(config.loyalty_max_visits_per_day > 0 ? String(config.loyalty_max_visits_per_day) : "");
    setRewardItemId(config.loyalty_reward_menu_item_id ?? "");
    setLabel(config.loyalty_reward_label ?? "");
  }, [config]);

  const items = useMemo(
    () => categories.flatMap((c) => (c.items ?? []).map((i) => ({ id: i.id, name: i.name, cat: c.name }))),
    [categories]
  );

  async function save() {
    setSaving(true);
    try {
      await api.patch("/config/restaurant", {
        loyalty_enabled: enabled,
        loyalty_visits_required: visits,
        loyalty_max_visits_per_day: perDay === "" ? 0 : Math.max(1, Math.min(20, parseInt(perDay, 10) || 1)),
        loyalty_reward_menu_item_id: rewardItemId,
        loyalty_reward_label: label,
      });
      await useConfigStore.getState().fetchConfig();
      toast({ title: "Loyalty saved", variant: "success" });
    } catch {
      toast({ title: "Could not save loyalty settings", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  }

  const rewardName = items.find((i) => i.id === rewardItemId)?.name;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Gift className="h-7 w-7 text-primary-600" />
          <h1 className="text-pos-2xl font-bold text-secondary-900">Loyalty</h1>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" className="min-h-[48px] gap-2" asChild>
            <a href="/customer-display" target="_blank" rel="noreferrer">
              <ExternalLink className="h-4 w-4" /> Counter screen
            </a>
          </Button>
          <Button onClick={save} disabled={saving} className="min-h-[48px] gap-2">
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            Save
          </Button>
        </div>
      </div>

      <Card>
        <CardContent className="space-y-4 pt-6">
          <div className="flex items-center justify-between rounded-lg border p-4">
            <div>
              <Label>Loyalty card</Label>
              <p className="text-pos-sm text-secondary-500">
                Every paid bill can earn one visit: the cashier adds the customer&apos;s phone,
                or the customer scans the QR on the bill or the counter screen. One visit per
                bill; a bill with the customer&apos;s phone on it counts only for that customer.
              </p>
            </div>
            <Switch checked={enabled} onCheckedChange={setEnabled} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="space-y-2">
              <Label htmlFor="visits">Visits per reward</Label>
              <Input
                id="visits"
                type="number"
                min={1}
                max={50}
                value={visits}
                onChange={(e) => setVisits(Math.max(1, Math.min(50, parseInt(e.target.value, 10) || 1)))}
                className="min-h-[48px]"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="perDay">Max visits per customer per day</Label>
              <Input
                id="perDay"
                type="number"
                min={1}
                max={20}
                value={perDay}
                placeholder="No limit"
                onChange={(e) => setPerDay(e.target.value === "" ? "" : String(Math.max(1, Math.min(20, parseInt(e.target.value, 10) || 1))))}
                className="min-h-[48px]"
                aria-describedby="perDayHelp"
              />
              <p id="perDayHelp" className="text-pos-sm text-secondary-500">
                Leave empty for no limit. With no limit, one meal split into several bills can
                earn several visits.
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="rewardItem">Reward item (given free)</Label>
              <select
                id="rewardItem"
                value={rewardItemId}
                onChange={(e) => setRewardItemId(e.target.value)}
                className="h-12 w-full rounded-md border border-secondary-300 bg-white px-3 text-sm"
              >
                <option value="">Choose a menu item</option>
                {items.map((i) => (
                  <option key={i.id} value={i.id}>
                    {i.name} ({i.cat})
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="rewardLabel">What the customer sees</Label>
              <Input
                id="rewardLabel"
                value={label}
                maxLength={80}
                onChange={(e) => setLabel(e.target.value)}
                placeholder={rewardName ? `Free ${rewardName}` : "Free coffee"}
                className="min-h-[48px]"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="space-y-3 pt-6">
          <h2 className="text-pos-lg font-semibold text-secondary-800">
            Members {members ? `(${members.length})` : ""}
          </h2>
          {members === null ? (
            <Loader2 className="h-6 w-6 animate-spin text-primary-600" />
          ) : members.length === 0 ? (
            <p className="text-sm text-secondary-500">No visits yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-secondary-500">
                  <tr>
                    <th className="py-2 pr-3">Customer</th>
                    <th className="py-2 pr-3">Phone</th>
                    <th className="py-2 pr-3 text-right">Visits</th>
                    <th className="py-2 pr-3 text-right">Card</th>
                    <th className="py-2 pr-3 text-right">Rewards ready</th>
                    <th className="py-2 pr-3 text-right">Given</th>
                    <th className="py-2">Last visit</th>
                  </tr>
                </thead>
                <tbody>
                  {members.map((m) => (
                    <tr key={m.customer_id} className="border-t border-secondary-100">
                      <td className="py-2 pr-3">{m.customer_name}</td>
                      <td className="py-2 pr-3">{m.phone}</td>
                      <td className="py-2 pr-3 text-right">{m.total_visits}</td>
                      <td className="py-2 pr-3 text-right">
                        {m.toward_next}/{m.visits_required}
                      </td>
                      <td className="py-2 pr-3 text-right font-semibold">{m.rewards_available}</td>
                      <td className="py-2 pr-3 text-right">{m.rewards_redeemed}</td>
                      <td className="py-2">{m.last_visit ?? "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
