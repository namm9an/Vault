export type UserRole = "ADMIN" | "FINANCE_MANAGER" | "EMPLOYEE";

export type User = {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  org_id: string;
  department_id: string | null;
  is_active: boolean;
};

export type Org = {
  id: string;
  name: string;
  slug: string;
  base_currency: string;
};

export type TokenPair = {
  access_token: string;
  refresh_token: string;
  user: User;
};

export type MeResponse = {
  user: User;
  org: Org;
};

export type CardStatus = "ACTIVE" | "FROZEN" | "CANCELLED";

export type SpendCategory =
  | "TRAVEL"
  | "MEALS"
  | "SAAS"
  | "OFFICE"
  | "MARKETING"
  | "HARDWARE"
  | "PROFESSIONAL_SERVICES"
  | "OTHER";

export type Card = {
  id: string;
  org_id: string;
  user_id: string;
  department_id: string | null;
  nickname: string;
  last_four: string;
  status: CardStatus;
  daily_limit: string;
  monthly_limit: string;
  total_limit: string;
  category_restrictions: SpendCategory[];
  currency: string;
  frozen_at: string | null;
  cancelled_at: string | null;
  created_at: string;
  updated_at: string;
};

export type UserListResponse = {
  items: User[];
  next_cursor: string | null;
};

export type UserInviteResponse = {
  user: User;
  invite_token: string;
};

// ---------------------------------------------------------------------------
// Transactions
// ---------------------------------------------------------------------------

export type TransactionState =
  | "INITIATED"
  | "POLICY_CHECKED"
  | "APPROVED"
  | "FLAGGED"
  | "BLOCKED"
  | "CLEARED"
  | "SETTLED";

export type PolicyVerdict = "APPROVED" | "FLAGGED" | "BLOCKED";

export type Transaction = {
  id: string;
  org_id: string;
  user_id: string;
  card_id: string;
  department_id: string | null;
  amount: string; // Decimal serialized as string
  currency: string;
  merchant: string;
  category: SpendCategory;
  state: TransactionState;
  description: string | null;
  occurred_at: string;
  created_at: string;
  updated_at: string;
  policy_verdict: PolicyVerdict | null;
};

export type TransactionEvent = {
  id: string;
  transaction_id: string;
  org_id: string;
  from_state: TransactionState | null;
  to_state: TransactionState;
  triggered_by_user: string | null;
  triggered_by_system: boolean;
  reason: string | null;
  event_metadata: Record<string, unknown>;
  created_at: string;
};

export type TransactionPolicyResult = {
  id: string;
  org_id: string;
  transaction_id: string;
  verdict: PolicyVerdict;
  reason: string;
  policy_matched: string | null;
  requires_approval_from_role: UserRole | null;
  llm_model: string;
  llm_latency_ms: number | null;
  created_at: string;
};

export type TransactionWithEvents = Transaction & {
  events: TransactionEvent[];
  latest_policy_result: TransactionPolicyResult | null;
};

// ---------------------------------------------------------------------------
// Policies
// ---------------------------------------------------------------------------

export type Policy = {
  id: string;
  org_id: string;
  policy_text: string;
  is_active: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
};

// ---------------------------------------------------------------------------
// Receipts
// ---------------------------------------------------------------------------

export type ReceiptStatus =
  | "PENDING_UPLOAD"
  | "PROCESSING"
  | "COMPLETED"
  | "NEEDS_REVIEW"
  | "FAILED";

export type Receipt = {
  id: string;
  org_id: string;
  uploaded_by: string;
  content_type: string;
  object_key: string;
  byte_size: number | null;
  status: ReceiptStatus;
  confidence: string | null;
  extracted_data: Record<string, unknown> | null;
  llm_error: string | null;
  created_at: string;
  updated_at: string;
};

export type UploadUrlResponse = {
  receipt_id: string;
  upload_url: string;
  object_key: string;
};

// ---------------------------------------------------------------------------
// Reimbursements
// ---------------------------------------------------------------------------

export type ReimbursementStatus =
  | "SUBMITTED"
  | "POLICY_CHECKED"
  | "APPROVED"
  | "REJECTED"
  | "PAID";

export type Reimbursement = {
  id: string;
  org_id: string;
  user_id: string;
  department_id?: string;
  amount: string;
  currency: string;
  category: SpendCategory;
  description: string;
  receipt_id?: string;
  status: ReimbursementStatus;
  decision_reason?: string;
  decided_by?: string;
  decided_at?: string;
  paid_at?: string;
  created_at: string;
  updated_at: string;
};

// ---------------------------------------------------------------------------
// Departments
// ---------------------------------------------------------------------------

export type Department = {
  id: string;
  org_id: string;
  name: string;
  monthly_budget: string;
  budget_currency: string;
  alert_threshold_pct: number;
  manager_id?: string;
};

export type BudgetStatus = {
  department_id: string;
  department_name: string;
  monthly_budget: string;
  budget_currency: string;
  spent: string;
  remaining: string;
  utilization_pct: number;
  alert_threshold_pct: number;
  is_over_threshold: boolean;
};

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------

export type CategorySpend = {
  category: string;
  amount: string;
  transaction_count: number;
};

export type DepartmentSpend = {
  department_id: string;
  department_name: string;
  amount: string;
};

export type MerchantSpend = {
  merchant: string;
  amount: string;
  count: number;
};

export type TimeseriesPoint = {
  period: string;
  amount: string;
};

export type DashboardSummary = {
  total_spend: string;
  transaction_count: number;
  mom_delta_pct: number | null;
  by_category: CategorySpend[];
  by_department: DepartmentSpend[];
  top_merchants: MerchantSpend[];
  pending_approvals: number;
  active_cards: number;
};

// ---------------------------------------------------------------------------
// Notifications
// ---------------------------------------------------------------------------

export type NotificationType =
  | "POLICY_FLAGGED"
  | "POLICY_BLOCKED"
  | "APPROVAL_REQUESTED"
  | "APPROVAL_GRANTED"
  | "APPROVAL_REJECTED"
  | "BUDGET_THRESHOLD"
  | "DIGEST_READY"
  | "RECEIPT_REVIEW_NEEDED";

export type Notification = {
  id: string;
  type: string;
  title: string;
  body: string;
  link: string | null;
  payload: Record<string, unknown>;
  read_at: string | null;
  created_at: string;
};

// ---------------------------------------------------------------------------
// Digest
// ---------------------------------------------------------------------------

export type DigestStatus = "PENDING" | "COMPLETED" | "FAILED";

export interface Digest {
  id: string;
  org_id: string;
  period_start: string;
  period_end: string;
  status: DigestStatus;
  headline: string | null;
  body: string | null;
  top_recommendations: string[] | null;
  flagged_items: Array<{ description: string; amount: number; reason: string }> | null;
  created_at: string;
  updated_at: string;
}
