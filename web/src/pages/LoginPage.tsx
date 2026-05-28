import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useLogin } from "@/features/auth/hooks";

export function LoginPage() {
  const navigate = useNavigate();
  const login = useLogin();
  const [email, setEmail] = useState("admin@acme.com");
  const [password, setPassword] = useState("vault-demo-pass");

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await login.mutateAsync({ email, password });
      navigate("/");
    } catch {
      /* error rendered below */
    }
  }

  return (
    <div className="min-h-full flex items-center justify-center px-4">
      <form onSubmit={onSubmit} className="w-full max-w-sm bg-white rounded-xl shadow-sm border p-8 space-y-5">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Vault</h1>
          <p className="text-sm text-neutral-500 mt-1">Sign in to your organisation</p>
        </div>

        <label className="block">
          <span className="text-sm text-neutral-700">Email</span>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-vault-accent/30"
          />
        </label>

        <label className="block">
          <span className="text-sm text-neutral-700">Password</span>
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-vault-accent/30"
          />
        </label>

        {login.isError && (
          <p className="text-sm text-red-600">
            {(login.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Login failed"}
          </p>
        )}

        <button
          type="submit"
          disabled={login.isPending}
          className="w-full py-2 rounded-md bg-vault-ink text-white font-medium disabled:opacity-50"
        >
          {login.isPending ? "Signing in…" : "Sign in"}
        </button>

        <p className="text-sm text-neutral-500 text-center">
          No org yet? <Link to="/signup" className="text-vault-accent hover:underline">Create one</Link>
        </p>
      </form>
    </div>
  );
}
