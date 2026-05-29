import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium transition-colors",
  {
    variants: {
      variant: {
        default:        "bg-gray-100 text-gray-600 border-gray-200",
        ACTIVE:         "bg-emerald-100 text-emerald-800 border-emerald-200",
        FROZEN:         "bg-amber-100 text-amber-800 border-amber-200",
        CANCELLED:      "bg-gray-100 text-gray-600 border-gray-200",
        APPROVED:       "bg-emerald-100 text-emerald-800 border-emerald-200",
        FLAGGED:        "bg-orange-100 text-orange-800 border-orange-200",
        BLOCKED:        "bg-red-100 text-red-800 border-red-200",
        INITIATED:      "bg-blue-100 text-blue-800 border-blue-200",
        POLICY_CHECKED: "bg-purple-100 text-purple-800 border-purple-200",
        CLEARED:        "bg-sky-100 text-sky-800 border-sky-200",
        SETTLED:        "bg-slate-100 text-slate-700 border-slate-200",
        SUBMITTED:      "bg-blue-100 text-blue-800 border-blue-200",
        REJECTED:       "bg-red-100 text-red-800 border-red-200",
        PAID:           "bg-emerald-100 text-emerald-800 border-emerald-200",
        PENDING:        "bg-amber-100 text-amber-800 border-amber-200",
        COMPLETED:      "bg-emerald-100 text-emerald-800 border-emerald-200",
        FAILED:         "bg-red-100 text-red-800 border-red-200",
        NEEDS_REVIEW:   "bg-amber-100 text-amber-800 border-amber-200",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

export type BadgeVariant = NonNullable<VariantProps<typeof badgeVariants>["variant"]>;

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
