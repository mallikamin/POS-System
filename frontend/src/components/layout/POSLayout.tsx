import { useEffect, useState } from "react";
import { Outlet, Navigate, useNavigate, Link } from "react-router-dom";
import { LogOut, User, ClipboardList, Settings } from "lucide-react";
import { useAuthStore } from "@/stores/authStore";
import { useUIStore } from "@/stores/uiStore";
import { useConfigStore } from "@/stores/configStore";
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
  const navigate = useNavigate();

  // Fetch restaurant config once after the user is authenticated
  useEffect(() => {
    if (isAuthenticated) {
      fetchConfig();
    }
  }, [isAuthenticated, fetchConfig]);

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  const channel = currentChannel ? channelLabels[currentChannel] : null;

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-secondary-50">
      {/* Header */}
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-secondary-200 bg-white px-4 shadow-sm">
        {/* Left: Restaurant name + channel */}
        <div className="flex items-center gap-3">
          <h1 className="text-pos-lg font-bold text-secondary-800">POS System</h1>
          {channel && (
            <span
              className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold text-white ${channel.color}`}
            >
              {channel.label}
            </span>
          )}
        </div>

        {/* Right: Orders link, Clock, User, Logout */}
        <div className="flex items-center gap-4">
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
          <Clock />

          {user && (
            <div className="flex items-center gap-2 text-pos-sm text-secondary-600">
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
