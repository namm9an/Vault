import { useState } from "react";
import { motion } from "framer-motion";
import { useMe } from "@/features/auth/hooks";
import { EmptyState } from "@/components/EmptyState";
import {
  useReimbursements,
  useCreateReimbursement,
  useApproveReimbursement,
  useRejectReimbursement,
  useMarkPaid,
} from "@/features/reimbursements/hooks";
import { useDepartments } from "@/features/departments/hooks";
import { Badge, type BadgeVariant } from "@/components/ui/badge";
import { ReceiptUploader } from "@/components/ReceiptUploader";
import type { Reimbursement, SpendCategory } from "@/types/api";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ALL_CATEGORIES: SpendCategory[] = [
  "TRAVEL", "MEALS", "SAAS", "OFFICE", "MARKETING", "HARDWARE",
  "PROFESSIONAL_SERVICES", "OTHER",
];

function fmtAmount(amount: string, currency: string) {
  if (currency === "INR") {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 2,
    }).format(Number(amount));
  }
  return `${currency} ${Number(amount).toFixed(2)}`;
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

// ---------------------------------------------------------------------------
// Submit dialog
// ---------------------------------------------------------------------------

type SubmitDialogProps = { onClose: () => void };

function SubmitDialog({ onClose }: SubmitDialogProps) {
  const { data: depts = [] } = useDepartments();
  const create = useCreateReimbursement();
  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState("INR");
  const [category, setCategory] = useState<SpendCategory>("MEALS");
  const [description, setDescription] = useState("");
  const [deptId, setDeptId] = useState("");
  const [receiptId, setReceiptId] = useState<string | undefined>(undefined);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await create.mutateAsync({
        amount,
        currency,
        category,
        description,
        department_id: deptId || undefined,
        receipt_id: receiptId,
      });
      onClose();
    } catch {
      // error shown below
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6 space-y-4">
        <h2 className="text-lg font-semibold text-[#0c0a08]">Submit reimbursement</h2>
        <form onSubmit={onSubmit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="text-sm text-[#6e6a68]">Amount</span>
              <input
                required
                type="number"
                min="0.01"
                step="0.01"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="e.g. 1200.00"
                className="mt-1 w-full border border-[#d2cecb] rounded-[6px] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-solar/50"
              />
            </label>
            <label className="block">
              <span className="text-sm text-[#6e6a68]">Currency</span>
              <select
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                className="mt-1 w-full border border-[#d2cecb] rounded-[6px] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-solar/50"
              >
                {["INR", "USD", "EUR", "GBP"].map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </label>
          </div>

          <label className="block">
            <span className="text-sm text-[#6e6a68]">Category</span>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value as SpendCategory)}
              className="mt-1 w-full border border-[#d2cecb] rounded-[6px] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-solar/50"
            >
              {ALL_CATEGORIES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="text-sm text-[#6e6a68]">Description</span>
            <textarea
              required
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief description of the expense…"
              className="mt-1 w-full border border-[#d2cecb] rounded-[6px] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-solar/50 resize-none"
            />
          </label>

          <ReceiptUploader
            onReceiptReady={(id) => setReceiptId(id)}
            onClear={() => setReceiptId(undefined)}
          />

          {depts.length > 0 && (
            <label className="block">
              <span className="text-sm text-[#6e6a68]">Department (optional)</span>
              <select
                value={deptId}
                onChange={(e) => setDeptId(e.target.value)}
                className="mt-1 w-full border border-[#d2cecb] rounded-[6px] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-solar/50"
              >
                <option value="">None</option>
                {depts.map((d) => (
                  <option key={d.id} value={d.id}>{d.name}</option>
                ))}
              </select>
            </label>
          )}

          {create.isError && (
            <p className="text-sm text-red-600">
              {(create.error as { response?: { data?: { detail?: string } } })
                ?.response?.data?.detail ?? "Failed to submit reimbursement"}
            </p>
          )}

          <div className="flex gap-3 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2 rounded-[6px] border border-[#d2cecb] text-sm text-[#0c0a08] hover:bg-[#f4f2f0]"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={create.isPending}
              className="flex-1 py-2 rounded-[6px] bg-solar text-[#0c0a08] text-sm font-semibold hover:bg-solar-light disabled:opacity-50"
            >
              {create.isPending ? "Submitting…" : "Submit"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Reason dialog (approve / reject)
// ---------------------------------------------------------------------------

type ReasonDialogProps = {
  title: string;
  confirmLabel: string;
  danger?: boolean;
  onConfirm: (reason: string) => void;
  onClose: () => void;
  isPending: boolean;
};

function ReasonDialog({
  title,
  confirmLabel,
  danger,
  onConfirm,
  onClose,
  isPending,
}: ReasonDialogProps) {
  const [reason, setReason] = useState("");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-sm p-6 space-y-4">
        <h2 className="text-lg font-semibold text-[#0c0a08]">{title}</h2>
        <label className="block">
          <span className="text-sm text-[#6e6a68]">Reason (optional)</span>
          <textarea
            rows={3}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className="mt-1 w-full border border-[#d2cecb] rounded-[6px] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-solar/50 resize-none"
          />
        </label>
        <div className="flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 py-2 rounded-[6px] border border-[#d2cecb] text-sm text-[#0c0a08] hover:bg-[#f4f2f0]"
          >
            Cancel
          </button>
          <button
            onClick={() => onConfirm(reason)}
            disabled={isPending}
            className={`flex-1 py-2 rounded-[6px] text-sm font-medium disabled:opacity-50 ${
              danger
                ? "bg-red-600 text-white hover:bg-red-700"
                : "bg-solar text-[#0c0a08] hover:bg-solar-light"
            }`}
          >
            {isPending ? "…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function ReimbursementsPage() {
  const me = useMe();
  const role = me.data?.user.role;
  const isFMOrAdmin = role === "FINANCE_MANAGER" || role === "ADMIN";

  const { data: reimbs = [], isLoading } = useReimbursements();
  const approve = useApproveReimbursement();
  const reject = useRejectReimbursement();
  const markPaid = useMarkPaid();

  const [showSubmit, setShowSubmit] = useState(false);
  const [reasonDialog, setReasonDialog] = useState<{
    reimb: Reimbursement;
    action: "approve" | "reject";
  } | null>(null);

  async function handleMarkPaid(id: string) {
    try {
      await markPaid.mutateAsync(id);
    } catch { /* ignore */ }
  }

  async function handleReason(reason: string) {
    if (!reasonDialog) return;
    const { reimb, action } = reasonDialog;
    try {
      if (action === "approve") {
        await approve.mutateAsync({ id: reimb.id, reason: reason || undefined });
      } else {
        await reject.mutateAsync({ id: reimb.id, reason: reason || undefined });
      }
      setReasonDialog(null);
    } catch { /* leave dialog open */ }
  }

  const actionPending =
    approve.isPending || reject.isPending || markPaid.isPending;

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-[#0c0a08]">Reimbursements</h1>
        <button
          onClick={() => setShowSubmit(true)}
          className="px-4 py-2 rounded-[6px] bg-solar text-[#0c0a08] text-sm font-semibold hover:bg-solar-light"
        >
          + Submit request
        </button>
      </div>

      {isLoading ? (
        <p className="text-[#6e6a68]">Loading…</p>
      ) : reimbs.length === 0 ? (
        <EmptyState
          title="No reimbursements yet"
          description="Submit your first expense reimbursement above."
        />
      ) : (
        <div className="border border-[#d2cecb] rounded-lg overflow-hidden bg-white">
          <table className="w-full text-sm">
            <thead className="bg-[#f4f2f0] text-xs uppercase tracking-wide text-[#6e6a68]">
              <tr>
                <th className="px-4 py-3 text-left">Description</th>
                <th className="px-4 py-3 text-left">Category</th>
                <th className="px-4 py-3 text-right">Amount</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-left">Submitted</th>
                {isFMOrAdmin && (
                  <th className="px-4 py-3 text-right">Actions</th>
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-[#d2cecb]">
              {reimbs.map((r, index) => (
                <motion.tr
                  key={r.id}
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.03, duration: 0.2 }}
                  className="hover:bg-[#f4f2f0]"
                >
                  <td className="px-4 py-3">
                    <div className="font-medium text-[#0c0a08] max-w-xs truncate">
                      {r.description}
                    </div>
                    {r.decision_reason && (
                      <div className="text-xs text-[#6e6a68] mt-0.5 max-w-xs truncate">
                        {r.decision_reason}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-[#6e6a68]">{r.category}</td>
                  <td className="px-4 py-3 text-right font-mono font-medium text-[#0c0a08]">
                    {fmtAmount(r.amount, r.currency)}
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant={r.status as BadgeVariant}>
                      {r.status}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-[#6e6a68] text-xs">
                    {fmtDate(r.created_at)}
                  </td>
                  {isFMOrAdmin && (
                    <td className="px-4 py-3 text-right">
                      <div className="flex justify-end gap-2">
                        {r.status === "POLICY_CHECKED" && (
                          <>
                            <button
                              onClick={() =>
                                setReasonDialog({ reimb: r, action: "approve" })
                              }
                              className="text-xs text-green-700 hover:underline"
                            >
                              Approve
                            </button>
                            <button
                              onClick={() =>
                                setReasonDialog({ reimb: r, action: "reject" })
                              }
                              className="text-xs text-red-600 hover:underline"
                            >
                              Reject
                            </button>
                          </>
                        )}
                        {r.status === "APPROVED" && (
                          <>
                            <button
                              onClick={() => handleMarkPaid(r.id)}
                              disabled={actionPending}
                              className="text-xs text-purple-700 hover:underline disabled:opacity-50"
                            >
                              Mark paid
                            </button>
                            <button
                              onClick={() =>
                                setReasonDialog({ reimb: r, action: "reject" })
                              }
                              className="text-xs text-red-600 hover:underline"
                            >
                              Reject
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  )}
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showSubmit && <SubmitDialog onClose={() => setShowSubmit(false)} />}

      {reasonDialog && (
        <ReasonDialog
          title={
            reasonDialog.action === "approve"
              ? "Approve reimbursement?"
              : "Reject reimbursement?"
          }
          confirmLabel={
            reasonDialog.action === "approve" ? "Approve" : "Reject"
          }
          danger={reasonDialog.action === "reject"}
          onConfirm={handleReason}
          onClose={() => setReasonDialog(null)}
          isPending={approve.isPending || reject.isPending}
        />
      )}
    </div>
  );
}
