import { useParams } from "react-router-dom";
import { CreditCard } from "lucide-react";

function PaymentPage() {
  const { orderId } = useParams<{ orderId: string }>();

  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 p-8">
      <CreditCard className="h-16 w-16 text-primary-300" />
      <h2 className="text-pos-2xl font-bold text-secondary-800">Payment</h2>
      <p className="text-pos-base text-secondary-500">
        Payment processing for order <span className="font-mono font-semibold">{orderId}</span> coming soon.
      </p>
      <span className="rounded-full bg-primary-100 px-4 py-1.5 text-pos-sm font-medium text-primary-700">
        Phase 3
      </span>
    </div>
  );
}

export default PaymentPage;
