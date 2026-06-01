import { useState } from "react";
import { motion } from "framer-motion";
import { useMe } from "@/features/auth/hooks";
import {
  useCards,
  useCreateCard,
  useFreezeCard,
  useUnfreezeCard,
  useCancelCard,
} from "@/features/cards/hooks";
import { useUsers } from "@/features/users/hooks";
import { EmptyState } from "@/components/EmptyState";
import { Badge, type BadgeVariant } from "@/components/ui/badge";
import type { Card, SpendCategory } from "@/types/api";

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
        <h2 className="text-lg font-semibold text-[#0c0a08]">Issue new card</h2>
        <form onSubmit={onSubmit} className="space-y-3">
          <label className="block">
            <span className="text-sm text-[#6e6a68]">Assign to</span>
            <select
              required
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              className="mt-1 w-full border border-[#d2cecb] rounded-[6px] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-solar/50"
            >
              <option value="">Select user…</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>{u.full_name} ({u.email})</option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-sm text-[#6e6a68]">Nickname</span>
            <input
              required
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
              placeholder="e.g. Marketing card"
              className="mt-1 w-full border border-[#d2cecb] rounded-[6px] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-solar/50"
            />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="text-sm text-[#6e6a68]">Daily limit (₹)</span>
              <input
                required
                type="number"
                min="0"
                value={daily}
                onChange={(e) => setDaily(e.target.value)}
                className="mt-1 w-full border border-[#d2cecb] rounded-[6px] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-solar/50"
              />
            </label>
            <label className="block">
              <span className="text-sm text-[#6e6a68]">Monthly limit (₹)</span>
              <input
                required
                type="number"
                min="0"
                value={monthly}
                onChange={(e) => setMonthly(e.target.value)}
                className="mt-1 w-full border border-[#d2cecb] rounded-[6px] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-solar/50"
              />
            </label>
          </div>
          <div>
            <span className="text-sm text-[#6e6a68]">Allowed categories (leave empty = all allowed)</span>
            <div className="mt-1 flex flex-wrap gap-2">
              {ALL_CATEGORIES.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => toggleCat(c)}
                  className={`px-2 py-0.5 rounded text-xs border transition-colors ${
                    categories.includes(c)
                      ? "bg-solar text-[#0c0a08] border-solar"
                      : "bg-white text-[#6e6a68] border-[#d2cecb] hover:border-solar"
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
              className="flex-1 py-2 rounded-[6px] border border-[#d2cecb] text-sm text-[#0c0a08] hover:bg-[#f4f2f0]"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={create.isPending}
              className="flex-1 py-2 rounded-[6px] bg-solar text-[#0c0a08] text-sm font-semibold hover:bg-solar-light disabled:opacity-50"
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
        <h2 className="text-lg font-semibold text-[#0c0a08]">{title}</h2>
        <p className="text-sm text-[#6e6a68]">{body}</p>
        <div className="flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 py-2 rounded-[6px] border border-[#d2cecb] text-sm text-[#0c0a08] hover:bg-[#f4f2f0]"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={isPending}
            className={`flex-1 py-2 rounded-[6px] text-sm font-medium disabled:opacity-50 ${
              danger ? "bg-red-600 text-white hover:bg-red-700" : "bg-solar text-[#0c0a08] hover:bg-solar-light"
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
        <h1 className="text-2xl font-semibold tracking-tight text-[#0c0a08]">Cards</h1>
        {isAdmin && (
          <button
            onClick={() => setShowNew(true)}
            className="px-4 py-2 rounded-[6px] bg-solar text-[#0c0a08] text-sm font-semibold hover:bg-solar-light"
          >
            + Issue card
          </button>
        )}
      </div>

      {isLoading ? (
        <p className="text-[#6e6a68]">Loading…</p>
      ) : cards.length === 0 ? (
        <EmptyState
          title="No cards yet"
          description="Issue a virtual card to get started."
        />
      ) : (
        <div className="border border-[#d2cecb] rounded-lg overflow-hidden bg-white">
          <table className="w-full text-sm">
            <thead className="bg-[#f4f2f0] text-xs uppercase tracking-wide text-[#6e6a68]">
              <tr>
                <th className="px-4 py-3 text-left">Card</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-right">Daily limit</th>
                <th className="px-4 py-3 text-right">Monthly limit</th>
                <th className="px-4 py-3 text-left">Allowed Categories</th>
                {isAdmin && <th className="px-4 py-3 text-right">Actions</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-[#d2cecb]">
              {cards.map((card, index) => (
                <motion.tr
                  key={card.id}
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.03, duration: 0.2 }}
                  className="hover:bg-[#f4f2f0]"
                >
                  <td className="px-4 py-3">
                    <div className="font-medium text-[#0c0a08]">{card.nickname}</div>
                    <div className="text-[#6e6a68] text-xs">•••• {card.last_four}</div>
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant={card.status as BadgeVariant}>
                      {card.status}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-[#0c0a08]">{fmt(card.daily_limit)}</td>
                  <td className="px-4 py-3 text-right font-mono text-[#0c0a08]">{fmt(card.monthly_limit)}</td>
                  <td className="px-4 py-3">
                    {card.category_restrictions.length === 0 ? (
                      <span className="text-[#6e6a68] text-xs">All categories</span>
                    ) : (
                      <span className="text-xs text-[#6e6a68]">{card.category_restrictions.join(", ")}</span>
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
                </motion.tr>
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
