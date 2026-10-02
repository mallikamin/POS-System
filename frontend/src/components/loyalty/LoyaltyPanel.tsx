/**
 * Danny's D-99: loyalty on the payment screen. Shows the customer's stamp
 * card when the bill carries their phone, and the "Apply reward" button when a
 * reward is due AND the reward item is on this bill. Hidden entirely when the
 * tenant has loyalty off, or the bill has no customer and no code.
 */
import { useCallback, useEffect, useState } from "react";
import { Gift, Loader2 } from "lucide-react";
import { isAxiosError } from "axios";
import { Button } from "@/components/ui/button";
import {
  fetchOrderLoyalty,
  redeemReward,
  type OrderLoyaltyStatus,
} from "@/services/loyaltyApi";

interface LoyaltyPanelProps {
  orderId: string;
  /** Called after a reward is applied, so the page reloads its totals. */
  onRedeemed?: () => void;
}

export function LoyaltyPanel({ orderId, onRedeemed }: LoyaltyPanelProps) {
  const [st, setSt] = useState<OrderLoyaltyStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    fetchOrderLoyalty(orderId).then(setSt).catch(() => setSt(null));
  }, [orderId]);

  useEffect(load, [load]);

  if (!st || !st.enabled) return null;
  const p = st.progress;
  if (!p && !st.loyalty_code) return null;

  async function apply() {
    setBusy(true);
    setError(null);
    try {
      await redeemReward(orderId);
      load();
      onRedeemed?.();
    } catch (err) {
      const d = isAxiosError(err) ? (err.response?.data as { detail?: unknown })?.detail : null;
      setError(typeof d === "string" ? d : "Could not apply the reward.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-lg border border-primary-200 bg-primary-50 p-3 text-sm">
      <div className="flex items-center gap-2 font-semibold text-primary-800">
        <Gift className="h-4 w-4" /> Loyalty
      </div>
      {p ? (
        <div className="mt-1 space-y-1 text-secondary-700">
          <p>
            {p.customer_name}: {p.toward_next} of {p.visits_required} visits
            {p.rewards_available > 0 && (
              <span className="font-semibold text-success-700">
                {" "}· {p.rewards_available} reward ready ({p.reward_label})
              </span>
            )}
          </p>
          {st.redeemed_on_this_bill && (
            <p className="font-medium text-success-700">Reward applied to this bill.</p>
          )}
          {p.rewards_available > 0 && !st.redeemed_on_this_bill && !st.reward_on_bill && (
            <p className="text-xs text-secondary-500">
              Add the reward item to the order to give it free.
            </p>
          )}
          {st.can_redeem && (
            <Button size="sm" onClick={apply} disabled={busy} className="mt-1 gap-1">
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Gift className="h-4 w-4" />}
              Apply reward: {p.reward_label}
            </Button>
          )}
        </div>
      ) : (
        <p className="mt-1 text-secondary-600">
          No phone on this bill. The customer can scan the QR on the receipt after paying.
        </p>
      )}
      {error && <p className="mt-1 text-danger-700">{error}</p>}
    </div>
  );
}
