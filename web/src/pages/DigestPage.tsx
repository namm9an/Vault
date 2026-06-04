import { useState } from "react";
import { motion } from "framer-motion";
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { useMe } from "@/features/auth/hooks";
import { useDeleteDigest, useDigests, useGenerateDigest } from "@/features/digest/hooks";
import { EmptyState } from "@/components/EmptyState";
import { Badge, type BadgeVariant } from "@/components/ui/badge";
import type { Digest, DigestAggregated, DigestStatus } from "@/types/api";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const CATEGORY_COLORS: Record<string, string> = {
  TRAVEL: "#1a1919",
  MEALS: "#f59e0b",
  SAAS: "#10b981",
  OFFICE: "#3b82f6",
  MARKETING: "#ec4899",
  HARDWARE: "#8b5cf6",
  PROFESSIONAL_SERVICES: "#14b8a6",
  OTHER: "#94a3b8",
};

function fmtINR(amount: number) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(amount);
}

function fmtDate(d: string) {
  return new Date(d).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function toInputDate(d: Date) {
  return d.toISOString().split("T")[0];
}

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`bg-[#d2cecb] rounded animate-pulse ${className}`} />;
}

function statusBadge(status: DigestStatus) {
  return (
    <Badge variant={status as BadgeVariant}>
      {status === "COMPLETED" ? "Completed" : status === "PENDING" ? "Pending" : "Failed"}
    </Badge>
  );
}

const tooltipStyle = {
  borderRadius: 8,
  border: "1px solid #e5e7eb",
  fontSize: 12,
};

// ---------------------------------------------------------------------------
// Generate Modal
// ---------------------------------------------------------------------------

