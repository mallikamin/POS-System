/**
 * Danny's D-99: the screen facing the customer at the counter.
 *
 * Runs on a tablet or monitor signed in as staff. When a bill has just been
 * paid it shows that bill's QR, so the customer scans it straight off the
 * screen. Otherwise it is the restaurant's welcome: how the loyalty card
 * works and, when the shop has set its Google review link, a QR to rate the
 * restaurant (D-107). Polls; no buttons, nothing for a customer to press.
 *
 * D-106: customer-facing, so it wears the restaurant's own look (logo, black
 * marble and gold, classic serif), not the POS's.
 */
import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuthStore } from "@/stores/authStore";
import { useConfigStore } from "@/stores/configStore";
import { fetchCounterDisplay, type CounterDisplay } from "@/services/loyaltyApi";
import { LoyaltyQR, QRImage } from "@/components/loyalty/LoyaltyQR";
import { BrandMark, Eyebrow, GoldRule, LuxeShell, SERIF } from "@/components/loyalty/luxe";
import { formatPKR } from "@/utils/currency";

const POLL_MS = 3000;

function QRCard({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-2xl bg-gradient-to-br from-[#f0d79a] via-[#b8892e] to-[#f0d79a] p-[2px] shadow-[0_20px_60px_rgba(0,0,0,0.55)]">
      <div className="rounded-[14px] bg-[#fbf7ee] p-4">{children}</div>
    </div>
  );
}

/** How the card works at a glance: one stamp per visit, the last one is the reward. */
function StampRow({ total }: { total: number }) {
  const shown = Math.min(Math.max(total, 1), 10);
  return (
    <div className="flex items-center gap-3 py-2" aria-hidden>
      {Array.from({ length: shown }, (_, i) =>
        i === shown - 1 ? (
          <div
            key={i}
            style={SERIF}
            className="flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-[#f0d79a] to-[#b8892e] text-sm font-semibold uppercase tracking-wider text-[#1a150d] shadow-[0_0_24px_rgba(212,175,106,0.45)]"
          >
            Free
          </div>
        ) : (
          <div
            key={i}
            style={SERIF}
            className="flex h-11 w-11 items-center justify-center rounded-full border border-[#c9a24d]/50 text-lg text-[#e6c77a]/80"
          >
            {i + 1}
          </div>
        )
      )}
    </div>
  );
}

function Stars() {
  return (
    <p className="text-2xl tracking-[0.3em] text-[#e6c77a]" aria-label="Five stars">
      ★★★★★
    </p>
  );
}

export default function CustomerDisplayPage() {
  const { isAuthenticated } = useAuthStore();
  const config = useConfigStore((s) => s.config);
  const [display, setDisplay] = useState<CounterDisplay | null>(null);

  useEffect(() => {
    if (!isAuthenticated) return;
    void useConfigStore.getState().fetchConfig();
    let alive = true;
    const tick = () =>
      fetchCounterDisplay()
        .then((d) => alive && setDisplay(d))
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
  const slug = config?.tenant_slug;
  const reviewUrl = config?.google_review_url;
  const rule = display ? `${display.visits_required} visits = ${display.reward_label}` : null;

  // A bill was just paid: its QR, and nothing else to scan.
  if (display?.loyalty_code) {
    return (
      <LuxeShell className="flex flex-col items-center justify-center gap-7 px-8 py-10 text-center">
        <BrandMark slug={slug} name={name} size={104} />
        <div className="space-y-3">
          <Eyebrow>Thank you for dining with us</Eyebrow>
          <h1 style={SERIF} className="text-5xl font-semibold leading-tight md:text-6xl">
            Scan to collect your visit
          </h1>
        </div>
        <QRCard>
          <LoyaltyQR code={display.loyalty_code} size={300} />
        </QRCard>
        {rule && (
          <p style={SERIF} className="text-3xl italic text-[#e6c77a]">
            {rule}
          </p>
        )}
        <p className="text-sm tracking-wide text-[#f4ecdc]/50">
          Bill {display.order_number}
          {display.total != null ? ` · ${formatPKR(display.total)}` : ""}
        </p>
      </LuxeShell>
    );
  }

  // Welcome: the loyalty card, and the Google review when the shop has a link.
  return (
    <LuxeShell className="flex flex-col items-center justify-center gap-10 px-8 py-10 text-center">
      <div className="flex flex-col items-center gap-5">
        <BrandMark slug={slug} name={name} size={128} />
        <h1 style={SERIF} className="text-5xl font-semibold tracking-wide md:text-6xl">
          {name}
        </h1>
        <GoldRule className="w-72" />
      </div>

      <div className={`grid w-full max-w-5xl gap-8 ${reviewUrl ? "md:grid-cols-2" : "max-w-xl"}`}>
        <section className="flex flex-col items-center justify-center gap-4 rounded-3xl border border-[#c9a24d]/30 bg-white/[0.03] px-8 py-10 backdrop-blur">
          <Eyebrow>Loyalty card</Eyebrow>
          <h2 style={SERIF} className="text-4xl font-semibold leading-tight">
            Every visit counts
          </h2>
          {rule && (
            <p style={SERIF} className="text-3xl italic text-[#e6c77a]">
              {rule}
            </p>
          )}
          {display && <StampRow total={display.visits_required} />}
          <p className="max-w-sm text-lg font-light leading-relaxed text-[#f4ecdc]/75">
            Pay at the counter, then scan the code that appears on this screen to collect your
            visit. No app, just your mobile number.
          </p>
        </section>

        {reviewUrl && (
          <section className="flex flex-col items-center justify-center gap-4 rounded-3xl border border-[#c9a24d]/30 bg-white/[0.03] px-8 py-10 backdrop-blur">
            <Eyebrow>Enjoyed your meal?</Eyebrow>
            <h2 style={SERIF} className="text-4xl font-semibold leading-tight">
              Rate us on Google
            </h2>
            <Stars />
            <QRCard>
              <QRImage value={reviewUrl} alt="Google review link" size={180} />
            </QRCard>
            <p className="text-base font-light text-[#f4ecdc]/75">Scan to leave a review</p>
          </section>
        )}
      </div>
    </LuxeShell>
  );
}
