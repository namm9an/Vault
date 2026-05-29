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
      navigate("/dashboard");
    } catch {
      /* error rendered below */
    }
  }

  return (
    <div
      className="min-h-screen flex items-center justify-center bg-[#f4f2f0]"
      style={{
        backgroundImage: 'radial-gradient(circle, #d2cecb 1px, transparent 1px)',
        backgroundSize: '24px 24px',
      }}
    >
      <form onSubmit={onSubmit} className="w-full max-w-md mx-4 bg-white rounded-2xl border border-[#d2cecb] shadow-lg p-10 space-y-5">
        <div className="flex flex-col items-center mb-2">
          <div className="w-10 h-10 bg-solar rounded-lg flex items-center justify-center mb-6">
            <span className="text-[#0c0a08] font-bold text-sm">V</span>
          </div>
          <h1 className="text-2xl font-bold text-[#0c0a08] text-center">Sign in to Vault</h1>
          <p className="text-sm text-[#6e6a68] text-center mt-1">Corporate spend intelligence</p>
        </div>

        <label className="block">
          <span className="text-sm text-[#0c0a08] font-medium">Email</span>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full px-3 py-2.5 border border-[#d2cecb] rounded-[6px] focus:outline-none focus:ring-2 focus:ring-solar/50 focus:border-solar"
          />
        </label>

        <label className="block">
          <span className="text-sm text-[#0c0a08] font-medium">Password</span>
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full px-3 py-2.5 border border-[#d2cecb] rounded-[6px] focus:outline-none focus:ring-2 focus:ring-solar/50 focus:border-solar"
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
          className="w-full py-2.5 rounded-[6px] bg-solar text-[#0c0a08] font-semibold hover:bg-solar-light disabled:opacity-50 transition-colors"
        >
          {login.isPending ? "Signing in…" : "Sign in"}
        </button>

        <p className="text-sm text-[#6e6a68] text-center">
          No org yet?{" "}
          <Link to="/signup" className="text-[#0c0a08] underline">
            Create one
          </Link>
        </p>
      </form>
    </div>
  );
}
