import { useState } from "react";
import { motion } from "framer-motion";
import { useMe } from "@/features/auth/hooks";
import { EmptyState } from "@/components/EmptyState";
import {
  useDepartments,
  useBudgetStatus,
  useCreateDepartment,
  useUpdateDepartment,
  useDeleteDepartment,
} from "@/features/departments/hooks";
import type { BudgetStatus, Department } from "@/types/api";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtINR(amount: string | number) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(Number(amount));
}

// ---------------------------------------------------------------------------
// Budget row (loads its own budget-status query)
// ---------------------------------------------------------------------------

function BudgetRow({
  dept,
  onEdit,
  onDelete,
  isAdmin,
  index,
}: {
  dept: Department;
  onEdit: (dept: Department) => void;
  onDelete: (dept: Department) => void;
  isAdmin: boolean;
  index: number;
}) {
  const { data: budget, isLoading } = useBudgetStatus(dept.id);

  function barColor(bs: BudgetStatus) {
    if (bs.utilization_pct >= 100) return "bg-red-500";
    if (bs.is_over_threshold) return "bg-amber-400";
    return "bg-green-500";
  }

  return (
    <motion.tr
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.03, duration: 0.2 }}
      className="hover:bg-[#f4f2f0]"
    >
      <td className="px-4 py-3 font-medium text-[#0c0a08]">{dept.name}</td>
      <td className="px-4 py-3 text-right font-mono text-[#0c0a08]">
        {fmtINR(dept.monthly_budget)}
      </td>
      <td className="px-4 py-3 text-right font-mono text-[#0c0a08]">
        {isLoading ? (
          <span className="inline-block w-16 h-4 bg-[#d2cecb] rounded animate-pulse" />
        ) : budget ? (
          fmtINR(budget.spent)
        ) : (
          "—"
        )}
      </td>
      <td className="px-4 py-3 w-48">
        {isLoading ? (
          <div className="h-3 bg-[#d2cecb] rounded animate-pulse" />
        ) : budget ? (
          <div className="flex items-center gap-2">
            <div className="flex-1 h-2 bg-[#d2cecb] rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${barColor(budget)}`}
                style={{
                  width: `${Math.min(budget.utilization_pct, 100).toFixed(1)}%`,
                }}
              />
            </div>
            <span
              className={`text-xs font-medium w-10 text-right ${
                budget.utilization_pct >= 100
                  ? "text-red-600"
                  : budget.is_over_threshold
                  ? "text-amber-600"
                  : "text-[#6e6a68]"
              }`}
            >
              {budget.utilization_pct.toFixed(0)}%
            </span>
          </div>
        ) : (
          "—"
        )}
      </td>
      <td className="px-4 py-3 text-xs text-[#6e6a68]">
        {dept.alert_threshold_pct}%
      </td>
      {isAdmin && (
        <td className="px-4 py-3 text-right">
          <div className="flex justify-end gap-3">
            <button
              onClick={() => onEdit(dept)}
              className="text-xs text-spring hover:underline"
            >
              Edit
            </button>
            <button
              onClick={() => onDelete(dept)}
              className="text-xs text-red-600 hover:underline"
            >
              Delete
            </button>
          </div>
        </td>
      )}
    </motion.tr>
  );
}

// ---------------------------------------------------------------------------
// Create / Edit dialog
// ---------------------------------------------------------------------------

type DeptDialogProps = {
  initial?: Department;
  onClose: () => void;
};

