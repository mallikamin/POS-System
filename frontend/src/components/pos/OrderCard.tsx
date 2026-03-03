import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Clock,
  ChefHat,
  CheckCircle,
  XCircle,
  UtensilsCrossed,
  Package,
  Phone,
  CreditCard,
  FileText,
  Send,
  MapPin,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { formatPKR } from "@/utils/currency";
import { ReceiptModal } from "@/components/pos/ReceiptModal";
import { verifyPassword } from "@/services/ordersApi";
import type { OrderListItem } from "@/types/order";

/* -------------------------------------------------------------------------- */
/*  Props                                                                     */
/* -------------------------------------------------------------------------- */

interface OrderCardProps {
  order: OrderListItem;
  onTransition: (id: string, status: string) => void;
  onVoid: (id: string, reason: string, authToken?: string) => void;
}

/* -------------------------------------------------------------------------- */
/*  Lookup maps                                                               */
/* -------------------------------------------------------------------------- */

const ORDER_TYPE_CONFIG: Record<
  string,
  { label: string; bg: string; text: string; icon: React.ElementType }
> = {
  dine_in: {
    label: "Dine-In",
    bg: "bg-success-100",
    text: "text-success-700",
    icon: UtensilsCrossed,
  },
  takeaway: {
    label: "Takeaway",
    bg: "bg-primary-100",
    text: "text-primary-700",
    icon: Package,
  },
  call_center: {
    label: "Call Center",
    bg: "bg-accent-100",
    text: "text-accent-700",
    icon: Phone,
  },
};

const STATUS_CONFIG: Record<
  string,
  { label: string; bg: string; text: string; dot: string }
> = {
  draft: {
    label: "Draft",
    bg: "bg-secondary-100",
    text: "text-secondary-700",
    dot: "bg-secondary-400",
  },
  confirmed: {
    label: "Confirmed",
    bg: "bg-primary-100",
    text: "text-primary-700",
    dot: "bg-primary-500",
  },
  in_kitchen: {
    label: "In Kitchen",
    bg: "bg-warning-100",
    text: "text-warning-700",
    dot: "bg-warning-500",
  },
  ready: {
    label: "Ready",
    bg: "bg-success-100",
    text: "text-success-700",
    dot: "bg-success-500",
  },
  served: {
    label: "Served",
    bg: "bg-primary-100",
    text: "text-primary-700",
    dot: "bg-primary-500",
  },
  completed: {
    label: "Completed",
    bg: "bg-secondary-100",
    text: "text-secondary-600",
    dot: "bg-secondary-400",
  },
  voided: {
    label: "Voided",
    bg: "bg-danger-100",
    text: "text-danger-700",
    dot: "bg-danger-500",
  },
};

/** Statuses that can receive a transition (non-terminal). */
const TRANSITION_ACTIONS: Record<string, { label: string; next: string; icon: React.ElementType }> = {
  confirmed: { label: "Send to Kitchen", next: "in_kitchen", icon: Send },
  in_kitchen: { label: "Mark Ready", next: "ready", icon: ChefHat },
  ready: { label: "Mark Served", next: "served", icon: UtensilsCrossed },
  served: { label: "Complete", next: "completed", icon: CheckCircle },
};

/** Statuses from which voiding is allowed (anything not already terminal). */
const VOIDABLE_STATUSES = new Set([
  "draft",
  "confirmed",
  "in_kitchen",
  "ready",
  "served",
]);

/* -------------------------------------------------------------------------- */
/*  Helpers                                                                   */
/* -------------------------------------------------------------------------- */

function formatElapsed(createdAt: string): string {
  const diffMs = Date.now() - new Date(createdAt).getTime();
  const minutes = Math.max(0, Math.floor(diffMs / 60_000));

  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  if (remainingMinutes === 0) return `${hours}h ago`;
  return `${hours}h ${remainingMinutes}m ago`;
}

/* -------------------------------------------------------------------------- */
/*  Component                                                                 */
/* -------------------------------------------------------------------------- */

