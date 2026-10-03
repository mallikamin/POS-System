/**
 * Danny's D-99: the page a customer reaches by scanning a bill's QR, on their
 * own phone. No login. One field (the mobile number), an optional name and a
 * consent tick, then their stamp card.
 *
 * Shows only this customer's own count, never anyone else's details.
 * D-106: customer-facing, so it wears the restaurant's own look.
 */
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { CheckCircle2, Loader2 } from "lucide-react";
import { isAxiosError } from "axios";
import {
  fetchClaimInfo,
  fetchGoogleWalletUrl,
  submitClaim,
  type PublicClaimInfo,
  type PublicClaimResult,
} from "@/services/loyaltyApi";
import { BrandMark, Eyebrow, GoldRule, LuxeShell, SERIF } from "@/components/loyalty/luxe";

function errorText(err: unknown, fallback: string): string {
  if (isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: unknown } | undefined)?.detail;
    if (typeof detail === "string") return detail;
  }
  return fallback;
}

function Stamps({ filled, total }: { filled: number; total: number }) {
  return (
    <div className="flex flex-wrap justify-center gap-2.5" aria-label={`${filled} of ${total} visits`}>
      {Array.from({ length: total }, (_, i) => (
        <div
          key={i}
          style={SERIF}
          className={
            "flex h-12 w-12 items-center justify-center rounded-full text-lg font-semibold " +
            (i < filled
              ? "bg-gradient-to-br from-[#f0d79a] to-[#b8892e] text-[#1a150d] shadow-[0_0_18px_rgba(212,175,106,0.35)]"
              : "border border-[#c9a24d]/40 text-[#c9a24d]/60")
          }
        >
          {i + 1}
        </div>
      ))}
    </div>
  );
}

const IS_IOS = /iPhone|iPad|iPod/i.test(navigator.userAgent);

