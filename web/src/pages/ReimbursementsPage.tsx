import { useState } from "react";
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
import type { Reimbursement, ReimbursementStatus, SpendCategory } from "@/types/api";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ALL_CATEGORIES: SpendCategory[] = [
  "TRAVEL",
  "MEALS",
  "SAAS",
  "OFFICE",
  "MARKETING",
  "HARDWARE",
  "PROFESSIONAL_SERVICES",
  "OTHER",
];

const STATUS_COLORS: Record<ReimbursementStatus, string> = {
  SUBMITTED: "bg-neutral-100 text-neutral-600",
  POLICY_CHECKED: "bg-blue-100 text-blue-700",
  APPROVED: "bg-green-100 text-green-700",
  REJECTED: "bg-red-100 text-red-700",
  PAID: "bg-purple-100 text-purple-700",
};

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

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await create.mutateAsync({
        amount,
        currency,
        category,
        description,
        department_id: deptId || undefined,
      });
      onClose();
    } catch {
      // error shown below
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6 space-y-4">
        <h2 className="text-lg font-semibold">Submit reimbursement</h2>
        <form onSubmit={onSubmit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="text-sm text-neutral-600">Amount</span>
              <input
                required
                type="number"
                min="0.01"
                step="0.01"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="e.g. 1200.00"
                className="mt-1 w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30"
              />
            </label>
            <label className="block">
              <span className="text-sm text-neutral-600">Currency</span>
              <select
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                className="mt-1 w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30"
              >
                {["INR", "USD", "EUR", "GBP"].map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </label>
          </div>

          <label className="block">
            <span className="text-sm text-neutral-600">Category</span>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value as SpendCategory)}
              className="mt-1 w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30"
            >
              {ALL_CATEGORIES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="text-sm text-neutral-600">Description</span>
            <textarea
              required
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief description of the expense…"
              className="mt-1 w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30 resize-none"
            />
          </label>

          {depts.length > 0 && (
            <label className="block">
              <span className="text-sm text-neutral-600">Department (optional)</span>
              <select
                value={deptId}
                onChange={(e) => setDeptId(e.target.value)}
                className="mt-1 w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30"
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
              className="flex-1 py-2 rounded-md border text-sm text-neutral-700 hover:bg-neutral-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={create.isPending}
              className="flex-1 py-2 rounded-md bg-neutral-900 text-white text-sm font-medium disabled:opacity-50"
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
        <h2 className="text-lg font-semibold">{title}</h2>
        <label className="block">
          <span className="text-sm text-neutral-600">Reason (optional)</span>
          <textarea
            rows={3}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className="mt-1 w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30 resize-none"
          />
        </label>
        <div className="flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 py-2 rounded-md border text-sm text-neutral-700 hover:bg-neutral-50"
          >
            Cancel
          </button>
          <button
            onClick={() => onConfirm(reason)}
            disabled={isPending}
            className={`flex-1 py-2 rounded-md text-white text-sm font-medium disabled:opacity-50 ${
              danger
                ? "bg-red-600 hover:bg-red-700"
                : "bg-neutral-900 hover:bg-neutral-800"
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
        <h1 className="text-2xl font-semibold tracking-tight">Reimbursements</h1>
        <button
          onClick={() => setShowSubmit(true)}
          className="px-4 py-2 rounded-md bg-neutral-900 text-white text-sm font-medium hover:bg-neutral-800"
        >
          + Submit request
        </button>
      </div>

      {isLoading ? (
        <p className="text-neutral-500">Loading…</p>
      ) : reimbs.length === 0 ? (
        <EmptyState
          title="No reimbursements yet"
          description="Submit your first expense reimbursement above."
        />
      ) : (
        <div className="border rounded-lg overflow-hidden bg-white">
          <table className="w-full text-sm">
            <thead className="bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500">
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
            <tbody className="divide-y divide-neutral-100">
              {reimbs.map((r) => (
                <tr key={r.id} className="hover:bg-neutral-50">
                  <td className="px-4 py-3">
                    <div className="font-medium text-neutral-800 max-w-xs truncate">
                      {r.description}
                    </div>
                    {r.decision_reason && (
                      <div className="text-xs text-neutral-400 mt-0.5 max-w-xs truncate">
                        {r.decision_reason}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-neutral-500">{r.category}</td>
                  <td className="px-4 py-3 text-right font-mono font-medium">
                    {fmtAmount(r.amount, r.currency)}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[r.status]}`}
                    >
                      {r.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-neutral-400 text-xs">
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
                </tr>
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