function GenerateModal({
  onClose,
  onGenerate,
  loading,
}: {
  onClose: () => void;
  onGenerate: (start: string, end: string) => void;
  loading: boolean;
}) {
  const today = new Date();
  const lastWeekEnd = new Date(today);
  lastWeekEnd.setDate(today.getDate() - 1);
  const lastWeekStart = new Date(lastWeekEnd);
  lastWeekStart.setDate(lastWeekEnd.getDate() - 6);

  const [start, setStart] = useState(toInputDate(lastWeekStart));
  const [end, setEnd] = useState(toInputDate(lastWeekEnd));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-sm p-6">
        <h2 className="text-base font-semibold text-[#0c0a08] mb-4">
          Generate Weekly Digest
        </h2>
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-[#6e6a68] mb-1">Period start</label>
            <input
              type="date"
              value={start}
              onChange={(e) => setStart(e.target.value)}
              className="w-full border border-[#d2cecb] rounded-[6px] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-solar/50 focus:border-solar"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-[#6e6a68] mb-1">Period end</label>
            <input
              type="date"
              value={end}
              onChange={(e) => setEnd(e.target.value)}
              className="w-full border border-[#d2cecb] rounded-[6px] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-solar/50 focus:border-solar"
            />
          </div>
        </div>
        <div className="flex gap-2 mt-5">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 rounded-[6px] border border-[#d2cecb] text-sm font-medium text-[#6e6a68] hover:bg-[#f4f2f0]"
          >
            Cancel
          </button>
          <button
            disabled={loading || !start || !end || start >= end}
            onClick={() => start && end && onGenerate(start, end)}
            className="flex-1 px-4 py-2 rounded-[6px] bg-solar text-[#0c0a08] text-sm font-semibold hover:bg-solar-light disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "Generating…" : "Generate"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// KPI Card — matches DashboardPage exactly
// ---------------------------------------------------------------------------

function KpiCard({ label, value, sub }: { label: string; value: React.ReactNode; sub?: React.ReactNode }) {
  return (
    <div className="bg-white border border-[#d2cecb] rounded-xl p-5">
      <div className="text-xs uppercase tracking-wide text-[#6e6a68] mb-1">{label}</div>
      <div className="text-2xl font-semibold tracking-tight text-[#0c0a08]">{value}</div>
      {sub && <div className="mt-1 text-sm text-[#6e6a68]">{sub}</div>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Charts section
// ---------------------------------------------------------------------------

function DigestCharts({ agg, flaggedCount }: { agg: DigestAggregated; flaggedCount: number }) {
  const catData = (agg.top_categories ?? []).map((c) => ({
    category: c.category,
    name: c.category.replace(/_/g, " "),
    amount: c.amount,
  }));

  const deptData = (agg.top_departments ?? []).map((d) => ({
    name: d.department_name,
    amount: d.amount,
  }));

  return (
    <div className="space-y-4">
      {/* KPI row */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <KpiCard
          label="Total spend"
          value={fmtINR(agg.total_spend)}
          sub={`${agg.transaction_count} transactions`}
        />
        <KpiCard
          label="Pending approvals"
          value={agg.pending_approvals}
          sub="Awaiting FM review"
        />
        <KpiCard
          label="Policy blocked"
          value={agg.policy_blocked_count}
          sub="Reimbursements rejected"
        />
        <KpiCard
          label="Flagged items"
          value={flaggedCount}
          sub="AI-identified anomalies"
        />
      </div>

      {/* Category pie + Department bar */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Category breakdown */}
        <div className="bg-white border border-[#d2cecb] rounded-xl p-5">
          <h2 className="text-sm font-medium text-[#0c0a08] mb-4">Spend by category</h2>
          {!catData.length ? (
            <div className="h-48 flex items-center justify-center text-[#6e6a68] text-sm">No data</div>
          ) : (
            <div className="flex items-center gap-4">
              <div style={{ width: 160, height: 160 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={catData} dataKey="amount" nameKey="name" cx="50%" cy="50%" outerRadius={70} strokeWidth={2}>
                      {catData.map((entry) => (
                        <Cell key={entry.category} fill={CATEGORY_COLORS[entry.category] ?? "#94a3b8"} />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(v: unknown) => [fmtINR(v as number), ""]}
                      contentStyle={tooltipStyle}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="flex-1 space-y-1.5">
                {catData.map((c) => (
                  <div key={c.category} className="flex items-center gap-2 text-sm">
                    <span
                      className="inline-block w-2.5 h-2.5 rounded-full flex-shrink-0"
                      style={{ backgroundColor: CATEGORY_COLORS[c.category] ?? "#94a3b8" }}
                    />
                    <span className="text-[#6e6a68] flex-1 truncate">{c.name}</span>
                    <span className="font-medium text-[#0c0a08]">{fmtINR(c.amount)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Department breakdown */}
        <div className="bg-white border border-[#d2cecb] rounded-xl p-5">
          <h2 className="text-sm font-medium text-[#0c0a08] mb-4">Spend by department</h2>
          {!deptData.length ? (
            <div className="h-48 flex items-center justify-center text-[#6e6a68] text-sm">No department data</div>
          ) : (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={deptData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />
                <XAxis
                  type="number"
                  tick={{ fontSize: 11, fill: "#9ca3af" }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(v: number) => `₹${(v / 1000).toFixed(0)}k`}
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  tick={{ fontSize: 11, fill: "#9ca3af" }}
                  axisLine={false}
                  tickLine={false}
                  width={90}
                />
                <Tooltip
                  formatter={(v: unknown) => [fmtINR(v as number), "Spend"]}
                  contentStyle={tooltipStyle}
                />
                <Bar dataKey="amount" fill="#1a1919" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Top merchants table */}
      {agg.top_merchants?.length > 0 && (
        <div className="bg-white border border-[#d2cecb] rounded-xl p-5">
          <h2 className="text-sm font-medium text-[#0c0a08] mb-4">Top merchants</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs uppercase tracking-wide text-[#6e6a68]">
                  <th className="text-left pb-2 font-medium">Merchant</th>
                  <th className="text-right pb-2 font-medium">Transactions</th>
                  <th className="text-right pb-2 font-medium">Total spend</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#d2cecb]">
                {agg.top_merchants.map((m, i) => (
                  <motion.tr
                    key={m.merchant}
                    className="hover:bg-[#f4f2f0]"
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.04, duration: 0.2 }}
                  >
                    <td className="py-2 font-medium text-[#0c0a08]">{m.merchant}</td>
                    <td className="py-2 text-right text-[#6e6a68]">{m.count}</td>
                    <td className="py-2 text-right font-mono text-[#0c0a08]">{fmtINR(m.amount)}</td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Digest Detail Panel
// ---------------------------------------------------------------------------

function DigestDetail({ digest, isAdmin, onDelete, deleting }: {
  digest: Digest;
  isAdmin: boolean;
  onDelete: () => void;
  deleting: boolean;
}) {
  const agg = digest.aggregated_input;

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            {statusBadge(digest.status)}
            <span className="text-sm text-[#6e6a68]">
              {fmtDate(digest.period_start)} – {fmtDate(digest.period_end)}
            </span>
          </div>
          {digest.headline ? (
            <h1 className="text-2xl font-semibold tracking-tight text-[#0c0a08]">
              {digest.headline}
            </h1>
          ) : digest.status === "FAILED" ? (
            <p className="text-sm text-red-600">Digest generation failed. Try regenerating.</p>
          ) : (
            <p className="text-sm text-[#6e6a68] italic">Generating…</p>
          )}
        </div>
        {isAdmin && (
          <button
            onClick={onDelete}
            disabled={deleting}
            className="flex-shrink-0 px-3 py-1.5 text-xs font-medium rounded-[6px] border border-red-200 text-red-600 hover:bg-red-50 disabled:opacity-50"
          >
            {deleting ? "Deleting…" : "Delete"}
          </button>
        )}
      </div>

      {/* Charts + KPIs */}
      {agg && (
        <DigestCharts agg={agg} flaggedCount={digest.flagged_items?.length ?? 0} />
      )}

      {/* AI Summary */}
      {digest.body && (
        <div className="bg-white border border-[#d2cecb] rounded-xl p-5">
          <h2 className="text-sm font-medium text-[#0c0a08] mb-3">AI summary</h2>
          <p className="text-sm text-[#6e6a68] leading-relaxed whitespace-pre-line">{digest.body}</p>
        </div>
      )}

      {/* Recommendations */}
      {digest.top_recommendations && digest.top_recommendations.length > 0 && (
        <div className="bg-white border border-[#d2cecb] rounded-xl p-5">
          <h2 className="text-sm font-medium text-[#0c0a08] mb-3">Recommendations</h2>
          <ul className="space-y-2">
            {digest.top_recommendations.map((rec, i) => (
              <li key={i} className="flex gap-3 text-sm text-[#0c0a08]">
                <span className="flex-shrink-0 text-[#6e6a68] font-medium">{i + 1}.</span>
                {rec}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Flagged Items */}
      {digest.flagged_items && digest.flagged_items.length > 0 && (
        <div className="bg-white border border-[#d2cecb] rounded-xl p-5">
          <h2 className="text-sm font-medium text-[#0c0a08] mb-3">Flagged items</h2>
          <div className="space-y-2">
            {digest.flagged_items.map((item, i) => (
              <div key={i} className="rounded-lg border border-red-100 bg-red-50 px-4 py-3">
                <div className="flex items-start justify-between gap-2">
                  <span className="text-sm font-medium text-red-800">{item.description}</span>
                  <span className="text-sm font-mono text-red-700 flex-shrink-0">
                    {fmtINR(item.amount)}
                  </span>
                </div>
                <p className="mt-1 text-xs text-red-600">{item.reason}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function DigestPage() {
  const me = useMe();
  const digests = useDigests();
  const generateDigest = useGenerateDigest();
  const deleteDigest = useDeleteDigest();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);

  const user = me.data?.user;
  const isAdmin = user?.role === "ADMIN";

  const selected = selectedId
    ? ((digests.data ?? []).find((d) => d.id === selectedId) ?? generateDigest.data ?? null)
    : null;

  async function handleDelete() {
    if (!selectedId) return;
    await deleteDigest.mutateAsync(selectedId);
    setSelectedId(null);
  }

  async function handleGenerate(start: string, end: string) {
    try {
      const digest = await generateDigest.mutateAsync({ period_start: start, period_end: end });
      setShowModal(false);
      setSelectedId(digest.id);
    } catch {
      // error visible through mutation state
    }
  }

  return (
    <div className="h-full flex">
      {showModal && (
        <GenerateModal
          onClose={() => setShowModal(false)}
          onGenerate={handleGenerate}
          loading={generateDigest.isPending}
        />
      )}

      {/* Left: digest list */}
      <div className="w-72 flex-shrink-0 border-r border-[#d2cecb] bg-white flex flex-col">
        <div className="flex items-center justify-between px-4 py-4 border-b border-[#d2cecb]">
          <h1 className="text-sm font-semibold text-[#0c0a08]">Digests</h1>
          {isAdmin && (
            <button
              onClick={() => setShowModal(true)}
              className="text-xs px-3 py-1.5 rounded-[6px] bg-solar text-[#0c0a08] font-semibold hover:bg-solar-light"
            >
              Generate
            </button>
          )}
        </div>

        <div className="flex-1 overflow-y-auto">
          {digests.isLoading ? (
            <div className="p-4 space-y-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-16" />
              ))}
            </div>
          ) : !digests.data?.length ? (
            <EmptyState
              title="No digests yet"
              description={isAdmin ? "Generate your first weekly digest." : "No digests have been generated yet."}
            />
          ) : (
            <ul className="divide-y divide-[#d2cecb]">
              {digests.data.map((d) => (
                <li key={d.id}>
                  <button
                    onClick={() => setSelectedId(d.id)}
                    className={`w-full text-left px-4 py-3 hover:bg-[#f4f2f0] transition-colors ${
                      selectedId === d.id ? "bg-[#f4f2f0]" : ""
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs text-[#6e6a68]">
                        {fmtDate(d.period_start)} – {fmtDate(d.period_end)}
                      </span>
                      {statusBadge(d.status)}
                    </div>
                    {d.headline ? (
                      <p className="text-sm text-[#0c0a08] line-clamp-2">{d.headline}</p>
                    ) : (
                      <p className="text-sm text-[#6e6a68] italic">
                        {d.status === "PENDING" ? "Generating…" : "No headline"}
                      </p>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Right: detail panel */}
      <div className="flex-1 overflow-y-auto bg-[#f4f2f0]">
        {selected ? (
          <DigestDetail
            digest={selected}
            isAdmin={isAdmin}
            onDelete={handleDelete}
            deleting={deleteDigest.isPending}
          />
        ) : (
          <div className="h-full flex items-center justify-center">
            <EmptyState
              title="Select a digest"
              description="Choose a digest from the list to view details."
              icon={
                <svg xmlns="http://www.w3.org/2000/svg" className="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              }
            />
          </div>
        )}
      </div>
    </div>
  );
}