const field =
  "h-12 w-full rounded-xl border border-[#c9a24d]/35 bg-black/30 px-4 text-base text-[#f4ecdc] " +
  "placeholder:text-[#f4ecdc]/35 focus:border-[#e6c77a] focus:outline-none focus:ring-1 focus:ring-[#e6c77a]";

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
  const [walletBusy, setWalletBusy] = useState(false);
  const [walletError, setWalletError] = useState<string | null>(null);

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

  async function addToGoogleWallet() {
    if (walletBusy) return;
    setWalletBusy(true);
    setWalletError(null);
    try {
      window.location.href = await fetchGoogleWalletUrl(code, phone);
    } catch (err) {
      setWalletError(errorText(err, "Google Wallet is not reachable right now. Please try again."));
      setWalletBusy(false);
    }
  }

  const shell = (children: React.ReactNode) => (
    <LuxeShell className="px-5 py-10">
      <div className="mx-auto max-w-sm space-y-7">{children}</div>
    </LuxeShell>
  );

  if (loadError) {
    return shell(<p className="pt-24 text-center text-lg font-light text-[#f4ecdc]/80">{loadError}</p>);
  }
  if (!info) {
    return shell(
      <div className="flex justify-center pt-32">
        <Loader2 className="h-8 w-8 animate-spin text-[#e6c77a]" />
      </div>
    );
  }

  const header = (
    <div className="flex flex-col items-center gap-4 text-center">
      <BrandMark slug={info.tenant_slug} name={info.restaurant_name} size={96} />
      <h1 style={SERIF} className="text-3xl font-semibold tracking-wide">
        {info.restaurant_name}
      </h1>
      <GoldRule className="w-48" />
      <p style={SERIF} className="text-2xl italic text-[#e6c77a]">
        {info.visits_required} visits = {info.reward_label}
      </p>
    </div>
  );

  if (done) {
    const filled = done.toward_next === 0 && done.rewards_available > 0 ? done.visits_required : done.toward_next;
    const title = {
      counted: "Visit counted. Thank you!",
      daily_limit: "You have collected all of today's visits.",
      // Dine-in: scanned at the table before paying.
      pending: "You're on the card.",
    }[done.result];
    return shell(
      <>
        {header}
        <div className="flex flex-col items-center gap-2 text-center">
          <CheckCircle2 className="h-10 w-10 text-[#e6c77a]" />
          <p style={SERIF} className="text-3xl font-semibold">
            {title}
          </p>
          {done.result === "pending" && (
            <p className="text-base font-light text-[#f4ecdc]/80">
              This visit is added as soon as the bill is paid.
            </p>
          )}
          <p className="text-xs tracking-wide text-[#f4ecdc]/50">Card for {done.phone}</p>
        </div>
        <Stamps filled={filled} total={done.visits_required} />
        <p className="text-center text-lg font-light leading-relaxed text-[#f4ecdc]/85">
          {done.rewards_available > 0
            ? `You have ${done.rewards_available} reward ready: ${done.reward_label}. Ask for it on your next visit.`
            : done.result === "pending"
              ? `${done.toward_next} of ${done.visits_required} so far, before this visit.`
              : `${done.visits_required - done.toward_next} more visit${done.visits_required - done.toward_next === 1 ? "" : "s"} to ${done.reward_label}.`}
        </p>
        {/* Google Wallet runs on Android; an iPhone gets the Apple card when it ships. */}
        {info.google_wallet && !IS_IOS && (
          <div className="flex flex-col items-center gap-3 pt-2">
            <p className="text-center text-sm font-light text-[#f4ecdc]/70">
              Keep your card on your phone and get a message after every visit.
            </p>
            <button
              type="button"
              onClick={addToGoogleWallet}
              disabled={walletBusy}
              aria-label="Add to Google Wallet"
              className="disabled:opacity-60"
            >
              {walletBusy ? (
                <Loader2 className="h-12 w-12 animate-spin text-[#e6c77a]" />
              ) : (
                <img src="/wallet/add-to-google-wallet.svg" alt="Add to Google Wallet" className="h-12 w-auto" />
              )}
            </button>
            {walletError && <p className="text-center text-sm text-red-200">{walletError}</p>}
          </div>
        )}
      </>
    );
  }

  if (info.status !== "open") {
    const msg = {
      counted: "This bill's visit has already been counted.",
      linked: "This bill is already linked to a customer's loyalty card.",
      pending: "This bill is already on a loyalty card. The visit is added when it's paid.",
      expired: "This code can no longer be used.",
      disabled: "The loyalty card isn't running at the moment.",
    }[info.status];
    return shell(
      <>
        {header}
        <p className="text-center text-lg font-light text-[#f4ecdc]/85">{msg}</p>
      </>
    );
  }

  return shell(
    <>
      {header}
      <div className="space-y-1 text-center">
        <Eyebrow>Loyalty card</Eyebrow>
        <p className="font-light text-[#f4ecdc]/75">Enter your mobile number to collect this visit.</p>
      </div>
      <form onSubmit={handleSubmit} className="space-y-4">
        <label className="block space-y-1.5">
          <span className="text-sm text-[#f4ecdc]/70">Mobile number</span>
          <input
            type="tel"
            inputMode="tel"
            autoComplete="tel"
            required
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="03xx xxxxxxx"
            className={field}
          />
        </label>
        <label className="block space-y-1.5">
          <span className="text-sm text-[#f4ecdc]/70">Name (optional)</span>
          <input
            type="text"
            autoComplete="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={100}
            className={field}
          />
        </label>
        <label className="flex items-start gap-3 text-sm font-light leading-relaxed text-[#f4ecdc]/75">
          <input
            type="checkbox"
            checked={consent}
            onChange={(e) => setConsent(e.target.checked)}
            className="mt-0.5 h-5 w-5 shrink-0 accent-[#c9a24d]"
          />
          <span>
            Join {info.restaurant_name}&apos;s loyalty card. My number is kept only to count my
            visits and is never sold or shared.{" "}
            <a href="/loyalty-privacy.html" target="_blank" rel="noopener" className="underline">
              Privacy and terms
            </a>
          </span>
        </label>
        {error && (
          <p className="rounded-xl border border-red-400/40 bg-red-500/10 p-3 text-sm text-red-200">{error}</p>
        )}
        <button
          type="submit"
          disabled={!consent || busy || phone.trim().length < 7}
          className="flex min-h-[52px] w-full items-center justify-center rounded-xl bg-gradient-to-r from-[#e6c77a] via-[#c9a24d] to-[#e6c77a] text-base font-medium uppercase tracking-[0.2em] text-[#1a150d] shadow-[0_10px_30px_rgba(201,162,77,0.25)] disabled:opacity-40"
        >
          {busy ? <Loader2 className="h-5 w-5 animate-spin" /> : "Collect my visit"}
        </button>
      </form>
      <p className="text-center text-xs tracking-wide text-[#f4ecdc]/40">Bill {info.order_number}</p>
    </>
  );
}
