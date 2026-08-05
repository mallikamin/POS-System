import { useState } from "react";
import { useNavigate, Navigate } from "react-router-dom";
import { AxiosError } from "axios";
import { useAuthStore } from "@/stores/authStore";
import { NumberPad } from "@/components/pos/NumberPad";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getTenantSlug, setTenantSlug } from "@/lib/tenant";

/** Extract a human-readable message from an API error response. */
function getErrorMessage(err: unknown, fallback: string): string {
  if (err instanceof AxiosError && err.response?.data) {
    const data = err.response.data as Record<string, unknown>;
    // Backend may send { detail: "..." } or { message: "..." }
    if (typeof data.detail === "string") return data.detail;
    if (typeof data.message === "string") return data.message;
  }
  return fallback;
}

function LoginPage() {
  const [mode, setMode] = useState<"pin" | "password">("pin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const { loginWithPin, loginWithPassword, isLoading, isAuthenticated } =
    useAuthStore();
  const navigate = useNavigate();

  /*
   * Which restaurant (OI-69). One backend serves several, and a PIN is only
   * unique inside one of them, so the login routes have to be told.
   *
   * Collapsed by default and prefilled with whatever this device already
   * remembers: shop staff signing back in on their own tablet should never
   * have to think about it, and it is normally already correct. It is here for
   * the person arriving from `/switch`, who has just cleared the slug
   * precisely because they want a different shop.
   */
  const [shop, setShop] = useState(getTenantSlug() ?? "");
  const [showShop, setShowShop] = useState(!getTenantSlug());

  // If the user is already authenticated, redirect straight to the dashboard
  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  /*
   * Persist before authenticating, never after: `authStore` reads the slug
   * through `getTenantSlug()` at call time, so a slug that is only saved on
   * success would be missing from the very request that needs it.
   */
  const rememberShop = () => {
    if (showShop) setTenantSlug(shop);
  };

  const handlePinSubmit = async (pin: string) => {
    setError(null);
    rememberShop();
    try {
      await loginWithPin(pin);
      navigate("/");
    } catch (err) {
      setError(getErrorMessage(err, "Invalid PIN. Please try again."));
    }
  };

  const handlePasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    rememberShop();
    try {
      await loginWithPassword(email, password);
      navigate("/");
    } catch (err) {
      setError(
        getErrorMessage(err, "Invalid email or password. Please try again.")
      );
    }
  };

  const shopField = showShop ? (
    <div className="mt-4">
      <label
        htmlFor="shop"
        className="mb-1 block text-pos-sm font-medium text-secondary-300"
      >
        Restaurant
      </label>
      <input
        id="shop"
        type="text"
        value={shop}
        onChange={(e) => setShop(e.target.value)}
        className="w-full rounded-lg border border-secondary-600 bg-secondary-700 px-4 py-3 text-pos-base text-white placeholder-secondary-500 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
        placeholder="e.g. chick-shack"
        autoCapitalize="none"
        autoCorrect="off"
        spellCheck={false}
      />
      <p className="mt-1 text-pos-xs text-secondary-500">
        Leave blank if this server only hosts one restaurant.
      </p>
    </div>
  ) : (
    <div className="mt-4 text-center">
      <button
        type="button"
        onClick={() => setShowShop(true)}
        className="text-pos-xs text-secondary-400 underline-offset-4 hover:text-secondary-300 hover:underline"
      >
        Signing in to <span className="font-semibold">{shop}</span> — change
        restaurant
      </button>
    </div>
  );

  return (
    <div className="flex min-h-screen items-center justify-center bg-secondary-900 p-4">
      <div className="w-full max-w-md">
        {/* Logo / Title */}
        <div className="mb-8 text-center">
          <h1 className="text-pos-3xl font-bold text-white">POS System</h1>
          <p className="mt-2 text-pos-sm text-secondary-400">
            Restaurant Point of Sale
          </p>
        </div>

        <Card className="border-secondary-700 bg-secondary-800 shadow-2xl">
          <CardHeader className="text-center">
            <CardTitle className="text-pos-xl text-white">
              {mode === "pin" ? "Enter Your PIN" : "Staff Login"}
            </CardTitle>
          </CardHeader>

          <CardContent>
            {mode === "pin" ? (
              <>
                {/* PIN NumberPad */}
                <NumberPad
                  onSubmit={handlePinSubmit}
                  maxLength={6}
                  masked
                />

                {/* Error message */}
                {error && (
                  <div
                    className="mt-3 rounded-lg bg-danger-500/10 p-3 text-center text-pos-sm text-danger-400"
                    role="alert"
                  >
                    {error}
                  </div>
                )}

                {/* Password login fallback */}
                <div className="mt-4 text-center">
                  <button
                    onClick={() => setMode("password")}
                    className="text-pos-xs text-primary-400 underline-offset-4 hover:text-primary-300 hover:underline"
                  >
                    Login with email and password instead
                  </button>
                </div>
              </>
            ) : (
              <>
                <form onSubmit={handlePasswordSubmit} className="space-y-4">
                  <div>
                    <label
                      htmlFor="email"
                      className="mb-1 block text-pos-sm font-medium text-secondary-300"
                    >
                      Email
                    </label>
                    <input
                      id="email"
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="w-full rounded-lg border border-secondary-600 bg-secondary-700 px-4 py-3 text-pos-base text-white placeholder-secondary-500 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                      placeholder="you@restaurant.com"
                      required
                      autoComplete="email"
                    />
                  </div>
                  <div>
                    <label
                      htmlFor="password"
                      className="mb-1 block text-pos-sm font-medium text-secondary-300"
                    >
                      Password
                    </label>
                    <input
                      id="password"
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="w-full rounded-lg border border-secondary-600 bg-secondary-700 px-4 py-3 text-pos-base text-white placeholder-secondary-500 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                      placeholder="Enter password"
                      required
                      autoComplete="current-password"
                    />
                  </div>

                  <Button
                    type="submit"
                    size="pos"
                    className="w-full"
                    disabled={isLoading}
                  >
                    {isLoading ? "Signing in..." : "Sign In"}
                  </Button>
                </form>

                {/* Error message */}
                {error && (
                  <div
                    className="mt-3 rounded-lg bg-danger-500/10 p-3 text-center text-pos-sm text-danger-400"
                    role="alert"
                  >
                    {error}
                  </div>
                )}

                <div className="mt-4 text-center">
                  <button
                    onClick={() => setMode("pin")}
                    className="text-pos-xs text-primary-400 underline-offset-4 hover:text-primary-300 hover:underline"
                  >
                    Login with PIN instead
                  </button>
                </div>
              </>
            )}

            {/* Shared by both modes — a PIN needs it more than a password
                does, since four digits can collide across restaurants. */}
            <div className="mt-4 border-t border-secondary-700 pt-4">
              {shopField}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default LoginPage;
