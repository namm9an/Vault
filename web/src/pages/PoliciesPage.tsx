import { useState } from "react";
import { useMe } from "@/features/auth/hooks";
import {
  usePolicies,
  useCreatePolicy,
  useUpdatePolicy,
  useDeletePolicy,
} from "@/features/policies/hooks";
import type { Policy } from "@/types/api";

// ---------------------------------------------------------------------------
// PolicyForm — shared create / edit form
// ---------------------------------------------------------------------------

function PolicyForm({
  initialText = "",
  initialActive = true,
  isPending,
  onSubmit,
  onCancel,
  submitLabel,
}: {
  initialText?: string;
  initialActive?: boolean;
  isPending: boolean;
  onSubmit: (text: string, isActive: boolean) => void;
  onCancel: () => void;
  submitLabel: string;
}) {
  const [text, setText] = useState(initialText);
  const [isActive, setIsActive] = useState(initialActive);

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (!text.trim()) return;
        onSubmit(text.trim(), isActive);
      }}
      className="space-y-3"
    >
      <div>
        <label className="block text-sm font-medium text-neutral-700 mb-1">
          Policy text *
        </label>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={3}
          minLength={5}
          maxLength={2000}
          placeholder="e.g. No purchases above ₹50,000 without Finance Manager approval."
          className="w-full border rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-neutral-900"
          required
        />
        <p className="text-xs text-neutral-400 mt-0.5 text-right">
          {text.length}/2000
        </p>
      </div>

      <label className="flex items-center gap-2 text-sm cursor-pointer">
        <input
          type="checkbox"
          checked={isActive}
          onChange={(e) => setIsActive(e.target.checked)}
          className="rounded"
        />
        <span>Active</span>
        <span className="text-neutral-400 text-xs ml-1">
          (inactive policies are not evaluated by the LLM engine)
        </span>
      </label>

      <div className="flex justify-end gap-3 pt-1">
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 text-sm rounded-lg border hover:bg-neutral-50"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={isPending || !text.trim()}
          className="px-4 py-2 text-sm rounded-lg bg-neutral-900 text-white hover:bg-neutral-700 disabled:opacity-50"
        >
          {isPending ? "Saving…" : submitLabel}
        </button>
      </div>
    </form>
  );
}

// ---------------------------------------------------------------------------
// PolicyRow
// ---------------------------------------------------------------------------

