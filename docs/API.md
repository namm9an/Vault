# Vault — API Reference

Base path: `/api/v1`. All endpoints accept and return JSON. Auth is `Authorization: Bearer <access_token>` unless noted. List endpoints support `?limit=<1..100, default 25>` and `?cursor=<opaque>`.

**Standard error envelope:**
```json
{ "error": { "code": "VALIDATION_ERROR", "message": "amount must be positive" } }
```

**Common errors omitted per-endpoint:** `401` (missing/invalid token), `500` (server error). They apply everywhere.

---

## Auth

### POST /auth/signup
**Auth required:** No
**Description:** Create a new organization and its first ADMIN user.

**Request body:**
```json
{
  "org_name": "Acme Corp",
  "email": "alice@acme.com",
  "password": "correct horse battery staple",
  "full_name": "Alice Sharma"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOi...",
  "refresh_token": "eyJhbGciOi...",
  "user": { "id": "uuid", "email": "alice@acme.com", "role": "ADMIN", "org_id": "uuid", "full_name": "Alice Sharma" }
}
```

**Error responses:**
- 409 — email or org slug already in use
- 422 — password too weak / fields missing

---

### POST /auth/login
**Auth required:** No
**Description:** Exchange credentials for tokens.

**Request body:**
```json
{ "email": "alice@acme.com", "password": "..." }
```

**Response:**
```json
{
  "access_token": "...",
  "refresh_token": "...",
  "user": { "id": "uuid", "email": "...", "role": "ADMIN", "org_id": "uuid", "full_name": "..." }
}
```

**Error responses:**
- 401 — invalid credentials
- 403 — user disabled

---

### POST /auth/refresh
**Auth required:** No (uses refresh token in body)
**Description:** Mint a new access token (and rotate the refresh token).

**Request body:**
```json
{ "refresh_token": "..." }
```

**Response:**
```json
{ "access_token": "...", "refresh_token": "..." }
```

**Error responses:**
- 401 — refresh token expired or revoked

---

### POST /auth/logout
**Auth required:** Yes
**Description:** Revoke a refresh token.

**Request body:**
```json
{ "refresh_token": "..." }
```

**Response:**
```json
{ "ok": true }
```

---

### GET /auth/me
**Auth required:** Yes
**Description:** Return the current user plus their organization.

**Request body:** —

**Response:**
```json
{
  "user": { "id": "uuid", "email": "...", "role": "ADMIN", "full_name": "...", "department_id": null },
  "org":  { "id": "uuid", "name": "Acme Corp", "slug": "acme", "base_currency": "INR" }
}
```

---

## Users

### GET /users
**Auth required:** Yes — any role
**Description:** List users in the current org.

**Response:**
```json
{ "items": [{ "id": "uuid", "email": "...", "role": "EMPLOYEE", "full_name": "...", "department_id": "uuid", "is_active": true }], "next_cursor": null }
```

---

### POST /users
**Auth required:** Yes — ADMIN
**Description:** Invite a user. The user is created `is_active=true` and can log in immediately with the supplied password. `invite_token` is a placeholder UUID reserved for a future email-delivery flow.

**Request body:**
```json
{ "email": "bob@acme.com", "full_name": "Bob Patel", "role": "EMPLOYEE", "password": "changeme1", "department_id": "uuid" }
```

**Response:**
```json
{ "user": { "id": "uuid", "email": "...", "role": "EMPLOYEE", "is_active": true }, "invite_token": "uuid" }
```

**Error responses:**
- 403 — caller is not ADMIN
- 409 — email already registered
- 422 — password shorter than 8 characters

---

### GET /users/{id}
**Auth required:** Yes — self, ADMIN, or FINANCE_MANAGER
**Description:** Get one user.

**Response:**
```json
{ "user": { "id": "uuid", "email": "...", "role": "...", "full_name": "...", "department_id": "uuid", "is_active": true, "last_login_at": "2026-05-26T10:00:00Z" } }
```

**Error responses:**
- 403 — EMPLOYEE trying to read another user
- 404 — not found in this org

---

### PATCH /users/{id}
**Auth required:** Yes — ADMIN
**Description:** Update role, department, or active state.

**Request body:**
```json
{ "role": "FINANCE_MANAGER", "department_id": "uuid", "is_active": true }
```

**Response:**
```json
{ "user": { "...": "..." } }
```

