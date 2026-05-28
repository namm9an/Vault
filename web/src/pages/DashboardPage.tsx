import { useMe } from "@/features/auth/hooks";

export function DashboardPage() {
  const me = useMe();

  if (me.isLoading) return <div className="p-8 text-neutral-500">Loading…</div>;
  if (me.isError || !me.data) return null;

  const { user, org } = me.data;
  return (
    <div className="p-8 max-w-3xl mx-auto">
      <h1 className="text-3xl font-semibold tracking-tight">Welcome, {user.full_name.split(" ")[0]}.</h1>
      <p className="mt-2 text-neutral-600">
        Phase 2 is live. Cards and team management are wired. Transactions and AI pipelines come next.
      </p>

      <div className="mt-8 grid grid-cols-2 gap-4">
        <div className="border rounded-lg p-4 bg-white">
          <div className="text-xs uppercase tracking-wide text-neutral-500">Organisation</div>
          <div className="mt-1 font-medium">{org.name}</div>
          <div className="text-sm text-neutral-500">{org.slug} · {org.base_currency}</div>
        </div>
        <div className="border rounded-lg p-4 bg-white">
          <div className="text-xs uppercase tracking-wide text-neutral-500">You</div>
          <div className="mt-1 font-medium">{user.email}</div>
          <div className="text-sm text-neutral-500">{user.role}</div>
        </div>
      </div>
    </div>
  );
}
