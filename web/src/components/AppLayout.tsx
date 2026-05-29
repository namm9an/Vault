import { useRef, useEffect, useState, type ReactNode } from "react";
import { NavLink, useNavigate, useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { useLogout, useMe } from "@/features/auth/hooks";
import {
  useNotifications,
  useUnreadCount,
  useMarkRead,
  useMarkAllRead,
} from "@/features/notifications/hooks";

// ---------------------------------------------------------------------------
// SVG Icons (inline — no new icon library)
// ---------------------------------------------------------------------------

function IconDashboard() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l9-9 9 9M5 10v9a1 1 0 001 1h4v-5h4v5h4a1 1 0 001-1v-9" />
    </svg>
  );
}

function IconCards() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 10h18M7 15h.01M11 15h2M3 6h18a1 1 0 011 1v10a1 1 0 01-1 1H3a1 1 0 01-1-1V7a1 1 0 011-1z" />
    </svg>
  );
}

function IconTransactions() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
    </svg>
  );
}

function IconReimbursements() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 14l6-6m-5.5.5h.01m4.99 5h.01M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16l3.5-2 3.5 2 3.5-2 3.5 2z" />
    </svg>
  );
}

function IconDepartments() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
    </svg>
  );
}

function IconDigest() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
  );
}

function IconPolicies() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
    </svg>
  );
}

function IconSettings() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  );
}

function IconBell() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
    </svg>
  );
}

function IconSignOut() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Time-ago helper
// ---------------------------------------------------------------------------

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

// ---------------------------------------------------------------------------
// Notification Bell Dropdown
// ---------------------------------------------------------------------------

