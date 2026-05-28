import { createBrowserRouter } from "react-router-dom";
import { RequireAuth } from "@/components/auth/RequireAuth";
import { AppLayout } from "@/components/AppLayout";
import { LoginPage } from "@/pages/LoginPage";
import { SignupPage } from "@/pages/SignupPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { CardsPage } from "@/pages/CardsPage";
import { DepartmentsPage } from "@/pages/DepartmentsPage";
import { PoliciesPage } from "@/pages/PoliciesPage";
import { ReimbursementsPage } from "@/pages/ReimbursementsPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { TransactionsPage } from "@/pages/TransactionsPage";

function ProtectedLayout({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth>
      <AppLayout>{children}</AppLayout>
    </RequireAuth>
  );
}

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/signup", element: <SignupPage /> },
  {
    path: "/",
    element: <ProtectedLayout><DashboardPage /></ProtectedLayout>,
  },
  {
    path: "/transactions",
    element: <ProtectedLayout><TransactionsPage /></ProtectedLayout>,
  },
  {
    path: "/cards",
    element: <ProtectedLayout><CardsPage /></ProtectedLayout>,
  },
  {
    path: "/policies",
    element: <ProtectedLayout><PoliciesPage /></ProtectedLayout>,
  },
  {
    path: "/settings",
    element: <ProtectedLayout><SettingsPage /></ProtectedLayout>,
  },
  {
    path: "/reimbursements",
    element: <ProtectedLayout><ReimbursementsPage /></ProtectedLayout>,
  },
  {
    path: "/departments",
    element: <ProtectedLayout><DepartmentsPage /></ProtectedLayout>,
  },
]);
