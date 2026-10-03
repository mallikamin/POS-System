/**
 * Danny's D-106: the look of every CUSTOMER-facing loyalty screen (the counter
 * screen and the claim page on the customer's phone). Black marble and gold,
 * taken from the restaurant's own logo; a classic serif for headings
 * (Cormorant Garamond) over a clean geometric sans (Jost).
 *
 * The fonts are bundled (@fontsource, OFL-1.1) and imported only here, so they
 * load with these lazy pages and never touch the POS or admin screens.
 */
import type { ReactNode } from "react";
import "@fontsource/cormorant-garamond/500.css";
import "@fontsource/cormorant-garamond/600.css";
import "@fontsource/cormorant-garamond/500-italic.css";
import "@fontsource/jost/300.css";
import "@fontsource/jost/400.css";
import "@fontsource/jost/500.css";
import { tenantBrand } from "@/lib/tenantBranding";

// Lining numerals: Cormorant's default old-style digits sit low and read small
// in stamp counts and "5 visits".
export const SERIF = {
  fontFamily: "'Cormorant Garamond', Georgia, serif",
  fontVariantNumeric: "lining-nums",
} as const;
const SANS = { fontFamily: "'Jost', system-ui, sans-serif" } as const;

/** Full-height black marble page with a soft gold glow; ivory text. */
export function LuxeShell({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div
      style={{
        ...SANS,
        background:
          "radial-gradient(ellipse at 50% 0%, rgba(212,175,106,0.16), transparent 60%)," +
          "radial-gradient(ellipse at 100% 100%, rgba(255,255,255,0.05), transparent 55%)," +
          "linear-gradient(160deg, #141210 0%, #0b0a09 55%, #16130f 100%)",
      }}
      className={`min-h-dvh text-[#f4ecdc] ${className}`}
    >
      {children}
    </div>
  );
}

/** The restaurant's logo in a thin gold ring, or its initial when it has none. */
export function BrandMark({ slug, name, size = 120 }: { slug?: string | null; name: string; size?: number }) {
  const brand = tenantBrand(slug);
  return (
    <div
      className="flex items-center justify-center rounded-full p-[3px] shadow-[0_0_40px_rgba(212,175,106,0.25)]"
      style={{ width: size, height: size, background: "linear-gradient(135deg, #f0d79a, #b8892e 50%, #f0d79a)" }}
    >
      {brand ? (
        <img src={brand.logo} alt={name} className="h-full w-full rounded-full object-cover" />
      ) : (
        <div style={SERIF} className="flex h-full w-full items-center justify-center rounded-full bg-[#0b0a09] text-5xl text-[#e6c77a]">
          {name.trim().charAt(0)}
        </div>
      )}
    </div>
  );
}

/** A thin gold rule with a centred diamond. */
export function GoldRule({ className = "" }: { className?: string }) {
  return (
    <div className={`flex items-center gap-3 ${className}`} aria-hidden>
      <span className="h-px flex-1 bg-gradient-to-r from-transparent to-[#c9a24d]" />
      <span className="h-1.5 w-1.5 rotate-45 bg-[#e6c77a]" />
      <span className="h-px flex-1 bg-gradient-to-l from-transparent to-[#c9a24d]" />
    </div>
  );
}

/** Small spaced capitals in gold, for labels above headings. */
export function Eyebrow({ children }: { children: ReactNode }) {
  return <p className="text-xs font-medium uppercase tracking-[0.35em] text-[#d4af6a]">{children}</p>;
}
