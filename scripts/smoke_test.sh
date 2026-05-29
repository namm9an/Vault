#!/bin/bash
# Vault production smoke test
# Usage: ./scripts/smoke_test.sh [BASE_URL]
# Default: http://101.53.140.68

set -euo pipefail

BASE="${1:-http://101.53.140.68}"
EMAIL="naman.moudgill@e2enetworks.com"
PASSWORD="vault-demo-pass"
PASS=0
FAIL=0

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

check() {
  local desc="$1" expected="$2" actual="$3"
  if [ "$actual" = "$expected" ]; then
    echo -e "${GREEN}✓${NC} $desc"
    PASS=$((PASS + 1))
  else
    echo -e "${RED}✗${NC} $desc  (expected '$expected', got '$actual')"
    FAIL=$((FAIL + 1))
  fi
}

check_gte() {
  local desc="$1" min="$2" actual="$3"
  if [ "$actual" -ge "$min" ] 2>/dev/null; then
    echo -e "${GREEN}✓${NC} $desc  (${actual} ≥ ${min})"
    PASS=$((PASS + 1))
  else
    echo -e "${RED}✗${NC} $desc  (expected ≥ ${min}, got '${actual}')"
    FAIL=$((FAIL + 1))
  fi
}

echo "Vault smoke test → $BASE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── Auth ─────────────────────────────────────────────────────────────────────

LOGIN_RESP=$(curl -sf -X POST "$BASE/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" 2>/dev/null || echo "{}")

TOKEN=$(echo "$LOGIN_RESP" | python3 -c "
import sys, json
try:
    print(json.load(sys.stdin).get('access_token',''))
except Exception:
    print('')
" 2>/dev/null)

check "POST /auth/login → token present" "true" "$([[ -n $TOKEN ]] && echo true || echo false)"

if [[ -z $TOKEN ]]; then
  echo "Login failed — cannot continue smoke test."
  exit 1
fi

_get() {
  curl -sf -H "Authorization: Bearer $TOKEN" "$BASE/api/v1/$1" 2>/dev/null
}

_status() {
  curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer $TOKEN" "$BASE/api/v1/$1" 2>/dev/null
}

# ── Core endpoints ───────────────────────────────────────────────────────────

check "GET /auth/me → 200"          "200" "$(_status auth/me)"
check "GET /cards → 200"            "200" "$(_status cards)"
check "GET /policies → 200"         "200" "$(_status policies)"
check "GET /departments → 200"      "200" "$(_status departments)"
check "GET /reimbursements → 200"   "200" "$(_status reimbursements)"
check "GET /notifications → 200"    "200" "$(_status notifications)"
check "GET /digest → 200"           "200" "$(_status digest)"

# ── Transactions ─────────────────────────────────────────────────────────────

TXN_RESP=$(_get transactions)
TXN_COUNT=$(echo "$TXN_RESP" | python3 -c "
import sys, json
try:
    print(len(json.load(sys.stdin)))
except Exception as e:
    print(f'PARSE_FAIL: {e}', file=sys.stderr)
    print(0)
" 2>/dev/null)

check "GET /transactions → 200"     "200" "$(_status transactions)"
check_gte "GET /transactions → ≥30 rows" 30 "$TXN_COUNT"

# Check policy_verdict field is present
HAS_VERDICT=$(echo "$TXN_RESP" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    has = any('policy_verdict' in t for t in data[:5])
    print('true' if has else 'false')
except Exception as e:
    print(f'PARSE_FAIL: {e}', file=sys.stderr)
    print('false')
" 2>/dev/null)
check "GET /transactions → includes policy_verdict field" "true" "$HAS_VERDICT"

# ── Dashboard ────────────────────────────────────────────────────────────────

FROM=$(python3 -c "from datetime import datetime, timedelta; print((datetime.utcnow()-timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ'))")
TO=$(python3 -c "from datetime import datetime; print(datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'))")

SUMMARY_RESP=$(_get "dashboard/summary?from_date=${FROM}&to_date=${TO}")
SUMMARY_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $TOKEN" \
  "$BASE/api/v1/dashboard/summary?from_date=${FROM}&to_date=${TO}" 2>/dev/null)

check "GET /dashboard/summary → 200" "200" "$SUMMARY_STATUS"

TOTAL_SPEND=$(echo "$SUMMARY_RESP" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print('nonzero' if float(d.get('total_spend', 0)) > 0 else 'zero')
except Exception as e:
    print(f'PARSE_FAIL: {e}', file=sys.stderr)
    print('zero')
" 2>/dev/null)
check "Dashboard total_spend > 0"   "nonzero" "$TOTAL_SPEND"

PENDING=$(echo "$SUMMARY_RESP" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('pending_approvals', 0))
except Exception as e:
    print(f'PARSE_FAIL: {e}', file=sys.stderr)
    print(0)
" 2>/dev/null)
check_gte "Dashboard pending_approvals ≥ 5" 5 "$PENDING"

TS_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $TOKEN" \
  "$BASE/api/v1/dashboard/timeseries?bucket=day&from_date=${FROM}&to_date=${TO}" 2>/dev/null)
check "GET /dashboard/timeseries → 200" "200" "$TS_STATUS"

# ── Cards count ──────────────────────────────────────────────────────────────

CARD_COUNT=$(curl -sf -H "Authorization: Bearer $TOKEN" \
  "$BASE/api/v1/cards" 2>/dev/null | python3 -c "
import sys, json
try:
    print(len(json.load(sys.stdin)))
except Exception as e:
    print(f'PARSE_FAIL: {e}', file=sys.stderr)
    print(0)
")
check_gte "GET /cards → ≥ 6 cards" 6 "$CARD_COUNT"

# ── Policies count ───────────────────────────────────────────────────────────

POLICY_COUNT=$(curl -sf -H "Authorization: Bearer $TOKEN" \
  "$BASE/api/v1/policies" 2>/dev/null | python3 -c "
import sys, json
try:
    print(len(json.load(sys.stdin)))
except Exception as e:
    print(f'PARSE_FAIL: {e}', file=sys.stderr)
    print(0)
")
check_gte "GET /policies → ≥ 5 active policies" 5 "$POLICY_COUNT"

# ── Notifications for Naman ──────────────────────────────────────────────────

UNREAD=$(curl -sf -H "Authorization: Bearer $TOKEN" \
  "$BASE/api/v1/notifications/unread-count" 2>/dev/null | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('unread_count', 0))
except Exception as e:
    print(f'PARSE_FAIL: {e}', file=sys.stderr)
    print(0)
")
check_gte "Naman unread notifications ≥ 3" 3 "$UNREAD"

# ── Health ───────────────────────────────────────────────────────────────────

HEALTH=$(curl -sf "$BASE/health" 2>/dev/null | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    ok = d.get('db') == 'ok' and d.get('redis') == 'ok'
    print('ok' if ok else 'degraded')
except Exception:
    print('error')
")
check "GET /health → db+redis ok" "ok" "$HEALTH"

# ── Summary ──────────────────────────────────────────────────────────────────

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Results: ${PASS} passed, ${FAIL} failed"

[ $FAIL -eq 0 ] && exit 0 || exit 1
