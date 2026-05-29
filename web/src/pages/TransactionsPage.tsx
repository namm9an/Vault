import { useState } from "react";
import { motion } from "framer-motion";
import { useMe } from "@/features/auth/hooks";
import { useCards } from "@/features/cards/hooks";
import { EmptyState } from "@/components/EmptyState";
import { Badge, type BadgeVariant } from "@/components/ui/badge";
import {
  useTransactions,
  useTransaction,
  useCreateTransaction,
  useApproveTransaction,
  useRejectTransaction,
  type TransactionFilters,
} from "@/features/transactions/hooks";
import { ReceiptUploader } from "@/components/ReceiptUploader";
import type { PolicyVerdict, SpendCategory, Transaction, TransactionEvent, TransactionState } from "@/types/api";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CATEGORIES: SpendCategory[] = [
  "TRAVEL", "MEALS", "SAAS", "OFFICE", "MARKETING", "HARDWARE",
  "PROFESSIONAL_SERVICES", "OTHER",
];

const STATES: TransactionState[] = [
  "INITIATED", "POLICY_CHECKED", "APPROVED", "FLAGGED", "BLOCKED", "CLEARED", "SETTLED",
];

// ---------------------------------------------------------------------------
// State / verdict badges — thin wrappers over the shared Badge component
// ---------------------------------------------------------------------------

function StateBadge({ state }: { state: TransactionState }) {
  return <Badge variant={state as BadgeVariant}>{state}</Badge>;
}

function VerdictBadge({ verdict }: { verdict: PolicyVerdict }) {
  return <Badge variant={verdict as BadgeVariant}>{verdict}</Badge>;
}

// ---------------------------------------------------------------------------
// Currency / date helpers
// ---------------------------------------------------------------------------

function fmtAmount(amount: string, currency: string) {
  const n = parseFloat(amount);
  if (currency === "INR") return `₹${n.toLocaleString("en-IN", { minimumFractionDigits: 2 })}`;
  return `${currency} ${n.toFixed(2)}`;
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-IN", {
    day: "2-digit", month: "short", year: "numeric",
  });
}

// ---------------------------------------------------------------------------
// NewTransactionDialog
// ---------------------------------------------------------------------------

