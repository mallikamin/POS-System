import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { LogOut, Store, UserCircle } from "lucide-react";
import { useAuthStore } from "@/stores/authStore";
import { useConfigStore } from "@/stores/configStore";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { clearTenantSlug, getTenantSlug } from "@/lib/tenant";

/**
 * The way out (OI-69).
 *
 * A website-only tenant lands on `/online-orders`, which is mounted outside
 * both layouts so it can run fullscreen on the shop's tablet — and the layouts
 * are where the app's only logout buttons live. `/login` is no escape either:
 * it redirects an authenticated user to `/`, and `/` redirects a website-only
 * tenant straight back to `/online-orders`. The loop closes, and the only way
 * out was to know that `/admin` happens to be typeable. Malik: *"once im
 * logged in chick shack, theres no way for me to logout — im stuck in this
 * window."*
 *
 * **This is deliberately a separate bookmarked route rather than a button on
 * the queue.** That tablet sits unattended in a live shop during service. A
 * "Sign out" in its header is one mis-tap away from locking the counter out
 * mid-rush, and getting back in needs a PIN that whoever is on shift may not
 * have. Nothing here appears on the shop's screen at all — you arrive on
 * purpose, by URL or bookmark.
 *
 * It clears the remembered tenant slug as well as the session, which ordinary
 * `logout()` deliberately does not: a staff member signing out on the tablet
 * must come back to the same shop, whereas someone arriving here is asking to
 * change which one.
 */
export default function SwitchPage() {
  const { isAuthenticated, user, logout } = useAuthStore();
  const config = useConfigStore((s) => s.config);
  const navigate = useNavigate();
  const [signingOut, setSigningOut] = useState(false);

  // Nothing to sign out of — go straight to the login form, which is where the
  // restaurant picker lives.
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  /*
   * 🔴 Both of these read the SESSION, not the device.
   *
   * This screen used to show `config?.name` (a field that does not exist on the
   * response -- the API returns `restaurant_name`, so it was always undefined
   * and the screen permanently read "Restaurant not loaded") next to
   * `getTenantSlug()`, which prefers `?shop=` from the URL and otherwise reads
   * localStorage. The combination meant that opening a link for one restaurant
   * while signed in to another displayed the second one's slug underneath the
   * first one's user. Found in UAT on 2026-08-27. Nothing crossed tenants, but
   * showing a client another client's slug is not something to leave standing.
   *
   * The session knows which shop it belongs to. Ask it.
   */
  const shopName = config?.restaurant_name;
  const shopSlug = config?.tenant_slug ?? getTenantSlug();

  function handleSwitch() {
    setSigningOut(true);
    // Order matters: `logout()` clears the config store, and clearing the slug
    // afterwards means the login form opens with no restaurant assumed.
    logout();
    clearTenantSlug();
    navigate("/login", { replace: true });
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-secondary-900 p-4">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <h1 className="text-pos-3xl font-bold text-white">Switch account</h1>
          <p className="mt-2 text-pos-sm text-secondary-400">
            Sign out, then sign back in as another user or another restaurant.
          </p>
        </div>

        <Card className="border-secondary-700 bg-secondary-800 shadow-2xl">
          <CardHeader>
            <CardTitle className="text-pos-xl text-white">
              Currently signed in
            </CardTitle>
          </CardHeader>

          <CardContent>
            <div className="space-y-3 rounded-lg bg-secondary-900/60 p-4">
              <div className="flex items-start gap-3">
                <UserCircle className="mt-0.5 h-5 w-5 shrink-0 text-secondary-400" />
                <div>
                  <p className="text-pos-base font-semibold text-white">
                    {user?.full_name || user?.email || "Unknown user"}
                  </p>
                  {user?.role?.name ? (
                    <p className="text-pos-xs capitalize text-secondary-400">
                      {user.role.name}
                    </p>
                  ) : null}
                </div>
              </div>

              <div className="flex items-start gap-3">
                <Store className="mt-0.5 h-5 w-5 shrink-0 text-secondary-400" />
                <div>
                  <p className="text-pos-base font-semibold text-white">
                    {shopName || "Restaurant not loaded"}
                  </p>
                  {shopSlug ? (
                    <p className="text-pos-xs text-secondary-400">{shopSlug}</p>
                  ) : null}
                </div>
              </div>
            </div>

            <Button
              size="pos"
              variant="destructive"
              className="mt-5 w-full"
              disabled={signingOut}
              onClick={handleSwitch}
            >
              <LogOut className="mr-2 h-5 w-5" />
              {signingOut ? "Signing out..." : "Sign out and switch"}
            </Button>

            <button
              onClick={() => navigate(-1)}
              className="mt-4 w-full text-center text-pos-xs text-primary-400 underline-offset-4 hover:text-primary-300 hover:underline"
            >
              Cancel and go back
            </button>
          </CardContent>
        </Card>

        <p className="mt-6 text-center text-pos-xs text-secondary-500">
          Bookmark this page — it is not linked from the order queue, so the
          shop's tablet can never land on it by accident.
        </p>
      </div>
    </div>
  );
}