function NotificationBell() {
  const unread = useUnreadCount();
  const notifs = useNotifications();
  const markRead = useMarkRead();
  const markAllRead = useMarkAllRead();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const count = unread.data?.count ?? 0;

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="relative p-2 rounded-lg text-[#6e6a68] hover:text-[#0c0a08] hover:bg-white border border-transparent hover:border-[#d2cecb] transition-colors"
        aria-label="Notifications"
      >
        <IconBell />
        {count > 0 && (
          <span className="absolute -top-0.5 -right-0.5 w-4 h-4 rounded-full bg-solar text-[#0c0a08] text-[10px] font-bold flex items-center justify-center">
            {count > 9 ? "9+" : count}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-10 w-80 bg-white rounded-xl shadow-xl border border-[#d2cecb] z-50 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-[#d2cecb]">
            <span className="text-sm font-semibold text-[#0c0a08]">Notifications</span>
            {count > 0 && (
              <button
                onClick={() => markAllRead.mutate()}
                className="text-xs text-[#0c0a08] hover:underline"
              >
                Mark all read
              </button>
            )}
          </div>

          <div className="max-h-80 overflow-y-auto divide-y divide-[#d2cecb]">
            {!notifs.data?.length ? (
              <div className="px-4 py-8 text-center text-sm text-[#6e6a68]">
                You're all caught up
              </div>
            ) : (
              notifs.data.map((n) => (
                <button
                  key={n.id}
                  onClick={() => {
                    markRead.mutate(n.id);
                    if (n.link) {
                      setOpen(false);
                      navigate(n.link);
                    }
                  }}
                  className="w-full text-left px-4 py-3 hover:bg-[#f4f2f0] transition-colors flex gap-3 items-start"
                >
                  {!n.read_at && (
                    <span className="mt-1.5 w-2 h-2 rounded-full bg-solar flex-shrink-0" />
                  )}
                  <div className={!n.read_at ? "" : "pl-5"}>
                    <p className="text-sm font-medium text-[#0c0a08] truncate">
                      {n.title}
                    </p>
                    <p className="text-xs text-[#6e6a68] line-clamp-2 mt-0.5">
                      {n.body}
                    </p>
                    <p className="text-xs text-[#6e6a68] mt-1">
                      {timeAgo(n.created_at)}
                    </p>
                  </div>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// NavItem — icon-only with Framer Motion tooltip
// ---------------------------------------------------------------------------

interface NavItemProps {
  to: string;
  exact?: boolean;
  icon: ReactNode;
  label: string;
  expanded?: boolean;
}

function NavItem({ to, exact, icon, label, expanded = false }: NavItemProps) {
  const [hovered, setHovered] = useState(false);

  return (
    <div
      className="relative flex items-center mb-1"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <NavLink
        to={to}
        end={exact}
        className={({ isActive }) =>
          `relative h-10 rounded-lg flex items-center cursor-pointer transition-colors ${
            expanded ? "w-full px-3 gap-3" : "w-10 mx-auto justify-center"
          } ${
            isActive
              ? "text-solar bg-white/10"
              : "text-white/40 hover:text-white hover:bg-white/10"
          }`
        }
      >
        {({ isActive }) => (
          <>
            {isActive && (
              <motion.div
                layoutId="sidebar-active"
                className="absolute inset-0 bg-white/10 rounded-lg"
                transition={{ type: "spring", bounce: 0.2, duration: 0.4 }}
              />
            )}
            <span className="relative z-10 flex-shrink-0">{icon}</span>
            {expanded && (
              <span className="relative z-10 text-sm font-medium whitespace-nowrap overflow-hidden">
                {label}
              </span>
            )}
          </>
        )}
      </NavLink>
      {!expanded && (
        <AnimatePresence>
          {hovered && (
            <motion.div
              className="absolute left-14 bg-[#1a1919] text-white text-xs px-2 py-1 rounded whitespace-nowrap z-50 border border-white/10 pointer-events-none"
              initial={{ opacity: 0, x: -4 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -4 }}
              transition={{ duration: 0.12 }}
            >
              {label}
            </motion.div>
          )}
        </AnimatePresence>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page title from pathname
// ---------------------------------------------------------------------------

function usePageTitle(): string {
  const location = useLocation();
  const map: Record<string, string> = {
    "/dashboard":      "Dashboard",
    "/cards":          "Cards",
    "/transactions":   "Transactions",
    "/reimbursements": "Reimbursements",
    "/departments":    "Departments",
    "/digest":         "Digest",
    "/policies":       "Policies",
    "/settings":       "Settings",
  };
  return map[location.pathname] ?? "Vault";
}

// ---------------------------------------------------------------------------
// AppLayout
// ---------------------------------------------------------------------------

export function AppLayout({ children }: { children: ReactNode }) {
  const me = useMe();
  const logout = useLogout();
  const navigate = useNavigate();
  const pageTitle = usePageTitle();
  const location = useLocation();

  const [signingOut, setSigningOut] = useState(false);
  const [expanded, setExpanded] = useState(false);

  async function onLogout() {
    setSigningOut(true);
    try {
      await logout.mutateAsync();
    } finally {
      setSigningOut(false);
    }
    navigate("/login");
  }

  const user = me.data?.user;
  const org = me.data?.org;
  const isEmployee = user?.role === "EMPLOYEE";

  const initials = user?.full_name
    ? user.full_name
        .split(" ")
        .slice(0, 2)
        .map((w) => w[0])
        .join("")
        .toUpperCase()
    : "?";

  return (
    <div className="flex h-screen overflow-hidden bg-[#f4f2f0]">
      {/* Sidebar — collapsible */}
      <aside
        className="flex-shrink-0 h-screen bg-[#1a1919] flex flex-col py-3 transition-all duration-200 overflow-hidden"
        style={{ width: expanded ? 192 : 56 }}
      >
        {/* Logo — click to toggle expand */}
        <button
          onClick={() => setExpanded((v) => !v)}
          className="flex items-center gap-2 mb-6 px-3 flex-shrink-0 focus:outline-none"
        >
          <div className="w-9 h-9 bg-solar rounded-lg flex items-center justify-center flex-shrink-0">
            <span className="text-[#0c0a08] font-bold text-sm">V</span>
          </div>
          {expanded && (
            <span className="text-white font-semibold text-base whitespace-nowrap">vault</span>
          )}
        </button>

        {/* Navigation */}
        <nav className="flex-1 flex flex-col w-full px-2 overflow-y-auto">
          <NavItem to="/dashboard" exact icon={<IconDashboard />} label="Dashboard" expanded={expanded} />
          <NavItem to="/cards" icon={<IconCards />} label="Cards" expanded={expanded} />
          <NavItem to="/transactions" icon={<IconTransactions />} label="Transactions" expanded={expanded} />
          <NavItem to="/reimbursements" icon={<IconReimbursements />} label="Reimbursements" expanded={expanded} />
          {!isEmployee && (
            <>
              <NavItem to="/departments" icon={<IconDepartments />} label="Departments" expanded={expanded} />
              <NavItem to="/digest" icon={<IconDigest />} label="Digest" expanded={expanded} />
              <NavItem to="/policies" icon={<IconPolicies />} label="Policies" expanded={expanded} />
            </>
          )}

          {/* Divider */}
          <div className="my-2 border-t border-white/10 mx-2" />

          <NavItem to="/settings" icon={<IconSettings />} label="Settings" expanded={expanded} />
        </nav>

        {/* Bottom: user initials + sign out */}
        <div className="flex flex-col items-center gap-2 pb-1 w-full px-2">
          <div
            className={`h-10 rounded-lg bg-white/10 flex items-center cursor-default gap-2 ${expanded ? "w-full px-3" : "w-10 justify-center"}`}
            title={user?.full_name ?? ""}
          >
            <span className="text-white text-xs font-semibold flex-shrink-0">{initials}</span>
            {expanded && (
              <span className="text-white/60 text-xs truncate">{user?.full_name ?? ""}</span>
            )}
          </div>
          <button
            onClick={onLogout}
            disabled={signingOut}
            className={`h-10 rounded-lg flex items-center justify-center text-white/40 hover:text-white hover:bg-white/10 transition-colors gap-2 ${expanded ? "w-full px-3" : "w-10"}`}
            title="Sign out"
          >
            <IconSignOut />
            {expanded && <span className="text-sm">Sign out</span>}
          </button>
        </div>
      </aside>

      {/* Main content area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top bar */}
        <header className="h-[62px] flex-shrink-0 bg-[#f4f2f0] border-b border-[#d2cecb] flex items-center justify-between px-6">
          <span className="text-base font-semibold text-[#0c0a08]">
            {pageTitle}
          </span>
          <div className="flex items-center gap-3">
            <NotificationBell />
            {org?.name && (
              <span className="text-xs px-2 py-1 rounded border border-[#d2cecb] bg-[#f4f2f0] text-[#6e6a68]">
                {user?.role?.replace("_", " ") ?? ""}
              </span>
            )}
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto">
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.18, ease: "easeOut" }}
              className="h-full"
            >
              {children}
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}