---

### DELETE /users/{id}
**Auth required:** Yes — ADMIN
**Description:** Soft-delete (sets `is_active=false`); does not remove transactions.

**Response:** `{ "ok": true }`

---

## Cards

### GET /cards
**Auth required:** Yes — EMPLOYEE sees only own; ADMIN/FM sees all in org.
**Description:** List cards. Returns a flat array (cursor pagination deferred).

**Response:**
```json
[
  {
    "id": "uuid", "org_id": "uuid", "user_id": "uuid", "department_id": null,
    "nickname": "Marketing card", "last_four": "4242", "status": "ACTIVE",
    "daily_limit": "10000.00", "monthly_limit": "200000.00", "total_limit": "0.00",
    "category_restrictions": ["MARKETING","SAAS"], "currency": "INR",
    "frozen_at": null, "cancelled_at": null, "created_at": "...", "updated_at": "..."
  }
]
```

---

### POST /cards
**Auth required:** Yes — ADMIN
**Description:** Issue a virtual card to a user.

**Request body:**
```json
{
  "user_id": "uuid",
  "nickname": "Travel card — Bob",
  "daily_limit": "5000.00",
  "monthly_limit": "100000.00",
  "total_limit": "0.00",
  "category_restrictions": ["TRAVEL", "MEALS"],
  "department_id": "uuid",
  "currency": "INR"
}
```

**Response:** `{ "card": { ... } }`

**Error responses:**
- 403 — not ADMIN
- 422 — user not in same org / limit invalid

---

### GET /cards/{id}
**Auth required:** Yes — owner, ADMIN, or FM
**Response:** `{ "card": { ... } }`

**Error responses:**
- 403 — EMPLOYEE asking for another user's card
- 404 — not found in this org

---

### PATCH /cards/{id}
**Auth required:** Yes — ADMIN
**Description:** Update limits, nickname, restrictions, department.

**Request body:**
```json
{ "daily_limit": "8000.00", "category_restrictions": ["TRAVEL"] }
```

**Response:** `{ "card": { ... } }`

---

### POST /cards/{id}/freeze
**Auth required:** Yes — ADMIN
**Description:** Freeze the card. Active transactions in non-terminal states are not affected, but new ones will be blocked.

**Response:** `{ "card": { "status": "FROZEN", "frozen_at": "..." } }`

---

### POST /cards/{id}/unfreeze
**Auth required:** Yes — ADMIN
**Response:** `{ "card": { "status": "ACTIVE", "frozen_at": null } }`

---

### POST /cards/{id}/cancel
**Auth required:** Yes — ADMIN
**Description:** Terminal. Cancelled cards cannot be unfrozen.
**Response:** `{ "card": { "status": "CANCELLED", "cancelled_at": "..." } }`

---

## Transactions

> **Phase 4 update:** The policy engine is now a real async LLM job. `POST /transactions` commits INITIATED + POLICY_CHECKED events and returns immediately with `state: "POLICY_CHECKED"`. The ARQ worker picks up `run_policy_check` and calls Llama 3.1 8B (temp 0) against the org's active policies, then transitions the transaction to APPROVED / FLAGGED / BLOCKED. If no active policies exist, the transaction auto-approves. Poll `GET /transactions/{id}` until `state` leaves `POLICY_CHECKED`. The old amount-threshold stub has been removed.

### GET /transactions
**Auth required:** Yes — EMPLOYEE sees only own; ADMIN/FM sees all in org.
**Description:** List transactions with optional filters. Returns a flat array (cursor pagination deferred — same decision as GET /cards).

**Query params:** `from_date`, `to_date`, `category`, `department_id`, `card_id`, `user_id`, `state`.

**Response:**
```json
[
  {
    "id": "uuid", "org_id": "uuid", "card_id": "uuid", "user_id": "uuid",
    "department_id": "uuid",
    "amount": "850.00", "currency": "INR", "merchant": "Blue Tokai",
    "category": "MEALS", "state": "CLEARED",
    "description": "Team coffee", "occurred_at": "2026-05-26T08:30:00Z",
    "created_at": "...", "updated_at": "..."
  }
]
```

---

### POST /transactions
**Auth required:** Yes
**Description:** Create a transaction (mock — no real card network). Commits INITIATED + POLICY_CHECKED events and enqueues the `run_policy_check` ARQ job. Returns immediately with `state: "POLICY_CHECKED"`. Poll until state changes. Optionally supply `receipt_id` to attach a receipt (must belong to same org).

