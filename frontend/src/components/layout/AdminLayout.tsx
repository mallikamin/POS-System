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
} from "lucide-react";
import { useAuthStore } from "@/stores/authStore";
import { useUIStore } from "@/stores/uiStore";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const navItems = [
  { to: "/admin", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/admin/menu", label: "Menu", icon: UtensilsCrossed, end: false },
  { to: "/admin/staff", label: "Staff", icon: Users, end: false },
  { to: "/admin/settings", label: "Settings", icon: Settings, end: false },
  { to: "/admin/reports", label: "Reports", icon: BarChart3, end: false },
  { to: "/admin/z-report", label: "Z-Report", icon: FileText, end: false },
  { to: "/admin/roles", label: "Roles", icon: Shield, end: false },
  { to: "/admin/discounts", label: "Discounts", icon: Tag, end: false },
  { to: "/admin/quickbooks", label: "QuickBooks", icon: BookOpen, end: false },
];

function AdminLayout() {
  const { isAuthenticated, user, logout } = useAuthStore();
  const { sidebarOpen, setSidebarOpen } = useUIStore();
  const navigate = useNavigate();

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
    <div className="flex h-screen overflow-hidden bg-secondary-50">
      {/* Sidebar */}
      <aside
        className={cn(
          "flex w-64 shrink-0 flex-col border-r border-secondary-200 bg-white transition-all duration-200",
          !sidebarOpen && "max-lg:-ml-64"
        )}
      >
        {/* Sidebar header */}
        <div className="flex h-14 items-center justify-between border-b border-secondary-200 px-4">
          <h2 className="text-pos-base font-bold text-secondary-800">Admin Panel</h2>
          <button
            onClick={() => setSidebarOpen(false)}
            className="rounded p-1 text-secondary-400 hover:text-secondary-600 lg:hidden"
            aria-label="Close sidebar"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-1 p-3">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2.5 text-pos-sm font-medium transition-colors",
                  isActive
                    ? "bg-primary-50 text-primary-700"
                    : "text-secondary-600 hover:bg-secondary-100 hover:text-secondary-900"
                )
              }
            >
              <item.icon className="h-5 w-5 shrink-0" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* Sidebar footer */}
        <div className="border-t border-secondary-200 p-3">
          <Button
            variant="ghost"
            className="w-full justify-start gap-3 text-secondary-600 hover:text-danger-600"
            onClick={handleLogout}
          >
            <LogOut className="h-5 w-5" />
            Logout
          </Button>
        </div>
      </aside>

      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/30 lg:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Main area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Header */}
        <header className="flex h-14 shrink-0 items-center justify-between border-b border-secondary-200 bg-white px-4 shadow-sm">
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
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export default AdminLayout;
