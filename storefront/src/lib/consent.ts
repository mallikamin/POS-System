/**
 * Cookie consent for the Google Ads tag.
 *
 * UK PECR: an advertising cookie may not be set until the visitor has agreed.
 * `index.html` therefore pushes `consent default: denied` before gtag.js loads,
 * and nothing here can set a cookie on its own — the only thing this module
 * does is tell an already-loaded tag whether it is now allowed to.
 *
 * The choice is stored in localStorage rather than a cookie, deliberately:
 * storing "no thanks" in a cookie means setting a cookie to record that the
 * customer did not want cookies.
 */

/** Bumping this re-asks everyone. Only bump if what we collect changes. */
const STORAGE_KEY = "cs_consent_v1";

export type ConsentChoice = "granted" | "denied";

type GtagArgs =
  | ["consent", "update", Record<string, "granted" | "denied">]
  | ["event", string, Record<string, unknown>];

/**
 * Push to the tag if it is there.
 *
 * An ad blocker, a failed script load or a very early call all land here, and
 * none of them are errors worth surfacing to a customer buying chicken — the
 * order matters, the measurement does not. `dataLayer` exists from the inline
 * block in `index.html`, so queued calls still replay if gtag.js arrives late.
 */
function push(...args: GtagArgs): void {
  const w = window as unknown as { gtag?: (...a: unknown[]) => void };
  try {
    w.gtag?.(...args);
  } catch {
    /* measurement is never allowed to break the shop */
  }
}

/** What the visitor decided last time, or null if they have not been asked. */
export function storedConsent(): ConsentChoice | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw === "granted" || raw === "denied" ? raw : null;
  } catch {
    // Private mode, or storage disabled. Treat as "never asked": the banner
    // shows again next visit, which is the safe direction to fail in.
    return null;
  }
}

function remember(choice: ConsentChoice): void {
  try {
    localStorage.setItem(STORAGE_KEY, choice);
  } catch {
    /* nothing to do; the banner simply reappears next time */
  }
}

function apply(choice: ConsentChoice): void {
  push("consent", "update", {
    ad_storage: choice,
    ad_user_data: choice,
    ad_personalization: choice,
    analytics_storage: choice,
  });
}

export function grantConsent(): void {
  remember("granted");
  apply("granted");
}

export function denyConsent(): void {
  remember("denied");
  apply("denied");
}

/**
 * Replay a previous decision on page load.
 *
 * Without this a returning customer who already agreed would be measured as
 * denied for the whole visit, because `index.html` re-defaults to denied on
 * every load. Only "granted" needs replaying — denied is already the default,
 * and re-sending it would be a no-op.
 */
export function replayStoredConsent(): void {
  if (storedConsent() === "granted") apply("granted");
}
