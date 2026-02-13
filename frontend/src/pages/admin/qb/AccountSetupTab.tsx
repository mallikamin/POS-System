/**
 * Account Setup Tab — Attempt 2 core UI.
 *
 * Replaces DiagnosticTab + TemplatesTab + PreviewTab with a single flow:
 *   1. Run Matching (POS needs vs partner's QB Chart of Accounts)
 *   2. Review matches — accept, pick alternative, or create new
 *   3. Apply — creates QB accounts + mappings
 *   4. Health check — verify everything is in order
 */

import { useState } from "react";
import {
  Loader2,
  Play,
  CheckCircle2,
  AlertCircle,
  ChevronDown,
  ChevronRight,
  ArrowRight,
  RefreshCw,
  Shield,
  Zap,
  Search,
  AlertTriangle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useQuickBooksStore } from "@/stores/quickbooksStore";
import * as qbApi from "@/services/quickbooksApi";
import type {
  QBMatchResult,
  QBMatchItem,
  QBMatchCandidate,
  QBMatchDecision,
  QBMatchApplyResult,
  QBHealthCheckResult,
} from "@/types/quickbooks";

interface AccountSetupTabProps {
  isConnected: boolean;
}

export function AccountSetupTab({ isConnected }: AccountSetupTabProps) {
  const matchResult = useQuickBooksStore((s) => s.matchResult);
  const isMatching = useQuickBooksStore((s) => s.isMatching);
  const runMatching = useQuickBooksStore((s) => s.runMatching);
  const setMatchResult = useQuickBooksStore((s) => s.setMatchResult);

  const [applyResult, setApplyResult] = useState<QBMatchApplyResult | null>(null);
  const [isApplying, setIsApplying] = useState(false);
  const [healthCheck, setHealthCheck] = useState<QBHealthCheckResult | null>(null);
  const [isCheckingHealth, setIsCheckingHealth] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isConnected) {
    return (
      <div className="py-16 text-center">
        <Search className="h-12 w-12 mx-auto text-secondary-300 mb-3" />
        <p className="text-secondary-500 font-medium">
          Connect to QuickBooks first
        </p>
        <p className="text-sm text-secondary-400 mt-1">
          Once connected, we'll automatically match your POS accounts to your QuickBooks Chart of Accounts.
        </p>
      </div>
    );
  }

  async function handleRunMatching() {
    setError(null);
    setApplyResult(null);
    setHealthCheck(null);
    await runMatching();
  }

  async function handleUpdateDecision(_index: number, decision: QBMatchDecision) {
    if (!matchResult) return;
    setError(null);
    try {
      const updated = await qbApi.updateMatchDecisions(matchResult.id, [decision]);
      setMatchResult(updated);
    } catch {
      setError("Failed to update decision");
    }
  }

  async function handleApply() {
    if (!matchResult) return;
    setIsApplying(true);
    setError(null);
    try {
      const result = await qbApi.applyMatchDecisions(matchResult.id);
      setApplyResult(result);
      // Refresh match result to get applied_at timestamp
      const refreshed = await qbApi.fetchMatchResult(matchResult.id);
      setMatchResult(refreshed);
    } catch {
      setError("Failed to apply decisions");
    } finally {
      setIsApplying(false);
    }
  }

  async function handleHealthCheck() {
    setIsCheckingHealth(true);
    setError(null);
    try {
      const result = await qbApi.runHealthCheck();
      setHealthCheck(result);
    } catch {
      setError("Failed to run health check");
    } finally {
      setIsCheckingHealth(false);
    }
  }

  return (
    <div className="space-y-6">
      {error && (
        <div className="rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-700">
          {error}
          <button onClick={() => setError(null)} className="ml-2 underline">dismiss</button>
        </div>
      )}

      {/* Step 1: Run Matching */}
      {!matchResult && !isMatching && (
        <Card>
          <CardContent className="py-12 text-center">
            <Zap className="h-12 w-12 mx-auto text-primary-400 mb-4" />
            <h3 className="text-lg font-semibold text-secondary-900 mb-2">
              Set Up Account Matching
            </h3>
            <p className="text-sm text-secondary-500 max-w-md mx-auto mb-6">
              We'll analyze your QuickBooks Chart of Accounts and automatically
              match them to the POS accounting categories needed for syncing.
            </p>
            <Button onClick={handleRunMatching} size="lg">
              <Play className="h-4 w-4 mr-2" />
              Run Account Matching
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Running */}
      {isMatching && (
        <Card>
          <CardContent className="py-12 text-center">
            <Loader2 className="h-10 w-10 mx-auto animate-spin text-primary-600 mb-4" />
            <p className="text-secondary-600 font-medium">
              Analyzing your QuickBooks Chart of Accounts...
            </p>
            <p className="text-sm text-secondary-400 mt-1">
              Fuzzy-matching POS needs against your accounts
            </p>
          </CardContent>
        </Card>
      )}

      {/* Step 2: Review Results */}
      {matchResult && (
        <>
          <MatchSummaryCard result={matchResult} onRerun={handleRunMatching} />

          <MatchItemsList
            items={matchResult.items}
            onUpdateDecision={handleUpdateDecision}
          />

          {/* Apply Button */}
          {!matchResult.applied_at && (
            <div className="flex items-center gap-4">
              <Button
                onClick={handleApply}
                disabled={isApplying || !matchResult.decision_summary?.ready_to_apply}
                size="lg"
              >
                {isApplying ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <ArrowRight className="h-4 w-4 mr-2" />
                )}
                Apply Mappings
              </Button>
              {matchResult.decision_summary && !matchResult.decision_summary.ready_to_apply && (
                <p className="text-sm text-amber-600">
                  {matchResult.decision_summary.pending} item{matchResult.decision_summary.pending !== 1 && "s"} still
                  need a decision before applying.
                </p>
              )}
            </div>
          )}

          {/* Apply Result */}
          {applyResult && <ApplyResultCard result={applyResult} />}

          {/* Step 3: Health Check */}
          {matchResult.applied_at && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Shield className="h-5 w-5 text-primary-600" />
                  Health Check
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-sm text-secondary-500">
                  Verify your account mappings are valid and all QB accounts are accessible.
                </p>
                <Button
                  variant="outline"
                  onClick={handleHealthCheck}
                  disabled={isCheckingHealth}
                >
                  {isCheckingHealth ? (
                    <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                  ) : (
                    <Shield className="h-4 w-4 mr-1" />
                  )}
                  Run Health Check
                </Button>

                {healthCheck && <HealthCheckResultCard result={healthCheck} />}
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function MatchSummaryCard({
  result,
  onRerun,
}: {
  result: QBMatchResult;
  onRerun: () => void;
}) {
  return (
    <Card>
      <CardContent className="py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <GradeIndicator grade={result.health_grade} />
            <div>
              <p className="text-sm font-semibold text-secondary-900">
                {result.coverage_pct.toFixed(0)}% Coverage
              </p>
              <p className="text-xs text-secondary-500">
                {result.matched} matched, {result.candidates} candidates, {result.unmatched} unmatched
                {" / "}{result.total_needs} needs
              </p>
            </div>
            <div className="text-xs text-secondary-400 border-l border-secondary-200 pl-4 ml-2">
              <p>{result.total_qb_accounts} QB accounts analyzed</p>
              <p>{result.required_matched}/{result.required_total} required covered</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {result.applied_at && (
              <Badge variant="success">Applied</Badge>
            )}
            <Button variant="outline" size="sm" onClick={onRerun}>
              <RefreshCw className="h-3.5 w-3.5 mr-1" />
              Re-run
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function GradeIndicator({ grade }: { grade: string }) {
  const colors: Record<string, string> = {
    A: "bg-success-100 text-success-700 border-success-300",
    B: "bg-blue-100 text-blue-700 border-blue-300",
    C: "bg-amber-100 text-amber-700 border-amber-300",
    F: "bg-danger-100 text-danger-700 border-danger-300",
  };
  const cls = colors[grade] ?? colors["F"] ?? "bg-secondary-100 text-secondary-700 border-secondary-300";
  return (
    <div className={`w-12 h-12 rounded-lg border-2 flex items-center justify-center text-xl font-bold ${cls}`}>
      {grade}
    </div>
  );
}

function MatchItemsList({
  items,
  onUpdateDecision,
}: {
  items: QBMatchItem[];
  onUpdateDecision: (index: number, decision: QBMatchDecision) => void;
}) {
  const required = items.filter((it) => it.required);
  const optional = items.filter((it) => !it.required);

  return (
    <div className="space-y-4">
      {required.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-secondary-700 mb-2">
            Required ({required.length})
          </h3>
          <div className="space-y-2">
            {required.map((item) => (
                <MatchItemRow
                  key={item.need_key}
                  item={item}
                  index={items.indexOf(item)}
                  onUpdateDecision={onUpdateDecision}
                />
            ))}
          </div>
        </div>
      )}
      {optional.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-secondary-700 mb-2">
            Optional ({optional.length})
          </h3>
          <div className="space-y-2">
            {optional.map((item) => {
              const globalIndex = items.indexOf(item);
              return (
                <MatchItemRow
                  key={item.need_key}
                  item={item}
                  index={globalIndex}
                  onUpdateDecision={onUpdateDecision}
                />
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function MatchItemRow({
  item,
  index,
  onUpdateDecision,
}: {
  item: QBMatchItem;
  index: number;
  onUpdateDecision: (index: number, decision: QBMatchDecision) => void;
}) {
  const [expanded, setExpanded] = useState(false);

  const statusIcon =
    item.status === "matched" ? (
      <CheckCircle2 className="h-4 w-4 text-success-600" />
    ) : item.status === "candidates" ? (
      <AlertCircle className="h-4 w-4 text-amber-500" />
    ) : (
      <AlertTriangle className="h-4 w-4 text-danger-500" />
    );

  const decisionLabel =
    item.decision === "use_existing"
      ? item.decision_account_name ?? "Selected"
      : item.decision === "create_new"
        ? "Create new"
        : item.decision === "skip"
          ? "Skip"
          : null;

  return (
    <div className="rounded-lg border border-secondary-200 bg-white">
      {/* Header row */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-secondary-50 transition-colors"
      >
        {expanded ? (
          <ChevronDown className="h-4 w-4 text-secondary-400 shrink-0" />
        ) : (
          <ChevronRight className="h-4 w-4 text-secondary-400 shrink-0" />
        )}
        {statusIcon}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-secondary-900">
              {item.need_label}
            </span>
            {item.required && (
              <Badge variant="outline" className="text-[9px] px-1.5 py-0">required</Badge>
            )}
          </div>
          <p className="text-xs text-secondary-400 truncate">{item.need_description}</p>
        </div>
        <div className="shrink-0 text-right">
          {item.decision ? (
            <Badge
              variant={item.decision === "skip" ? "outline" : "success"}
              className="text-[10px]"
            >
              {decisionLabel}
            </Badge>
          ) : item.best_match ? (
            <span className="text-xs text-secondary-600">
              {item.best_match.qb_account_name}
              <span className="ml-1 text-secondary-400">
                ({(item.best_match.score * 100).toFixed(0)}%)
              </span>
            </span>
          ) : (
            <span className="text-xs text-secondary-400">No match</span>
          )}
        </div>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="border-t border-secondary-100 px-4 py-3 bg-secondary-50/50 space-y-3">
          <div className="text-xs text-secondary-500">
            Expected QB types: {item.expected_qb_types.join(", ")}
            {item.expected_qb_sub_type && ` / ${item.expected_qb_sub_type}`}
          </div>

          {/* Candidates list */}
          {item.candidates.length > 0 ? (
            <div className="space-y-1">
              <p className="text-xs font-medium text-secondary-600">
                Candidates ({item.candidates.length}):
              </p>
              {item.candidates.map((c) => (
                <CandidateRow
                  key={c.qb_account_id}
                  candidate={c}
                  isSelected={item.decision_account_id === c.qb_account_id}
                  onSelect={() =>
                    onUpdateDecision(index, {
                      index,
                      decision: "use_existing",
                      qb_account_id: c.qb_account_id,
                      qb_account_name: c.qb_account_name,
                    })
                  }
                />
              ))}
            </div>
          ) : (
            <p className="text-xs text-secondary-400">No matching candidates found.</p>
          )}

          {/* Action buttons */}
          <div className="flex gap-2 pt-1">
            <Button
              variant={item.decision === "create_new" ? "default" : "outline"}
              size="sm"
              className="h-7 text-xs"
              onClick={() =>
                onUpdateDecision(index, {
                  index,
                  decision: "create_new",
                  qb_account_name: item.need_label,
                })
              }
            >
              Create New Account
            </Button>
            {!item.required && (
              <Button
                variant={item.decision === "skip" ? "default" : "outline"}
                size="sm"
                className="h-7 text-xs"
                onClick={() => onUpdateDecision(index, { index, decision: "skip" })}
              >
                Skip
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function CandidateRow({
  candidate,
  isSelected,
  onSelect,
}: {
  candidate: QBMatchCandidate;
  isSelected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      onClick={onSelect}
      className={`w-full flex items-center gap-2 px-3 py-2 rounded text-left text-xs transition-colors ${
        isSelected
          ? "bg-primary-50 border border-primary-300 text-primary-900"
          : "bg-white border border-secondary-200 hover:border-primary-200 text-secondary-700"
      }`}
    >
      <div className="flex-1 min-w-0">
        <span className="font-medium">{candidate.qb_account_name}</span>
        <span className="text-secondary-400 ml-2">
          {candidate.qb_account_type}
          {candidate.qb_account_sub_type && ` / ${candidate.qb_account_sub_type}`}
        </span>
      </div>
      <ConfidenceBadge confidence={candidate.confidence} score={candidate.score} />
      {isSelected && <CheckCircle2 className="h-3.5 w-3.5 text-primary-600 shrink-0" />}
    </button>
  );
}

function ConfidenceBadge({ confidence, score }: { confidence: string; score: number }) {
  const cls =
    confidence === "high"
      ? "bg-success-100 text-success-700"
      : confidence === "medium"
        ? "bg-amber-100 text-amber-700"
        : "bg-secondary-100 text-secondary-600";

  return (
    <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${cls}`}>
      {(score * 100).toFixed(0)}%
    </span>
  );
}

function ApplyResultCard({ result }: { result: QBMatchApplyResult }) {
  const hasErrors = result.errors.length > 0;
  return (
    <Card>
      <CardContent className="py-4 space-y-3">
        <div className="flex items-center gap-2">
          {hasErrors ? (
            <AlertTriangle className="h-5 w-5 text-amber-500" />
          ) : (
            <CheckCircle2 className="h-5 w-5 text-success-600" />
          )}
          <span className="font-semibold text-secondary-900">
            {hasErrors ? "Applied with warnings" : "Successfully applied"}
          </span>
        </div>
        <div className="grid grid-cols-3 gap-4 text-sm">
          <div>
            <p className="text-secondary-500">Accounts Created</p>
            <p className="text-xl font-bold text-secondary-900">{result.accounts_created}</p>
          </div>
          <div>
            <p className="text-secondary-500">Mappings Created</p>
            <p className="text-xl font-bold text-secondary-900">{result.mappings_created}</p>
          </div>
          <div>
            <p className="text-secondary-500">Skipped</p>
            <p className="text-xl font-bold text-secondary-900">{result.skipped}</p>
          </div>
        </div>
        {result.errors.length > 0 && (
          <div className="rounded bg-danger-50 px-3 py-2 text-xs text-danger-700">
            <p className="font-medium mb-1">Errors:</p>
            <ul className="list-disc ml-4 space-y-0.5">
              {result.errors.map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          </div>
        )}
        {result.details.length > 0 && (
          <div className="text-xs text-secondary-500 space-y-0.5">
            {result.details.map((d, i) => (
              <p key={i}>{d}</p>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function HealthCheckResultCard({ result }: { result: QBHealthCheckResult }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <GradeIndicator grade={result.grade} />
        <div className="text-sm">
          <p className="font-semibold text-secondary-900">
            {result.healthy} healthy, {result.warnings} warnings, {result.critical} critical
          </p>
          <p className="text-xs text-secondary-400">
            {result.total_mappings} mappings checked at{" "}
            {new Date(result.checked_at).toLocaleString()}
          </p>
        </div>
      </div>

      {result.details.length > 0 && (
        <div className="rounded-lg border border-secondary-200 overflow-hidden">
          <table className="w-full text-xs">
            <thead className="bg-secondary-50 text-secondary-600">
              <tr>
                <th className="px-3 py-1.5 text-left font-medium">Mapping</th>
                <th className="px-3 py-1.5 text-left font-medium">Account</th>
                <th className="px-3 py-1.5 text-left font-medium">Status</th>
                <th className="px-3 py-1.5 text-left font-medium">Message</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-secondary-100">
              {result.details.map((d) => (
                <tr key={d.mapping_id}>
                  <td className="px-3 py-1.5">
                    <Badge variant="outline" className="text-[9px]">
                      {d.mapping_type}
                    </Badge>
                  </td>
                  <td className="px-3 py-1.5 text-secondary-700">{d.qb_account_name}</td>
                  <td className="px-3 py-1.5">
                    <HealthStatusBadge status={d.status} />
                  </td>
                  <td className="px-3 py-1.5 text-secondary-500">{d.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function HealthStatusBadge({ status }: { status: string }) {
  if (status === "healthy") {
    return (
      <Badge variant="success" className="text-[9px]">
        <CheckCircle2 className="h-3 w-3 mr-0.5" />
        OK
      </Badge>
    );
  }
  if (status === "warning") {
    return (
      <Badge className="text-[9px] bg-amber-100 text-amber-700">
        <AlertCircle className="h-3 w-3 mr-0.5" />
        Warning
      </Badge>
    );
  }
  return (
    <Badge variant="destructive" className="text-[9px]">
      <AlertTriangle className="h-3 w-3 mr-0.5" />
      Critical
    </Badge>
  );
}
