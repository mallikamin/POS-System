import { Phone } from "lucide-react";

function CallCenterPage() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 p-8">
      <Phone className="h-16 w-16 text-accent-300" />
      <h2 className="text-pos-2xl font-bold text-secondary-800">Call Center</h2>
      <p className="text-pos-base text-secondary-500">
        Phone order management and delivery coming soon.
      </p>
      <span className="rounded-full bg-accent-100 px-4 py-1.5 text-pos-sm font-medium text-accent-700">
        Phase 2
      </span>
    </div>
  );
}

export default CallCenterPage;
