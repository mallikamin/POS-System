/**
 * QuickBooks integration API service.
 *
 * All calls go through the JWT-intercepted axios instance.
 */

import api, { getAccessToken } from "@/lib/axios";
import type {
  QBConnectionStatus,
  QBTemplateInfo,
  QBAccountMapping,
  QBAccountMappingCreate,
  QBSmartDefaultsResult,
  QBSyncStats,
  QBSyncJob,
  QBSyncLog,
  QBPreviewResponse,
  QBDiagnosticReport,
  QBDiagnosticReportSummary,
  QBDiagnosticDecision,
  QBDiagnosticApplyResult,
  QBHealthCheckResult,
  QBTestFixture,
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
// Templates (preview mode — no connection required)
// ---------------------------------------------------------------------------

export async function fetchTemplates(): Promise<QBTemplateInfo[]> {
  const { data } = await api.get<QBTemplateInfo[]>(`${QB}/templates-preview`);
  return data;
}

// ---------------------------------------------------------------------------
// Smart Defaults
// ---------------------------------------------------------------------------

export async function applyTemplate(
  template: string,
  autoCreateAccounts = true,
): Promise<QBSmartDefaultsResult> {
  const { data } = await api.post<QBSmartDefaultsResult>(
    `${QB}/mappings/smart-defaults`,
    { template, auto_create_accounts: autoCreateAccounts },
  );
  return data;
}

// ---------------------------------------------------------------------------
// Account Mappings
// ---------------------------------------------------------------------------

export async function fetchMappings(mappingType?: string): Promise<QBAccountMapping[]> {
  const { data } = await api.get<QBAccountMapping[]>(`${QB}/mappings`, {
    params: mappingType ? { mapping_type: mappingType } : undefined,
  });
  return data;
}

export async function createMapping(
  body: QBAccountMappingCreate,
): Promise<QBAccountMapping> {
  const { data } = await api.post<QBAccountMapping>(`${QB}/mappings`, body);
  return data;
}

export async function updateMapping(
  id: string,
  body: Partial<QBAccountMappingCreate>,
): Promise<QBAccountMapping> {
  const { data } = await api.patch<QBAccountMapping>(`${QB}/mappings/${id}`, body);
  return data;
}

export async function deleteMapping(id: string): Promise<void> {
  await api.delete(`${QB}/mappings/${id}`);
}

export async function validateMappings(): Promise<{ valid: boolean; errors: string[] }> {
  const { data } = await api.post<{
    is_valid: boolean;
    missing_required: string[];
    warnings: string[];
    summary: Record<string, number>;
  }>(`${QB}/mappings/validate`);
  // Map backend response shape to frontend expected shape
  return {
    valid: data.is_valid,
    errors: data.missing_required.map((t) => `Missing default mapping for: ${t}`),
  };
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
  page_size?: number;
}): Promise<QBSyncJob[]> {
  const { data } = await api.get<QBSyncJob[]>(`${QB}/sync/jobs`, { params });
  return data;
}

export async function fetchSyncLog(params?: {
  sync_type?: string;
  status?: string;
  page?: number;
  page_size?: number;
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
  const { data } = await api.post<{
    jobs_created: number;
    message: string;
    batch_id: string;
  }>(`${QB}/sync`, body);
  return data;
}

export async function retrySyncJob(jobId: string): Promise<QBSyncJob> {
  const { data } = await api.post<QBSyncJob>(`${QB}/sync/jobs/${jobId}/retry`);
  return data;
}

// ---------------------------------------------------------------------------
// Preview (no connection required)
// ---------------------------------------------------------------------------

export async function previewSalesReceipt(
  orderId: string,
  templateName: string,
): Promise<QBPreviewResponse> {
  const { data } = await api.post<QBPreviewResponse>(
    `${QB}/preview/sales-receipt`,
    { order_id: orderId, template_name: templateName },
  );
  return data;
}

// ---------------------------------------------------------------------------
// Diagnostic & Onboarding Tool
// ---------------------------------------------------------------------------

export async function fetchTestFixtures(): Promise<QBTestFixture[]> {
  const { data } = await api.get<QBTestFixture[]>(`${QB}/diagnostic/fixtures`);
  return data;
}

export async function runDiagnostic(
  templateKey: string,
  fixtureName?: string,
): Promise<QBDiagnosticReport> {
  const { data } = await api.post<QBDiagnosticReport>(`${QB}/diagnostic/run`, {
    template_key: templateKey,
    fixture_name: fixtureName ?? null,
  });
  return data;
}

export async function fetchDiagnosticReports(): Promise<QBDiagnosticReportSummary[]> {
  const { data } = await api.get<QBDiagnosticReportSummary[]>(
    `${QB}/diagnostic/reports`,
  );
  return data;
}

export async function fetchDiagnosticReport(
  reportId: string,
): Promise<QBDiagnosticReport> {
  const { data } = await api.get<QBDiagnosticReport>(
    `${QB}/diagnostic/reports/${reportId}`,
  );
  return data;
}

export async function updateDiagnosticDecisions(
  reportId: string,
  decisions: QBDiagnosticDecision[],
): Promise<QBDiagnosticReport> {
  const { data } = await api.post<QBDiagnosticReport>(
    `${QB}/diagnostic/reports/${reportId}/decisions`,
    { decisions },
  );
  return data;
}

export async function applyDiagnosticDecisions(
  reportId: string,
): Promise<QBDiagnosticApplyResult> {
  const { data } = await api.post<QBDiagnosticApplyResult>(
    `${QB}/diagnostic/reports/${reportId}/apply`,
  );
  return data;
}

export async function runHealthCheck(): Promise<QBHealthCheckResult> {
  const { data } = await api.get<QBHealthCheckResult>(
    `${QB}/diagnostic/health-check`,
  );
  return data;
}

/** Trigger a browser file download from a Blob */
function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.style.display = "none";
  document.body.appendChild(a);
  a.click();
  // Delay revoke so the browser has time to start the download
  setTimeout(() => {
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, 200);
}

export async function downloadDiagnosticPdf(reportId: string): Promise<void> {
  const token = getAccessToken();
  const { data } = await api.get(
    `${QB}/diagnostic/reports/${reportId}/export/pdf`,
    {
      responseType: "blob",
      params: token ? { token } : undefined,
    },
  );
  triggerBlobDownload(data as Blob, `diagnostic-${reportId}.pdf`);
}

export async function downloadDiagnosticExcel(reportId: string): Promise<void> {
  const token = getAccessToken();
  const { data } = await api.get(
    `${QB}/diagnostic/reports/${reportId}/export/excel`,
    {
      responseType: "blob",
      params: token ? { token } : undefined,
    },
  );
  triggerBlobDownload(data as Blob, `diagnostic-${reportId}.xlsx`);
}
