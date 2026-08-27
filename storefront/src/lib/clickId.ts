/**
 * Google Ads click id capture.
 *
 * Auto-tagging (verified ON for account 758-817-4548, 2026-08-27) puts a
 * `gclid` on the landing URL when a visitor arrives from an ad. That parameter
 * is the only thing that ties a sale back to the click, and it is fragile: the
 * customer browses, the SPA moves them between views, and a card payer leaves
 * the domain entirely for Stripe and comes back to a fixed success_url with a
 * clean query string. So it is read once on arrival and kept.
 *
 * Everything here is best-effort and silent. A missing, malformed or
 * unstorable click id must never be able to affect an order: the worst
 * outcome allowed is a sale that is simply not attributed, which is exactly
 * how every order behaved before this file existed.
 */

/** Google's own click-id shape. Same bound the API applies server-side. */
const CLICK_ID_RE = /^[A-Za-z0-9_.-]{8,150}$/;

/**
 * The three parameters auto-tagging can land on.
 *
 * `gbraid` and `wbraid` are the iOS/privacy-safe variants. Google does not
 * treat them as interchangeable with `gclid` when a conversion is uploaded,
 * so which one arrived is recorded rather than guessed at later.
 *
 * Ordered: if more than one is somehow present, `gclid` is the most specific
 * and wins.
 */
const CLICK_PARAMS = ["gclid", "gbraid", "wbraid"] as const;
export type ClickType = (typeof CLICK_PARAMS)[number];

const STORAGE_KEY = "cs_click_id_v1";

/**
 * How long a stored click stays eligible to be credited.
 *
 * 30 days, matching the click-through window the conversion action was cut to
 * on 2026-08-25. A takeaway order happens the same evening; anything still
 * sitting here weeks later is far more likely to be a stale tab than a real
 * influence on tonight's dinner, and crediting it would teach Google the wrong
 * thing about which clicks are worth buying.
 */
const MAX_AGE_MS = 30 * 24 * 60 * 60 * 1000;

type Stored = { id: string; type: ClickType; at: number };

/**
 * Read a click id off the current URL, if there is one.
 *
 * Returns null for the overwhelmingly common case of an ordinary visit.
 */
function fromUrl(): Stored | null {
  try {
    const params = new URLSearchParams(window.location.search);
    for (const type of CLICK_PARAMS) {
      const raw = params.get(type);
      if (raw && CLICK_ID_RE.test(raw)) {
        return { id: raw, type, at: Date.now() };
      }
    }
  } catch {
    /* a URL we cannot parse is a visit with no ad, as far as this is concerned */
  }
  return null;
}

/**
 * Capture the click id on arrival. Call once, as early as possible.
 *
 * A NEW click always overwrites an older stored one. Last-click is the model
 * the conversion action is configured for, and it is also the honest answer:
 * if someone clicked an ad again today, today's click is the one that brought
 * them back.
 */
export function captureClickId(): void {
  const found = fromUrl();
  if (!found) return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(found));
  } catch {
    /* private mode, storage disabled, quota. The order still goes through. */
  }
}

/**
 * The click to credit this order to, or null.
 *
 * Read at the moment the basket is submitted, so it survives the whole browse
 * and, for a card payer, the round trip through Stripe.
 */
export function storedClickId(): { gclid: string; click_type: ClickType } | null {
  let raw: string | null = null;
  try {
    raw = window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
  if (!raw) return null;

  try {
    const stored = JSON.parse(raw) as Stored;
    const usable =
      typeof stored?.id === "string" &&
      CLICK_ID_RE.test(stored.id) &&
      (CLICK_PARAMS as readonly string[]).includes(stored.type) &&
      typeof stored.at === "number" &&
      Date.now() - stored.at < MAX_AGE_MS;
    return usable ? { gclid: stored.id, click_type: stored.type } : null;
  } catch {
    // Corrupt or from an older shape. Not worth clearing: the next real click
    // overwrites it, and until then it simply reads as "no ad".
    return null;
  }
}
