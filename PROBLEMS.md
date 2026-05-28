# Known Issues — Phase 4

Tracked here after the Phase 4 validation review (2026-05-28).
C1–C5 and H1–H7 are fixed. The items below are medium-priority and safe
to leave until after the demo (2026-06-01).

---

## M1 — get_bytes in s3.py has no 404 handling

**File:** `api/api/storage/s3.py`

`get_bytes()` raises a raw `botocore.exceptions.ClientError` when the S3 key
does not exist.  `head()` already translates `ClientError(404)` →
`FileNotFoundError`.  `get_bytes()` should do the same so callers get a
consistent contract.

**Fix:** wrap `_sync_get_bytes` with the same `ClientError` →
`FileNotFoundError` translation used in `head()`.

*(Note: this translation was already added in the H2/C2 s3.py rewrite for
the `_sync_get_bytes` helper, but not yet covered by a test.)*

---

## M2 — Polling loop in ReceiptUploader.tsx has no timeout

**File:** `web/src/components/ReceiptUploader.tsx`

If the ARQ worker crashes or the job is never dequeued, the browser polls
`GET /receipts/{id}` forever.  There is also no `useEffect` cleanup —
unmounting the component while polling leaks the `setTimeout` handle.

**Fix:**
- Add a counter; after 60 attempts (~2 min) set `stage = "error"` and
  surface a "OCR timed out — retry?" message.
- Return a cleanup from `useEffect` that calls `clearTimeout(pollTimer.current)`.

---

## M3 — notify_all_fms N+1 inserts in a loop

**File:** `api/api/services/notification_service.py`

`notify_all_fms` issues one `db.add()` per Finance Manager.  At demo scale
(≤ 5 FMs) this is fine.  At production scale with hundreds of FMs this
should be a single `INSERT … SELECT` or a bulk `insert()`.

**Fix (post-demo):** use `db.execute(insert(Notification).values([…]))` to
batch all FM notifications in one SQL statement.

---

## M4 — LLM error message written raw to receipt.llm_error

**File:** `api/api/jobs/ocr_receipt.py`

The `LLMUnavailableError` string may include the raw HTTP response from TIR,
which could contain fragments of the API key in error context.  Writing it
directly to `receipt.llm_error` (surfaced via `GET /receipts/{id}`) risks
exposing token material to the frontend.

**Fix:** sanitize before writing — strip anything that looks like a Bearer
token (`Bearer [A-Za-z0-9._-]{20,}`) or truncate to the first 200 chars of
the exception message.

*(Note: with the C3 fix the OCR job no longer calls the LLM at all, so
this is currently inert.  It becomes relevant again when real OCR is wired
in.)*

---

## M5 — Duplicate model_config in PolicyOut

**File:** `api/api/schemas/policy.py`

**Status: FIXED** — merged into a single `ConfigDict(from_attributes=True,
populate_by_name=True)` in the same validation pass.

---

## M6 — _write_transition in policy_check.py bypasses AuditLog

**File:** `api/api/jobs/policy_check.py`

System-driven state transitions written by `_write_transition` produce
`TransactionEvent` rows (the append-only event log) but no `AuditLog` row
(the privileged-action audit table).  This means FM-facing audit reports
miss the system-initiated APPROVED/CLEARED/FLAGGED/BLOCKED transitions.

**Fix:** either write an `AuditLog` row inside `_write_transition` (using
a synthetic `actor_user_id` sentinel UUID for "system"), or refactor to
reuse `transaction_service.transition()` which already writes both.

---
