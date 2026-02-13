/**
 * DiagnosticTab — QB Diagnostic & Onboarding Wizard.
 *
 * 5-step wizard: Select Template + Data Source -> Run Diagnostic ->
 * Gap Analysis Review -> Apply Decisions -> Health Check
 *
 * Works with both live QB connections and test fixtures for offline testing.
 */

import { useCallback, useEffect, useState } from "react";
import {
  Search,
  Play,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Download,
  FileSpreadsheet,
  FileText,
  ChevronDown,
  ChevronUp,
  Heart,
  Loader2,
  ArrowRight,
  RotateCcw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useQuickBooksStore } from "@/stores/quickbooksStore";
import * as qbApi from "@/services/quickbooksApi";
import {
  MAPPING_TYPE_LABELS,
  type QBDiagnosticReport,
  type QBDiagnosticItem,
  type QBDiagnosticDecision,
  type QBHealthCheckResult,
  type QBMatchCandidate,
} from "@/types/quickbooks";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const GRADE_COLORS: Record<string, string> = {
  A: "bg-green-100 text-green-800 border-green-300",
  B: "bg-blue-100 text-blue-800 border-blue-300",
  C: "bg-orange-100 text-orange-800 border-orange-300",
  F: "bg-red-100 text-red-800 border-red-300",
};

const GRADE_BG: Record<string, string> = {
  A: "bg-green-500",
  B: "bg-blue-500",
  C: "bg-orange-500",
  F: "bg-red-500",
};

const STATUS_BADGE: Record<string, { color: string; label: string }> = {
  matched: { color: "bg-green-100 text-green-800", label: "Matched" },
  candidates: { color: "bg-yellow-100 text-yellow-800", label: "Candidates" },
  unmatched: { color: "bg-red-100 text-red-800", label: "Unmatched" },
};