function NewTransactionDialog({ onClose }: { onClose: () => void }) {
  const { data: cardsData } = useCards();
  const { mutateAsync, isPending, error } = useCreateTransaction();

  const [cardId, setCardId] = useState("");
  const [merchant, setMerchant] = useState("");
  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState("INR");
  const [category, setCategory] = useState<SpendCategory>("OTHER");
  const [description, setDescription] = useState("");
  const [occurredAt, setOccurredAt] = useState("");
  const [receiptId, setReceiptId] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!cardId || !merchant || !amount) return;
    await mutateAsync({
      card_id: cardId,
      merchant,
      amount,
      currency,
      category,
      description: description || undefined,
      occurred_at: occurredAt ? new Date(occurredAt).toISOString() : undefined,
      receipt_id: receiptId ?? undefined,
    });
    onClose();
  }

  const cards = cardsData ?? [];
  const errMsg = error
    ? ((error as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? "Failed to create transaction")
    : null;

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 p-6">
        <h2 className="text-lg font-semibold text-[#0c0a08] mb-4">New Transaction</h2>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-[#0c0a08] mb-1">Card *</label>
            <select
              value={cardId}
              onChange={(e) => setCardId(e.target.value)}
              className="w-full border border-[#d2cecb] rounded-[6px] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-solar/50"
              required
            >
              <option value="">Select a card…</option>
              {cards
                .filter((c) => c.status === "ACTIVE")
                .map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nickname} (•••• {c.last_four})
                  </option>
                ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-[#0c0a08] mb-1">Merchant *</label>
            <input
              type="text"
              value={merchant}
              onChange={(e) => setMerchant(e.target.value)}
              className="w-full border border-[#d2cecb] rounded-[6px] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-solar/50"
              placeholder="e.g. Amazon Web Services"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-[#0c0a08] mb-1">Amount *</label>
              <input
                type="number"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className="w-full border border-[#d2cecb] rounded-[6px] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-solar/50"
                placeholder="0.00"
                min="0.01"
                step="0.01"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-[#0c0a08] mb-1">Currency</label>
              <select
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                className="w-full border border-[#d2cecb] rounded-[6px] px-3 py-2 text-sm"
              >
                <option value="INR">INR</option>
                <option value="USD">USD</option>
                <option value="EUR">EUR</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-[#0c0a08] mb-1">Category</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value as SpendCategory)}
              className="w-full border border-[#d2cecb] rounded-[6px] px-3 py-2 text-sm"
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-[#0c0a08] mb-1">Description</label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full border border-[#d2cecb] rounded-[6px] px-3 py-2 text-sm"
              placeholder="Optional description"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-[#0c0a08] mb-1">Date &amp; Time</label>
            <input
              type="datetime-local"
              value={occurredAt}
              onChange={(e) => setOccurredAt(e.target.value)}
              className="w-full border border-[#d2cecb] rounded-[6px] px-3 py-2 text-sm"
            />
          </div>

          <ReceiptUploader
            onReceiptReady={(id) => setReceiptId(id)}
            onClear={() => setReceiptId(null)}
          />

          {errMsg && (
            <p className="text-sm text-red-600 bg-red-50 rounded-[6px] px-3 py-2">{errMsg}</p>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm rounded-[6px] border border-[#d2cecb] text-[#0c0a08] hover:bg-[#f4f2f0]"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isPending}
              className="px-4 py-2 text-sm rounded-[6px] bg-solar text-[#0c0a08] font-semibold hover:bg-solar-light disabled:opacity-50"
            >
              {isPending ? "Creating…" : "Create Transaction"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Event timeline row
// ---------------------------------------------------------------------------

function EventRow({ event }: { event: TransactionEvent }) {
  return (
    <div className="flex items-start gap-3 py-2 border-b border-[#d2cecb] last:border-0">
      <div className="mt-0.5">
        <StateBadge state={event.to_state} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm">
          {event.from_state ? (
            <span className="text-[#6e6a68]">{event.from_state} → </span>
          ) : null}
          <span className="font-medium text-[#0c0a08]">{event.to_state}</span>
          {event.triggered_by_system && (
            <span className="ml-2 text-xs text-[#6e6a68]">(system)</span>
          )}
        </p>
        {event.reason && (
          <p className="text-xs text-[#6e6a68] mt-0.5 truncate">{event.reason}</p>
        )}
        <p className="text-xs text-[#6e6a68] mt-0.5">
          {new Date(event.created_at).toLocaleString("en-IN")}
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// TransactionDetailDrawer
// ---------------------------------------------------------------------------

function TransactionDetailDrawer({
  txnId,
  onClose,
}: {
  txnId: string;
  onClose: () => void;
}) {
  const { data: txnDetail, isLoading } = useTransaction(txnId);
  const _isPolicyPending = txnDetail?.state === "POLICY_CHECKED"; void _isPolicyPending;
  const { data: me } = useMe();
  const approve = useApproveTransaction();
  const reject = useRejectTransaction();
  const [reason, setReason] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);

  const userRole = me?.user?.role;
  const canActOnFlagged =
    txnDetail?.state === "FLAGGED" &&
    (userRole === "ADMIN" || userRole === "FINANCE_MANAGER");

  async function handleApprove() {
    if (!reason.trim()) return;
    setActionError(null);
    try {
      await approve.mutateAsync({ id: txnId, reason });
      setReason("");
    } catch {
      setActionError("Approval failed — try again.");
    }
  }

  async function handleReject() {
    if (!reason.trim()) return;
    setActionError(null);
    try {
      await reject.mutateAsync({ id: txnId, reason });
      setReason("");
    } catch {
      setActionError("Rejection failed — try again.");
    }
  }

  return (
    <>
      <div className="fixed inset-0 bg-black/20 z-40" onClick={onClose} />
      <div className="fixed right-0 top-0 h-full w-full max-w-md bg-white shadow-2xl z-50 flex flex-col">
        <div className="flex items-center justify-between border-b border-[#d2cecb] px-6 py-4">
          <h2 className="text-base font-semibold text-[#0c0a08]">Transaction Details</h2>
          <button
            onClick={onClose}
            className="text-[#6e6a68] hover:text-[#0c0a08] text-xl leading-none"
          >
            ×
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
          {isLoading ? (
            <p className="text-sm text-[#6e6a68]">Loading…</p>
          ) : txnDetail ? (
            <>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-2xl font-bold text-[#0c0a08]">
                    {fmtAmount(txnDetail.amount, txnDetail.currency)}
                  </span>
                  <StateBadge state={txnDetail.state} />
                </div>
                <p className="text-sm font-medium text-[#0c0a08]">{txnDetail.merchant}</p>
                <div className="grid grid-cols-2 gap-2 text-sm text-[#6e6a68]">
                  <span>Category: {txnDetail.category}</span>
                  <span>Date: {fmtDate(txnDetail.occurred_at)}</span>
                  {txnDetail.description && (
                    <span className="col-span-2">Note: {txnDetail.description}</span>
                  )}
                </div>
              </div>

              {txnDetail.state === "POLICY_CHECKED" && (
                <div className="flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2">
                  <div className="w-3 h-3 border-2 border-blue-400 border-t-blue-700 rounded-full animate-spin flex-shrink-0" />
                  <p className="text-sm text-blue-800">
                    AI policy engine is reviewing this transaction…
                  </p>
                </div>
              )}

              {txnDetail.latest_policy_result && (
                <div className="border border-[#d2cecb] rounded-lg p-3 bg-[#f4f2f0]">
                  <p className="text-xs font-semibold text-[#6e6a68] uppercase tracking-wide mb-1">
                    Policy Result
                  </p>
                  <div className="flex items-center gap-2 mb-1">
                    <VerdictBadge verdict={txnDetail.latest_policy_result.verdict} />
                    <span className="text-xs text-[#6e6a68]">
                      {txnDetail.latest_policy_result.llm_model}
                    </span>
                  </div>
                  <p className="text-sm text-[#0c0a08]">{txnDetail.latest_policy_result.reason}</p>
                  {txnDetail.latest_policy_result.policy_matched && (
                    <p className="text-xs italic text-[#6e6a68] mt-1">
                      Matched: "{txnDetail.latest_policy_result.policy_matched}"
                    </p>
                  )}
                </div>
              )}

              {canActOnFlagged && (
                <div className="border border-yellow-200 rounded-lg p-3 bg-yellow-50">
                  <p className="text-xs font-semibold text-yellow-800 uppercase tracking-wide mb-2">
                    Review Required
                  </p>
                  <textarea
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    placeholder="Enter reason for your decision…"
                    className="w-full border border-[#d2cecb] rounded-[6px] px-3 py-2 text-sm mb-2 bg-white resize-none"
                    rows={2}
                  />
                  {actionError && (
                    <p className="text-xs text-red-600 mb-2">{actionError}</p>
                  )}
                  <div className="flex gap-2">
                    <button
                      onClick={handleApprove}
                      disabled={approve.isPending || !reason.trim()}
                      className="flex-1 py-1.5 text-sm rounded-[6px] bg-green-600 text-white hover:bg-green-700 disabled:opacity-50"
                    >
                      {approve.isPending ? "Approving…" : "Approve"}
                    </button>
                    <button
                      onClick={handleReject}
                      disabled={reject.isPending || !reason.trim()}
                      className="flex-1 py-1.5 text-sm rounded-[6px] bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
                    >
                      {reject.isPending ? "Rejecting…" : "Reject"}
                    </button>
                  </div>
                </div>
              )}

              <div>
                <p className="text-xs font-semibold text-[#6e6a68] uppercase tracking-wide mb-2">
                  Event Timeline
                </p>
                {txnDetail.events.length === 0 ? (
                  <p className="text-sm text-[#6e6a68]">No events yet.</p>
                ) : (
                  <div>
                    {txnDetail.events.map((ev) => (
                      <EventRow key={ev.id} event={ev} />
                    ))}
                  </div>
                )}
              </div>
            </>
          ) : (
            <p className="text-sm text-[#6e6a68]">Transaction not found.</p>
          )}
        </div>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function TransactionsPage() {
  const [filters, setFilters] = useState<TransactionFilters>({});
  const [selectedTxnId, setSelectedTxnId] = useState<string | null>(null);
  const [showNewDialog, setShowNewDialog] = useState(false);
  const [selectedYear, setSelectedYear] = useState<number | "">("");

  const currentYear = new Date().getFullYear();
  const YEARS = [currentYear, currentYear - 1, currentYear - 2];

  function applyYear(year: number | "") {
    setSelectedYear(year);
    if (year === "") {
      setFilters((prev) => { const f = { ...prev }; delete f.from_date; delete f.to_date; return f; });
    } else {
      setFilters((prev) => ({
        ...prev,
        from_date: new Date(`${year}-01-01T00:00:00`).toISOString(),
        to_date: new Date(`${year}-12-31T23:59:59`).toISOString(),
      }));
    }
  }

  const { data: txns, isLoading, error } = useTransactions(filters);
  const transactions = txns ?? [];

  function setFilter<K extends keyof TransactionFilters>(key: K, value: TransactionFilters[K]) {
    setFilters((prev) => ({ ...prev, [key]: value || undefined }));
  }

  return (
    <div className="max-w-7xl mx-auto px-6 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-[#0c0a08]">Transactions</h1>
          <p className="text-sm text-[#6e6a68] mt-0.5">Track and review spend activity</p>
        </div>
        <button
          onClick={() => setShowNewDialog(true)}
          className="px-4 py-2 rounded-[6px] bg-solar text-[#0c0a08] text-sm font-semibold hover:bg-solar-light"
        >
          + New Transaction
        </button>
      </div>

      {/* Filter bar */}
      <div className="bg-white border border-[#d2cecb] rounded-xl p-4 mb-4 flex flex-wrap gap-3">
        <select
          value={selectedYear}
          onChange={(e) => applyYear(e.target.value === "" ? "" : Number(e.target.value))}
          className="border border-[#d2cecb] rounded-[6px] px-3 py-1.5 text-sm"
        >
          <option value="">All years</option>
          {YEARS.map((y) => (
            <option key={y} value={y}>{y}</option>
          ))}
        </select>

        <select
          value={filters.state ?? ""}
          onChange={(e) => setFilter("state", e.target.value as TransactionState || undefined)}
          className="border border-[#d2cecb] rounded-[6px] px-3 py-1.5 text-sm"
        >
          <option value="">All states</option>
          {STATES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>

        <select
          value={filters.category ?? ""}
          onChange={(e) => setFilter("category", e.target.value as SpendCategory || undefined)}
          className="border border-[#d2cecb] rounded-[6px] px-3 py-1.5 text-sm"
        >
          <option value="">All categories</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>

        <input
          type="date"
          value={filters.from_date ? new Date(filters.from_date).toISOString().split("T")[0] : ""}
          onChange={(e) => {
            if (!e.target.value) { setFilter("from_date", undefined); return; }
            setFilter("from_date", new Date(e.target.value + "T00:00:00").toISOString());
          }}
          className="border border-[#d2cecb] rounded-[6px] px-3 py-1.5 text-sm"
          placeholder="From date"
        />
        <input
          type="date"
          value={filters.to_date ? new Date(filters.to_date).toISOString().split("T")[0] : ""}
          onChange={(e) => {
            if (!e.target.value) { setFilter("to_date", undefined); return; }
            setFilter("to_date", new Date(e.target.value + "T23:59:59").toISOString());
          }}
          className="border border-[#d2cecb] rounded-[6px] px-3 py-1.5 text-sm"
          placeholder="To date"
        />

        {Object.keys(filters).length > 0 && (
          <button
            onClick={() => setFilters({})}
            className="text-sm text-[#6e6a68] hover:text-[#0c0a08] underline"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Table */}
      <div className="bg-white border border-[#d2cecb] rounded-xl overflow-hidden">
        {isLoading ? (
          <div className="py-16 text-center text-[#6e6a68] text-sm">Loading transactions…</div>
        ) : error ? (
          <div className="py-16 text-center text-red-500 text-sm">Failed to load transactions.</div>
        ) : transactions.length === 0 ? (
          <EmptyState
            title="No transactions yet"
            description="Record your first spend transaction to get started."
          />
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-[#f4f2f0] border-b border-[#d2cecb]">
              <tr>
                {["Date", "Merchant", "Amount", "Category", "State", "Policy"].map((h) => (
                  <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-[#6e6a68] uppercase tracking-wide">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {transactions.map((txn: Transaction, index: number) => (
                <motion.tr
                  key={txn.id}
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.03, duration: 0.2 }}
                  onClick={() => setSelectedTxnId(txn.id)}
                  className="border-b border-[#d2cecb] last:border-0 hover:bg-[#f4f2f0] cursor-pointer"
                >
                  <td className="px-4 py-3 text-[#6e6a68] whitespace-nowrap">
                    {fmtDate(txn.occurred_at)}
                  </td>
                  <td className="px-4 py-3 font-medium text-[#0c0a08] max-w-xs truncate">{txn.merchant}</td>
                  <td className="px-4 py-3 font-mono tabular-nums text-[#0c0a08]">
                    {fmtAmount(txn.amount, txn.currency)}
                  </td>
                  <td className="px-4 py-3 text-[#6e6a68]">{txn.category}</td>
                  <td className="px-4 py-3">
                    <StateBadge state={txn.state} />
                  </td>
                  <td className="px-4 py-3">
                    {txn.policy_verdict ? (
                      <VerdictBadge verdict={txn.policy_verdict} />
                    ) : null}
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showNewDialog && (
        <NewTransactionDialog onClose={() => setShowNewDialog(false)} />
      )}
      {selectedTxnId && (
        <TransactionDetailDrawer
          txnId={selectedTxnId}
          onClose={() => setSelectedTxnId(null)}
        />
      )}
    </div>
  );
}
