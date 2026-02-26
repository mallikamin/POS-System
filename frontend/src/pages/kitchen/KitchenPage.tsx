import { useEffect, useMemo, useRef, useState } from "react";
import { Navigate } from "react-router-dom";
import {
  AlertTriangle,
  Bell,
  BellOff,
  ChefHat,
  Loader2,
  RefreshCw,
  RotateCcw,
} from "lucide-react";
import { useAuthStore } from "@/stores/authStore";
import { useKitchenStore } from "@/stores/kitchenStore";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/select";
import { formatPKR } from "@/utils/currency";
import type { KitchenStationFilter, KitchenTicket, KitchenTicketColumn } from "@/types/kitchen";

const COLUMN_CONFIG: Array<{
  key: KitchenTicketColumn;
  label: string;
  border: string;
}> = [
  { key: "new", label: "New", border: "border-warning-500" },
  { key: "preparing", label: "Preparing", border: "border-primary-500" },
  { key: "ready", label: "Ready", border: "border-success-500" },
  { key: "served", label: "Served", border: "border-secondary-500" },
];

function playNewTicketCue() {
  const AudioCtx = window.AudioContext || (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!AudioCtx) return;

  const ctx = new AudioCtx();
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();

  osc.connect(gain);
  gain.connect(ctx.destination);
  osc.type = "triangle";
  osc.frequency.setValueAtTime(880, ctx.currentTime);
  gain.gain.setValueAtTime(0.001, ctx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.2, ctx.currentTime + 0.03);
  gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.25);

  osc.start();
  osc.stop(ctx.currentTime + 0.25);
}

function elapsedMinutes(createdAt: string, nowMs: number): number {
  return Math.max(0, Math.floor((nowMs - new Date(createdAt).getTime()) / 60000));
}

function elapsedToneClass(minutes: number): string {
  if (minutes >= 20) return "text-danger-300";
  if (minutes >= 10) return "text-warning-300";
  return "text-success-300";
}

function typeBadge(orderType: KitchenTicket["order_type"]): "default" | "success" | "warning" {
  if (orderType === "dine_in") return "default";
  if (orderType === "takeaway") return "success";
  return "warning";
}

function nextStatusLabel(rawStatus: KitchenTicket["raw_status"]): string {
  if (rawStatus === "confirmed") return "Start";
  if (rawStatus === "in_kitchen") return "Bump Ready";
  if (rawStatus === "ready") return "Serve";
  if (rawStatus === "served") return "Complete";
  return "Bump";
}

function statusButtonDisabled(
  current: KitchenTicket["raw_status"],
  target: "in_kitchen" | "ready" | "served"
): boolean {
  if (target === "in_kitchen") return current !== "confirmed";
  if (target === "ready") return current !== "in_kitchen";
  if (target === "served") return current !== "ready";
  return true;
}

