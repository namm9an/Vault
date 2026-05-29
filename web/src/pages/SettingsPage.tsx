import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMe } from "@/features/auth/hooks";
import { useUsers, useInviteUser, useUpdateUser } from "@/features/users/hooks";
import { useToast } from "@/components/Toast";
import { api } from "@/lib/api";
import type { User, UserRole } from "@/types/api";

const ROLE_COLORS: Record<UserRole, string> = {
  ADMIN: "bg-purple-100 text-purple-800",
  FINANCE_MANAGER: "bg-blue-100 text-blue-800",
  EMPLOYEE: "bg-[#f4f2f0] text-[#6e6a68]",
};

const ALL_ROLES: UserRole[] = ["ADMIN", "FINANCE_MANAGER", "EMPLOYEE"];

// ── Invite Dialog ─────────────────────────────────────────────────────────────

type InviteDialogProps = { onClose: () => void };

function InviteDialog({ onClose }: InviteDialogProps) {
  const invite = useInviteUser();
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState<UserRole>("EMPLOYEE");
  const [password, setPassword] = useState("");

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await invite.mutateAsync({ email, full_name: fullName, role, password });
      onClose();
    } catch { /* error shown below */ }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6 space-y-4">
        <h2 className="text-lg font-semibold text-[#0c0a08]">Invite team member</h2>
        <form onSubmit={onSubmit} className="space-y-3">
          <label className="block">
            <span className="text-sm text-[#6e6a68]">Full name</span>
            <input
              required
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Alice Sharma"
              className="mt-1 w-full border border-[#d2cecb] rounded-[6px] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-solar/50 focus:border-solar"
            />
          </label>
          <label className="block">
            <span className="text-sm text-[#6e6a68]">Email</span>
            <input
              required
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="alice@acme.com"
              className="mt-1 w-full border border-[#d2cecb] rounded-[6px] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-solar/50 focus:border-solar"
            />
          </label>
          <label className="block">
            <span className="text-sm text-[#6e6a68]">Temporary password</span>
            <input
              required
              type="password"
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Min 8 characters"
              className="mt-1 w-full border border-[#d2cecb] rounded-[6px] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-solar/50 focus:border-solar"
            />
          </label>
          <label className="block">
            <span className="text-sm text-[#6e6a68]">Role</span>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as UserRole)}
              className="mt-1 w-full border border-[#d2cecb] rounded-[6px] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-solar/50"
            >
              {ALL_ROLES.map((r) => (
                <option key={r} value={r}>{r.replace("_", " ")}</option>
              ))}
            </select>
          </label>
          {invite.isError && (
            <p className="text-sm text-red-600">
              {(invite.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Failed to invite user"}
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
              disabled={invite.isPending}
              className="flex-1 py-2 rounded-[6px] bg-solar text-[#0c0a08] text-sm font-semibold hover:bg-solar-light disabled:opacity-50"
            >
              {invite.isPending ? "Inviting…" : "Invite"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Role Change Dialog ────────────────────────────────────────────────────────

type RoleDialogProps = {
  user: User;
  onClose: () => void;
};

function RoleDialog({ user, onClose }: RoleDialogProps) {
  const update = useUpdateUser();
  const [role, setRole] = useState<UserRole>(user.role);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await update.mutateAsync({ id: user.id, role });
      onClose();
    } catch { /* error shown below */ }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-sm p-6 space-y-4">
        <h2 className="text-lg font-semibold text-[#0c0a08]">Change role</h2>
        <p className="text-sm text-[#6e6a68]">{user.full_name} ({user.email})</p>
        <form onSubmit={onSubmit} className="space-y-3">
          <label className="block">
            <span className="text-sm text-[#6e6a68]">New role</span>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as UserRole)}
              className="mt-1 w-full border border-[#d2cecb] rounded-[6px] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-solar/50"
            >
              {ALL_ROLES.map((r) => (
                <option key={r} value={r}>{r.replace("_", " ")}</option>
              ))}
            </select>
          </label>
          {update.isError && (
            <p className="text-sm text-red-600">
              {(update.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Failed to update role"}
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
              disabled={update.isPending || role === user.role}
              className="flex-1 py-2 rounded-[6px] bg-solar text-[#0c0a08] text-sm font-semibold hover:bg-solar-light disabled:opacity-50"
            >
              {update.isPending ? "Saving…" : "Save"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Demo Reset ────────────────────────────────────────────────────────────────

function useDemoReset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (): Promise<{ status: string; transactions: number; reimbursements: number }> => {
      const { data } = await api.post("/demo/reset");
      return data;
    },
    onSuccess: () => {
      // Invalidate everything so the UI reflects the fresh data
      qc.invalidateQueries();
    },
  });
}

function ResetDemoConfirmModal({ onClose }: { onClose: () => void }) {
  const reset = useDemoReset();
  const { success, error } = useToast();

  async function handleConfirm() {
    try {
      const result = await reset.mutateAsync();
      success(`Demo reset complete — ${result.transactions} transactions reseeded`);
      onClose();
    } catch {
      error("Demo reset failed — check server logs");
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6 space-y-4">
        <h2 className="text-lg font-semibold text-[#0c0a08]">Reset demo data?</h2>
        <p className="text-sm text-[#6e6a68]">
          This will permanently delete all transactions, reimbursements, digests, and
          notifications for this org and replace them with the standard demo seed data.
          Users, cards, and policies are preserved.
        </p>
        <p className="text-sm font-medium text-red-600">This action cannot be undone.</p>
        <div className="flex gap-3 pt-1">
          <button
            type="button"
            onClick={onClose}
            disabled={reset.isPending}
            className="flex-1 py-2 rounded-[6px] border border-[#d2cecb] text-sm text-[#0c0a08] hover:bg-[#f4f2f0] disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={reset.isPending}
            className="flex-1 py-2 rounded-[6px] bg-red-600 text-white text-sm font-semibold hover:bg-red-700 disabled:opacity-50"
          >
            {reset.isPending ? "Resetting…" : "Yes, reset demo"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export function SettingsPage() {
  const me = useMe();
  const { data: users = [], isLoading } = useUsers();
  const update = useUpdateUser();

  const [showInvite, setShowInvite] = useState(false);
  const [roleTarget, setRoleTarget] = useState<User | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [showResetConfirm, setShowResetConfirm] = useState(false);

  const isAdmin = me.data?.user.role === "ADMIN";
  const myId = me.data?.user.id;

  async function toggleActive(user: User) {
    setActionError(null);
    try {
      await update.mutateAsync({ id: user.id, is_active: !user.is_active });
    } catch (err) {
      setActionError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
          ?? "Failed to update user",
      );
    }
  }

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-[#0c0a08]">Settings</h1>
        {isAdmin && (
          <button
            onClick={() => setShowInvite(true)}
            className="px-4 py-2 rounded-[6px] bg-solar text-[#0c0a08] text-sm font-semibold hover:bg-solar-light"
          >
            + Invite member
          </button>
        )}
      </div>

      <section>
        <h2 className="text-base font-medium text-[#6e6a68] mb-3">Team members</h2>
        {isLoading ? (
          <p className="text-[#6e6a68]">Loading…</p>
        ) : (
          <div className="border border-[#d2cecb] rounded-lg overflow-hidden bg-white">
            <table className="w-full text-sm">
              <thead className="bg-[#f4f2f0] text-xs uppercase tracking-wide text-[#6e6a68]">
                <tr>
                  <th className="px-4 py-3 text-left">Name</th>
                  <th className="px-4 py-3 text-left">Email</th>
                  <th className="px-4 py-3 text-left">Role</th>
                  <th className="px-4 py-3 text-left">Status</th>
                  {isAdmin && <th className="px-4 py-3 text-right">Actions</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-[#d2cecb]">
                {users.map((user) => (
                  <tr key={user.id} className="hover:bg-[#f4f2f0]">
                    <td className="px-4 py-3 font-medium text-[#0c0a08]">
                      {user.full_name}
                      {user.id === myId && (
                        <span className="ml-2 text-xs text-[#6e6a68]">(you)</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-[#6e6a68]">{user.email}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${ROLE_COLORS[user.role]}`}>
                        {user.role.replace("_", " ")}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                        user.is_active ? "bg-green-100 text-green-800" : "bg-[#f4f2f0] text-[#6e6a68]"
                      }`}>
                        {user.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    {isAdmin && (
                      <td className="px-4 py-3 text-right">
                        <div className="flex justify-end gap-3">
                          {user.id !== myId && (
                            <>
                              <button
                                onClick={() => setRoleTarget(user)}
                                className="text-xs text-blue-700 hover:underline"
                              >
                                Change role
                              </button>
                              <button
                                onClick={() => toggleActive(user)}
                                disabled={update.isPending}
                                className={`text-xs hover:underline disabled:opacity-40 ${
                                  user.is_active ? "text-red-600" : "text-green-700"
                                }`}
                              >
                                {user.is_active ? "Deactivate" : "Reactivate"}
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
      </section>

      {actionError && (
        <p className="mt-3 text-sm text-red-600">{actionError}</p>
      )}

      {isAdmin && (
        <section className="mt-10 pt-6 border-t border-[#d2cecb]">
          <h2 className="text-base font-medium text-[#6e6a68] mb-1">Danger Zone</h2>
          <p className="text-sm text-[#6e6a68] mb-4">
            Reset all demo data to the original seeded state. Users, cards, and policies
            are preserved. Transactions, reimbursements, digests, and notifications are wiped
            and replaced with fresh demo data.
          </p>
          <button
            onClick={() => setShowResetConfirm(true)}
            className="px-4 py-2 text-sm rounded-[6px] border border-red-300 text-red-600 hover:bg-red-50 font-medium"
          >
            Reset Demo Data
          </button>
        </section>
      )}

      {showInvite && <InviteDialog onClose={() => setShowInvite(false)} />}
      {roleTarget && <RoleDialog user={roleTarget} onClose={() => setRoleTarget(null)} />}
      {showResetConfirm && <ResetDemoConfirmModal onClose={() => setShowResetConfirm(false)} />}
    </div>
  );
}
