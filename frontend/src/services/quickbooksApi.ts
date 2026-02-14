/**
 * QuickBooks integration API service (Attempt 2 — client-centric).
 */

import api from "@/lib/axios";
import type {
  QBConnectionStatus,
  QBAccountMapping,
  QBAccountMappingCreate,
  QBSyncStats,
  QBSyncJob,
  QBSyncLog,
  QBMatchResult,
  QBMatchDecision,
  QBMatchApplyResult,
  QBHealthCheckResult,
  QBSnapshotSummary,
  QBSnapshotLatest,
} from "@/types/quickbooks";

const QB = "/integrations/quickbooks";

// ---------------------------------------------------------------------------
// Connection
// ---------------------------------------------------------------------------

export async function fetchConnectionStatus(): Promise<QBConnectionStatus> {
  const { data } = await api.get<QBConnectionStatus>(`${QB}/status`);
  return data;
}

export async function connectQuickBooks(): Promise<{ auth_url: string; state: string }> {
  const { data } = await api.get<{ auth_url: string; state: string }>(`${QB}/connect`);
  return data;
}

export async function disconnectQuickBooks(): Promise<{ message: string }> {
  const { data } = await api.post<{ message: string }>(`${QB}/disconnect`);
  return data;
}

// ---------------------------------------------------------------------------
// Account Matching (Attempt 2 core)
// ---------------------------------------------------------------------------

export async function runAccountMatching(): Promise<QBMatchResult> {
  const { data } = await api.post<QBMatchResult>(`${QB}/match`);
  return data;
}

export async function fetchMatchResult(resultId: string): Promise<QBMatchResult> {
  const { data } = await api.get<QBMatchResult>(`${QB}/match/results/${resultId}`);
  return data;
}

export async function updateMatchDecisions(
  resultId: string,
  decisions: QBMatchDecision[],
): Promise<QBMatchResult> {
  const { data } = await api.post<QBMatchResult>(
    `${QB}/match/results/${resultId}/decisions`,
    { decisions },
  );
  return data;
}

export async function applyMatchDecisions(resultId: string): Promise<QBMatchApplyResult> {
  const { data } = await api.post<QBMatchApplyResult>(
    `${QB}/match/results/${resultId}/apply`,
  );
  return data;
}

// ---------------------------------------------------------------------------
// CoA Snapshots
// ---------------------------------------------------------------------------

export async function fetchLatestSnapshots(): Promise<QBSnapshotLatest> {
  const { data } = await api.get<QBSnapshotLatest>(`${QB}/snapshots/latest`);
  return data;
}

export async function fetchSnapshots(): Promise<QBSnapshotSummary[]> {
  const { data } = await api.get<QBSnapshotSummary[]>(`${QB}/snapshots`);
  return data;
}

export async function refreshSnapshots(): Promise<{
  backup_id: string;
  working_copy_id: string;
  account_count: number;
  version: number;
}> {
  const { data } = await api.post(`${QB}/snapshots/refresh`);
  return data;
}

export async function exportSnapshotJson(snapshotId: string): Promise<void> {
  const { data } = await api.get(`${QB}/snapshots/${snapshotId}/export`, {
    responseType: "blob",
  });
  const blob = new Blob([data as BlobPart], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `coa_backup_${snapshotId}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// Health Check
// ---------------------------------------------------------------------------

export async function runHealthCheck(): Promise<QBHealthCheckResult> {
  const { data } = await api.get<QBHealthCheckResult>(`${QB}/health-check`);
  return data;
}

// ---------------------------------------------------------------------------
// Account Mappings (CRUD)
// ---------------------------------------------------------------------------

export async function fetchMappings(mappingType?: string): Promise<QBAccountMapping[]> {
  const { data } = await api.get<QBAccountMapping[]>(`${QB}/mappings`, {
    params: mappingType ? { mapping_type: mappingType } : undefined,
  });
  return data;
}

export async function createMapping(body: QBAccountMappingCreate): Promise<QBAccountMapping> {
  const { data } = await api.post<QBAccountMapping>(`${QB}/mappings`, body);
  return data;
}

export async function deleteMapping(id: string): Promise<void> {
  await api.delete(`${QB}/mappings/${id}`);
}

export async function validateMappings(): Promise<{
  is_valid: boolean;
  missing_required: string[];
  warnings: string[];
}> {
  const { data } = await api.post(`${QB}/mappings/validate`);
  return data;
}

// ---------------------------------------------------------------------------
// Sync
// ---------------------------------------------------------------------------

export async function fetchSyncStats(): Promise<QBSyncStats> {
  const { data } = await api.get<QBSyncStats>(`${QB}/sync/stats`);
  return data;
}

export async function fetchSyncJobs(params?: {
  status?: string;
  page?: number;
}): Promise<QBSyncJob[]> {
  const { data } = await api.get<QBSyncJob[]>(`${QB}/sync/jobs`, { params });
  return data;
}

export async function fetchSyncLog(params?: {
  sync_type?: string;
  status?: string;
  page?: number;
}): Promise<QBSyncLog[]> {
  const { data } = await api.get<QBSyncLog[]>(`${QB}/sync/log`, { params });
  return data;
}

export async function triggerSync(body: {
  sync_type: string;
  date_from?: string;
  date_to?: string;
  entity_ids?: string[];
}): Promise<{ jobs_created: number; message: string; batch_id: string }> {
  const { data } = await api.post(`${QB}/sync`, body);
  return data;
}

export async function retrySyncJob(jobId: string): Promise<QBSyncJob> {
  const { data } = await api.post<QBSyncJob>(`${QB}/sync/jobs/${jobId}/retry`);
  return data;
}
