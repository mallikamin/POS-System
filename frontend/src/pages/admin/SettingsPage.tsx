import { Settings } from "lucide-react";

function SettingsPage() {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-20">
      <Settings className="h-16 w-16 text-secondary-300" />
      <h2 className="text-pos-2xl font-bold text-secondary-800">Settings</h2>
      <p className="text-pos-base text-secondary-500">
        Restaurant configuration and preferences coming soon.
      </p>
      <span className="rounded-full bg-primary-100 px-4 py-1.5 text-pos-sm font-medium text-primary-700">
        Phase 3
      </span>
    </div>
  );
}

export default SettingsPage;
