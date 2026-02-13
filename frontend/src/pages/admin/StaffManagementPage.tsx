import { Users } from "lucide-react";

function StaffManagementPage() {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-20">
      <Users className="h-16 w-16 text-secondary-300" />
      <h2 className="text-pos-2xl font-bold text-secondary-800">Staff Management</h2>
      <p className="text-pos-base text-secondary-500">
        Staff accounts, roles, and permissions coming soon.
      </p>
      <span className="rounded-full bg-primary-100 px-4 py-1.5 text-pos-sm font-medium text-primary-700">
        Phase 2
      </span>
    </div>
  );
}

export default StaffManagementPage;
