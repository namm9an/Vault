import { useState } from "react";
import { useMe } from "@/features/auth/hooks";
import { useUsers, useInviteUser, useUpdateUser } from "@/features/users/hooks";
import type { User, UserRole } from "@/types/api";

const ROLE_COLORS: Record<UserRole, string> = {
  ADMIN: "bg-purple-100 text-purple-800",
  FINANCE_MANAGER: "bg-blue-100 text-blue-800",
  EMPLOYEE: "bg-neutral-100 text-neutral-700",
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
        <h2 className="text-lg font-semibold">Invite team member</h2>
        <form onSubmit={onSubmit} className="space-y-3">
          <label className="block">
            <span className="text-sm text-neutral-600">Full name</span>
            <input
              required
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Alice Sharma"
              className="mt-1 w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30"
            />
          </label>
          <label className="block">
            <span className="text-sm text-neutral-600">Email</span>
            <input
              required
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="alice@acme.com"
              className="mt-1 w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30"
            />
          </label>
          <label className="block">
            <span className="text-sm text-neutral-600">Temporary password</span>
            <input
              required
              type="password"
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Min 8 characters"
              className="mt-1 w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30"
            />
          </label>
          <label className="block">
            <span className="text-sm text-neutral-600">Role</span>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as UserRole)}
              className="mt-1 w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30"
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
              className="flex-1 py-2 rounded-md border text-sm text-neutral-700 hover:bg-neutral-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={invite.isPending}
              className="flex-1 py-2 rounded-md bg-neutral-900 text-white text-sm font-medium disabled:opacity-50"
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
        <h2 className="text-lg font-semibold">Change role</h2>
        <p className="text-sm text-neutral-500">{user.full_name} ({user.email})</p>
        <form onSubmit={onSubmit} className="space-y-3">
          <label className="block">
            <span className="text-sm text-neutral-600">New role</span>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as UserRole)}
              className="mt-1 w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30"
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
              className="flex-1 py-2 rounded-md border text-sm text-neutral-700 hover:bg-neutral-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={update.isPending || role === user.role}
              className="flex-1 py-2 rounded-md bg-neutral-900 text-white text-sm font-medium disabled:opacity-50"
            >
              {update.isPending ? "Saving…" : "Save"}
            </button>
          </div>
        </form>
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
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        {isAdmin && (
          <button
            onClick={() => setShowInvite(true)}
            className="px-4 py-2 rounded-md bg-neutral-900 text-white text-sm font-medium hover:bg-neutral-800"
          >
            + Invite member
          </button>
        )}
      </div>

      <section>
        <h2 className="text-base font-medium text-neutral-700 mb-3">Team members</h2>
        {isLoading ? (
          <p className="text-neutral-500">Loading…</p>
        ) : (
          <div className="border rounded-lg overflow-hidden bg-white">
            <table className="w-full text-sm">
              <thead className="bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500">
                <tr>
                  <th className="px-4 py-3 text-left">Name</th>
                  <th className="px-4 py-3 text-left">Email</th>
                  <th className="px-4 py-3 text-left">Role</th>
                  <th className="px-4 py-3 text-left">Status</th>
                  {isAdmin && <th className="px-4 py-3 text-right">Actions</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {users.map((user) => (
                  <tr key={user.id} className="hover:bg-neutral-50">
                    <td className="px-4 py-3 font-medium">
                      {user.full_name}
                      {user.id === myId && (
                        <span className="ml-2 text-xs text-neutral-400">(you)</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-neutral-600">{user.email}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${ROLE_COLORS[user.role]}`}>
                        {user.role.replace("_", " ")}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                        user.is_active ? "bg-green-100 text-green-800" : "bg-neutral-100 text-neutral-500"
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

      {showInvite && <InviteDialog onClose={() => setShowInvite(false)} />}
      {roleTarget && <RoleDialog user={roleTarget} onClose={() => setRoleTarget(null)} />}
    </div>
  );
}
