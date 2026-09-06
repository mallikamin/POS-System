import { useEffect, useState } from "react";
import { Outlet, Navigate, useNavigate, Link } from "react-router-dom";
import { LogOut, User, ClipboardList, Settings, Loader2 } from "lucide-react";
import { useAuthStore } from "@/stores/authStore";
import { useUIStore } from "@/stores/uiStore";
import { useConfigStore } from "@/stores/configStore";
import { useSaleAttributionStore } from "@/stores/saleAttributionStore";
import { Button } from "@/components/ui/button";

function Clock() {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <span className="font-mono text-pos-sm tabular-nums text-secondary-400">
      {time.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
    </span>
  );
}

const channelLabels: Record<string, { label: string; color: string }> = {
  dine_in: { label: "Dine-In", color: "bg-primary-500" },
  takeaway: { label: "Takeaway", color: "bg-success-500" },
  call_center: { label: "Call Center", color: "bg-accent-500" },
};

function POSLayout() {
  const { isAuthenticated, user, logout } = useAuthStore();
  const { currentChannel } = useUIStore();
  const { fetchConfig } = useConfigStore();
  const config = useConfigStore((s) => s.config);
  const configError = useConfigStore((s) => s.error);
  const navigate = useNavigate();
  const salesChannels = useSaleAttributionStore((s) => s.channels);
  const salesChannelId = useSaleAttributionStore((s) => s.channelId);

  // Fetch restaurant config once after the user is authenticated
  useEffect(() => {
    if (isAuthenticated) {
      fetchConfig();
    }
  }, [isAuthenticated, fetchConfig]);

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  /*
   * 🔴 Nothing under this layout may paint a price before the tenant config
   * has landed.
   *
   * Found in UAT on 2026-09-06 on a real phone: the Pick up till priced a
   * croissant "Rs. 9" for a UAE tenant. `formatMoney` reads the module-level
   * `activeCode` in `utils/currency.ts`, which starts at "PKR" and is only
   * corrected when `configStore.fetchConfig` calls `setActiveCurrency`. That
   * variable is NOT reactive, so a component that has already painted a price
   * never repaints it. The menu simply won the race against the config on a
   * mobile connection; the same laptop reloaded the same screen as AED.
   *
   * F15 (2026-08-28) patched the same class of fault by making sure the fetch
   * was ISSUED from AdminLayout too. Issuing it early is not enough, because
   * the fetch still has to arrive. Waiting for it is.
   *
   * `error` is the deliberate escape hatch: if the config call fails outright
   * we render the app rather than trapping the user behind a spinner, and the
   * error toast already tells them. A wrong currency is bad; an unusable till
   * is worse.
   */
  if (!config && !configError) {
    return (
      <div className="flex h-screen items-center justify-center bg-secondary-50">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    );
  }

  const salesChannel = salesChannelId
    ? salesChannels.find((c) => c.id === salesChannelId)
    : undefined;

  /*
   * The header badge names the sales channel the till is ringing up under
   * (Careem Now, Deliveroo, ...) when one is chosen, otherwise the order type,
   * using the tenant's own word for the walk-in channel ("Pick up").
   */
  let channel = currentChannel ? channelLabels[currentChannel] : null;
  if (channel && currentChannel === "takeaway") {
    if (salesChannel) {
      channel = { label: salesChannel.name, color: "bg-orange-500" };
    } else if (config?.takeaway_label) {
      channel = { ...channel, label: config.takeaway_label };
    }
  }

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-secondary-50">
      {/* Header */}
      {/*
        🔴 `h-14` is a FIXED height and the restaurant name inside it is free
        text. Found in UAT on 2026-09-06: "FZ LLC — Bakery & Cafe (Demo)"
        wrapped to three lines on a 360px phone, overflowed this 56px box and
        painted over the channel tiles beneath it, so Pick up and Call Center
        could not be tapped at all, in portrait or in landscape. The name is
        now truncated (`min-w-0` on the flex child is what lets `truncate`
        work) and the right-hand controls refuse to shrink.
      */}
      <header className="flex h-14 shrink-0 items-center justify-between gap-2 overflow-hidden border-b border-secondary-200 bg-white px-4 shadow-sm">
        {/* Left: Restaurant name + channel */}
        <div className="flex min-w-0 items-center gap-3">
          {/* The comment above said "Restaurant name" while the code said "POS
              System" for every tenant. The name has always been in the config
              response as `restaurant_name`; nothing read it. A client sitting in
              front of a demo should see their own business at the top of the
              screen, not our internal product name. Falls back only for the
              frame before config lands. */}
          <Link
            to="/"
            className="truncate text-pos-lg font-bold text-secondary-800 hover:text-primary-600 transition-colors"
          >
            {config?.restaurant_name ?? "POS System"}
          </Link>
          {channel && (
            <span
              className={`inline-flex shrink-0 items-center whitespace-nowrap rounded-full px-3 py-1 text-xs font-semibold text-white ${channel.color}`}
            >
              {channel.label}
            </span>
          )}
        </div>

        {/* Right: Orders link, Clock, User, Logout */}
        <div className="flex shrink-0 items-center gap-2 sm:gap-4">
          <Link
            to="/orders"
            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-secondary-600 hover:bg-secondary-100 hover:text-secondary-800 transition-colors"
          >
            <ClipboardList className="h-4 w-4" />
            Orders
          </Link>
          <Link
            to="/admin"
            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-secondary-600 hover:bg-secondary-100 hover:text-secondary-800 transition-colors"
          >
            <Settings className="h-4 w-4" />
            Admin
          </Link>
          {/* The clock and the operator's name are the first things to go on a
              phone: they are reassurance, not controls, and the tiles below
              need the room more. */}
          <span className="hidden sm:inline">
            <Clock />
          </span>

          {user && (
            <div className="hidden items-center gap-2 text-pos-sm text-secondary-600 sm:flex">
              <User className="h-4 w-4" />
              <span>{user.full_name}</span>
            </div>
          )}

          <Button
            variant="ghost"
            size="icon"
            onClick={handleLogout}
            aria-label="Logout"
            className="text-secondary-500 hover:text-danger-600"
          >
            <LogOut className="h-5 w-5" />
          </Button>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}

export default POSLayout;
