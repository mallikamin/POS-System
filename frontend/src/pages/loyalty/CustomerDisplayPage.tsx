/**
 * Danny's D-99: the screen facing the customer at the counter.
 *
 * Runs on a cheap tablet or monitor signed in as staff. Shows the QR of the
 * bill just paid (newest paid, unclaimed bill from the last few minutes), so
 * the customer scans it straight off the screen. Once it is claimed, or after
 * a few minutes, it falls back to a welcome card. Polls; no buttons, nothing
 * for a customer to press.
 */
import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { Gift } from "lucide-react";
import { useAuthStore } from "@/stores/authStore";
import { useConfigStore } from "@/stores/configStore";
import { fetchCounterDisplay, type CounterDisplay } from "@/services/loyaltyApi";
import { LoyaltyQR } from "@/components/loyalty/LoyaltyQR";
import { formatPKR } from "@/utils/currency";

const POLL_MS = 3000;

export default function CustomerDisplayPage() {
  const { isAuthenticated } = useAuthStore();
  const config = useConfigStore((s) => s.config);
  const [current, setCurrent] = useState<CounterDisplay | null>(null);

  useEffect(() => {
    if (!isAuthenticated) return;
    void useConfigStore.getState().fetchConfig();
    let alive = true;
    const tick = () =>
      fetchCounterDisplay()
        .then((d) => alive && setCurrent(d))
        .catch(() => undefined);
    tick();
    const id = setInterval(tick, POLL_MS);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [isAuthenticated]);

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  const name = config?.restaurant_name ?? "";

  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-8 bg-white p-8 text-center">
      <h1 className="text-3xl font-bold text-secondary-900 md:text-4xl">{name}</h1>
      {current ? (
        <>
          <p className="text-2xl font-semibold text-secondary-800 md:text-3xl">
            Scan to collect your visit
          </p>
          <LoyaltyQR code={current.loyalty_code} size={300} />
          <p className="flex items-center gap-2 text-xl text-secondary-700">
            <Gift className="h-6 w-6 text-primary-600" />
            {current.visits_required} visits = {current.reward_label}
          </p>
          <p className="text-sm text-secondary-400">
            Bill {current.order_number} · {formatPKR(current.total)}
          </p>
        </>
      ) : (
        <>
          <Gift className="h-20 w-20 text-primary-600" />
          <p className="text-2xl font-semibold text-secondary-800 md:text-3xl">
            Thank you for visiting
          </p>
          <p className="max-w-md text-lg text-secondary-600">
            Pay at the counter, then scan the code that appears here to collect a visit
            on your loyalty card.
          </p>
        </>
      )}
    </div>
  );
}
