/**
 * QuickBooks integration TypeScript types.
 *
 * Maps to backend schemas in backend/app/schemas/quickbooks.py
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
// Templates
// ---------------------------------------------------------------------------

export interface QBTemplateMappingDef {
  mapping_type: string;
  name: string;
  account_type: string;
  account_sub_type: string;
  is_default: boolean;
  description: string;
}

export interface QBTemplateInfo {
  template_name: string;
  name: string;
  description: string;
  mapping_count: number;
  mappings: QBTemplateMappingDef[];
}

export type TemplateCategory =
  | "all"
  | "pakistani"
  | "international"
  | "format"
  | "specialty"
  | "niche";

export const TEMPLATE_CATEGORIES: Record<string, TemplateCategory> = {
  // Pakistani (8)
  pakistani_restaurant: "pakistani",
  pakistani_bbq_specialist: "pakistani",
  biryani_house: "pakistani",
  pakistani_street_food: "pakistani",
  nihari_paye_house: "pakistani",
  pakistani_sweets_bakery: "pakistani",
  karachi_seafood: "pakistani",
  lahore_food_street: "pakistani",
  // International (8)
  international_restaurant: "international",
  chinese_restaurant: "international",
  pizza_chain: "international",
  burger_joint: "international",
  steakhouse: "international",
  japanese_sushi: "international",
  thai_restaurant: "international",
  italian_restaurant: "international",
  // Format (10)
  qsr: "format",
  cafe: "format",
  fine_dining: "format",
  buffet_restaurant: "format",
  food_court_vendor: "format",
  cloud_kitchen: "format",
  food_truck: "format",
  catering_company: "format",
  hotel_restaurant: "format",
  bar_lounge: "format",
  // Specialty (8)
  juice_bar: "specialty",
  ice_cream_parlor: "specialty",
  bakery_wholesale: "specialty",
  breakfast_spot: "specialty",
  dessert_parlor: "specialty",
  tea_house: "specialty",
  shawarma_wrap_shop: "specialty",
  fried_chicken_chain: "specialty",
  // Niche (6)
  electronics_food: "niche",
  vegan_vegetarian: "niche",
  organic_farm_to_table: "niche",
  dark_kitchen: "niche",
  diner: "niche",
  roti_canteen: "niche",
};

export const CATEGORY_LABELS: Record<TemplateCategory, string> = {
  all: "All",
  pakistani: "Pakistani",
  international: "International",
  format: "Format / Model",
  specialty: "Specialty",
  niche: "Niche",
};

// ---------------------------------------------------------------------------
// Shared Constants
// ---------------------------------------------------------------------------

/** Canonical mapping type labels — single source of truth for all QB tabs */
export const MAPPING_TYPE_LABELS: Record<string, string> = {
  income: "Income",
  cogs: "Cost of Goods Sold",
  tax_payable: "Tax Payable",
  bank: "Bank / Cash",
  expense: "Expenses",
  discount: "Discounts",
  rounding: "Rounding",
  cash_over_short: "Cash Over/Short",
  tips: "Tips",
  service_charge: "Service Charge",
  delivery_fee: "Delivery Fee",
  foodpanda_commission: "Platform Commission",
  gift_card_liability: "Gift Cards",
  other_current_liability: "Other Liabilities",
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
// Smart Defaults
// ---------------------------------------------------------------------------

export interface QBSmartDefaultsResult {
  accounts_created: number;
  mappings_created: number;
  mappings_skipped: number;
  details: string[];
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
// Preview / Simulation
// ---------------------------------------------------------------------------

export interface QBPreviewResponse {
  template_name: string;
  template_display_name: string;
  order_number: string;
  order_type: string;
  qb_entity_type: string;
  payload: Record<string, unknown>;
  mappings_used: QBTemplateMappingDef[];
}

// ---------------------------------------------------------------------------
// Diagnostic & Onboarding Tool
// ---------------------------------------------------------------------------

export interface QBMatchSignals {
  exact: number;
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

export interface QBDiagnosticItem {
  mapping_type: string;
  template_account_name: string;
  template_account_type: string;
  template_account_sub_type?: string;
  template_description: string;
  is_default: boolean;
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

export interface QBDiagnosticReport {
  id: string;
  template_key: string;
  template_name: string;
  created_at: string;
  fixture_name: string | null;
  is_live: boolean;
  total_template_mappings: number;
  total_qb_accounts: number;
  matched: number;
  candidates: number;
  unmatched: number;
  coverage_pct: number;
  health_grade: "A" | "B" | "C" | "F";
  summary: string;
  items: QBDiagnosticItem[];
  unmapped_qb_accounts: QBUnmappedAccount[];
  decision_summary?: QBDecisionSummary;
  apply_result?: Record<string, unknown>;
  applied_at?: string;
}

export interface QBDiagnosticReportSummary {
  id: string;
  template_key: string;
  template_name: string;
  created_at: string;
  health_grade: string;
  matched: number;
  candidates: number;
  unmatched: number;
  total_template_mappings: number;
  coverage_pct: number;
  is_live: boolean;
  fixture_name: string | null;
}

export interface QBDiagnosticDecision {
  index: number;
  decision: "use_existing" | "create_new" | "skip";
  qb_account_id?: string;
  qb_account_name?: string;
}

export interface QBDiagnosticApplyResult {
  accounts_created: number;
  mappings_created: number;
  skipped: number;
  errors: string[];
  details: string[];
  report_id: string;
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

export interface QBTestFixture {
  name: string;
  description: string;
  account_count: number;
}
