import type { ReactNode } from "react";

interface EmptyStateProps {
  title: string;
  description?: string;
  icon?: ReactNode;
}

export function EmptyState({ title, description, icon }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      {icon && <div className="mb-4 text-neutral-300">{icon}</div>}
      <h3 className="text-base font-medium text-neutral-700">{title}</h3>
      {description && (
        <p className="mt-1 text-sm text-neutral-400">{description}</p>
      )}
    </div>
  );
}
