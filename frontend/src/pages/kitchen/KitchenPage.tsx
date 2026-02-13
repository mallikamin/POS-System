import { Navigate } from "react-router-dom";
import { ChefHat } from "lucide-react";
import { useAuthStore } from "@/stores/authStore";

function KitchenPage() {
  const { isAuthenticated } = useAuthStore();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="flex h-screen flex-col bg-secondary-900">
      {/* Kitchen header */}
      <header className="flex h-12 items-center justify-between border-b border-secondary-700 bg-secondary-800 px-4">
        <div className="flex items-center gap-2">
          <ChefHat className="h-5 w-5 text-warning-400" />
          <h1 className="text-pos-lg font-bold text-white">Kitchen Display</h1>
        </div>
        <span className="rounded-full bg-warning-500/20 px-3 py-1 text-pos-xs font-medium text-warning-400">
          Phase 3
        </span>
      </header>

      {/* Content placeholder */}
      <div className="flex flex-1 items-center justify-center">
        <div className="text-center">
          <ChefHat className="mx-auto mb-4 h-20 w-20 text-secondary-600" />
          <h2 className="text-pos-2xl font-bold text-secondary-400">
            Kitchen Display System
          </h2>
          <p className="mt-2 text-pos-base text-secondary-500">
            Real-time order tickets coming soon.
          </p>
        </div>
      </div>
    </div>
  );
}

export default KitchenPage;
