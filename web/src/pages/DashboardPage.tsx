import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  AreaChart,
  Area,
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
import {
  useDashboardSummary,
  useDashboardTimeseries,
} from "@/features/dashboard/hooks";

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

function fmtINR(amount: string | number) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(Number(amount));
}

function fmtDate(isoDate: string) {
  const d = new Date(isoDate);
  return d.toLocaleDateString("en-IN", { month: "short", day: "numeric" });
}

// ---------------------------------------------------------------------------
// Skeleton placeholder
// ---------------------------------------------------------------------------

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`bg-[#d2cecb] rounded animate-pulse ${className}`} />;
}

// ---------------------------------------------------------------------------
// Date range picker
// ---------------------------------------------------------------------------

const RANGES = [
  { label: "7d", days: 7 },
  { label: "30d", days: 30 },
  { label: "90d", days: 90 },
];

function toISOStr(d: Date) {
  return d.toISOString();
}

function getRangeDates(days: number): [string, string] {
  const to = new Date();
  const from = new Date();
  from.setDate(from.getDate() - days);
  return [toISOStr(from), toISOStr(to)];
}

// ---------------------------------------------------------------------------
// KPI card
// ---------------------------------------------------------------------------

type KpiCardProps = {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
};

function KpiCard({ label, value, sub }: KpiCardProps) {
  return (
    <div className="bg-white border border-[#d2cecb] rounded-xl p-5">
      <div className="text-xs uppercase tracking-wide text-[#6e6a68] mb-1">{label}</div>
      <div className="text-2xl font-semibold tracking-tight text-[#0c0a08]">{value}</div>
      {sub && <div className="mt-1 text-sm text-[#6e6a68]">{sub}</div>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function DashboardPage() {
  const me = useMe();
  const [rangeDays, setRangeDays] = useState(30);
  const [fromDate, toDate] = useMemo(() => getRangeDates(rangeDays), [rangeDays]);

  const summary = useDashboardSummary(fromDate, toDate);
  const timeseries = useDashboardTimeseries(fromDate, toDate, "day");

  const user = me.data?.user;
  const isAdminOrFM =
    user?.role === "ADMIN" || user?.role === "FINANCE_MANAGER";

  // MoM delta display
  const delta = summary.data?.mom_delta_pct;
  const deltaEl =
    delta == null ? (
      <span className="text-[#6e6a68]">— no prior data</span>
    ) : delta > 0 ? (
      <span className="text-green-600">
        +{delta.toFixed(1)}% vs prior period
      </span>
    ) : (
      <span className="text-red-600">
        {delta.toFixed(1)}% vs prior period
      </span>
    );

  if (me.isLoading) {
    return <div className="p-8 text-[#6e6a68]">Loading…</div>;
  }

  // EMPLOYEE: simple welcome screen
  if (!isAdminOrFM) {
    return (
      <div className="p-8 max-w-3xl mx-auto">
        <h1 className="text-3xl font-semibold tracking-tight">
          Welcome, {user?.full_name?.split(" ")[0] ?? "there"}.
        </h1>
        <p className="mt-2 text-[#6e6a68]">
          Submit reimbursements via the Reimbursements tab and track your card
          transactions below.
        </p>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      {/* Header + range toggle */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <div className="flex gap-1 bg-[#f4f2f0] border border-[#d2cecb] rounded-lg p-1">
          {RANGES.map(({ label, days }) => (
            <button
              key={days}
              onClick={() => setRangeDays(days)}
              className={`px-3 py-1 rounded-md text-sm font-medium transition-colors ${
                rangeDays === days
                  ? "bg-solar text-[#0c0a08]"
                  : "text-[#6e6a68] hover:text-[#0c0a08]"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {summary.isLoading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24" />
          ))
        ) : (
          <>
            <KpiCard
              label="Total spend"
              value={fmtINR(summary.data?.total_spend ?? "0")}
              sub={`${summary.data?.transaction_count ?? 0} transactions`}
            />
            <KpiCard
              label="MoM change"
              value={deltaEl}
              sub={`${rangeDays}-day window`}
            />
            <KpiCard
              label="Pending approvals"
              value={summary.data?.pending_approvals ?? 0}
              sub="Flagged transactions"
            />
            <KpiCard
              label="Active cards"
              value={summary.data?.active_cards ?? 0}
            />
          </>
        )}
      </div>

      {/* Spend over time (area chart) */}
      <div className="bg-white border border-[#d2cecb] rounded-xl p-5">
        <h2 className="text-sm font-medium text-[#0c0a08] mb-4">
          Spend over time
        </h2>
        {timeseries.isLoading ? (
          <Skeleton className="h-56" />
        ) : !timeseries.data?.length ? (
          <div className="h-56 flex items-center justify-center text-[#6e6a68] text-sm">
            No transactions in this period
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart
              data={timeseries.data.map((p) => ({
                period: fmtDate(p.period),
                amount: Number(p.amount),
              }))}
            >
              <defs>
                <linearGradient id="spendGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#1a1919" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#1a1919" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis
                dataKey="period"
                tick={{ fontSize: 11, fill: "#9ca3af" }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 11, fill: "#9ca3af" }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v: number) => `₹${(v / 1000).toFixed(0)}k`}
              />
              <Tooltip
                formatter={(v: unknown) => [fmtINR(v as number), "Spend"]}
                contentStyle={{
                  borderRadius: 8,
                  border: "1px solid #e5e7eb",
                  fontSize: 12,
                }}
              />
              <Area
                type="monotone"
                dataKey="amount"
                stroke="#1a1919"
                strokeWidth={2}
                fill="url(#spendGrad)"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Category pie + Department bar */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Category breakdown */}
        <div className="bg-white border border-[#d2cecb] rounded-xl p-5">
          <h2 className="text-sm font-medium text-[#0c0a08] mb-4">
            Spend by category
          </h2>
          {summary.isLoading ? (
            <Skeleton className="h-48" />
          ) : !summary.data?.by_category.length ? (
            <div className="h-48 flex items-center justify-center text-[#6e6a68] text-sm">
              No data
            </div>
          ) : (
            <div className="flex items-center gap-4">
              <div style={{ width: 160, height: 160 }}>
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={summary.data.by_category}
                    dataKey="amount"
                    nameKey="category"
                    cx="50%"
                    cy="50%"
                    outerRadius={70}
                    strokeWidth={2}
                  >
                    {summary.data.by_category.map((entry) => (
                      <Cell
                        key={entry.category}
                        fill={CATEGORY_COLORS[entry.category] ?? "#94a3b8"}
                      />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(v: unknown) => [fmtINR(v as number), ""]}
                    contentStyle={{
                      borderRadius: 8,
                      border: "1px solid #e5e7eb",
                      fontSize: 12,
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
              </div>
              <div className="flex-1 space-y-1.5">
                {summary.data.by_category.slice(0, 6).map((c) => (
                  <div key={c.category} className="flex items-center gap-2 text-sm">
                    <span
                      className="inline-block w-2.5 h-2.5 rounded-full flex-shrink-0"
                      style={{
                        backgroundColor:
                          CATEGORY_COLORS[c.category] ?? "#94a3b8",
                      }}
                    />
                    <span className="text-[#6e6a68] flex-1 truncate">
                      {c.category}
                    </span>
                    <span className="font-medium text-[#0c0a08]">
                      {fmtINR(c.amount)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Department breakdown */}
        <div className="bg-white border border-[#d2cecb] rounded-xl p-5">
          <h2 className="text-sm font-medium text-[#0c0a08] mb-4">
            Spend by department
          </h2>
          {summary.isLoading ? (
            <Skeleton className="h-48" />
          ) : !summary.data?.by_department.length ? (
            <div className="h-48 flex items-center justify-center text-[#6e6a68] text-sm">
              No department data
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart
                data={summary.data.by_department.map((d) => ({
                  name: d.department_name,
                  amount: Number(d.amount),
                }))}
                layout="vertical"
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="#f0f0f0"
                  horizontal={false}
                />
                <XAxis
                  type="number"
                  tick={{ fontSize: 11, fill: "#9ca3af" }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(v: number) =>
                    `₹${(v / 1000).toFixed(0)}k`
                  }
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
                  contentStyle={{
                    borderRadius: 8,
                    border: "1px solid #e5e7eb",
                    fontSize: 12,
                  }}
                />
                <Bar dataKey="amount" fill="#1a1919" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Top merchants */}
      <div className="bg-white border border-[#d2cecb] rounded-xl p-5">
        <h2 className="text-sm font-medium text-[#0c0a08] mb-4">
          Top merchants
        </h2>
        {summary.isLoading ? (
          <Skeleton className="h-32" />
        ) : !summary.data?.top_merchants.length ? (
          <p className="text-[#6e6a68] text-sm">No merchants in this period</p>
        ) : (
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
                {summary.data.top_merchants.map((m, i) => (
                  <motion.tr
                    key={m.merchant}
                    className="hover:bg-[#f4f2f0]"
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.04, duration: 0.2 }}
                  >
                    <td className="py-2 font-medium text-[#0c0a08]">
                      {m.merchant}
                    </td>
                    <td className="py-2 text-right text-[#6e6a68]">
                      {m.count}
                    </td>
                    <td className="py-2 text-right font-mono text-[#0c0a08]">
                      {fmtINR(m.amount)}
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
