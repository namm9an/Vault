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