function KitchenPage() {
  const { isAuthenticated } = useAuthStore();
  const {
    tickets,
    stations,
    selectedStation,
    isLoading,
    error,
    wsStatus,
    audioEnabled,
    recalledTicketIds,
    setStation,
    setAudioEnabled,
    initialize,
    connectRealtime,
    disconnectRealtime,
    toggleRecall,
    loadTickets,
    bumpTicket,
    updateTicketStatus,
  } = useKitchenStore();
  const [nowMs, setNowMs] = useState(Date.now());
  const knownTicketIdsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    void initialize();
    connectRealtime();

    const timer = setInterval(() => {
      setNowMs(Date.now());
    }, 1000);

    return () => {
      clearInterval(timer);
      disconnectRealtime();
    };
  }, [initialize, connectRealtime, disconnectRealtime]);

  useEffect(() => {
    if (wsStatus === "connected") return;
    const poll = setInterval(() => {
      void loadTickets();
    }, 5000);
    return () => clearInterval(poll);
  }, [wsStatus, loadTickets]);

  useEffect(() => {
    void loadTickets(true);
  }, [selectedStation, loadTickets]);

  useEffect(() => {
    const currentIds = new Set(tickets.map((t) => t.id));

    let newCount = 0;
    for (const ticket of tickets) {
      if (ticket.column !== "new") continue;
      if (!knownTicketIdsRef.current.has(ticket.id)) {
        newCount += 1;
      }
    }

    if (audioEnabled && newCount > 0) {
      playNewTicketCue();
    }

    knownTicketIdsRef.current = currentIds;
  }, [tickets, audioEnabled]);

  const ticketsByColumn = useMemo(() => {
    const recalled = new Set(recalledTicketIds);
    return COLUMN_CONFIG.reduce<Record<KitchenTicketColumn, KitchenTicket[]>>(
      (acc, col) => {
        const columnTickets = tickets
          .filter((ticket) => ticket.column === col.key)
          .sort((a, b) => {
            const aRecalled = recalled.has(a.id) ? 1 : 0;
            const bRecalled = recalled.has(b.id) ? 1 : 0;
            if (aRecalled !== bRecalled) return bRecalled - aRecalled;
            return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
          });
        acc[col.key] = columnTickets;
        return acc;
      },
      {
        new: [],
        preparing: [],
        ready: [],
        served: [],
      }
    );
  }, [tickets, recalledTicketIds]);

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="flex h-screen flex-col bg-secondary-950 text-white">
      <header className="flex h-14 items-center justify-between border-b border-secondary-700 bg-secondary-900 px-4">
        <div className="flex items-center gap-3">
          <ChefHat className="h-5 w-5 text-warning-400" />
          <div>
            <h1 className="text-lg font-bold">Kitchen Display</h1>
            <p className="text-xs text-secondary-300">Live ticket operations board</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Select
            value={selectedStation}
            onChange={(e) => setStation(e.target.value as KitchenStationFilter)}
            className="h-9 w-44 border-secondary-600 bg-secondary-800 text-secondary-100"
            aria-label="Station filter"
          >
            <option value="all">All Stations</option>
            {stations.map((station) => (
              <option key={station.id} value={station.id}>
                {station.name}
              </option>
            ))}
          </Select>
          <Badge
            variant={wsStatus === "connected" ? "success" : wsStatus === "connecting" ? "warning" : "destructive"}
            className="px-2 py-1"
          >
            {wsStatus === "connected" ? "Realtime" : wsStatus === "connecting" ? "Connecting" : "Degraded"}
          </Badge>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setAudioEnabled(!audioEnabled)}
            className="border-secondary-600 bg-secondary-800 text-secondary-100 hover:bg-secondary-700"
          >
            {audioEnabled ? <Bell className="h-4 w-4" /> : <BellOff className="h-4 w-4" />}
            {audioEnabled ? "Audio On" : "Audio Off"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void loadTickets(true)}
            className="border-secondary-600 bg-secondary-800 text-secondary-100 hover:bg-secondary-700"
          >
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
        </div>
      </header>

      {error && (
        <div className="flex items-center gap-2 border-b border-danger-700 bg-danger-900/70 px-4 py-2 text-sm text-danger-200">
          <AlertTriangle className="h-4 w-4" />
          {error}
        </div>
      )}

      <main className="flex-1 overflow-hidden p-3">
        <div className="grid h-full grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
          {COLUMN_CONFIG.map((column) => (
            <section
              key={column.key}
              className={`flex min-h-0 flex-col rounded-xl border ${column.border} bg-secondary-900/70`}
            >
              <div className="flex items-center justify-between border-b border-secondary-700 px-3 py-2">
                <h2 className="text-sm font-semibold uppercase tracking-wide text-secondary-200">
                  {column.label}
                </h2>
                <Badge variant="outline" className="border-secondary-600 text-secondary-200">
                  {ticketsByColumn[column.key].length}
                </Badge>
              </div>

              <div className="flex-1 space-y-2 overflow-y-auto p-2">
                {ticketsByColumn[column.key].map((ticket) => {
                  const minutes = elapsedMinutes(ticket.created_at, nowMs);
                  const recalled = recalledTicketIds.includes(ticket.id);

                  return (
                    <article
                      key={ticket.id}
                      className={`rounded-lg border border-secondary-700 bg-secondary-800 p-3 ${
                        recalled ? "ring-2 ring-warning-500" : ""
                      }`}
                    >
                      <div className="mb-2 flex items-start justify-between gap-2">
                        <div>
                          <p className="font-mono text-sm font-bold text-white">
                            #{ticket.order_number}
                          </p>
                          <div className="mt-1 flex items-center gap-1.5">
                            <Badge variant={typeBadge(ticket.order_type)} className="text-[10px]">
                              {ticket.order_type.replace("_", " ")}
                            </Badge>
                            {recalled && (
                              <Badge variant="warning" className="text-[10px]">
                                Recalled
                              </Badge>
                            )}
                          </div>
                        </div>

                        <div className="text-right">
                          <p className={`text-sm font-semibold ${elapsedToneClass(minutes)}`}>
                            {minutes}m
                          </p>
                          <p className="text-[10px] text-secondary-400">
                            {ticket.item_count} item{ticket.item_count === 1 ? "" : "s"}
                          </p>
                        </div>
                      </div>

                      <ul className="mb-2 space-y-0.5 text-xs text-secondary-200">
                        {ticket.items.map((item, idx) => (
                          <li key={idx} className="flex justify-between">
                            <span className="truncate">
                              {item.quantity > 1 && (
                                <span className="font-semibold text-white">{item.quantity}x </span>
                              )}
                              {item.item_name || "Unknown item"}
                            </span>
                          </li>
                        ))}
                      </ul>

                      <div className="mb-2 text-xs text-secondary-300">
                        <p className="font-medium text-secondary-100">{formatPKR(ticket.total)}</p>
                        {ticket.customer_name && (
                          <p className="truncate">{ticket.customer_name}</p>
                        )}
                      </div>

                      <div className="grid grid-cols-2 gap-2">
                        <Button
                          size="sm"
                          className="h-8"
                          onClick={() => void bumpTicket(ticket)}
                        >
                          {nextStatusLabel(ticket.raw_status)}
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-8 border-secondary-600 bg-secondary-800 text-secondary-100 hover:bg-secondary-700"
                          onClick={() => toggleRecall(ticket.id)}
                        >
                          <RotateCcw className="h-3.5 w-3.5" />
                          {recalled ? "Clear" : "Recall"}
                        </Button>
                      </div>

                      <div className="mt-2 grid grid-cols-3 gap-1">
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 text-[10px] text-secondary-300 hover:bg-secondary-700"
                          disabled={statusButtonDisabled(ticket.raw_status, "in_kitchen")}
                          onClick={() => void updateTicketStatus(ticket.ticket_id!, "preparing")}
                        >
                          Prep
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 text-[10px] text-secondary-300 hover:bg-secondary-700"
                          disabled={statusButtonDisabled(ticket.raw_status, "ready")}
                          onClick={() => void updateTicketStatus(ticket.ticket_id!, "ready")}
                        >
                          Ready
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 text-[10px] text-secondary-300 hover:bg-secondary-700"
                          disabled={statusButtonDisabled(ticket.raw_status, "served")}
                          onClick={() => void updateTicketStatus(ticket.ticket_id!, "served")}
                        >
                          Served
                        </Button>
                      </div>
                    </article>
                  );
                })}

                {ticketsByColumn[column.key].length === 0 && (
                  <div className="flex h-28 items-center justify-center rounded-lg border border-dashed border-secondary-700 bg-secondary-900">
                    <p className="text-xs text-secondary-500">No tickets</p>
                  </div>
                )}
              </div>
            </section>
          ))}
        </div>
      </main>

      {isLoading && (
        <div className="pointer-events-none absolute bottom-3 right-3 flex items-center gap-2 rounded-lg bg-secondary-800/90 px-3 py-2 text-xs text-secondary-200">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          Syncing tickets
        </div>
      )}
    </div>
  );
}

export default KitchenPage;
