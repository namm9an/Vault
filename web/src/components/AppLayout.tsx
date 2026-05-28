import type { ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useLogout, useMe } from "@/features/auth/hooks";

const NAV_LINKS = [
  { to: "/", label: "Dashboard", exact: true },
  { to: "/transactions", label: "Transactions" },
  { to: "/cards", label: "Cards" },
  { to: "/settings", label: "Settings" },
];

export function AppLayout({ children }: { children: ReactNode }) {
  const me = useMe();
  const logout = useLogout();
  const navigate = useNavigate();

  async function onLogout() {
    await logout.mutateAsync();
    navigate("/login");
  }

  const user = me.data?.user;
  const org = me.data?.org;

  return (
    <div className="min-h-screen bg-neutral-50">
      <nav className="border-b bg-white px-6 py-3 flex items-center justify-between sticky top-0 z-30">
        <div className="flex items-center gap-8">
          <div className="flex items-baseline gap-3">
            <span className="text-xl font-semibold">Vault</span>
            {org && <span className="text-sm text-neutral-400">{org.name}</span>}
          </div>
          <div className="flex items-center gap-1">
            {NAV_LINKS.map(({ to, label, exact }) => (
              <NavLink
                key={to}
                to={to}
                end={exact}
                className={({ isActive }) =>
                  `px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-neutral-100 text-neutral-900"
                      : "text-neutral-500 hover:text-neutral-900 hover:bg-neutral-50"
                  }`
                }
              >
                {label}
              </NavLink>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-4 text-sm">
          {user && (
            <>
              <span className="text-neutral-600">{user.full_name}</span>
              <span className="px-2 py-0.5 rounded-full bg-neutral-100 text-neutral-700 text-xs">
                {user.role}
              </span>
            </>
          )}
          <button
            onClick={onLogout}
            className="text-sm text-neutral-500 hover:text-neutral-900 hover:underline"
          >
            Sign out
          </button>
        </div>
      </nav>
      <main>{children}</main>
    </div>
  );
}
