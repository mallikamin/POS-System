/**
 * Danny's D-99: the page a customer reaches by scanning a bill's QR, on their
 * own phone. No login. One field (the mobile number), an optional name and a
 * consent tick, then their stamp card.
 *
 * Shows only this customer's own count, never anyone else's details.
 */
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { CheckCircle2, Gift, Loader2 } from "lucide-react";
import { isAxiosError } from "axios";
import {
  fetchClaimInfo,
  submitClaim,
  type PublicClaimInfo,
  type PublicClaimResult,
} from "@/services/loyaltyApi";

function errorText(err: unknown, fallback: string): string {
  if (isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: unknown } | undefined)?.detail;
    if (typeof detail === "string") return detail;
  }
  return fallback;
}

function Stamps({ filled, total }: { filled: number; total: number }) {
  return (
    <div className="flex flex-wrap justify-center gap-2" aria-label={`${filled} of ${total} visits`}>
      {Array.from({ length: total }, (_, i) => (
        <div
          key={i}
          className={
            "flex h-11 w-11 items-center justify-center rounded-full border-2 text-sm font-bold " +
            (i < filled
              ? "border-primary-600 bg-primary-600 text-white"
              : "border-secondary-300 text-secondary-300")
          }
        >
          {i + 1}
        </div>
      ))}
    </div>
  );
}

export default function ClaimPage() {
  const { code = "" } = useParams();
  const [info, setInfo] = useState<PublicClaimInfo | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [phone, setPhone] = useState("");
  const [name, setName] = useState("");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<PublicClaimResult | null>(null);

  useEffect(() => {
    fetchClaimInfo(code)
      .then(setInfo)
      .catch((err) => setLoadError(errorText(err, "This code could not be found.")));
  }, [code]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!consent || busy) return;
    setBusy(true);
    setError(null);
    try {
      setDone(await submitClaim(code, { phone, name: name.trim() || undefined, consent }));
    } catch (err) {
      setError(errorText(err, "Something went wrong. Please try again."));
    } finally {
      setBusy(false);
    }
  }

  const shell = (children: React.ReactNode) => (
    <div className="min-h-dvh bg-secondary-50 px-4 py-8">
      <div className="mx-auto max-w-sm space-y-5 rounded-2xl bg-white p-6 shadow-sm">{children}</div>
    </div>
  );

  if (loadError) {
    return shell(<p className="text-center text-secondary-700">{loadError}</p>);
  }
  if (!info) {
    return shell(
      <div className="flex justify-center py-10">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    );
  }

  const header = (
    <div className="space-y-1 text-center">
      <h1 className="text-xl font-bold text-secondary-900">{info.restaurant_name}</h1>
      <p className="flex items-center justify-center gap-1.5 text-sm text-secondary-600">
        <Gift className="h-4 w-4 text-primary-600" />
        {info.visits_required} visits = {info.reward_label}
      </p>
    </div>
  );

  if (done) {
    const filled = done.toward_next === 0 && done.rewards_available > 0 ? done.visits_required : done.toward_next;
    return shell(
      <>
        {header}
        <div className="flex flex-col items-center gap-2 text-center">
          <CheckCircle2 className="h-10 w-10 text-success-600" />
          <p className="text-lg font-semibold text-secondary-900">
            {done.result === "counted" ? "Visit counted. Thank you!" : "You have collected all of today's visits."}
          </p>
          <p className="text-xs text-secondary-500">Card for {done.phone}</p>
        </div>
        <Stamps filled={filled} total={done.visits_required} />
        <p className="text-center font-medium text-secondary-800">
          {done.rewards_available > 0
            ? `You have ${done.rewards_available} reward ready: ${done.reward_label}. Ask the cashier on your next visit.`
            : `${done.visits_required - done.toward_next} more visit${done.visits_required - done.toward_next === 1 ? "" : "s"} to ${done.reward_label}.`}
        </p>
      </>
    );
  }

  if (info.status !== "open") {
    const msg = {
      counted: "This bill's visit has already been counted.",
      linked: "This bill is already linked to a customer's loyalty card.",
      unpaid: "This bill isn't paid yet. Scan again once it's paid.",
      expired: "This code can no longer be used.",
      disabled: "The loyalty card isn't running at the moment.",
    }[info.status];
    return shell(
      <>
        {header}
        <p className="text-center text-secondary-700">{msg}</p>
      </>
    );
  }

  return shell(
    <>
      {header}
      <form onSubmit={handleSubmit} className="space-y-4">
        <label className="block space-y-1">
          <span className="text-sm font-medium text-secondary-700">Mobile number</span>
          <input
            type="tel"
            inputMode="tel"
            autoComplete="tel"
            required
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="03xx xxxxxxx"
            className="h-12 w-full rounded-lg border border-secondary-300 px-3 text-base focus:border-primary-500 focus:outline-none"
          />
        </label>
        <label className="block space-y-1">
          <span className="text-sm font-medium text-secondary-700">Name (optional)</span>
          <input
            type="text"
            autoComplete="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={100}
            className="h-12 w-full rounded-lg border border-secondary-300 px-3 text-base focus:border-primary-500 focus:outline-none"
          />
        </label>
        <label className="flex items-start gap-3 text-sm text-secondary-700">
          <input
            type="checkbox"
            checked={consent}
            onChange={(e) => setConsent(e.target.checked)}
            className="mt-0.5 h-5 w-5 shrink-0"
          />
          <span>
            Join {info.restaurant_name}&apos;s loyalty card. My number is kept only to count my
            visits and is never sold or shared.
          </span>
        </label>
        {error && <p className="rounded bg-danger-50 p-2 text-sm text-danger-700">{error}</p>}
        <button
          type="submit"
          disabled={!consent || busy || phone.trim().length < 7}
          className="flex h-12 w-full items-center justify-center rounded-lg bg-primary-600 font-semibold text-white disabled:opacity-50"
        >
          {busy ? <Loader2 className="h-5 w-5 animate-spin" /> : "Collect my visit"}
        </button>
      </form>
      <p className="text-center text-xs text-secondary-400">Bill {info.order_number}</p>
    </>
  );
}