export function OrderCard({ order, onTransition, onVoid }: OrderCardProps) {
  const navigate = useNavigate();
  const [receiptOpen, setReceiptOpen] = useState(false);
  const [voidOpen, setVoidOpen] = useState(false);
  const [voidReason, setVoidReason] = useState("");
  const [voidPassword, setVoidPassword] = useState("");
  const [voidError, setVoidError] = useState("");
  const [voidSubmitting, setVoidSubmitting] = useState(false);
  const typeConfig = ORDER_TYPE_CONFIG[order.order_type] ?? { label: "Order", bg: "bg-secondary-100", text: "text-secondary-700", icon: Package };
  const statusConfig = STATUS_CONFIG[order.status] ?? { label: "Unknown", bg: "bg-secondary-100", text: "text-secondary-600", dot: "bg-secondary-400" };
  const transition = TRANSITION_ACTIONS[order.status];
  const canVoid = VOIDABLE_STATUSES.has(order.status);
  const canPay = order.payment_status !== "paid" && order.status !== "voided" && order.status !== "draft";
  const canReceipt = order.status !== "draft";

  const TypeIcon = typeConfig.icon;

  const elapsed = useMemo(
    () => formatElapsed(order.created_at),
    [order.created_at]
  );
  const tableText = order.table_label
    ? order.table_label
    : order.table_number
      ? `Table ${order.table_number}`
      : null;

  async function handleVoidSubmit() {
    if (!voidReason.trim()) {
      setVoidError("Reason is required.");
      return;
    }
    if (!voidPassword.trim()) {
      setVoidError("Password is required for authorization.");
      return;
    }
    setVoidSubmitting(true);
    setVoidError("");
    try {
      const { auth_token } = await verifyPassword(voidPassword);
      await onVoid(order.id, voidReason.trim(), auth_token);
      setVoidOpen(false);
      setVoidReason("");
      setVoidPassword("");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Verification failed";
      // Check for axios error shape
      const axiosDetail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setVoidError(axiosDetail ?? msg);
    } finally {
      setVoidSubmitting(false);
    }
  }

  return (
    <Card
      className={cn(
        "transition-shadow hover:shadow-md",
        order.status === "voided" && "opacity-60"
      )}
    >
      <CardContent className="p-4 space-y-3">
        {/* Row 1: Order number + badges */}
        <div className="flex items-start justify-between gap-2">
          <div className="flex flex-col gap-1.5">
            <span className="text-base font-bold text-secondary-900">
              #{order.order_number}
            </span>
            <div className="flex flex-wrap items-center gap-1.5">
              {/* Order type badge */}
              <Badge
                className={cn(
                  "gap-1 border-transparent",
                  typeConfig.bg,
                  typeConfig.text
                )}
              >
                <TypeIcon className="h-3 w-3" />
                {typeConfig.label}
              </Badge>

              {/* Status badge */}
              <Badge
                className={cn(
                  "gap-1 border-transparent",
                  statusConfig.bg,
                  statusConfig.text
                )}
              >
                <span
                  className={cn(
                    "inline-block h-1.5 w-1.5 rounded-full",
                    statusConfig.dot
                  )}
                />
                {statusConfig.label}
              </Badge>
            </div>
          </div>

          {/* Elapsed time */}
          <span className="flex shrink-0 items-center gap-1 text-xs text-secondary-400">
            <Clock className="h-3 w-3" />
            {elapsed}
          </span>
        </div>

        {/* Row 2: Item count + total */}
        <div className="flex items-center justify-between border-t border-secondary-100 pt-2">
          <span className="text-sm text-secondary-500">
            {order.item_count} item{order.item_count !== 1 ? "s" : ""}
          </span>
          <span className="text-sm font-semibold text-secondary-900">
            {formatPKR(order.total)}
          </span>
        </div>

        {tableText && (
          <div className="flex items-center gap-1 text-xs text-secondary-500">
            <MapPin className="h-3 w-3" />
            <span>{tableText}</span>
          </div>
        )}

        {/* Row 3: Actions */}
        {(transition || canVoid || canPay || canReceipt) && (
          <div className="flex flex-wrap items-center gap-2 pt-1">
            {transition && (
              <Button
                size="sm"
                className="flex-1 gap-1.5"
                onClick={() => onTransition(order.id, transition.next)}
              >
                <transition.icon className="h-3.5 w-3.5" />
                {transition.label}
              </Button>
            )}
            {canPay && (
              <Button
                variant="outline"
                size="sm"
                className="gap-1"
                onClick={() => navigate(`/payment/${order.id}`)}
              >
                <CreditCard className="h-3.5 w-3.5" />
                Pay
              </Button>
            )}
            {canReceipt && (
              <Button
                variant="ghost"
                size="sm"
                className="gap-1"
                onClick={() => setReceiptOpen(true)}
              >
                <FileText className="h-3.5 w-3.5" />
                Receipt
              </Button>
            )}
            {canVoid && (
              <Button
                variant="ghost"
                size="sm"
                className="gap-1 text-danger-500 hover:text-danger-700 hover:bg-danger-50"
                onClick={() => { setVoidOpen(true); setVoidError(""); setVoidReason(""); setVoidPassword(""); }}
                aria-label={`Void order ${order.order_number}`}
              >
                <XCircle className="h-3.5 w-3.5" />
                Void
              </Button>
            )}
          </div>
        )}
      </CardContent>

      {/* Receipt Modal */}
      <ReceiptModal
        orderId={order.id}
        open={receiptOpen}
        onClose={() => setReceiptOpen(false)}
      />

      {/* Void Modal */}
      <Dialog open={voidOpen} onOpenChange={setVoidOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Void Order #{order.order_number}</DialogTitle>
            <DialogDescription>
              This action cannot be undone. Enter a reason and your password to authorize.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="space-y-1">
              <Label htmlFor={`void-reason-${order.id}`}>Reason *</Label>
              <Input
                id={`void-reason-${order.id}`}
                value={voidReason}
                onChange={(e) => setVoidReason(e.target.value)}
                placeholder="e.g. Customer changed mind, duplicate order..."
                autoFocus
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor={`void-password-${order.id}`}>Password *</Label>
              <Input
                id={`void-password-${order.id}`}
                type="password"
                value={voidPassword}
                onChange={(e) => setVoidPassword(e.target.value)}
                placeholder="Enter your password to authorize"
                onKeyDown={(e) => { if (e.key === "Enter") void handleVoidSubmit(); }}
              />
            </div>
            {voidError && (
              <p className="text-sm text-danger-600">{voidError}</p>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setVoidOpen(false)} disabled={voidSubmitting}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => void handleVoidSubmit()}
              disabled={voidSubmitting}
            >
              {voidSubmitting ? "Voiding..." : "Void Order"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
