import { useState } from "react";
import { useMe } from "@/features/auth/hooks";
import { useDigests, useGenerateDigest } from "@/features/digest/hooks";
import { EmptyState } from "@/components/EmptyState";
import type { Digest, DigestStatus } from "@/types/api";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`bg-neutral-100 rounded animate-pulse ${className}`} />;
}

function statusBadge(status: DigestStatus) {
  if (status === "COMPLETED") {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
        Completed
      </span>
    );
  }
  if (status === "PENDING") {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-700">
        Pending
      </span>
    );
  }
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">
      Failed
    </span>
  );
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
        <h2 className="text-base font-semibold text-neutral-900 mb-4">
          Generate Weekly Digest
        </h2>
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-neutral-600 mb-1">
              Period start
            </label>
            <input
              type="date"
              value={start}
              onChange={(e) => setStart(e.target.value)}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-neutral-600 mb-1">
              Period end
            </label>
            <input
              type="date"
              value={end}
              onChange={(e) => setEnd(e.target.value)}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        </div>
        <div className="flex gap-2 mt-5">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 rounded-lg border text-sm font-medium text-neutral-600 hover:bg-neutral-50"
          >
            Cancel
          </button>
          <button
            disabled={loading || !start || !end || start >= end}
            onClick={() => start && end && onGenerate(start, end)}
            className="flex-1 px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "Generating…" : "Generate"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Digest Detail Panel
// ---------------------------------------------------------------------------

function DigestDetail({ digest }: { digest: Digest }) {
  return (
    <div className="p-6 space-y-6">
      <div>
        <div className="flex items-center gap-2 mb-1">
          {statusBadge(digest.status)}
          <span className="text-xs text-neutral-400">
            {fmtDate(digest.period_start)} – {fmtDate(digest.period_end)}
          </span>
        </div>
        {digest.headline ? (
          <h2 className="text-lg font-semibold text-neutral-900 mt-2">
            {digest.headline}
          </h2>
        ) : digest.status === "FAILED" ? (
          <p className="text-sm text-red-600 mt-2">
            Digest generation failed. Try regenerating.
          </p>
        ) : (
          <p className="text-sm text-neutral-400 mt-2">No headline available.</p>
        )}
      </div>

      {digest.body && (
        <div>
          <h3 className="text-xs uppercase tracking-wide text-neutral-400 font-medium mb-2">
            Summary
          </h3>
          <p className="text-sm text-neutral-700 leading-relaxed whitespace-pre-line">
            {digest.body}
          </p>
        </div>
      )}

      {digest.top_recommendations && digest.top_recommendations.length > 0 && (
        <div>
          <h3 className="text-xs uppercase tracking-wide text-neutral-400 font-medium mb-2">
            Recommendations
          </h3>
          <ul className="space-y-2">
            {digest.top_recommendations.map((rec, i) => (
              <li key={i} className="flex gap-2 text-sm text-neutral-700">
                <span className="text-indigo-500 font-bold flex-shrink-0">{i + 1}.</span>
                {rec}
              </li>
            ))}
          </ul>
        </div>
      )}

      {digest.flagged_items && digest.flagged_items.length > 0 && (
        <div>
          <h3 className="text-xs uppercase tracking-wide text-neutral-400 font-medium mb-2">
            Flagged Items
          </h3>
          <div className="space-y-2">
            {digest.flagged_items.map((item, i) => (
              <div
                key={i}
                className="rounded-lg border border-red-100 bg-red-50 px-4 py-3"
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="text-sm font-medium text-red-800">
                    {item.description}
                  </span>
                  <span className="text-sm font-mono text-red-700 flex-shrink-0">
                    ₹{item.amount.toLocaleString("en-IN")}
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
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);

  const user = me.data?.user;
  const isAdmin = user?.role === "ADMIN";

  // L10: use generateDigest.data as fallback so the detail panel shows
  // the newly generated digest immediately (before refetch completes).
  const selected = selectedId
    ? ((digests.data ?? []).find((d) => d.id === selectedId) ?? generateDigest.data ?? null)
    : null;

  async function handleGenerate(start: string, end: string) {
    try {
      const digest = await generateDigest.mutateAsync({
        period_start: start,
        period_end: end,
      });
      setShowModal(false);
      setSelectedId(digest.id);
    } catch {
      // error is visible through mutation state
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
      <div className="w-72 flex-shrink-0 border-r bg-white flex flex-col">
        <div className="flex items-center justify-between px-4 py-4 border-b">
          <h1 className="text-sm font-semibold text-neutral-900">Digests</h1>
          {isAdmin && (
            <button
              onClick={() => setShowModal(true)}
              className="text-xs px-3 py-1.5 rounded-lg bg-indigo-600 text-white font-medium hover:bg-indigo-700"
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
              description={
                isAdmin
                  ? "Generate your first weekly digest."
                  : "No digests have been generated yet."
              }
            />
          ) : (
            <ul className="divide-y">
              {digests.data.map((d) => (
                <li key={d.id}>
                  <button
                    onClick={() => setSelectedId(d.id)}
                    className={`w-full text-left px-4 py-3 hover:bg-neutral-50 transition-colors ${
                      selectedId === d.id ? "bg-indigo-50" : ""
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs text-neutral-500">
                        {fmtDate(d.period_start)} – {fmtDate(d.period_end)}
                      </span>
                      {statusBadge(d.status)}
                    </div>
                    {d.headline ? (
                      <p className="text-sm text-neutral-800 line-clamp-2">
                        {d.headline}
                      </p>
                    ) : (
                      <p className="text-sm text-neutral-400 italic">
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
      <div className="flex-1 overflow-y-auto bg-neutral-50">
        {selected ? (
          <DigestDetail digest={selected} />
        ) : (
          <div className="h-full flex items-center justify-center">
            <EmptyState
              title="Select a digest"
              description="Choose a digest from the list to view details."
              icon={
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="w-10 h-10"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={1.5}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
              }
            />
          </div>
        )}
      </div>
    </div>
  );
}
