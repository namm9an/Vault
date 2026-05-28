import { useState } from "react";
import { useMe } from "@/features/auth/hooks";
import {
  useCards,
  useCreateCard,
  useFreezeCard,
  useUnfreezeCard,
  useCancelCard,
} from "@/features/cards/hooks";
import { useUsers } from "@/features/users/hooks";
import type { Card, SpendCategory } from "@/types/api";

const STATUS_COLORS: Record<string, string> = {
  ACTIVE: "bg-green-100 text-green-800",
  FROZEN: "bg-yellow-100 text-yellow-800",
  CANCELLED: "bg-red-100 text-red-800",
};

const ALL_CATEGORIES: SpendCategory[] = [
  "TRAVEL", "MEALS", "SAAS", "OFFICE", "MARKETING", "HARDWARE", "PROFESSIONAL_SERVICES", "OTHER",
];

function fmt(n: string) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(Number(n));
}

// ── New Card Dialog ──────────────────────────────────────────────────────────

type NewCardDialogProps = { onClose: () => void };

function NewCardDialog({ onClose }: NewCardDialogProps) {
  const { data: users = [] } = useUsers();
  const create = useCreateCard();
  const [userId, setUserId] = useState("");
  const [nickname, setNickname] = useState("");
  const [daily, setDaily] = useState("10000");
  const [monthly, setMonthly] = useState("100000");
  const [categories, setCategories] = useState<SpendCategory[]>([]);

  const toggleCat = (c: SpendCategory) =>
    setCategories((prev) => prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await create.mutateAsync({
        user_id: userId,
        nickname,
        daily_limit: daily,
        monthly_limit: monthly,
        total_limit: "0",
        category_restrictions: categories,
      });
      onClose();
    } catch { /* error shown below */ }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6 space-y-4">
        <h2 className="text-lg font-semibold">Issue new card</h2>
        <form onSubmit={onSubmit} className="space-y-3">
          <label className="block">
            <span className="text-sm text-neutral-600">Assign to</span>
            <select
              required
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              className="mt-1 w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30"
            >
              <option value="">Select user…</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>{u.full_name} ({u.email})</option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-sm text-neutral-600">Nickname</span>
            <input
              required
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
              placeholder="e.g. Marketing card"
              className="mt-1 w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30"
            />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="text-sm text-neutral-600">Daily limit (₹)</span>
              <input
                required
                type="number"
                min="0"
                value={daily}
                onChange={(e) => setDaily(e.target.value)}
                className="mt-1 w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30"
              />
            </label>
            <label className="block">
              <span className="text-sm text-neutral-600">Monthly limit (₹)</span>
              <input
                required
                type="number"
                min="0"
                value={monthly}
                onChange={(e) => setMonthly(e.target.value)}
                className="mt-1 w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30"
              />
            </label>
          </div>
          <div>
            <span className="text-sm text-neutral-600">Category restrictions (leave empty = all allowed)</span>
            <div className="mt-1 flex flex-wrap gap-2">
              {ALL_CATEGORIES.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => toggleCat(c)}
                  className={`px-2 py-0.5 rounded text-xs border transition-colors ${
                    categories.includes(c)
                      ? "bg-blue-600 text-white border-blue-600"
                      : "bg-white text-neutral-700 border-neutral-300 hover:border-blue-400"
                  }`}
                >
                  {c}
                </button>
              ))}
            </div>
          </div>
          {create.isError && (
            <p className="text-sm text-red-600">
              {(create.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Failed to create card"}
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
              {create.isPending ? "Creating…" : "Issue card"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Confirm Dialog ────────────────────────────────────────────────────────────

type ConfirmDialogProps = {
  title: string;
  body: string;
  confirmLabel: string;
  danger?: boolean;
  onConfirm: () => void;
  onClose: () => void;
  isPending: boolean;
};

function ConfirmDialog({ title, body, confirmLabel, danger, onConfirm, onClose, isPending }: ConfirmDialogProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-sm p-6 space-y-4">
        <h2 className="text-lg font-semibold">{title}</h2>
        <p className="text-sm text-neutral-600">{body}</p>
        <div className="flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 py-2 rounded-md border text-sm text-neutral-700 hover:bg-neutral-50"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={isPending}
            className={`flex-1 py-2 rounded-md text-white text-sm font-medium disabled:opacity-50 ${
              danger ? "bg-red-600 hover:bg-red-700" : "bg-neutral-900 hover:bg-neutral-800"
            }`}
          >
            {isPending ? "…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export function CardsPage() {
  const me = useMe();
  const { data: cards = [], isLoading } = useCards();
  const freeze = useFreezeCard();
  const unfreeze = useUnfreezeCard();
  const cancel = useCancelCard();

  const [showNew, setShowNew] = useState(false);
  const [confirm, setConfirm] = useState<{
    card: Card;
    action: "freeze" | "unfreeze" | "cancel";
  } | null>(null);

  const isAdmin = me.data?.user.role === "ADMIN";

  async function handleConfirm() {
    if (!confirm) return;
    const { card, action } = confirm;
    try {
      if (action === "freeze") await freeze.mutateAsync(card.id);
      else if (action === "unfreeze") await unfreeze.mutateAsync(card.id);
      else await cancel.mutateAsync(card.id);
      setConfirm(null);
    } catch { /* leave dialog open */ }
  }

  const confirmPending = freeze.isPending || unfreeze.isPending || cancel.isPending;

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">Cards</h1>
        {isAdmin && (
          <button
            onClick={() => setShowNew(true)}
            className="px-4 py-2 rounded-md bg-neutral-900 text-white text-sm font-medium hover:bg-neutral-800"
          >
            + Issue card
          </button>
        )}
      </div>

      {isLoading ? (
        <p className="text-neutral-500">Loading…</p>
      ) : cards.length === 0 ? (
        <p className="text-neutral-500">No cards yet.</p>
      ) : (
        <div className="border rounded-lg overflow-hidden bg-white">
          <table className="w-full text-sm">
            <thead className="bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500">
              <tr>
                <th className="px-4 py-3 text-left">Card</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-right">Daily limit</th>
                <th className="px-4 py-3 text-right">Monthly limit</th>
                <th className="px-4 py-3 text-left">Restrictions</th>
                {isAdmin && <th className="px-4 py-3 text-right">Actions</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {cards.map((card) => (
                <tr key={card.id} className="hover:bg-neutral-50">
                  <td className="px-4 py-3">
                    <div className="font-medium">{card.nickname}</div>
                    <div className="text-neutral-400 text-xs">•••• {card.last_four}</div>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[card.status] ?? ""}`}>
                      {card.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right font-mono">{fmt(card.daily_limit)}</td>
                  <td className="px-4 py-3 text-right font-mono">{fmt(card.monthly_limit)}</td>
                  <td className="px-4 py-3">
                    {card.category_restrictions.length === 0 ? (
                      <span className="text-neutral-400 text-xs">All</span>
                    ) : (
                      <span className="text-xs text-neutral-600">{card.category_restrictions.join(", ")}</span>
                    )}
                  </td>
                  {isAdmin && (
                    <td className="px-4 py-3 text-right">
                      <div className="flex justify-end gap-2">
                        {card.status === "ACTIVE" && (
                          <button
                            onClick={() => setConfirm({ card, action: "freeze" })}
                            className="text-xs text-yellow-700 hover:underline"
                          >
                            Freeze
                          </button>
                        )}
                        {card.status === "FROZEN" && (
                          <button
                            onClick={() => setConfirm({ card, action: "unfreeze" })}
                            className="text-xs text-green-700 hover:underline"
                          >
                            Unfreeze
                          </button>
                        )}
                        {card.status !== "CANCELLED" && (
                          <button
                            onClick={() => setConfirm({ card, action: "cancel" })}
                            className="text-xs text-red-600 hover:underline"
                          >
                            Cancel
                          </button>
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

      {showNew && <NewCardDialog onClose={() => setShowNew(false)} />}

      {confirm && (
        <ConfirmDialog
          title={
            confirm.action === "freeze"
              ? "Freeze card?"
              : confirm.action === "unfreeze"
              ? "Unfreeze card?"
              : "Cancel card?"
          }
          body={
            confirm.action === "cancel"
              ? `"${confirm.card.nickname}" will be permanently cancelled. This cannot be undone.`
              : confirm.action === "freeze"
              ? `"${confirm.card.nickname}" will be frozen. No new transactions until unfrozen.`
              : `"${confirm.card.nickname}" will be reactivated.`
          }
          confirmLabel={
            confirm.action === "freeze" ? "Freeze" : confirm.action === "unfreeze" ? "Unfreeze" : "Cancel card"
          }
          danger={confirm.action === "cancel"}
          onConfirm={handleConfirm}
          onClose={() => setConfirm(null)}
          isPending={confirmPending}
        />
      )}
    </div>
  );
}