**Request body:**
```json
{
  "card_id": "uuid",
  "amount": "850.00",
  "currency": "INR",
  "merchant": "Blue Tokai",
  "category": "MEALS",
  "description": "Team coffee",
  "occurred_at": "2026-05-26T08:30:00Z",
  "department_id": "uuid",
  "receipt_id": "uuid"
}
```

**Response:** Returns immediately with `state: "POLICY_CHECKED"`. Poll `GET /transactions/{id}` until state advances.
```json
{
  "id": "uuid", "org_id": "uuid", "card_id": "uuid", "user_id": "uuid",
  "amount": "850.00", "currency": "INR", "merchant": "Blue Tokai",
  "category": "MEALS", "state": "POLICY_CHECKED",
  "description": "Team coffee", "occurred_at": "...",
  "receipt_id": null,
  "created_at": "...", "updated_at": "..."
}
```

**Error responses:**
- 404 — card not found in this org (EMPLOYEE using another user's card also returns 404)
- 404 — receipt not found in this org (if receipt_id supplied)
- 422 — card is FROZEN or CANCELLED

---

### GET /transactions/{id}
**Auth required:** Yes — owner, ADMIN, or FM
**Description:** Full transaction with the complete event timeline and latest policy result.

**Response:**
```json
{
  "id": "uuid", "org_id": "uuid", "card_id": "uuid", "user_id": "uuid",
  "amount": "850.00", "currency": "INR", "merchant": "Blue Tokai",
  "category": "MEALS", "state": "CLEARED",
  "description": "Team coffee", "occurred_at": "...",
  "created_at": "...", "updated_at": "...",
  "events": [
    { "id": "uuid", "transaction_id": "uuid", "org_id": "uuid",
      "from_state": null, "to_state": "INITIATED",
      "triggered_by_user": "uuid", "triggered_by_system": false,
      "reason": "Transaction created", "created_at": "..." },
    { "id": "uuid", "transaction_id": "uuid", "org_id": "uuid",
      "from_state": "INITIATED", "to_state": "POLICY_CHECKED",
      "triggered_by_user": null, "triggered_by_system": true,
      "reason": null, "created_at": "..." },
    { "id": "uuid", "transaction_id": "uuid", "org_id": "uuid",
      "from_state": "POLICY_CHECKED", "to_state": "APPROVED",
      "triggered_by_user": null, "triggered_by_system": true,
      "reason": null, "created_at": "..." },
    { "id": "uuid", "transaction_id": "uuid", "org_id": "uuid",
      "from_state": "APPROVED", "to_state": "CLEARED",
      "triggered_by_user": null, "triggered_by_system": true,
      "reason": null, "created_at": "..." }
  ],
  "latest_policy_result": {
    "id": "uuid", "org_id": "uuid", "transaction_id": "uuid",
    "verdict": "APPROVED", "reason": "No applicable policy",
    "policy_matched": null, "requires_approval_from_role": null,
    "llm_model": "stub", "llm_latency_ms": null, "created_at": "..."
  }
}
```

**Error responses:**
- 403 — EMPLOYEE trying to read another user's transaction
- 404 — not found in this org

---

### POST /transactions/{id}/approve
**Auth required:** Yes — FINANCE_MANAGER or ADMIN
**Description:** Approve a FLAGGED transaction. Transitions `FLAGGED → APPROVED → CLEARED`.

**Request body:**
```json
{ "reason": "Pre-approved by VP" }
```

**Response:** Transaction object with updated state.

**Error responses:**
- 403 — caller is EMPLOYEE
- 404 — transaction not found in this org
- 409 — transaction is not in FLAGGED state

---

### POST /transactions/{id}/reject
**Auth required:** Yes — FINANCE_MANAGER or ADMIN
**Description:** Reject a FLAGGED transaction. Transitions `FLAGGED → BLOCKED`.

**Request body:**
```json
{ "reason": "Outside policy — personal expense" }
```

**Response:** Transaction object with `state: "BLOCKED"`.

**Error responses:**
- 403 — caller is EMPLOYEE
- 404 — transaction not found in this org
- 409 — transaction is not in FLAGGED state

---

### GET /transactions/{id}/events
**Auth required:** Yes — owner, ADMIN, or FM
**Description:** Full append-only event log for the transaction. Events are sorted by `created_at` ascending.

**Response:**
```json
[
  { "id": "uuid", "transaction_id": "uuid", "org_id": "uuid",
    "from_state": null, "to_state": "INITIATED",
    "triggered_by_user": "uuid", "triggered_by_system": false,
    "reason": "Transaction created", "created_at": "..." },
  { "id": "uuid", "transaction_id": "uuid", "org_id": "uuid",
    "from_state": "INITIATED", "to_state": "POLICY_CHECKED",
    "triggered_by_user": null, "triggered_by_system": true,
    "reason": null, "created_at": "..." }
]
```

**Error responses:**
- 403 — EMPLOYEE on another user's transaction
- 404 — not found in this org

---

## Receipts

### POST /receipts/upload-url
**Auth required:** Yes
**Description:** Allocate a `receipts` row and return a presigned PUT URL.

**Request body:**
```json
{ "filename": "lunch.jpg", "content_type": "image/jpeg" }
```

**Response:**
```json
{
  "receipt_id": "uuid",
  "upload_url": "https://objectstore.../...?X-Amz-Signature=...",
  "object_key": "org/uuid/receipts/uuid.jpg",
  "expires_at": "2026-05-26T10:05:00Z"
}
```

**Error responses:**
- 422 — content_type not in `image/jpeg`, `image/png`, `application/pdf`

---

### POST /receipts/{id}/confirm
**Auth required:** Yes
**Description:** Confirm the upload completed. API verifies via HEAD and enqueues OCR.

**Response:** `{ "receipt": { "id": "uuid", "status": "PROCESSING" } }`

**Error responses:**
- 404 — receipt not found in org
- 409 — object not present in storage / receipt already processed

---

### GET /receipts/{id}
**Auth required:** Yes — uploader, ADMIN, or FM
**Response:** Phase 4 — `ocr_receipt` marks all receipts `NEEDS_REVIEW` immediately (Llama 3.1 8B is text-only; `extracted_data` is null until a vision-capable model is wired in).
```json
{
  "id": "uuid",
  "org_id": "uuid",
  "uploaded_by": "uuid",
  "status": "NEEDS_REVIEW",
  "object_key": "org/uuid/receipts/uuid.jpg",
  "content_type": "image/jpeg",
  "byte_size": 142336,
  "extracted_data": null,
  "confidence": null,
  "llm_error": null,
  "transaction_id": null,
  "created_at": "...", "updated_at": "..."
}
```

---

### POST /receipts/{id}/link
**Auth required:** Yes (uploader)
**Description:** Link a receipt to a transaction or reimbursement after creation.

**Request body:**
```json
{ "transaction_id": "uuid" }
```

**Response:** `{ "receipt": { "...": "..." } }`

---

### POST /receipts/{id}/retry
**Auth required:** Yes
**Description:** Re-enqueue OCR after a FAILED status.

**Response:** `{ "receipt": { "status": "PROCESSING" } }`

**Error responses:**
- 409 — receipt is COMPLETED; nothing to retry

---

## Policies

### GET /policies
**Auth required:** Yes — any role
**Description:** List policies. Filter by `?active=true`.

**Response:**
```json
{
  "items": [{
    "id": "uuid", "text": "No alcohol purchases above ₹2,000",
    "is_active": true, "created_by": "uuid", "created_at": "..."
  }],
  "next_cursor": null
}
```

---

### POST /policies
**Auth required:** Yes — ADMIN

**Request body:**
```json
{ "text": "All SaaS tools over ₹10,000 require CFO approval", "is_active": true }
```

**Response:** `{ "policy": { "...": "..." } }`

---

### PATCH /policies/{id}
**Auth required:** Yes — ADMIN

**Request body:**
```json
{ "text": "...", "is_active": false }
```

**Response:** `{ "policy": { "...": "..." } }`

---

### DELETE /policies/{id}
**Auth required:** Yes — ADMIN
**Description:** Soft-deletes the policy (sets `is_active=false`, `deleted_at=now()`). Does not hard-delete — preserves FK references in `transaction_policy_results` for the audit trail.
**Response:** `{ "ok": true }`

---

## Reimbursements

### GET /reimbursements
**Auth required:** Yes — EMPLOYEE sees own; ADMIN/FM sees all.
**Query params:** `status`, `user_id`.

**Response:**
```json
{
  "items": [{
    "id": "uuid", "user_id": "uuid", "amount": "1200.00", "currency": "INR",
    "category": "TRAVEL", "description": "Cab to client",
    "status": "SUBMITTED", "receipt_id": "uuid", "created_at": "..."
  }],
  "next_cursor": null
}
```

---

### POST /reimbursements
**Auth required:** Yes — any role

**Request body:**
```json
{
  "amount": "1200.00", "currency": "INR",
  "category": "TRAVEL", "description": "Cab to client",
  "receipt_id": "uuid", "department_id": "uuid"
}
```

**Response:** `{ "reimbursement": { "status": "SUBMITTED", "...": "..." } }`

---

### GET /reimbursements/{id}
**Auth required:** Yes — owner, ADMIN, or FM

**Response:**
```json
{
  "reimbursement": { "...": "..." },
  "policy_result": { "verdict": "FLAGGED", "reason": "...", "policy_matched": "..." }
}
```

---

### POST /reimbursements/{id}/approve
**Auth required:** Yes — FM or ADMIN
**Description:** Approve a reimbursement. Requires `POLICY_CHECKED` status — the ARQ policy check job must have run first. If the LLM approved or flagged the request, it stays at `POLICY_CHECKED` awaiting FM sign-off. Only BLOCKED requests auto-transition to REJECTED; everything else requires this endpoint.

**Request body:**
```json
{ "reason": "Verified receipt" }
```

**Response:** `{ "reimbursement": { "status": "APPROVED", "decided_by": "uuid", "decided_at": "..." } }`

**Error responses:**
- 403 — caller is EMPLOYEE
- 404 — not found in org
- 409 — not in POLICY_CHECKED state (still SUBMITTED = job not run yet; already APPROVED/REJECTED/PAID = already decided)

---

### POST /reimbursements/{id}/reject
**Auth required:** Yes — FM or ADMIN

**Request body:**
```json
{ "reason": "Personal expense" }
```

**Response:** `{ "reimbursement": { "status": "REJECTED", "decision_reason": "..." } }`

---

### POST /reimbursements/{id}/mark-paid
**Auth required:** Yes — FM or ADMIN
**Description:** Mock payout — sets `paid_at`.
**Response:** `{ "reimbursement": { "status": "PAID", "paid_at": "..." } }`

**Error responses:**
- 409 — not in APPROVED state

---

## Departments

### GET /departments
**Auth required:** Yes — any role
**Response:**
```json
{ "items": [{ "id": "uuid", "name": "Engineering", "monthly_budget": "500000.00", "alert_threshold_pct": 80, "manager_id": "uuid" }] }
```

---

### POST /departments
**Auth required:** Yes — ADMIN

**Request body:**
```json
{ "name": "Sales", "monthly_budget": "300000.00", "alert_threshold_pct": 80, "manager_id": "uuid" }
```

**Response:** `{ "department": { "...": "..." } }`

**Error responses:**
- 409 — name already exists in org

---

### PATCH /departments/{id}
**Auth required:** Yes — ADMIN

**Request body:** Any subset of `{ "name", "monthly_budget", "alert_threshold_pct", "manager_id" }`

**Response:** `{ "department": { "...": "..." } }`

---

### DELETE /departments/{id}
**Auth required:** Yes — ADMIN
**Response:** `{ "ok": true }`

---

### GET /departments/{id}/budget-status
**Auth required:** Yes — ADMIN or FM
**Description:** Current calendar-month spend vs monthly budget. Fires a `BUDGET_THRESHOLD` notification (once per dept per month, Redis-deduped) if utilisation ≥ `alert_threshold_pct`. Redis failure degrades gracefully — budget data is always returned.

**Response:**
```json
{
  "department_id": "uuid",
  "department_name": "Engineering",
  "monthly_budget": "500000.00",
  "budget_currency": "INR",
  "spent": "415000.00",
  "remaining": "85000.00",
  "utilization_pct": 83.0,
  "alert_threshold_pct": 80,
  "is_over_threshold": true
}
```

**Error responses:**
- 404 — department not found in org

---

## Dashboard

### GET /dashboard/summary
**Auth required:** Yes — ADMIN or FM
**Description:** Aggregated spend summary for a date range. Cached in Redis for 5 minutes (keyed by org + date range MD5). Frontend `staleTime` matches this TTL.

**Query params:** `from_date` (ISO 8601), `to_date` (ISO 8601) — both required. Default: last 30 days if omitted.

**Response:**
```json
{
  "total_spend": "1250000.00",
  "transaction_count": 47,
  "mom_delta_pct": -12.3,
  "by_category": [
    { "category": "SAAS", "amount": "480000.00", "count": 12 },
    { "category": "TRAVEL", "amount": "310000.00", "count": 8 }
  ],
  "by_department": [
    { "department_id": "uuid", "department_name": "Engineering", "amount": "720000.00" }
  ],
  "top_merchants": [
    { "merchant": "AWS", "amount": "220000.00", "count": 4 }
  ],
  "pending_approvals": 3,
  "active_cards": 6
}
```

**Notes:**
- `mom_delta_pct`: `null` when there is no spend in the prior equivalent window (first period).
- `pending_approvals`: count of `FLAGGED` transactions awaiting FM action.

---

### GET /dashboard/timeseries
**Auth required:** Yes — ADMIN or FM
**Description:** Date-bucketed spend totals for sparkline / area chart rendering. Also Redis-cached (5 min, same key scheme).

**Query params:** `from_date`, `to_date`, `bucket` (`hour`|`day`|`week`|`month`, default `day`).

**Response:**
```json
[
  { "date": "2026-05-01", "amount": "85000.00", "count": 6 },
  { "date": "2026-05-02", "amount": "42000.00", "count": 3 }
]
```

**Error responses:**
- 403 — caller is EMPLOYEE

---

## Digest

### GET /digest
**Auth required:** Yes — ADMIN or FM
**Description:** List the last ~12 weekly digests for this org.

**Response:**
```json
{
  "items": [{
    "id": "uuid", "period_start": "2026-05-19", "period_end": "2026-05-25",
    "status": "COMPLETED", "headline": "Spend down 12% week-over-week",
    "created_at": "2026-05-26T03:30:00Z"
  }]
}
```

---

### GET /digest/{id}
**Auth required:** Yes — ADMIN or FM
**Response:**
```json
{
  "digest": {
    "id": "uuid", "period_start": "2026-05-19", "period_end": "2026-05-25",
    "status": "COMPLETED",
    "headline": "Spend down 12% week-over-week",
    "body": "Total spend was ₹4.2L, a 12% drop from last week...",
    "top_recommendations": [
      "Cancel unused Notion seat (₹4,500/mo)",
      "Consolidate Uber and Ola — same week, same routes"
    ],
    "flagged_items": [
      { "type": "DUPLICATE", "description": "AWS charged twice on 2026-05-22", "amount": "12000.00" }
    ]
  }
}
```

---

### POST /digest/generate
**Auth required:** Yes — ADMIN
**Description:** Trigger the digest job manually (demo-friendly).
**Response:** `{ "digest_id": "uuid", "status": "pending" }`

---

## Notifications

### GET /notifications
**Auth required:** Yes
**Query params:** `unread=true`

**Response:**
```json
{
  "items": [{
    "id": "uuid", "type": "POLICY_FLAGGED",
    "title": "Transaction flagged",
    "body": "₹3,500 at LiquorMart flagged by policy: 'No alcohol purchases above ₹2,000'",
    "link": "/transactions/uuid",
    "read_at": null,
    "created_at": "2026-05-26T11:02:00Z"
  }],
  "unread_count": 3,
  "next_cursor": null
}
```

---

### POST /notifications/{id}/read
**Auth required:** Yes (owner)
**Response:** `{ "ok": true }`

**Error responses:**
- 404 — notification not yours

---

### POST /notifications/read-all
**Auth required:** Yes
**Response:** `{ "ok": true, "count": 7 }`

---

### GET /notifications/stream
**Auth required:** Yes
**Description:** Server-Sent Events stream of notifications for the current user. Events are JSON-encoded notification records.

**Response:** `text/event-stream` chunks like:
```
event: notification
data: { "id": "uuid", "type": "DIGEST_READY", "title": "...", "body": "...", "link": "..." }

```

---

## Health

### GET /health
**Auth required:** No
**Response:**
```json
{ "db": "ok", "redis": "ok", "tir": "ok", "version": "0.1.0" }
```
