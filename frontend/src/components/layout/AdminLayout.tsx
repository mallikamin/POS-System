import { useState, useEffect } from "react";
import { Navigate, Outlet, NavLink, useNavigate, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  Menu,
  Contact,
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
  Factory,
  Wallet,
  Banknote,
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
  Loader2,
  ChevronDown,
  type LucideIcon,
} from "lucide-react";
import { useAuthStore } from "@/stores/authStore";
import { useTenantTab } from "@/lib/tenantBranding";
import { useUIStore } from "@/stores/uiStore";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import api from "@/lib/axios";
import { isModuleHidden, type UiModule } from "@/lib/modules";
import { useConfigStore } from "@/stores/configStore";

type NavItem = {
  to: string;
  label: string;
  icon: LucideIcon;
  end: boolean;
  /** Tenants can hide this entry through `hidden_ui_modules`. */
  module?: UiModule;
};

type NavGroup = { key: string; label: string; icon: LucideIcon; items: NavItem[] };

const dashboardItem: NavItem = { to: "/admin", label: "Dashboard", icon: LayoutDashboard, end: true };

/*
 * Grouped, collapsible sections (Danny's UAT, 2026-09-25: 25 flat entries read
 * as a bloated product). Each group follows a job the restaurant does; the
 * group holding the current screen opens by itself.
 */
const baseNavGroups: NavGroup[] = [
  {
    key: "sales",
    label: "Sales & Reports",
    icon: BarChart3,
    items: [
      { to: "/admin/reports", label: "Reports", icon: BarChart3, end: false },
      { to: "/admin/z-report", label: "Z-Report", icon: FileText, end: false },
      { to: "/admin/profitability", label: "Profitability", icon: TrendingUp, end: false },
      { to: "/admin/channels", label: "Sales Channels", icon: Percent, end: false },
    ],
  },
  {
    // Workflow order: define ingredients, build recipes, hold stock, produce
    // batches from it (Martin M9), move it between sites.
    key: "inventory",
    label: "Inventory",
    icon: Boxes,
    items: [
      { to: "/admin/ingredients", label: "Ingredients", icon: Carrot, end: false },
      { to: "/admin/recipes", label: "Recipes", icon: ChefHat, end: false },
      { to: "/admin/stock", label: "Stock", icon: Boxes, end: false },
      { to: "/admin/production", label: "Production", icon: Factory, end: false, module: "production" },
      { to: "/admin/transfers", label: "Transfers", icon: ArrowLeftRight, end: false, module: "transfers" },
    ],
  },
  {
    // Where stock and spend come from: purchase orders, and everything else
    // through Expenses (Martin M10). Other Income sits beside Expenses: the
    // owner reads the two as a pair (Danny's D-63).
    key: "purchasing",
    label: "Purchasing",
    icon: Truck,
    items: [
      { to: "/admin/suppliers", label: "Suppliers", icon: Truck, end: false },
      { to: "/admin/purchase-orders", label: "Purchase Orders", icon: ClipboardList, end: false },
      { to: "/admin/order-planner", label: "Order Planner", icon: Sparkles, end: false, module: "order-planner" },
      { to: "/admin/expenses", label: "Expenses", icon: Wallet, end: false },
      { to: "/admin/other-income", label: "Other Income", icon: Banknote, end: false },
    ],
  },
  {
    key: "invoicing",
    label: "B2B Invoicing",
    icon: Receipt,
    items: [
      { to: "/admin/quotations", label: "Quotations", icon: FileSignature, end: false, module: "quotations" },
      { to: "/admin/tax-invoices", label: "Tax Invoices", icon: Receipt, end: false, module: "tax-invoices" },
    ],
  },
  {
    key: "settings",
    label: "Settings",
    icon: Settings,
    items: [
      { to: "/admin/settings", label: "General", icon: Settings, end: false },
      { to: "/admin/menu", label: "Menu", icon: UtensilsCrossed, end: false },
      { to: "/admin/staff", label: "Staff", icon: Users, end: false },
      { to: "/admin/customers", label: "Customers", icon: Contact, end: false },
      { to: "/admin/roles", label: "Roles", icon: Shield, end: false },
      { to: "/admin/discounts", label: "Discounts", icon: Tag, end: false },
      { to: "/admin/locations", label: "Locations", icon: Store, end: false },
    ],
  },
];

function isItemActive(item: NavItem, pathname: string): boolean {
  return item.end ? pathname === item.to : pathname === item.to || pathname.startsWith(`${item.to}/`);
}