function scoreToPercent(score: number): string {
  return `${Math.round(score * 100)}%`;
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

interface DiagnosticTabProps {
  isConnected: boolean;
}

export function DiagnosticTab({ isConnected }: DiagnosticTabProps) {
  const templates = useQuickBooksStore((s) => s.templates);
  const loadTemplates = useQuickBooksStore((s) => s.loadTemplates);
  const fixtures = useQuickBooksStore((s) => s.fixtures);
  const loadFixtures = useQuickBooksStore((s) => s.loadFixtures);

  const [step, setStep] = useState<
    "setup" | "running" | "review" | "apply" | "health"
  >("setup");
  const [selectedTemplate, setSelectedTemplate] = useState("pakistani_restaurant");
  const [selectedFixture, setSelectedFixture] = useState<string>("");
  const [report, setReport] = useState<QBDiagnosticReport | null>(null);
  const [healthCheck, setHealthCheck] = useState<QBHealthCheckResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [expandedItems, setExpandedItems] = useState<Set<number>>(new Set());

  useEffect(() => {
    if (templates.length === 0) loadTemplates();
    loadFixtures();
  }, [templates.length, loadTemplates, loadFixtures]);

  // Run diagnostic
  const handleRunDiagnostic = useCallback(async () => {
    setError(null);
    setIsLoading(true);
    setStep("running");
    try {
      const result = await qbApi.runDiagnostic(
        selectedTemplate,
        selectedFixture || undefined,
      );
      setReport(result);
      setStep("review");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Diagnostic failed";
      setError(msg);
      setStep("setup");
    } finally {
      setIsLoading(false);
    }
  }, [selectedTemplate, selectedFixture]);

  // Update a single decision
  const handleDecision = useCallback(
    async (
      index: number,
      decision: "use_existing" | "create_new" | "skip",
      candidate?: QBMatchCandidate,
    ) => {
      if (!report) return;
      const dec: QBDiagnosticDecision = {
        index,
        decision,
        qb_account_id: candidate?.qb_account_id,
        qb_account_name: candidate?.qb_account_name,
      };
      try {
        const updated = await qbApi.updateDiagnosticDecisions(report.id, [dec]);
        setReport(updated);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Failed to update decision";
        setError(msg);
      }
    },
    [report],
  );

  // Auto-decide all: matched=use_existing, unmatched=create_new
  const handleAutoDecideAll = useCallback(async () => {
    if (!report) return;
    const decisions: QBDiagnosticDecision[] = report.items
      .map((item, idx) => {
        if (item.decision) return null; // already decided
        if (item.status === "matched" && item.best_match) {
          return {
            index: idx,
            decision: "use_existing" as const,
            qb_account_id: item.best_match.qb_account_id,
            qb_account_name: item.best_match.qb_account_name,
          };
        }
        return { index: idx, decision: "create_new" as const };
      })
      .filter((d): d is QBDiagnosticDecision => d !== null);

    if (decisions.length === 0) return;
    try {
      const updated = await qbApi.updateDiagnosticDecisions(
        report.id,
        decisions,
      );
      setReport(updated);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed";
      setError(msg);
    }
  }, [report]);

  // Apply decisions
  const handleApply = useCallback(async () => {
    if (!report) return;
    setIsLoading(true);
    setError(null);
    try {
      const result = await qbApi.applyDiagnosticDecisions(report.id);
      // Refresh report to get apply_result
      const updated = await qbApi.fetchDiagnosticReport(report.id);
      setReport(updated);
      setStep("apply");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Apply failed";
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [report]);

  // Health check
  const handleHealthCheck = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await qbApi.runHealthCheck();
      setHealthCheck(result);
      setStep("health");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Health check failed";
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Export helpers
  const handleExportPdf = useCallback(async () => {
    if (!report) return;
    try {
      await qbApi.downloadDiagnosticPdf(report.id);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "PDF export failed";
      setError(msg);
    }
  }, [report]);

  const handleExportExcel = useCallback(async () => {
    if (!report) return;
    try {
      await qbApi.downloadDiagnosticExcel(report.id);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Excel export failed";
      setError(msg);
    }
  }, [report]);

  // Toggle expanded item
  const toggleExpand = (idx: number) => {
    setExpandedItems((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  // Reset
  const handleReset = () => {
    setReport(null);
    setHealthCheck(null);
    setError(null);
    setStep("setup");
    setExpandedItems(new Set());
  };

  return (
    <div className="space-y-6">
      {/* Error banner */}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
          <button
            className="ml-2 underline"
            onClick={() => setError(null)}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Step 1: Setup */}
      {step === "setup" && (
        <SetupStep
          templates={templates}
          fixtures={fixtures}
          isConnected={isConnected}
          selectedTemplate={selectedTemplate}
          selectedFixture={selectedFixture}
          onSelectTemplate={setSelectedTemplate}
          onSelectFixture={setSelectedFixture}
          onRun={handleRunDiagnostic}
          onHealthCheck={handleHealthCheck}
          isLoading={isLoading}
        />
      )}

      {/* Step 2: Running */}
      {step === "running" && (
        <div className="flex flex-col items-center justify-center py-20">
          <Loader2 className="h-12 w-12 animate-spin text-primary-600" />
          <p className="mt-4 text-lg text-secondary-600">
            Running diagnostic analysis...
          </p>
          <p className="mt-1 text-sm text-secondary-400">
            Comparing template against{" "}
            {selectedFixture ? `fixture: ${selectedFixture}` : "live QB accounts"}
          </p>
        </div>
      )}

      {/* Step 3: Review */}
      {step === "review" && report && (
        <ReviewStep
          report={report}
          expandedItems={expandedItems}
          onToggleExpand={toggleExpand}
          onDecision={handleDecision}
          onAutoDecideAll={handleAutoDecideAll}
          onApply={handleApply}
          onExportPdf={handleExportPdf}
          onExportExcel={handleExportExcel}
          onReset={handleReset}
          isLoading={isLoading}
          isConnected={isConnected}
        />
      )}

      {/* Step 4: Apply result */}
      {step === "apply" && report && (
        <ApplyResultStep
          report={report}
          onHealthCheck={handleHealthCheck}
          onReset={handleReset}
          isConnected={isConnected}
        />
      )}

      {/* Step 5: Health check */}
      {step === "health" && healthCheck && (
        <HealthCheckStep
          result={healthCheck}
          onReset={handleReset}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step Components
// ---------------------------------------------------------------------------

function SetupStep({
  templates,
  fixtures,
  isConnected,
  selectedTemplate,
  selectedFixture,
  onSelectTemplate,
  onSelectFixture,
  onRun,
  onHealthCheck,
  isLoading,
}: {
  templates: { template_name: string; name: string; mapping_count: number }[];
  fixtures: { name: string; description: string; account_count: number }[];
  isConnected: boolean;
  selectedTemplate: string;
  selectedFixture: string;
  onSelectTemplate: (v: string) => void;
  onSelectFixture: (v: string) => void;
  onRun: () => void;
  onHealthCheck: () => void;
  isLoading: boolean;
}) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-secondary-900">
          Diagnostic & Onboarding Wizard
        </h2>
        <p className="mt-1 text-sm text-secondary-500">
          Compare a template against your client's QB Chart of Accounts.
          Find matches, gaps, and build a customized mapping.
        </p>
      </div>

      {/* Template selector */}
      <Card className="p-4">
        <label className="block text-sm font-medium text-secondary-700 mb-2">
          1. Select Template
        </label>
        <select
          className="w-full rounded-md border border-secondary-300 px-3 py-2 text-sm"
          value={selectedTemplate}
          onChange={(e) => onSelectTemplate(e.target.value)}
        >
          {templates.map((t) => (
            <option key={t.template_name} value={t.template_name}>
              {t.name} ({t.mapping_count} mappings)
            </option>
          ))}
        </select>
      </Card>

      {/* Data source */}
      <Card className="p-4">
        <label className="block text-sm font-medium text-secondary-700 mb-2">
          2. Data Source
        </label>
        <div className="space-y-2">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              name="datasource"
              checked={selectedFixture === ""}
              onChange={() => onSelectFixture("")}
              disabled={!isConnected}
            />
            <span className={!isConnected ? "text-secondary-400" : ""}>
              Live QB Connection
              {!isConnected && " (not connected)"}
            </span>
          </label>
          {fixtures.map((f) => (
            <label key={f.name} className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name="datasource"
                checked={selectedFixture === f.name}
                onChange={() => onSelectFixture(f.name)}
              />
              <span>
                {f.description} ({f.account_count} accounts)
              </span>
            </label>
          ))}
        </div>
      </Card>

      {/* Actions */}
      <div className="flex gap-3">
        <Button
          onClick={onRun}
          disabled={isLoading || (!isConnected && !selectedFixture)}
        >
          {isLoading ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Search className="mr-2 h-4 w-4" />
          )}
          Run Diagnostic
        </Button>

        {isConnected && (
          <Button variant="outline" onClick={onHealthCheck} disabled={isLoading}>
            <Heart className="mr-2 h-4 w-4" />
            Health Check
          </Button>
        )}
      </div>
    </div>
  );
}

function ReviewStep({
  report,
  expandedItems,
  onToggleExpand,
  onDecision,
  onAutoDecideAll,
  onApply,
  onExportPdf,
  onExportExcel,
  onReset,
  isLoading,
  isConnected,
}: {
  report: QBDiagnosticReport;
  expandedItems: Set<number>;
  onToggleExpand: (idx: number) => void;
  onDecision: (
    idx: number,
    decision: "use_existing" | "create_new" | "skip",
    candidate?: QBMatchCandidate,
  ) => void;
  onAutoDecideAll: () => void;
  onApply: () => void;
  onExportPdf: () => void;
  onExportExcel: () => void;
  onReset: () => void;
  isLoading: boolean;
  isConnected: boolean;
}) {
  const pendingCount = report.items.filter((i) => !i.decision).length;
  const readyToApply = pendingCount === 0;

  return (
    <div className="space-y-6">
      {/* Summary header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-lg font-semibold text-secondary-900">
            Gap Analysis: {report.template_name}
          </h2>
          <p className="text-sm text-secondary-500 mt-1">
            {report.fixture_name
              ? `Fixture: ${report.fixture_name}`
              : "Live QB data"}
            {" | "}
            {report.total_qb_accounts} QB accounts analyzed
          </p>
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={onExportPdf}>
            <FileText className="mr-1 h-4 w-4" /> PDF
          </Button>
          <Button size="sm" variant="outline" onClick={onExportExcel}>
            <FileSpreadsheet className="mr-1 h-4 w-4" /> Excel
          </Button>
          <Button size="sm" variant="ghost" onClick={onReset}>
            <RotateCcw className="mr-1 h-4 w-4" /> Reset
          </Button>
        </div>
      </div>

      {/* Grade + stats cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
        <Card
          className={`p-4 text-center border-2 ${GRADE_COLORS[report.health_grade] ?? ""}`}
        >
          <div className="text-3xl font-bold">{report.health_grade}</div>
          <div className="text-xs mt-1">Grade</div>
        </Card>
        <Card className="p-4 text-center">
          <div className="text-2xl font-bold text-green-600">
            {report.matched}
          </div>
          <div className="text-xs text-secondary-500 mt-1">Matched</div>
        </Card>
        <Card className="p-4 text-center">
          <div className="text-2xl font-bold text-yellow-600">
            {report.candidates}
          </div>
          <div className="text-xs text-secondary-500 mt-1">Candidates</div>
        </Card>
        <Card className="p-4 text-center">
          <div className="text-2xl font-bold text-red-600">
            {report.unmatched}
          </div>
          <div className="text-xs text-secondary-500 mt-1">Unmatched</div>
        </Card>
        <Card className="p-4 text-center">
          <div className="text-2xl font-bold">{report.coverage_pct}%</div>
          <div className="text-xs text-secondary-500 mt-1">Coverage</div>
        </Card>
      </div>

      {/* Auto-decide + Apply buttons */}
      <div className="flex items-center gap-3">
        <Button variant="outline" onClick={onAutoDecideAll}>
          <Play className="mr-2 h-4 w-4" />
          Auto-Decide All ({pendingCount} pending)
        </Button>
        {isConnected && (
          <Button
            onClick={onApply}
            disabled={!readyToApply || isLoading}
          >
            {isLoading ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <ArrowRight className="mr-2 h-4 w-4" />
            )}
            Apply Decisions
          </Button>
        )}
        {!readyToApply && (
          <span className="text-sm text-secondary-400">
            Decide all {pendingCount} pending item(s) to apply
          </span>
        )}
      </div>

      {/* Gap analysis items */}
      <div className="space-y-2">
        {report.items.map((item, idx) => (
          <GapAnalysisRow
            key={idx}
            index={idx}
            item={item}
            isExpanded={expandedItems.has(idx)}
            onToggle={() => onToggleExpand(idx)}
            onDecision={(decision, candidate) =>
              onDecision(idx, decision, candidate)
            }
          />
        ))}
      </div>

      {/* Unmapped QB accounts */}
      {report.unmapped_qb_accounts.length > 0 && (
        <div className="mt-8">
          <h3 className="text-sm font-semibold text-secondary-700 mb-2">
            Unmapped QB Accounts ({report.unmapped_qb_accounts.length})
          </h3>
          <p className="text-xs text-secondary-400 mb-3">
            These accounts exist in the client's QB but aren't covered by
            this template.
          </p>
          <div className="rounded-lg border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-secondary-50">
                  <th className="px-3 py-2 text-left font-medium">Account</th>
                  <th className="px-3 py-2 text-left font-medium">Type</th>
                  <th className="px-3 py-2 text-left font-medium">
                    Suggested POS Type
                  </th>
                </tr>
              </thead>
              <tbody>
                {report.unmapped_qb_accounts.map((a) => (
                  <tr key={a.qb_account_id} className="border-b last:border-0">
                    <td className="px-3 py-2">{a.qb_account_name}</td>
                    <td className="px-3 py-2 text-secondary-500">
                      {a.qb_account_type}
                    </td>
                    <td className="px-3 py-2">
                      {a.suggested_mapping_type ? (
                        <Badge variant="outline">
                          {MAPPING_TYPE_LABELS[a.suggested_mapping_type] ??
                            a.suggested_mapping_type}
                        </Badge>
                      ) : (
                        <span className="text-secondary-400">-</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Gap Analysis Row — one template mapping
// ---------------------------------------------------------------------------

function GapAnalysisRow({
  index,
  item,
  isExpanded,
  onToggle,
  onDecision,
}: {
  index: number;
  item: QBDiagnosticItem;
  isExpanded: boolean;
  onToggle: () => void;
  onDecision: (
    decision: "use_existing" | "create_new" | "skip",
    candidate?: QBMatchCandidate,
  ) => void;
}) {
  const badge = STATUS_BADGE[item.status] ?? STATUS_BADGE["unmatched"]!;

  return (
    <div className="rounded-lg border">
      {/* Main row */}
      <div
        className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-secondary-50"
        onClick={onToggle}
      >
        <span className="w-6 text-center text-xs text-secondary-400">
          {index + 1}
        </span>
        <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${badge.color}`}>
          {badge.label}
        </span>
        <div className="flex-1 min-w-0">
          <div className="font-medium text-sm truncate">
            {item.template_account_name}
          </div>
          <div className="text-xs text-secondary-400">
            {MAPPING_TYPE_LABELS[item.mapping_type] ?? item.mapping_type}
            {item.is_default && " (default)"}
          </div>
        </div>
        {item.best_match && (
          <div className="text-right text-sm">
            <div className="text-secondary-700 truncate max-w-[200px]">
              {item.best_match.qb_account_name}
            </div>
            <div className="text-xs text-secondary-400">
              {scoreToPercent(item.best_match.score)} match
            </div>
          </div>
        )}
        {item.decision && (
          <Badge
            variant={
              item.decision === "use_existing"
                ? "success"
                : item.decision === "create_new"
                  ? "default"
                  : "secondary"
            }
          >
            {item.decision === "use_existing"
              ? "Use Existing"
              : item.decision === "create_new"
                ? "Create New"
                : "Skip"}
          </Badge>
        )}
        {isExpanded ? (
          <ChevronUp className="h-4 w-4 text-secondary-400" />
        ) : (
          <ChevronDown className="h-4 w-4 text-secondary-400" />
        )}
      </div>

      {/* Expanded detail */}
      {isExpanded && (
        <div className="border-t bg-secondary-50 px-4 py-3 space-y-3">
          <div className="grid grid-cols-2 gap-4 text-xs">
            <div>
              <span className="font-medium">Template Account:</span>{" "}
              {item.template_account_name}
            </div>
            <div>
              <span className="font-medium">Type:</span>{" "}
              {item.template_account_type}
              {item.template_account_sub_type &&
                ` / ${item.template_account_sub_type}`}
            </div>
          </div>

          {/* Candidates list */}
          {item.candidates.length > 0 && (
            <div>
              <div className="text-xs font-medium text-secondary-600 mb-1">
                Candidates:
              </div>
              <div className="space-y-1">
                {item.candidates.map((c) => (
                  <div
                    key={c.qb_account_id}
                    className="flex items-center gap-2 rounded px-2 py-1.5 bg-white border text-sm"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="truncate font-medium">
                        {c.qb_account_name}
                      </div>
                      <div className="text-xs text-secondary-400">
                        {c.qb_account_type}
                        {c.fully_qualified_name &&
                          c.fully_qualified_name !== c.qb_account_name &&
                          ` | ${c.fully_qualified_name}`}
                      </div>
                    </div>
                    <div className="text-right">
                      <div
                        className={`text-xs font-semibold ${
                          c.confidence === "high"
                            ? "text-green-600"
                            : c.confidence === "medium"
                              ? "text-yellow-600"
                              : "text-secondary-400"
                        }`}
                      >
                        {scoreToPercent(c.score)}
                      </div>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      className="shrink-0"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDecision("use_existing", c);
                      }}
                    >
                      Use This
                    </Button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Action buttons */}
          <div className="flex gap-2 pt-1">
            <Button
              size="sm"
              variant="outline"
              onClick={() => onDecision("create_new")}
            >
              Create New in QB
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => onDecision("skip")}
            >
              Skip
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Apply Result Step
// ---------------------------------------------------------------------------

function ApplyResultStep({
  report,
  onHealthCheck,
  onReset,
  isConnected,
}: {
  report: QBDiagnosticReport;
  onHealthCheck: () => void;
  onReset: () => void;
  isConnected: boolean;
}) {
  const result = report.apply_result as
    | {
        accounts_created: number;
        mappings_created: number;
        skipped: number;
        errors: string[];
        details: string[];
      }
    | undefined;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <CheckCircle className="h-8 w-8 text-green-500" />
        <div>
          <h2 className="text-lg font-semibold text-secondary-900">
            Decisions Applied
          </h2>
          <p className="text-sm text-secondary-500">
            Template: {report.template_name}
          </p>
        </div>
      </div>

      {result && (
        <div className="grid grid-cols-3 gap-4">
          <Card className="p-4 text-center">
            <div className="text-2xl font-bold text-green-600">
              {result.accounts_created}
            </div>
            <div className="text-xs text-secondary-500 mt-1">
              QB Accounts Created
            </div>
          </Card>
          <Card className="p-4 text-center">
            <div className="text-2xl font-bold text-blue-600">
              {result.mappings_created}
            </div>
            <div className="text-xs text-secondary-500 mt-1">
              Mappings Created
            </div>
          </Card>
          <Card className="p-4 text-center">
            <div className="text-2xl font-bold text-secondary-400">
              {result.skipped}
            </div>
            <div className="text-xs text-secondary-500 mt-1">Skipped</div>
          </Card>
        </div>
      )}

      {result?.errors && result.errors.length > 0 && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4">
          <h3 className="text-sm font-medium text-red-800 mb-2">Errors</h3>
          <ul className="text-sm text-red-700 space-y-1">
            {result.errors.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </div>
      )}

      {result?.details && result.details.length > 0 && (
        <div className="rounded-lg border bg-secondary-50 p-4 max-h-64 overflow-y-auto">
          <h3 className="text-sm font-medium text-secondary-700 mb-2">
            Details
          </h3>
          <ul className="text-xs text-secondary-600 space-y-1 font-mono">
            {result.details.map((d, i) => (
              <li key={i}>{d}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex gap-3">
        {isConnected && (
          <Button onClick={onHealthCheck}>
            <Heart className="mr-2 h-4 w-4" />
            Run Health Check
          </Button>
        )}
        <Button variant="outline" onClick={onReset}>
          <RotateCcw className="mr-2 h-4 w-4" />
          Start New Diagnostic
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Health Check Step
// ---------------------------------------------------------------------------

function HealthCheckStep({
  result,
  onReset,
}: {
  result: QBHealthCheckResult;
  onReset: () => void;
}) {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Heart className="h-8 w-8 text-primary-600" />
        <div>
          <h2 className="text-lg font-semibold text-secondary-900">
            Health Check
          </h2>
          <p className="text-sm text-secondary-500">
            Checked {result.total_mappings} mapping(s) against live QB
          </p>
        </div>
      </div>

      {/* Grade + stats */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Card
          className={`p-4 text-center border-2 ${GRADE_COLORS[result.grade] ?? ""}`}
        >
          <div className="text-3xl font-bold">{result.grade}</div>
          <div className="text-xs mt-1">Grade</div>
        </Card>
        <Card className="p-4 text-center">
          <div className="text-2xl font-bold text-green-600">
            {result.healthy}
          </div>
          <div className="text-xs text-secondary-500 mt-1">Healthy</div>
        </Card>
        <Card className="p-4 text-center">
          <div className="text-2xl font-bold text-yellow-600">
            {result.warnings}
          </div>
          <div className="text-xs text-secondary-500 mt-1">Warnings</div>
        </Card>
        <Card className="p-4 text-center">
          <div className="text-2xl font-bold text-red-600">
            {result.critical}
          </div>
          <div className="text-xs text-secondary-500 mt-1">Critical</div>
        </Card>
      </div>

      {/* Details */}
      <div className="rounded-lg border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-secondary-50">
              <th className="px-3 py-2 text-left font-medium">Status</th>
              <th className="px-3 py-2 text-left font-medium">Mapping Type</th>
              <th className="px-3 py-2 text-left font-medium">QB Account</th>
              <th className="px-3 py-2 text-left font-medium">Issue</th>
            </tr>
          </thead>
          <tbody>
            {result.details.map((d) => (
              <tr
                key={d.mapping_id}
                className={`border-b last:border-0 ${
                  d.status === "critical"
                    ? "bg-red-50"
                    : d.status === "warning"
                      ? "bg-yellow-50"
                      : ""
                }`}
              >
                <td className="px-3 py-2">
                  {d.status === "healthy" && (
                    <CheckCircle className="h-4 w-4 text-green-500" />
                  )}
                  {d.status === "warning" && (
                    <AlertTriangle className="h-4 w-4 text-yellow-500" />
                  )}
                  {d.status === "critical" && (
                    <XCircle className="h-4 w-4 text-red-500" />
                  )}
                </td>
                <td className="px-3 py-2">
                  {MAPPING_TYPE_LABELS[d.mapping_type] ?? d.mapping_type}
                </td>
                <td className="px-3 py-2">{d.qb_account_name}</td>
                <td className="px-3 py-2 text-secondary-500">{d.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Button variant="outline" onClick={onReset}>
        <RotateCcw className="mr-2 h-4 w-4" />
        Back to Setup
      </Button>
    </div>
  );
}
