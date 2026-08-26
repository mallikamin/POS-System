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

/**
 * The slug carried by `?shop=` on the current URL, if any.
 *
 * Split out from the resolution order below because callers need to ask "is
 * this URL asking for a specific shop?" separately from "which shop is this
 * device using?". `LoginPage` needs the difference to notice that the URL is
 * asking for a different tenant than the one already signed in.
 */
/**
 * Is there a signed-in session on this device, read before React mounts?
 *
 * `main.tsx` has to decide whether `?shop=` may overwrite the remembered slug
 * before the first render, so it cannot ask the auth store through a hook. The
 * store persists under `auth-storage` via zustand's `persist` middleware, so the
 * answer is already sitting in localStorage.
 *
 * Deliberately conservative: any parse failure returns `true`, i.e. "assume a
 * session exists, do not overwrite". Wrongly keeping the old slug asks a user to
 * pick their shop again; wrongly replacing it points a tablet at the wrong
 * restaurant. Those are not equally bad.
 */
export function hasPersistedSession(): boolean {
  try {
    const raw = window.localStorage.getItem("auth-storage");
    if (!raw) return false;
    const parsed = JSON.parse(raw) as { state?: { isAuthenticated?: boolean } };
    return Boolean(parsed?.state?.isAuthenticated);
  } catch {
    return true;
  }
}

export function tenantSlugFromUrl(): string | undefined {
  try {
    const fromUrl = new URLSearchParams(window.location.search).get("shop");
    return fromUrl && fromUrl.trim() ? fromUrl.trim() : undefined;
  } catch {
    return undefined;
  }
}

/**
 * Persist a slug arriving via `?shop=`, so a tablet bookmarked with it keeps
 * working after it is bounced to a login page that no longer carries it.
 *
 * 🔴 **Refuses to overwrite while somebody is signed in.** This used to write
 * unconditionally at app boot, before any auth check, which meant ANY url could
 * silently repoint a device at a different restaurant with no authentication at
 * all. Two consequences, found in UAT on 2026-08-27:
 *
 *   1. The switch-account screen showed one tenant's slug inside another
 *      tenant's session, because it reads this value.
 *   2. Far worse and not yet seen in the wild: a shop tablet that ever opened a
 *      link carrying someone else's `?shop=` would keep it, and the next PIN
 *      sign-in on that tablet would be aimed at the wrong restaurant. A PIN is
 *      only unique inside one tenant. That is precisely the failure OI-69 was
 *      opened to prevent.
 *
 * A signed-in session is the authority on which shop this device is using.
 * `?shop=` is an input to a LOGIN, so it may only be persisted when there is no
 * session to contradict it. `LoginPage` handles the "signed in, but the URL asks
 * for a different shop" case explicitly, by signing out first.
 */
export function rememberTenantFromUrl(hasSession: boolean): void {
  if (hasSession) return;
  try {
    const fromUrl = tenantSlugFromUrl();
    if (fromUrl) {
      window.localStorage.setItem(STORAGE_KEY, fromUrl);
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
