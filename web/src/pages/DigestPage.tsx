import { useState } from "react";
import { useMe } from "@/features/auth/hooks";
import { useDeleteDigest, useDigests, useGenerateDigest } from "@/features/digest/hooks";
import { EmptyState } from "@/components/EmptyState";
import { Badge, type BadgeVariant } from "@/components/ui/badge";
import type { Digest, DigestStatus } from "@/types/api";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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
        <h2 className="text-base font-semibold text-[#0c0a08] mb-4">
          Generate Weekly Digest
        </h2>
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-[#6e6a68] mb-1">
              Period start
            </label>
            <input
              type="date"
              value={start}
              onChange={(e) => setStart(e.target.value)}
              className="w-full border border-[#d2cecb] rounded-[6px] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-solar/50 focus:border-solar"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-[#6e6a68] mb-1">
              Period end
            </label>
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
// Digest Detail Panel
// ---------------------------------------------------------------------------

function DigestDetail({ digest, isAdmin, onDelete, deleting }: {
  digest: Digest;
  isAdmin: boolean;
  onDelete: () => void;
  deleting: boolean;
}) {
  return (
    <div className="p-6 space-y-6">
      <div>
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-2">
            {statusBadge(digest.status)}
            <span className="text-xs text-[#6e6a68]">
              {fmtDate(digest.period_start)} – {fmtDate(digest.period_end)}
            </span>
          </div>
          {isAdmin && (
            <button
              onClick={onDelete}
              disabled={deleting}
              className="px-3 py-1.5 text-xs font-medium rounded-[6px] border border-red-200 text-red-600 hover:bg-red-50 disabled:opacity-50"
            >
              {deleting ? "Deleting…" : "Delete"}
            </button>
          )}
        </div>
        {digest.headline ? (
          <h2 className="text-lg font-semibold text-[#0c0a08] mt-2">
            {digest.headline}
          </h2>
        ) : digest.status === "FAILED" ? (
          <p className="text-sm text-red-600 mt-2">
            Digest generation failed. Try regenerating.
          </p>
        ) : (
          <p className="text-sm text-[#6e6a68] mt-2">No headline available.</p>
        )}
      </div>

      {digest.body && (
        <div>
          <h3 className="text-xs uppercase tracking-wide text-[#6e6a68] font-medium mb-2">
            Summary
          </h3>
          <p className="text-sm text-[#0c0a08] leading-relaxed whitespace-pre-line">
            {digest.body}
          </p>
        </div>
      )}

      {digest.top_recommendations && digest.top_recommendations.length > 0 && (
        <div>
          <h3 className="text-xs uppercase tracking-wide text-[#6e6a68] font-medium mb-2">
            Recommendations
          </h3>
          <ul className="space-y-2">
            {digest.top_recommendations.map((rec, i) => (
              <li key={i} className="flex gap-2 text-sm text-[#0c0a08]">
                <span className="text-solar font-bold flex-shrink-0">{i + 1}.</span>
                {rec}
              </li>
            ))}
          </ul>
        </div>
      )}

      {digest.flagged_items && digest.flagged_items.length > 0 && (
        <div>
          <h3 className="text-xs uppercase tracking-wide text-[#6e6a68] font-medium mb-2">
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
  const deleteDigest = useDeleteDigest();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);

  const user = me.data?.user;
  const isAdmin = user?.role === "ADMIN";

  // L10: use generateDigest.data as fallback so the detail panel shows
  // the newly generated digest immediately (before refetch completes).
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
              description={
                isAdmin
                  ? "Generate your first weekly digest."
                  : "No digests have been generated yet."
              }
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
                      <p className="text-sm text-[#0c0a08] line-clamp-2">
                        {d.headline}
                      </p>
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
