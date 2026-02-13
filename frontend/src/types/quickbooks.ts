/**
 * QuickBooks integration TypeScript types (Attempt 2 — client-centric).
 *
 * No templates. POS declares needs, fuzzy-matches against partner's QB accounts.
 */

// ---------------------------------------------------------------------------
// Connection
// ---------------------------------------------------------------------------

export interface QBConnectionStatus {
  is_connected: boolean;
  realm_id?: string;
  company_name?: string;
  connected_at?: string;
  last_sync_at?: string;
  last_sync_status?: string;
  token_expires_at?: string;
}

// ---------------------------------------------------------------------------
// POS Accounting Needs
// ---------------------------------------------------------------------------

export interface POSAccountingNeed {
  key: string;
  label: string;
  description: string;
  expected_qb_types: string[];
  expected_qb_sub_type: string | null;
  required: boolean;
  search_hints: string[];
}

// ---------------------------------------------------------------------------
// Mapping Type Labels
// ---------------------------------------------------------------------------

export const MAPPING_TYPE_LABELS: Record<string, string> = {
  income: "Food Sales Income",
  beverage_income: "Beverage Sales",
  cogs: "Cost of Goods Sold",
  tax_payable: "Sales Tax Payable",
  bank: "Bank / Deposit",
  cash: "Cash on Hand",
  mobile_wallet: "Mobile Wallet",
  discount: "Discounts Given",
  rounding: "Rounding Adjustment",
  cash_over_short: "Cash Over/Short",
  tips: "Tips / Gratuity",
  service_charge: "Service Charge",
  delivery_fee: "Delivery Fee",
  foodpanda_commission: "Platform Commission",
  gift_card_liability: "Gift Cards",
  rent_expense: "Rent / Occupancy",
  salary_expense: "Salaries & Wages",
  utility_expense: "Utilities",
  packaging_expense: "Packaging",
};

// ---------------------------------------------------------------------------
// Account Mappings
// ---------------------------------------------------------------------------

export interface QBAccountMapping {
  id: string;
  connection_id: string;
  mapping_type: string;
  pos_reference_id?: string;
  pos_reference_type?: string;
  pos_reference_name?: string;
  qb_account_id: string;
  qb_account_name: string;
  qb_account_type: string;
  qb_account_sub_type?: string;
  is_default: boolean;
  is_auto_created: boolean;
  created_at: string;
}

export interface QBAccountMappingCreate {
  mapping_type: string;
  qb_account_id: string;
  qb_account_name: string;
  qb_account_type: string;
  qb_account_sub_type?: string;
  pos_reference_id?: string;
  pos_reference_type?: string;
  pos_reference_name?: string;
  is_default?: boolean;
}

// ---------------------------------------------------------------------------
// Sync
// ---------------------------------------------------------------------------

export interface QBSyncStats {
  total_synced: number;
  last_24h_synced: number;
  last_24h_failed: number;
  pending_jobs: number;
  failed_jobs: number;
  dead_letter_jobs: number;
  last_sync_at?: string;
  sync_by_type: Record<string, number>;
}

export interface QBSyncJob {
  id: string;
  job_type: string;
  entity_type: string;
  entity_id?: string;
  priority: number;
  status: string;
  error_message?: string;
  retry_count: number;
  created_at: string;
  completed_at?: string;
  processing_duration_ms?: number;
}

export interface QBSyncLog {
  id: string;
  sync_type: string;
  pos_entity_type?: string;
  pos_entity_id?: string;
  qb_entity_type?: string;
  qb_entity_id?: string;
  action: string;
  status: string;
  error_message?: string;
  error_code?: string;
  duration_ms?: number;
  qb_doc_number?: string;
  amount_paisa?: number;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Account Matching (Attempt 2)
// ---------------------------------------------------------------------------

export interface QBMatchSignals {
  exact: number;
  anchor: number;
  jaccard: number;
  synonym: number;
  type_match: number;
  substring: number;
}

export interface QBMatchCandidate {
  qb_account_id: string;
  qb_account_name: string;
  qb_account_type: string;
  qb_account_sub_type?: string;
  fully_qualified_name?: string;
  active: boolean;
  score: number;
  signals: QBMatchSignals;
  confidence: "high" | "medium" | "low";
}

export interface QBMatchItem {
  need_key: string;
  need_label: string;
  need_description: string;
  expected_qb_types: string[];
  expected_qb_sub_type?: string;
  required: boolean;
  status: "matched" | "candidates" | "unmatched";
  best_match: QBMatchCandidate | null;
  candidates: QBMatchCandidate[];
  decision: "use_existing" | "create_new" | "skip" | null;
  decision_account_id: string | null;
  decision_account_name: string | null;
}

export interface QBUnmappedAccount {
  qb_account_id: string;
  qb_account_name: string;
  qb_account_type: string;
  qb_account_sub_type?: string;
  fully_qualified_name?: string;
  active: boolean;
  suggested_mapping_type: string | null;
}

export interface QBDecisionSummary {
  use_existing: number;
  create_new: number;
  skip: number;
  pending: number;
  ready_to_apply: boolean;
}

export interface QBMatchResult {
  id: string;
  created_at: string;
  is_live: boolean;
  total_needs: number;
  total_qb_accounts: number;
  matched: number;
  candidates: number;
  unmatched: number;
  required_total: number;
  required_matched: number;
  coverage_pct: number;
  health_grade: "A" | "B" | "C" | "F";
  items: QBMatchItem[];
  unmapped_qb_accounts: QBUnmappedAccount[];
  decision_summary?: QBDecisionSummary;
  apply_result?: Record<string, unknown>;
  applied_at?: string;
}

export interface QBMatchDecision {
  index: number;
  decision: "use_existing" | "create_new" | "skip";
  qb_account_id?: string;
  qb_account_name?: string;
}

export interface QBMatchApplyResult {
  accounts_created: number;
  mappings_created: number;
  skipped: number;
  errors: string[];
  details: string[];
  result_id: string;
}

export interface QBHealthCheckDetail {
  mapping_id: string;
  mapping_type: string;
  qb_account_id: string;
  qb_account_name: string;
  status: "healthy" | "warning" | "critical";
  issue: string | null;
  message: string;
  current_name: string | null;
}

export interface QBHealthCheckResult {
  grade: "A" | "B" | "C" | "F";
  total_mappings: number;
  healthy: number;
  warnings: number;
  critical: number;
  checked_at: string;
  details: QBHealthCheckDetail[];
}
