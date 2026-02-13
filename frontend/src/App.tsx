import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ErrorBoundary } from "@/components/ErrorBoundary";

/* ---------- Layouts ---------- */
const POSLayout = lazy(() => import("@/components/layout/POSLayout"));
const AdminLayout = lazy(() => import("@/components/layout/AdminLayout"));

/* ---------- Auth ---------- */
const LoginPage = lazy(() => import("@/pages/auth/LoginPage"));

/* ---------- POS Pages ---------- */
const DashboardPage = lazy(() => import("@/pages/dashboard/DashboardPage"));
const DineInPage = lazy(() => import("@/pages/dine-in/DineInPage"));
const TakeawayPage = lazy(() => import("@/pages/takeaway/TakeawayPage"));
const CallCenterPage = lazy(() => import("@/pages/call-center/CallCenterPage"));
const PaymentPage = lazy(() => import("@/pages/payment/PaymentPage"));
const FloorEditorPage = lazy(() => import("@/pages/floor-editor/FloorEditorPage"));
const OrdersPage = lazy(() => import("@/pages/orders/OrdersPage"));

/* ---------- Kitchen ---------- */
const KitchenPage = lazy(() => import("@/pages/kitchen/KitchenPage"));

/* ---------- Admin Pages ---------- */
const AdminDashboard = lazy(() => import("@/pages/admin/AdminDashboard"));
const MenuManagementPage = lazy(() => import("@/pages/admin/MenuManagementPage"));
const StaffManagementPage = lazy(() => import("@/pages/admin/StaffManagementPage"));
const SettingsPage = lazy(() => import("@/pages/admin/SettingsPage"));
const ReportsPage = lazy(() => import("@/pages/admin/ReportsPage"));
const QuickBooksPage = lazy(() => import("@/pages/admin/QuickBooksPage"));

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
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Suspense fallback={<LoadingFallback />}>
        <Routes>
          {/* Auth */}
          <Route path="/login" element={<LoginPage />} />

          {/* POS Routes (protected) */}
          <Route path="/" element={<POSLayout />}>
            <Route index element={<DashboardPage />} />
            <Route path="dine-in" element={<DineInPage />} />
            <Route path="takeaway" element={<TakeawayPage />} />
            <Route path="call-center" element={<CallCenterPage />} />
            <Route path="orders" element={<OrdersPage />} />
            <Route path="payment/:orderId" element={<PaymentPage />} />
            <Route path="floor-editor" element={<FloorEditorPage />} />
          </Route>

          {/* Kitchen (standalone, protected) */}
          <Route path="/kitchen" element={<KitchenPage />} />

          {/* Admin Routes (protected, manager+) */}
          <Route path="/admin" element={<AdminLayout />}>
            <Route index element={<AdminDashboard />} />
            <Route path="menu" element={<MenuManagementPage />} />
            <Route path="staff" element={<StaffManagementPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="reports" element={<ReportsPage />} />
            <Route path="quickbooks" element={<QuickBooksPage />} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
    </ErrorBoundary>
  );
}
