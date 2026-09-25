import { useCallback, useEffect, useRef, useState } from "react";
import {
  Ban,
  Banknote,
  ChefHat,
  CheckCircle2,
  ClipboardList,
  Radio,
  RotateCcw,
  UtensilsCrossed,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { fetchActivityFeed } from "@/services/dashboardApi";
import type { ActivityEvent } from "@/types/order";
import { formatPKR } from "@/utils/currency";
import { cn } from "@/lib/utils";

/**
 * The owner's live feed (Danny's D-57):
 *   "Tree House, Table 1 settled the bill, Cash   Rs 14,300"
 *   "Hall 1, Table 4 placed an order: 3 items     Rs 4,200"
 *
 * Every line is a recorded status change or payment; the server writes the
 * sentence from fixed templates. Refreshed every 10 seconds, which is live
 * enough for a manager glancing at a screen and costs one small query.
 */
const REFRESH_MS = 10_000;

const KIND_STYLE: Record<string, { icon: React.ElementType; tone: string }> = {
  placed: { icon: ClipboardList, tone: "bg-primary-50 text-primary-600" },
  in_kitchen: { icon: ChefHat, tone: "bg-warning-50 text-warning-600" },
  ready: { icon: CheckCircle2, tone: "bg-success-50 text-success-600" },
  served: { icon: UtensilsCrossed, tone: "bg-success-50 text-success-600" },
  completed: { icon: CheckCircle2, tone: "bg-secondary-100 text-secondary-600" },
  settled: { icon: Banknote, tone: "bg-success-100 text-success-700" },
  paid: { icon: Banknote, tone: "bg-success-50 text-success-600" },
  refund: { icon: RotateCcw, tone: "bg-danger-50 text-danger-600" },
  voided: { icon: Ban, tone: "bg-danger-50 text-danger-600" },
};

function clock(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
}

function FeedRow({ event, fresh }: { event: ActivityEvent; fresh: boolean }) {
  const style = KIND_STYLE[event.kind] ?? KIND_STYLE.completed!;
  const Icon = style.icon;
  return (
    <li
      className={cn(
        "flex items-start gap-3 border-b border-secondary-100 px-4 py-2.5 transition-colors duration-1000 last:border-0",
        fresh && "bg-primary-50",
      )}
    >
      <span className={cn("mt-0.5 rounded-md p-1.5", style.tone)}>
        <Icon className="h-4 w-4" aria-hidden="true" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-pos-sm text-secondary-800">
          <span className="font-semibold">{event.where}</span> {event.text}
        </p>
        <p className="text-pos-xs text-secondary-400">
          {clock(event.at)} · #{event.order_number}
        </p>
      </div>
      {event.amount != null && (
        <span
          className={cn(
            "whitespace-nowrap text-pos-sm font-semibold",
            event.kind === "voided" || event.kind === "refund"
              ? "text-danger-600 line-through decoration-1"
              : "text-secondary-800",
          )}
        >
          {formatPKR(event.amount)}
        </span>
      )}
    </li>
  );
}

export function ActivityFeedCard() {
  const [events, setEvents] = useState<ActivityEvent[] | null>(null);
  const [seen, setSeen] = useState<Set<string>>(new Set());
  const [failed, setFailed] = useState(false);
  const lastIds = useRef<Set<string> | null>(null);

  const load = useCallback(async () => {
    try {
      const feed = await fetchActivityFeed();
      const ids = new Set(feed.events.map((e) => e.id));
      // Highlight only what arrived since the last refresh, never the first
      // load (everything would light up).
      setSeen(lastIds.current ?? ids);
      lastIds.current = ids;
      setEvents(feed.events);
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }, []);

  useEffect(() => {
    void load();
    const id = setInterval(() => void load(), REFRESH_MS);
    return () => clearInterval(id);
  }, [load]);

  return (
    <Card className="flex flex-col">
      <CardHeader className="flex flex-row items-center gap-2 pb-3">
        <Radio className="h-5 w-5 text-danger-500" aria-hidden="true" />
        <CardTitle className="text-pos-sm font-semibold text-secondary-700">Live feed</CardTitle>
        <span className="ml-auto text-pos-xs text-secondary-400">
          {failed ? "Reconnecting..." : "Today, updates every 10 s"}
        </span>
      </CardHeader>
      <CardContent className="flex-1 p-0">
        {events === null ? (
          <p className="px-4 py-8 text-center text-pos-xs text-secondary-400">Loading...</p>
        ) : events.length === 0 ? (
          <p className="px-4 py-8 text-center text-pos-xs text-secondary-400">
            Nothing yet today. Orders, kitchen moves and payments appear here as they happen.
          </p>
        ) : (
          <ul className="max-h-96 overflow-y-auto scrollbar-visible">
            {events.map((e) => (
              <FeedRow key={e.id} event={e} fresh={!seen.has(e.id)} />
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
