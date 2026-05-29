type Status =
  | "active"
  | "inactive"
  | "pending"
  | "flagged"
  | "approved"
  | "declined"
  | "completed"
  | "cancelled";

const STATUS_MAP: Record<
  Status,
  { label: string; className: string }
> = {
  active:    { label: "Active",    className: "bg-emerald-100 text-emerald-800 border-emerald-200" },
  inactive:  { label: "Inactive",  className: "bg-gray-100 text-gray-600 border-gray-200" },
  pending:   { label: "Pending",   className: "bg-amber-100 text-amber-800 border-amber-200" },
  flagged:   { label: "Flagged",   className: "bg-orange-100 text-orange-800 border-orange-200" },
  approved:  { label: "Approved",  className: "bg-emerald-100 text-emerald-800 border-emerald-200" },
  declined:  { label: "Declined",  className: "bg-red-100 text-red-800 border-red-200" },
  completed: { label: "Completed", className: "bg-emerald-100 text-emerald-800 border-emerald-200" },
  cancelled: { label: "Cancelled", className: "bg-gray-100 text-gray-600 border-gray-200" },
};

type StatusBadgeProps = {
  status: Status;
  className?: string;
};

export function StatusBadge({ status, className = "" }: StatusBadgeProps) {
  const config = STATUS_MAP[status] ?? { label: status, className: "bg-gray-100 text-gray-600 border-gray-200" };
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${config.className} ${className}`}
    >
      {config.label}
    </span>
  );
}
