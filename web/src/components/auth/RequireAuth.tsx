import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { getAuth } from "@/lib/auth";

export function RequireAuth({ children }: { children: ReactNode }) {
  if (!getAuth()) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
