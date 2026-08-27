import { useState, useEffect } from "react";
import { Navigate, Outlet, NavLink, useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  UtensilsCrossed,
  Users,
  Settings,
  BarChart3,
  BookOpen,
  FileText,
  Tag,
  Shield,
  ArrowLeft,
  LogOut,
  Carrot,
  ChefHat,
  Store,
  Boxes,
  ArrowLeftRight,
  Percent,
  TrendingUp,
  Receipt,
  Truck,
  ClipboardList,
  Sparkles,
  FileSignature,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";
import { useAuthStore } from "@/stores/authStore";
import { useUIStore } from "@/stores/uiStore";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import api from "@/lib/axios";
import { isModuleHidden } from "@/lib/modules";
import { useConfigStore } from "@/stores/configStore";

const baseNavItems = [
  { to: "/admin", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/admin/menu", label: "Menu", icon: UtensilsCrossed, end: false },
  { to: "/admin/staff", label: "Staff", icon: Users, end: false },
  { to: "/admin/settings", label: "Settings", icon: Settings, end: false },
  { to: "/admin/reports", label: "Reports", icon: BarChart3, end: false },
  { to: "/admin/z-report", label: "Z-Report", icon: FileText, end: false },
  { to: "/admin/roles", label: "Roles", icon: Shield, end: false },
  { to: "/admin/discounts", label: "Discounts", icon: Tag, end: false },
  // Inventory, production and multi-location. Grouped in this order because it
  // follows the actual workflow: define ingredients, build recipes, hold stock
  // at a location, move it between locations, then read what it earned.
  { to: "/admin/ingredients", label: "Ingredients", icon: Carrot, end: false },
  { to: "/admin/recipes", label: "Recipes", icon: ChefHat, end: false },
  { to: "/admin/locations", label: "Locations", icon: Store, end: false },
  { to: "/admin/stock", label: "Stock", icon: Boxes, end: false },
  { to: "/admin/transfers", label: "Transfers", icon: ArrowLeftRight, end: false },
  // Procurement sits between holding stock and reporting on it: this is where
  // stock comes FROM.
  { to: "/admin/suppliers", label: "Suppliers", icon: Truck, end: false },
  { to: "/admin/purchase-orders", label: "Purchase Orders", icon: ClipboardList, end: false },
  { to: "/admin/order-planner", label: "Order Planner", icon: Sparkles, end: false },
  { to: "/admin/channels", label: "Sales Channels", icon: Percent, end: false },
  { to: "/admin/profitability", label: "Profitability", icon: TrendingUp, end: false },
  { to: "/admin/quotations", label: "Quotations", icon: FileSignature, end: false },
  { to: "/admin/tax-invoices", label: "Tax Invoices", icon: Receipt, end: false },
];

function AdminLayout() {
  const { isAuthenticated, user, logout } = useAuthStore();
  const config = useConfigStore((s) => s.config);
  const fetchConfig = useConfigStore((s) => s.fetchConfig);
  const {
    sidebarOpen,
    setSidebarOpen,
    adminSidebarCollapsed: collapsed,
    setAdminSidebarCollapsed,
  } = useUIStore();
  const navigate = useNavigate();
  const [qbConnectionType, setQbConnectionType] = useState<string | null>(null);
  const [qbLoaded, setQbLoaded] = useState(false);

  /*
   * Load the tenant config here, not only in POSLayout.
   *
   * 🔴 Found in UAT on 2026-08-28 (F15). `fetchConfig()` was called by
   * POSLayout alone, so anyone reaching an admin screen WITHOUT passing
   * through it -- a deep link, a hard refresh, a bookmarked `/admin/stock`,
   * a second tab -- got `config === null`. That is not a cosmetic gap:
   * `setActiveCurrency()` is called from inside `fetchConfig`, so the
   * currency module stayed on its `"PKR"` default and a UAE tenant's Stock
   * page rendered "Rs. 28" for AED 28.00.
   *
   * The module-level `activeCode` is not reactive, so nothing re-renders it
   * back to the truth later. The only reliable fix is to make sure the fetch
   * has been issued before an admin page paints a price.
   *
   * Three pages had already worked around this one at a time
   * (OnlineOrdersPage, OnlineReportsPage, ZReportPage), each with a comment
   * about deep links skipping POSLayout. Those guards stay -- they also cover
   * non-admin deep links -- but the layout is where it belonged.
   *
   * Guarded on `!config` and idempotent in the store (`isLoading` short-
   * circuits), so navigating between admin pages issues no extra requests.
   */
  useEffect(() => {
    if (isAuthenticated && !config) void fetchConfig();
  }, [isAuthenticated, config, fetchConfig]);

  // Fetch QB connection type for this tenant
  useEffect(() => {
    if (isAuthenticated) {
      api
        .get("/integrations/quickbooks/status")
        .then((res) => {
          if (res.data.is_connected && res.data.connection_type) {
            setQbConnectionType(res.data.connection_type);
          }
          setQbLoaded(true);
        })
        .catch(() => {
          setQbLoaded(true);
        });
    }
  }, [isAuthenticated]);

  // Build nav items with conditional QB links.
  //
  // Two independent conditions, and they answer different questions. The QB
  // connection type answers "which QuickBooks does this tenant use"; the hidden
  // module list answers "does this tenant want to see QuickBooks at all". A
  // client who has never bought an accounting integration should not be shown
  // two entries for one, which is what Martin saw in UAT on 2026-08-27.
  const navItems = [...baseNavItems];
  if (qbLoaded) {
    if (
      (!qbConnectionType || qbConnectionType === "online") &&
      !isModuleHidden(config, "quickbooks-online")
    ) {
      navItems.push({ to: "/admin/quickbooks", label: "QuickBooks Online", icon: BookOpen, end: false });
    }
    if (
      (!qbConnectionType || qbConnectionType === "desktop") &&
      !isModuleHidden(config, "quickbooks-desktop")
    ) {
      navItems.push({ to: "/admin/qb-desktop", label: "QB Desktop", icon: BookOpen, end: false });
    }
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  // Role check: only manager and above can access admin
  const allowedRoles = ["admin", "manager", "owner"];
  if (user && !allowedRoles.includes(user.role.name.toLowerCase())) {
    return <Navigate to="/" replace />;
  }

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="flex h-screen overflow-hidden bg-secondary-50 print:block print:h-auto print:overflow-visible print:bg-white">
      {/* Sidebar.
          F10: on a desktop or landscape tablet it collapses to an icon rail so a
          three-column screen like the Recipe Builder gets the width back. The
          collapse applies at `lg` and up only; below that the sidebar is the
          existing slide-in drawer, where a 4rem rail would be unusable. */}
      <aside
        className={cn(
          "flex shrink-0 flex-col border-r border-secondary-200 bg-white transition-all duration-200 print:hidden",
          collapsed ? "w-64 lg:w-16" : "w-64",
          !sidebarOpen && "max-lg:-ml-64"
        )}
      >
        {/* Sidebar header */}
        <div
          className={cn(
            "flex h-14 items-center justify-between border-b border-secondary-200 px-4",
            collapsed && "lg:justify-center lg:px-0"
          )}
        >
          <h2
            className={cn(
              "text-pos-base font-bold text-secondary-800",
              collapsed && "lg:hidden"
            )}
          >
            Admin Panel
          </h2>
          <button
            onClick={() => setSidebarOpen(false)}
            className="rounded p-1 text-secondary-400 hover:text-secondary-600 lg:hidden"
            aria-label="Close sidebar"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <button
            onClick={() => setAdminSidebarCollapsed(!collapsed)}
            className="hidden rounded p-1 text-secondary-400 hover:text-secondary-600 lg:inline-flex"
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? (
              <PanelLeftOpen className="h-5 w-5" />
            ) : (
              <PanelLeftClose className="h-5 w-5" />
            )}
          </button>
        </div>

        {/* Navigation
            `overflow-y-auto` AND `min-h-0` are both required, and the second is
            the one that is easy to miss. A flex child defaults to
            `min-height: auto`, so `flex-1` alone will not let this shrink below
            its content: the list grew past the viewport, the `overflow-hidden`
            on the page wrapper clipped it, and the last entries became
            unreachable with no scrollbar to reveal them. Found in UAT on
            2026-08-27 with 22 modules in the list, where Quotations and Tax
            Invoices could only be reached by zooming the browser out. */}
        <nav className="min-h-0 flex-1 space-y-1 overflow-y-auto p-3">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              title={item.label}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2.5 text-pos-sm font-medium transition-colors",
                  collapsed && "lg:justify-center lg:px-0",
                  isActive
                    ? "bg-primary-50 text-primary-700"
                    : "text-secondary-600 hover:bg-secondary-100 hover:text-secondary-900"
                )
              }
            >
              <item.icon className="h-5 w-5 shrink-0" />
              <span className={cn(collapsed && "lg:hidden")}>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        {/* Sidebar footer */}
        <div className="border-t border-secondary-200 p-3">
          <Button
            variant="ghost"
            className={cn(
              "w-full justify-start gap-3 text-secondary-600 hover:text-danger-600",
              collapsed && "lg:justify-center lg:px-0"
            )}
            onClick={handleLogout}
            title="Logout"
          >
            <LogOut className="h-5 w-5" />
            <span className={cn(collapsed && "lg:hidden")}>Logout</span>
          </Button>
        </div>
      </aside>

      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/30 lg:hidden print:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Main area */}
      <div className="flex flex-1 flex-col overflow-hidden print:block print:overflow-visible">
        {/* Header */}
        <header className="flex h-14 shrink-0 items-center justify-between border-b border-secondary-200 bg-white px-4 shadow-sm print:hidden">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(true)}
              className="rounded p-1 text-secondary-400 hover:text-secondary-600 lg:hidden"
              aria-label="Open sidebar"
            >
              <LayoutDashboard className="h-5 w-5" />
            </button>

            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate("/")}
              className="gap-2"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to POS
            </Button>
          </div>

          {user && (
            <span className="text-pos-sm text-secondary-600">
              {user.full_name} ({user.role.name})
            </span>
          )}
        </header>

        {/* Content */}
        <main className="flex-1 overflow-auto p-6 print:overflow-visible print:p-0">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export default AdminLayout;