function PolicyRow({
  policy,
  canEdit,
  onEdit,
  onToggle,
  onDelete,
}: {
  policy: Policy;
  canEdit: boolean;
  onEdit: (p: Policy) => void;
  onToggle: (p: Policy) => void;
  onDelete: (p: Policy) => void;
}) {
  return (
    <div className="flex items-start gap-4 px-5 py-4 border-b last:border-0 hover:bg-neutral-50 group">
      {/* Active indicator */}
      <div
        className={`mt-1 flex-shrink-0 w-2 h-2 rounded-full ${
          policy.is_active ? "bg-green-500" : "bg-neutral-300"
        }`}
        title={policy.is_active ? "Active" : "Inactive"}
      />

      {/* Text */}
      <p className="flex-1 text-sm leading-relaxed">{policy.text}</p>

      {/* Actions */}
      {canEdit && (
        <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
          <button
            onClick={() => onToggle(policy)}
            className="text-xs px-2 py-1 rounded border hover:bg-neutral-100 text-neutral-600"
            title={policy.is_active ? "Deactivate" : "Activate"}
          >
            {policy.is_active ? "Disable" : "Enable"}
          </button>
          <button
            onClick={() => onEdit(policy)}
            className="text-xs px-2 py-1 rounded border hover:bg-neutral-100 text-neutral-600"
          >
            Edit
          </button>
          <button
            onClick={() => onDelete(policy)}
            className="text-xs px-2 py-1 rounded border hover:bg-red-50 hover:border-red-200 text-red-600"
          >
            Delete
          </button>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function PoliciesPage() {
  const { data: me } = useMe();
  const { data: policies, isLoading, error } = usePolicies();
  const createPolicy = useCreatePolicy();
  const updatePolicy = useUpdatePolicy();
  const deletePolicy = useDeletePolicy();

  const [showCreate, setShowCreate] = useState(false);
  const [editingPolicy, setEditingPolicy] = useState<Policy | null>(null);
  const [deleteCandidate, setDeleteCandidate] = useState<Policy | null>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);

  const userRole = me?.user?.role;
  const canEdit = userRole === "ADMIN";

  const allPolicies = policies ?? [];
  const activePolicies = allPolicies.filter((p) => p.is_active);

  async function handleCreate(text: string, isActive: boolean) {
    setMutationError(null);
    try {
      await createPolicy.mutateAsync({ text, is_active: isActive });
      setShowCreate(false);
    } catch {
      setMutationError("Failed to create policy — try again.");
    }
  }

  async function handleEdit(text: string, isActive: boolean) {
    if (!editingPolicy) return;
    setMutationError(null);
    try {
      await updatePolicy.mutateAsync({ id: editingPolicy.id, text, is_active: isActive });
      setEditingPolicy(null);
    } catch {
      setMutationError("Failed to update policy — try again.");
    }
  }

  async function handleToggle(policy: Policy) {
    setMutationError(null);
    try {
      await updatePolicy.mutateAsync({ id: policy.id, is_active: !policy.is_active });
    } catch {
      setMutationError("Failed to toggle policy — try again.");
    }
  }

  async function handleDelete() {
    if (!deleteCandidate) return;
    setMutationError(null);
    try {
      await deletePolicy.mutateAsync(deleteCandidate.id);
      setDeleteCandidate(null);
    } catch {
      setMutationError("Failed to delete policy — try again.");
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-6 py-8">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Spend Policies</h1>
          <p className="text-sm text-neutral-500 mt-0.5">
            Plain-English rules evaluated by the AI policy engine on every transaction.
            {" "}
            <span className="font-medium text-green-700">{activePolicies.length} active</span>
            {" / "}
            <span>{allPolicies.length} total</span>
          </p>
        </div>
        {canEdit && !showCreate && (
          <button
            onClick={() => { setShowCreate(true); setMutationError(null); }}
            className="px-4 py-2 rounded-lg bg-neutral-900 text-white text-sm hover:bg-neutral-700"
          >
            + Add Policy
          </button>
        )}
      </div>

      {/* Non-admin notice */}
      {!canEdit && (
        <div className="mb-4 px-4 py-3 rounded-lg bg-neutral-100 text-sm text-neutral-600">
          You have read-only access. Only Admins can create or modify policies.
        </div>
      )}

      {/* Global error */}
      {mutationError && (
        <div className="mb-4 px-4 py-3 rounded-lg bg-red-50 text-sm text-red-700 border border-red-200">
          {mutationError}
        </div>
      )}

      {/* Create form */}
      {showCreate && (
        <div className="bg-white border rounded-xl p-5 mb-4">
          <h2 className="text-sm font-semibold mb-3">New Policy</h2>
          <PolicyForm
            isPending={createPolicy.isPending}
            onSubmit={handleCreate}
            onCancel={() => setShowCreate(false)}
            submitLabel="Create Policy"
          />
        </div>
      )}

      {/* Edit form (inline, replaces row) */}
      {editingPolicy && (
        <div className="bg-white border border-blue-200 rounded-xl p-5 mb-4">
          <h2 className="text-sm font-semibold mb-3">Edit Policy</h2>
          <PolicyForm
            initialText={editingPolicy.text}
            initialActive={editingPolicy.is_active}
            isPending={updatePolicy.isPending}
            onSubmit={handleEdit}
            onCancel={() => setEditingPolicy(null)}
            submitLabel="Save Changes"
          />
        </div>
      )}

      {/* Policy list */}
      <div className="bg-white border rounded-xl overflow-hidden">
        {isLoading ? (
          <div className="py-16 text-center text-neutral-400 text-sm">
            Loading policies…
          </div>
        ) : error ? (
          <div className="py-16 text-center text-red-500 text-sm">
            Failed to load policies.
          </div>
        ) : allPolicies.length === 0 ? (
          <div className="py-16 text-center text-neutral-400 text-sm">
            No policies yet.{" "}
            {canEdit && (
              <button
                onClick={() => setShowCreate(true)}
                className="underline hover:text-neutral-700"
              >
                Add the first one
              </button>
            )}
          </div>
        ) : (
          <div>
            {allPolicies.map((policy) =>
              editingPolicy?.id === policy.id ? null : (
                <PolicyRow
                  key={policy.id}
                  policy={policy}
                  canEdit={canEdit}
                  onEdit={setEditingPolicy}
                  onToggle={handleToggle}
                  onDelete={setDeleteCandidate}
                />
              )
            )}
          </div>
        )}
      </div>

      {/* Delete confirmation modal */}
      {deleteCandidate && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-sm mx-4 p-6">
            <h2 className="text-base font-semibold mb-2">Delete policy?</h2>
            <p className="text-sm text-neutral-600 mb-4 line-clamp-3">
              "{deleteCandidate.text}"
            </p>
            <p className="text-sm text-red-600 mb-5">
              This cannot be undone. The policy will stop being evaluated immediately.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setDeleteCandidate(null)}
                className="px-4 py-2 text-sm rounded-lg border hover:bg-neutral-50"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={deletePolicy.isPending}
                className="px-4 py-2 text-sm rounded-lg bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
              >
                {deletePolicy.isPending ? "Deleting…" : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
