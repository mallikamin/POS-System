import { useState } from "react";
import { useNavigate, Navigate } from "react-router-dom";
import { AxiosError } from "axios";
import { useAuthStore } from "@/stores/authStore";
import { NumberPad } from "@/components/pos/NumberPad";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

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

  // If the user is already authenticated, redirect straight to the dashboard
  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  const handlePinSubmit = async (pin: string) => {
    setError(null);
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
    try {
      await loginWithPassword(email, password);
      navigate("/");
    } catch (err) {
      setError(
        getErrorMessage(err, "Invalid email or password. Please try again.")
      );
    }
  };

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
            {/* Error message */}
            {error && (
              <div
                className="mb-4 rounded-lg bg-danger-500/10 p-3 text-center text-pos-sm text-danger-400"
                role="alert"
              >
                {error}
              </div>
            )}

            {mode === "pin" ? (
              <>
                {/* Staff grid placeholder */}
                <div className="mb-6 grid grid-cols-3 gap-2">
                  {["Staff 1", "Staff 2", "Staff 3", "Staff 4", "Staff 5", "Staff 6"].map(
                    (name) => (
                      <button
                        key={name}
                        className="touch-feedback rounded-lg bg-secondary-700 p-3 text-center text-pos-xs text-secondary-300 hover:bg-secondary-600"
                        disabled
                      >
                        <div className="mx-auto mb-1 flex h-10 w-10 items-center justify-center rounded-full bg-secondary-600 text-pos-sm font-bold text-secondary-300">
                          {name.charAt(0)}
                        </div>
                        {name}
                      </button>
                    )
                  )}
                </div>

                {/* PIN NumberPad */}
                <NumberPad
                  onSubmit={handlePinSubmit}
                  maxLength={6}
                  masked
                />

                {/* Password login fallback */}
                <div className="mt-6 text-center">
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

                <div className="mt-6 text-center">
                  <button
                    onClick={() => setMode("pin")}
                    className="text-pos-xs text-primary-400 underline-offset-4 hover:text-primary-300 hover:underline"
                  >
                    Login with PIN instead
                  </button>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default LoginPage;