function DeptDialog({ initial, onClose }: DeptDialogProps) {
  const create = useCreateDepartment();
  const update = useUpdateDepartment();

  const [name, setName] = useState(initial?.name ?? "");
  const [budget, setBudget] = useState(initial?.monthly_budget ?? "0");
  const [threshold, setThreshold] = useState(
    String(initial?.alert_threshold_pct ?? 80)
  );

  const isEdit = !!initial;
  const isPending = create.isPending || update.isPending;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      if (isEdit && initial) {
        await update.mutateAsync({
          id: initial.id,
          name,
          monthly_budget: budget,
          alert_threshold_pct: Number(threshold),
        });
      } else {
        await create.mutateAsync({
          name,
          monthly_budget: budget,
          alert_threshold_pct: Number(threshold),
        });
      }
      onClose();
    } catch {
      // error shown below
    }
  }

  const mutError = isEdit ? update.error : create.error;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6 space-y-4">
        <h2 className="text-lg font-semibold text-[#0c0a08]">
          {isEdit ? "Edit department" : "Add department"}
        </h2>
        <form onSubmit={onSubmit} className="space-y-3">
          <label className="block">
            <span className="text-sm text-[#6e6a68]">Name</span>
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Engineering"
              className="mt-1 w-full border border-[#d2cecb] rounded-[6px] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-solar/50"
            />
          </label>
          <label className="block">
            <span className="text-sm text-[#6e6a68]">Monthly budget (INR)</span>
            <input
              required
              type="number"
              min="0"
              step="0.01"
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
              className="mt-1 w-full border border-[#d2cecb] rounded-[6px] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-solar/50"
            />
          </label>
          <label className="block">
            <span className="text-sm text-[#6e6a68]">Alert threshold (%)</span>
            <input
              required
              type="number"
              min="1"
              max="100"
              value={threshold}
              onChange={(e) => setThreshold(e.target.value)}
              className="mt-1 w-full border border-[#d2cecb] rounded-[6px] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-solar/50"
            />
          </label>

          {mutError && (
            <p className="text-sm text-red-600">
              {(mutError as { response?: { data?: { detail?: string } } })
                ?.response?.data?.detail ?? "Failed to save department"}
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
              disabled={isPending}
              className="flex-1 py-2 rounded-[6px] bg-solar text-[#0c0a08] text-sm font-semibold hover:bg-solar-light disabled:opacity-50"
            >
              {isPending ? "Saving…" : isEdit ? "Save" : "Create"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Delete confirmation
// ---------------------------------------------------------------------------

type DeleteConfirmProps = {
  dept: Department;
  onClose: () => void;
};

function DeleteConfirm({ dept, onClose }: DeleteConfirmProps) {
  const del = useDeleteDepartment();

  async function onConfirm() {
    try {
      await del.mutateAsync(dept.id);
      onClose();
    } catch {
      // error shown below
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-sm p-6 space-y-4">
        <h2 className="text-lg font-semibold text-[#0c0a08]">Delete department?</h2>
        <p className="text-sm text-[#6e6a68]">
          <span className="font-medium text-[#0c0a08]">{dept.name}</span> will be permanently
          deleted. This cannot be undone.
        </p>
        {del.isError && (
          <p className="text-sm text-red-600">
            {(del.error as { response?: { data?: { detail?: string } } })
              ?.response?.data?.detail ?? "Failed to delete"}
          </p>
        )}
        <div className="flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 py-2 rounded-[6px] border border-[#d2cecb] text-sm text-[#0c0a08] hover:bg-[#f4f2f0]"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={del.isPending}
            className="flex-1 py-2 rounded-[6px] bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50"
          >
            {del.isPending ? "Deleting…" : "Delete"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function DepartmentsPage() {
  const me = useMe();
  const { data: depts = [], isLoading } = useDepartments();
  const isAdmin = me.data?.user.role === "ADMIN";

  const [showCreate, setShowCreate] = useState(false);
  const [editDept, setEditDept] = useState<Department | null>(null);
  const [deleteDept, setDeleteDept] = useState<Department | null>(null);

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-[#0c0a08]">Departments</h1>
        {isAdmin && (
          <button
            onClick={() => setShowCreate(true)}
            className="px-4 py-2 rounded-[6px] bg-solar text-[#0c0a08] text-sm font-semibold hover:bg-solar-light"
          >
            + Add department
          </button>
        )}
      </div>

      {isLoading ? (
        <p className="text-[#6e6a68]">Loading…</p>
      ) : depts.length === 0 ? (
        <EmptyState
          title="No departments yet"
          description={
            isAdmin
              ? "Create a department to start tracking budgets."
              : "No departments have been created yet."
          }
        />
      ) : (
        <div className="border border-[#d2cecb] rounded-lg overflow-hidden bg-white">
          <table className="w-full text-sm">
            <thead className="bg-[#f4f2f0] text-xs uppercase tracking-wide text-[#6e6a68]">
              <tr>
                <th className="px-4 py-3 text-left">Department</th>
                <th className="px-4 py-3 text-right">Monthly budget</th>
                <th className="px-4 py-3 text-right">Spent this month</th>
                <th className="px-4 py-3 text-left">Utilization</th>
                <th className="px-4 py-3 text-left">Alert at</th>
                {isAdmin && (
                  <th className="px-4 py-3 text-right">Actions</th>
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-[#d2cecb]">
              {depts.map((d, index) => (
                <BudgetRow
                  key={d.id}
                  dept={d}
                  isAdmin={isAdmin}
                  onEdit={setEditDept}
                  onDelete={setDeleteDept}
                  index={index}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showCreate && <DeptDialog onClose={() => setShowCreate(false)} />}
      {editDept && (
        <DeptDialog initial={editDept} onClose={() => setEditDept(null)} />
      )}
      {deleteDept && (
        <DeleteConfirm dept={deleteDept} onClose={() => setDeleteDept(null)} />
      )}
    </div>
  );
}