function AdminLayout() {
  const { isAuthenticated, user, logout } = useAuthStore();
  const config = useConfigStore((s) => s.config);
  useTenantTab(config?.tenant_slug);
  const fetchConfig = useConfigStore((s) => s.fetchConfig);
  const configError = useConfigStore((s) => s.error);
  const {
    sidebarOpen,
    setSidebarOpen,
    adminSidebarCollapsed: collapsed,
    setAdminSidebarCollapsed,
  } = useUIStore();
  const navigate = useNavigate();
  const location = useLocation();
  const [qbConnectionType, setQbConnectionType] = useState<string | null>(null);
  const [qbLoaded, setQbLoaded] = useState(false);
  // Groups the user opened or closed by hand; the rest follow the current page.
  const [groupChoice, setGroupChoice] = useState<Record<string, boolean>>({});

  /*
   * Martin (FZ LLC, 2026-09-02): "On the phone you can't really enter the
   * sections of the admin portal." Three things were wrong below `lg`:
   *
   *  1. The overlay was `fixed z-40` while the drawer was a plain flex child
   *     with no z-index, so the overlay painted OVER the drawer. Every tap on
   *     a nav entry landed on the overlay and closed it. The drawer is now
   *     `fixed z-50` on small screens (and back in normal flow at `lg`).
   *  2. The drawer pushed the page instead of floating over it, squeezing the
   *     content to a strip on a 360px phone.
   *  3. Nothing closed it after a tap, so even a successful navigation left
   *     the drawer covering the page. It closes on every route change.
   */
  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname, setSidebarOpen]);

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
  const qbItems: NavItem[] = [];
  if (qbLoaded) {
    if (
      (!qbConnectionType || qbConnectionType === "online") &&
      !isModuleHidden(config, "quickbooks-online")
    ) {
      qbItems.push({ to: "/admin/quickbooks", label: "QuickBooks Online", icon: BookOpen, end: false });
    }
    if (
      (!qbConnectionType || qbConnectionType === "desktop") &&
      !isModuleHidden(config, "quickbooks-desktop")
    ) {
      qbItems.push({ to: "/admin/qb-desktop", label: "QB Desktop", icon: BookOpen, end: false });
    }
  }
  const navGroups: NavGroup[] = [
    ...baseNavGroups,
    { key: "integrations", label: "Integrations", icon: BookOpen, items: qbItems },
  ]
    .map((g) => ({
      ...g,
      items: g.items.filter((i) => !i.module || !isModuleHidden(config, i.module)),
    }))
    .filter((g) => g.items.length > 0);

  const activeGroup = navGroups.find((g) =>
    g.items.some((i) => isItemActive(i, location.pathname)),
  )?.key;

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  /*
   * Wait for the config before any admin screen paints a price, for the same
   * reason POSLayout does. The comment above explains why the fetch belongs
   * here; UAT on 2026-09-06 showed that ISSUING it is not enough, because
   * `activeCode` in `utils/currency.ts` is not reactive and a price painted
   * before the response never corrects itself. `configError` is the escape
   * hatch so a failed call degrades instead of trapping the user.
   */
  if (!config && !configError) {
    return (
      <div className="flex h-screen items-center justify-center bg-secondary-50">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    );
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

  const renderLink = (item: NavItem, nested = false) => (
    <NavLink
      key={item.to}
      to={item.to}
      end={item.end}
      title={item.label}
      onClick={() => setSidebarOpen(false)}
      className={({ isActive }) =>
        cn(
          "flex min-h-[44px] items-center gap-3 rounded-lg px-3 py-2.5 text-pos-sm font-medium transition-colors",
          nested && "pl-6",
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
  );

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
          // Below `lg`: a drawer floating above the page and above the overlay.
          "max-lg:fixed max-lg:inset-y-0 max-lg:left-0 max-lg:z-50 max-lg:shadow-xl",
          collapsed ? "w-64 lg:w-16" : "w-64",
          !sidebarOpen && "max-lg:-translate-x-full"
        )}
        aria-hidden={!sidebarOpen ? undefined : false}
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
            className="-mr-2 flex h-11 w-11 items-center justify-center rounded text-secondary-400 hover:text-secondary-600 lg:hidden"
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
        <nav className="min-h-0 flex-1 space-y-1 overflow-y-auto p-3 scrollbar-visible">
          {renderLink(dashboardItem)}
          {navGroups.map((group) => {
            const open = groupChoice[group.key] ?? group.key === activeGroup;
            return (
              <div key={group.key} className="pt-1">
                <button
                  type="button"
                  onClick={() => setGroupChoice((c) => ({ ...c, [group.key]: !open }))}
                  aria-expanded={open}
                  title={group.label}
                  className={cn(
                    "flex min-h-[40px] w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-pos-xs font-semibold uppercase tracking-wide text-secondary-500 hover:bg-secondary-100",
                    // The icon rail shows every entry and no section headers.
                    collapsed && "lg:hidden"
                  )}
                >
                  <group.icon className="h-4 w-4 shrink-0" />
                  <span className="flex-1">{group.label}</span>
                  <ChevronDown
                    className={cn("h-4 w-4 shrink-0 transition-transform", !open && "-rotate-90")}
                  />
                </button>
                <div className={cn("space-y-1", !open && "hidden", collapsed && "lg:block")}>
                  {group.items.map((item) => renderLink(item, true))}
                </div>
              </div>
            );
          })}
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
              className="-ml-2 flex h-11 w-11 items-center justify-center rounded text-secondary-600 hover:bg-secondary-100 lg:hidden"
              aria-label="Open menu"
            >
              <Menu className="h-6 w-6" />
            </button>

            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate("/")}
              className="gap-2"
            >
              <ArrowLeft className="h-4 w-4" />
              <span className="hidden sm:inline">Back to POS</span>
              <span className="sm:hidden">POS</span>
            </Button>
          </div>

          {user && (
            <span className="truncate text-pos-sm text-secondary-600">
              {user.full_name}
              <span className="hidden sm:inline"> ({user.role.name})</span>
            </span>
          )}
        </header>

        {/* Content */}
        {/* `scrollbar-visible`: the global 6px bar on a clear track was too
            faint to notice on a long stock list (Danny's D-50). */}
        <main className="flex-1 overflow-auto p-3 sm:p-6 scrollbar-visible print:overflow-visible print:p-0">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export default AdminLayout;
