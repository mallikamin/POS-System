import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { Toaster } from "@/components/ui/toaster";

/* ---------- Layouts ---------- */
const POSLayout = lazy(() => import("@/components/layout/POSLayout"));
const AdminLayout = lazy(() => import("@/components/layout/AdminLayout"));

/* ---------- Auth ---------- */
const LoginPage = lazy(() => import("@/pages/auth/LoginPage"));
const SwitchPage = lazy(() => import("@/pages/auth/SwitchPage"));

/* ---------- POS Pages ---------- */
const DashboardPage = lazy(() => import("@/pages/dashboard/DashboardPage"));
const DineInPage = lazy(() => import("@/pages/dine-in/DineInPage"));
const TakeawayPage = lazy(() => import("@/pages/takeaway/TakeawayPage"));
const CallCenterPage = lazy(() => import("@/pages/call-center/CallCenterPage"));
const PaymentPage = lazy(() => import("@/pages/payment/PaymentPage"));
const SessionPaymentPage = lazy(() => import("@/pages/payment/SessionPaymentPage"));
const FloorEditorPage = lazy(() => import("@/pages/floor-editor/FloorEditorPage"));
const OrdersPage = lazy(() => import("@/pages/orders/OrdersPage"));

/* ---------- Kitchen ---------- */
const KitchenPage = lazy(() => import("@/pages/kitchen/KitchenPage"));
const OnlineOrdersPage = lazy(
  () => import("@/pages/online-orders/OnlineOrdersPage"),
);
const OnlineReportsPage = lazy(
  () => import("@/pages/online-orders/OnlineReportsPage"),
);

/* ---------- Admin Pages ---------- */
const AdminDashboard = lazy(() => import("@/pages/admin/AdminDashboard"));
const MenuManagementPage = lazy(() => import("@/pages/admin/MenuManagementPage"));
const StaffManagementPage = lazy(() => import("@/pages/admin/StaffManagementPage"));
const SettingsPage = lazy(() => import("@/pages/admin/SettingsPage"));
const ReportsPage = lazy(() => import("@/pages/admin/ReportsPage"));
const QuickBooksPage = lazy(() => import("@/pages/admin/QuickBooksPage"));
const QBDesktopPage = lazy(() => import("@/pages/admin/QBDesktopPage"));
const ZReportPage = lazy(() => import("@/pages/admin/ZReportPage"));
const DiscountTypesPage = lazy(() => import("@/pages/admin/DiscountTypesPage"));
const RoleManagementPage = lazy(() => import("@/pages/admin/RoleManagementPage"));
/* Inventory & production. Built during BOM Phase 3 but left unrouted, so the
   screens were unreachable and never exercised — which is why the Postgres
   timezone bug in recipe creation survived a "100% complete" status. Enabled
   2026-08-26 for FZ LLC, whose whole case rests on these. */
const IngredientManagementPage = lazy(() => import("@/pages/admin/IngredientManagementPage"));
const RecipeBuilderPage = lazy(() => import("@/pages/admin/RecipeBuilderPage"));
const LocationsPage = lazy(() => import("@/pages/admin/LocationsPage"));
const StockPage = lazy(() => import("@/pages/admin/StockPage"));
const TransfersPage = lazy(() => import("@/pages/admin/TransfersPage"));
const SuppliersPage = lazy(() => import("@/pages/admin/SuppliersPage"));
const PurchaseOrdersPage = lazy(() => import("@/pages/admin/PurchaseOrdersPage"));
const OrderPlannerPage = lazy(() => import("@/pages/admin/OrderPlannerPage"));
const QuotationsPage = lazy(() => import("@/pages/admin/QuotationsPage"));
const SalesChannelsPage = lazy(() => import("@/pages/admin/SalesChannelsPage"));
const ProfitabilityPage = lazy(() => import("@/pages/admin/ProfitabilityPage"));
const TaxInvoicesPage = lazy(() => import("@/pages/admin/TaxInvoicesPage"));

function LoadingFallback() {
  return (
    <div className="flex h-screen w-screen items-center justify-center bg-secondary-50">
      <div className="flex flex-col items-center gap-4">
        <div className="h-12 w-12 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
        <p className="text-pos-sm text-secondary-500">Loading...</p>
      </div>
    </div>
  );
}

export function App() {
  return (
    <ErrorBoundary>
    <Toaster />
    <BrowserRouter future={{ v7_relativeSplatPath: true }}>
      <Suspense fallback={<LoadingFallback />}>
        <Routes>
          {/* Auth */}
          <Route path="/login" element={<LoginPage />} />
          {/* OI-69: the way out of a fullscreen, layout-less tenant queue.
              Deliberately unlinked from anywhere — bookmarked, never tapped
              by accident on a shop's unattended tablet mid-service. */}
          <Route path="/switch" element={<SwitchPage />} />

          {/* POS Routes (protected) */}
          <Route path="/" element={<POSLayout />}>
            <Route index element={<DashboardPage />} />
            <Route path="dine-in" element={<DineInPage />} />
            <Route path="takeaway" element={<TakeawayPage />} />
            <Route path="call-center" element={<CallCenterPage />} />
            <Route path="orders" element={<OrdersPage />} />
            <Route path="payment/session/:sessionId" element={<SessionPaymentPage />} />
            <Route path="payment/:orderId" element={<PaymentPage />} />
            <Route path="floor-editor" element={<FloorEditorPage />} />
          </Route>

          {/* Kitchen (standalone, protected) */}
          <Route path="/kitchen" element={<KitchenPage />} />

          {/* Online order queue — the shop's tablet. Standalone and
              fullscreen like the KDS: it runs on a tablet propped up in a
              takeaway, not inside the POS chrome. */}
          <Route path="/online-orders" element={<OnlineOrdersPage />} />
          <Route path="/online-orders/reports" element={<OnlineReportsPage />} />

          {/* Admin Routes (protected, manager+) */}
          <Route path="/admin" element={<AdminLayout />}>
            <Route index element={<AdminDashboard />} />
            <Route path="menu" element={<MenuManagementPage />} />
            <Route path="staff" element={<StaffManagementPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="reports" element={<ReportsPage />} />
            <Route path="z-report" element={<ZReportPage />} />
            <Route path="quickbooks" element={<QuickBooksPage />} />
            <Route path="qb-desktop" element={<QBDesktopPage />} />
            <Route path="roles" element={<RoleManagementPage />} />
            <Route path="discounts" element={<DiscountTypesPage />} />
            {/* Inventory, production and multi-location. Every tenant can reach
                these; a single-site tenant simply has one location. */}
            <Route path="ingredients" element={<IngredientManagementPage />} />
            <Route path="recipes" element={<RecipeBuilderPage />} />
            <Route path="locations" element={<LocationsPage />} />
            <Route path="stock" element={<StockPage />} />
            <Route path="transfers" element={<TransfersPage />} />
            <Route path="suppliers" element={<SuppliersPage />} />
            <Route path="purchase-orders" element={<PurchaseOrdersPage />} />
            <Route path="order-planner" element={<OrderPlannerPage />} />
            <Route path="quotations" element={<QuotationsPage />} />
            <Route path="channels" element={<SalesChannelsPage />} />
            <Route path="profitability" element={<ProfitabilityPage />} />
            <Route path="tax-invoices" element={<TaxInvoicesPage />} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
    </ErrorBoundary>
  );
}
