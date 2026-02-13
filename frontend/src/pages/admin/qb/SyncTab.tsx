import { useCallback, useEffect, useState } from "react";
import {
  Loader2,
  RefreshCw,
  Play,
  RotateCcw,
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  Zap,
  FileText,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useQuickBooksStore } from "@/stores/quickbooksStore";
import * as qbApi from "@/services/quickbooksApi";
import type { QBSyncJob, QBSyncLog } from "@/types/quickbooks";

const SYNC_TYPES = [
  { value: "sync_orders", label: "Sync Orders", description: "Sync completed orders as SalesReceipts" },
  { value: "daily_summary", label: "Daily Summary", description: "Journal Entry + Deposit for a date" },
  { value: "full_sync", label: "Full Sync", description: "Sync all unsynced entities" },
] as const;

const JOB_STATUS_FILTERS = ["all", "pending", "processing", "completed", "failed", "dead_letter"] as const;

interface SyncTabProps {
  isConnected: boolean;
}

export function SyncTab({ isConnected }: SyncTabProps) {
  const syncStats = useQuickBooksStore((s) => s.syncStats);
  const isLoadingStats = useQuickBooksStore((s) => s.isLoadingSyncStats);
  const loadSyncStats = useQuickBooksStore((s) => s.loadSyncStats);

  const [syncType, setSyncType] = useState("sync_orders");
  const [dateFrom, setDateFrom] = useState(() => new Date().toISOString().split("T")[0] ?? "");
  const [dateTo, setDateTo] = useState(() => new Date().toISOString().split("T")[0] ?? "");
  const [triggering, setTriggering] = useState(false);
  const [triggerResult, setTriggerResult] = useState<{ jobs_created: number; message: string } | null>(null);

  const [jobs, setJobs] = useState<QBSyncJob[]>([]);
  const [jobsLoading, setJobsLoading] = useState(false);
  const [jobFilter, setJobFilter] = useState("all");
  const [retryingId, setRetryingId] = useState<string | null>(null);

  const [logs, setLogs] = useState<QBSyncLog[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);

  const [activeView, setActiveView] = useState<"jobs" | "logs">("jobs");
  const [error, setError] = useState<string | null>(null);

  const loadJobs = useCallback(async () => {
    setJobsLoading(true);
    try {
      const data = await qbApi.fetchSyncJobs(
        jobFilter === "all" ? undefined : { status: jobFilter },
      );
      setJobs(data);
    } catch {
      setError("Failed to load sync jobs");
    } finally {
      setJobsLoading(false);
    }
  }, [jobFilter]);

  const loadLogs = useCallback(async () => {
    setLogsLoading(true);
    try {
      const data = await qbApi.fetchSyncLog();
      setLogs(data);
    } catch {
      setError("Failed to load sync log");
    } finally {
      setLogsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isConnected) {
      loadSyncStats();
      loadJobs();
    }
  }, [isConnected, loadSyncStats, loadJobs]);

  useEffect(() => {
    if (isConnected && activeView === "logs") {
      loadLogs();
    }
  }, [isConnected, activeView, loadLogs]);

  async function handleTriggerSync() {
    setTriggering(true);
    setError(null);
    setTriggerResult(null);
    try {
      const result = await qbApi.triggerSync({
        sync_type: syncType,
        date_from: dateFrom,
        date_to: dateTo,
      });
      setTriggerResult(result);
      loadSyncStats();
      loadJobs();
    } catch {
      setError("Failed to trigger sync");
    } finally {
      setTriggering(false);
    }
  }

  async function handleRetry(jobId: string) {
    setRetryingId(jobId);
    setError(null);
    try {
      await qbApi.retrySyncJob(jobId);
      loadJobs();
      loadSyncStats();
    } catch {
      setError("Failed to retry job");
    } finally {
      setRetryingId(null);
    }
  }

  function formatDate(iso: string) {
    try {
      return new Date(iso).toLocaleString();
    } catch {
      return iso;
    }
  }

  function formatPKR(paisa: number) {
    return `Rs.${(paisa / 100).toLocaleString("en-PK", { minimumFractionDigits: 2 })}`;
  }

  if (!isConnected) {
    return (
      <div className="py-16 text-center">
        <p className="text-secondary-400">
          Connect to QuickBooks to sync data and view job queue.
        </p>
        <p className="text-sm text-secondary-300 mt-1">
          Use the Preview tab to simulate sync payloads without a connection.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {error && (
        <div className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">
          {error}
          <button onClick={() => setError(null)} className="ml-2 underline">
            dismiss
          </button>
        </div>
      )}

      {triggerResult && (
        <div className="rounded-lg bg-success-50 px-4 py-3 text-sm text-success-700">
          <div className="flex items-center gap-2 font-medium">
            <CheckCircle2 className="h-4 w-4" />
            {triggerResult.message}
          </div>
          <p className="mt-1 text-xs">
            {triggerResult.jobs_created} job{triggerResult.jobs_created !== 1 && "s"} created.
          </p>
          <button onClick={() => setTriggerResult(null)} className="mt-1 underline text-xs">
            dismiss
          </button>
        </div>
      )}

      {/* Stats Cards */}
      {isLoadingStats ? (
        <div className="flex justify-center py-4">
          <Loader2 className="h-6 w-6 animate-spin text-primary-600" />
        </div>
      ) : syncStats ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard
            label="Total Synced"
            value={syncStats.total_synced}
            icon={<CheckCircle2 className="h-4 w-4 text-success-600" />}
          />
          <StatCard
            label="Last 24h"
            value={syncStats.last_24h_synced}
            sub={syncStats.last_24h_failed > 0 ? `${syncStats.last_24h_failed} failed` : undefined}
            icon={<Zap className="h-4 w-4 text-primary-600" />}
          />
          <StatCard
            label="Pending"
            value={syncStats.pending_jobs}
            icon={<Clock className="h-4 w-4 text-amber-500" />}
          />
          <StatCard
            label="Failed / Dead"
            value={`${syncStats.failed_jobs} / ${syncStats.dead_letter_jobs}`}
            icon={<XCircle className="h-4 w-4 text-danger-500" />}
          />
        </div>
      ) : null}

      {/* Sync by type breakdown */}
      {syncStats && Object.keys(syncStats.sync_by_type).length > 0 && (
        <div className="flex flex-wrap gap-2">
          {Object.entries(syncStats.sync_by_type).map(([type, count]) => (
            <Badge key={type} variant="outline" className="text-xs">
              {type.replace(/_/g, " ")}: {count}
            </Badge>
          ))}
        </div>
      )}

      {/* Manual Sync Trigger */}
      <div className="rounded-lg border border-secondary-200 p-4 space-y-3">
        <h3 className="text-sm font-semibold text-secondary-900">Trigger Sync</h3>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <Label className="text-xs">Sync Type</Label>
            <select
              value={syncType}
              onChange={(e) => setSyncType(e.target.value)}
              className="mt-1 block rounded-lg border border-secondary-200 bg-white px-3 py-2 text-sm"
            >
              {SYNC_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <Label className="text-xs">From</Label>
            <Input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="mt-1 w-40"
            />
          </div>
          <div>
            <Label className="text-xs">To</Label>
            <Input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="mt-1 w-40"
            />
          </div>
          <Button onClick={handleTriggerSync} disabled={triggering}>
            {triggering ? (
              <Loader2 className="h-4 w-4 mr-1 animate-spin" />
            ) : (
              <Play className="h-4 w-4 mr-1" />
            )}
            Trigger Sync
          </Button>
        </div>
        <p className="text-xs text-secondary-400">
          {SYNC_TYPES.find((t) => t.value === syncType)?.description}
        </p>
      </div>

      {/* Jobs / Logs Toggle */}
      <div className="flex items-center gap-2 border-b border-secondary-200">
        <button
          onClick={() => setActiveView("jobs")}
          className={`px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
            activeView === "jobs"
              ? "border-primary-600 text-primary-600"
              : "border-transparent text-secondary-500 hover:text-secondary-700"
          }`}
        >
          <Clock className="h-3.5 w-3.5 inline mr-1" />
          Job Queue ({jobs.length})
        </button>
        <button
          onClick={() => setActiveView("logs")}
          className={`px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
            activeView === "logs"
              ? "border-primary-600 text-primary-600"
              : "border-transparent text-secondary-500 hover:text-secondary-700"
          }`}
        >
          <FileText className="h-3.5 w-3.5 inline mr-1" />
          Audit Log ({logs.length})
        </button>
        <div className="ml-auto flex items-center gap-2 pb-1">
          {activeView === "jobs" && (
            <select
              value={jobFilter}
              onChange={(e) => setJobFilter(e.target.value)}
              className="rounded border border-secondary-200 bg-white px-2 py-1 text-xs"
            >
              {JOB_STATUS_FILTERS.map((f) => (
                <option key={f} value={f}>
                  {f === "all" ? "All statuses" : f.replace(/_/g, " ")}
                </option>
              ))}
            </select>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={activeView === "jobs" ? loadJobs : loadLogs}
          >
            <RefreshCw className="h-3.5 w-3.5 mr-1" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Jobs Table */}
      {activeView === "jobs" && (
        jobsLoading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-primary-600" />
          </div>
        ) : jobs.length === 0 ? (
          <div className="py-8 text-center text-sm text-secondary-400">
            No sync jobs found.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-secondary-200">
            <table className="w-full text-sm">
              <thead className="bg-secondary-50 text-xs text-secondary-600">
                <tr>
                  <th className="px-3 py-2 text-left font-medium">Type</th>
                  <th className="px-3 py-2 text-left font-medium">Entity</th>
                  <th className="px-3 py-2 text-left font-medium">Status</th>
                  <th className="px-3 py-2 text-left font-medium">Retries</th>
                  <th className="px-3 py-2 text-left font-medium">Created</th>
                  <th className="px-3 py-2 text-left font-medium">Duration</th>
                  <th className="px-3 py-2 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-secondary-100">
                {jobs.map((job) => (
                  <tr key={job.id} className="hover:bg-secondary-50">
                    <td className="px-3 py-2">
                      <Badge variant="outline" className="text-[10px]">
                        {job.job_type.replace(/_/g, " ")}
                      </Badge>
                    </td>
                    <td className="px-3 py-2 text-secondary-600 text-xs font-mono">
                      {job.entity_id ? `${job.entity_type}:${job.entity_id.slice(0, 8)}...` : job.entity_type}
                    </td>
                    <td className="px-3 py-2">
                      <JobStatusBadge status={job.status} />
                    </td>
                    <td className="px-3 py-2 text-secondary-500 text-xs">{job.retry_count}</td>
                    <td className="px-3 py-2 text-secondary-500 text-xs">{formatDate(job.created_at)}</td>
                    <td className="px-3 py-2 text-secondary-500 text-xs">
                      {job.processing_duration_ms != null ? `${job.processing_duration_ms}ms` : "—"}
                    </td>
                    <td className="px-3 py-2 text-right">
                      {(job.status === "failed" || job.status === "dead_letter") && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleRetry(job.id)}
                          disabled={retryingId === job.id}
                          className="h-7 text-xs"
                        >
                          {retryingId === job.id ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            <RotateCcw className="h-3 w-3 mr-1" />
                          )}
                          Retry
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}

      {/* Logs Table */}
      {activeView === "logs" && (
        logsLoading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-primary-600" />
          </div>
        ) : logs.length === 0 ? (
          <div className="py-8 text-center text-sm text-secondary-400">
            No sync log entries yet.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-secondary-200">
            <table className="w-full text-sm">
              <thead className="bg-secondary-50 text-xs text-secondary-600">
                <tr>
                  <th className="px-3 py-2 text-left font-medium">Time</th>
                  <th className="px-3 py-2 text-left font-medium">Sync Type</th>
                  <th className="px-3 py-2 text-left font-medium">Action</th>
                  <th className="px-3 py-2 text-left font-medium">QB Entity</th>
                  <th className="px-3 py-2 text-left font-medium">Doc #</th>
                  <th className="px-3 py-2 text-left font-medium">Amount</th>
                  <th className="px-3 py-2 text-left font-medium">Status</th>
                  <th className="px-3 py-2 text-left font-medium">Duration</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-secondary-100">
                {logs.map((log) => (
                  <tr key={log.id} className="hover:bg-secondary-50">
                    <td className="px-3 py-2 text-secondary-500 text-xs">{formatDate(log.created_at)}</td>
                    <td className="px-3 py-2">
                      <Badge variant="outline" className="text-[10px]">
                        {log.sync_type.replace(/_/g, " ")}
                      </Badge>
                    </td>
                    <td className="px-3 py-2 text-secondary-700 text-xs">{log.action}</td>
                    <td className="px-3 py-2 text-secondary-600 text-xs">{log.qb_entity_type ?? "—"}</td>
                    <td className="px-3 py-2 text-secondary-900 text-xs font-mono">
                      {log.qb_doc_number ?? "—"}
                    </td>
                    <td className="px-3 py-2 text-secondary-700 text-xs">
                      {log.amount_paisa != null ? formatPKR(log.amount_paisa) : "—"}
                    </td>
                    <td className="px-3 py-2">
                      <JobStatusBadge status={log.status} />
                    </td>
                    <td className="px-3 py-2 text-secondary-500 text-xs">
                      {log.duration_ms != null ? `${log.duration_ms}ms` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}
    </div>
  );
}

function StatCard({
  label,
  value,
  sub,
  icon,
}: {
  label: string;
  value: string | number;
  sub?: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-secondary-200 bg-white px-4 py-3">
      <div className="flex items-center gap-2 text-xs text-secondary-500">
        {icon}
        {label}
      </div>
      <p className="mt-1 text-2xl font-bold text-secondary-900">{value}</p>
      {sub && <p className="text-xs text-danger-500">{sub}</p>}
    </div>
  );
}

function JobStatusBadge({ status }: { status: string }) {
  switch (status) {
    case "completed":
    case "success":
      return (
        <Badge variant="success" className="text-[10px]">
          <CheckCircle2 className="h-3 w-3 mr-0.5" />
          {status}
        </Badge>
      );
    case "failed":
      return (
        <Badge variant="destructive" className="text-[10px]">
          <XCircle className="h-3 w-3 mr-0.5" />
          failed
        </Badge>
      );
    case "dead_letter":
      return (
        <Badge variant="destructive" className="text-[10px]">
          <AlertTriangle className="h-3 w-3 mr-0.5" />
          dead letter
        </Badge>
      );
    case "processing":
      return (
        <Badge className="text-[10px] bg-blue-100 text-blue-700">
          <Loader2 className="h-3 w-3 mr-0.5 animate-spin" />
          processing
        </Badge>
      );
    case "pending":
    default:
      return (
        <Badge variant="outline" className="text-[10px]">
          <Clock className="h-3 w-3 mr-0.5" />
          {status}
        </Badge>
      );
  }
}
