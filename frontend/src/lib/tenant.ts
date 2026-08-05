/**
 * Which restaurant is this browser logging in to?
 *
 * One backend now serves several restaurants, and a **PIN is only unique
 * inside one of them**. The login routes therefore need to be told which shop
 * they are talking to. Previously the server guessed, which meant a staff
 * member could be authenticated into a different restaurant entirely if their
 * four digits happened to collide.
 *
 * Resolution order, most specific first:
 *
 *   1. `?shop=<slug>` in the URL. This is what a shop gets bookmarked with,
 *      e.g. `/login?shop=chick-shack`. It is remembered afterwards, because
 *      the tablet will be reopened, sent to `/online-orders` directly, and
 *      bounced back to a login page that no longer carries the parameter.
 *   2. A previously remembered slug from this device.
 *   3. `VITE_TENANT_SLUG` baked in at build time, for a deployment that only
 *      ever serves one restaurant.
 *   4. Nothing — in which case the server falls back to the single active
 *      tenant, and only refuses if there is genuinely more than one. That is
 *      what keeps existing single-restaurant deployments working untouched.
 */

const STORAGE_KEY = "pos.tenant.slug";

export function rememberTenantFromUrl(): void {
  try {
    const fromUrl = new URLSearchParams(window.location.search).get("shop");
    if (fromUrl && fromUrl.trim()) {
      window.localStorage.setItem(STORAGE_KEY, fromUrl.trim());
    }
  } catch {
    // Private browsing can refuse localStorage. Losing the slug means the
    // login form asks for it again; it is not worth breaking the page over.
  }
}

export function getTenantSlug(): string | undefined {
  try {
    const fromUrl = new URLSearchParams(window.location.search).get("shop");
    if (fromUrl && fromUrl.trim()) return fromUrl.trim();

    const remembered = window.localStorage.getItem(STORAGE_KEY);
    if (remembered) return remembered;
  } catch {
    // fall through to the build-time default
  }

  const baked = import.meta.env.VITE_TENANT_SLUG as string | undefined;
  return baked && baked.trim() ? baked.trim() : undefined;
}

/** Remember a slug typed by a human, rather than one arriving via `?shop=`. */
export function setTenantSlug(slug: string): void {
  try {
    const clean = slug.trim();
    if (clean) window.localStorage.setItem(STORAGE_KEY, clean);
    else window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Private browsing can refuse localStorage. The slug still reaches this
    // login attempt through the form itself; only the memory of it is lost.
  }
}

export function clearTenantSlug(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* nothing to do */
  }
}
