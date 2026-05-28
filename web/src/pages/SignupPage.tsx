import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useSignup } from "@/features/auth/hooks";

export function SignupPage() {
  const navigate = useNavigate();
  const signup = useSignup();
  const [orgName, setOrgName] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await signup.mutateAsync({
        org_name: orgName,
        full_name: fullName,
        email,
        password,
      });
      navigate("/");
    } catch {
      /* error rendered below */
    }
  }

  return (
    <div className="min-h-full flex items-center justify-center px-4">
      <form onSubmit={onSubmit} className="w-full max-w-sm bg-white rounded-xl shadow-sm border p-8 space-y-5">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Create your Vault</h1>
          <p className="text-sm text-neutral-500 mt-1">You'll be the admin of this organisation.</p>
        </div>

        <label className="block">
          <span className="text-sm text-neutral-700">Organisation name</span>
          <input
            required
            value={orgName}
            onChange={(e) => setOrgName(e.target.value)}
            className="mt-1 w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-vault-accent/30"
          />
        </label>

        <label className="block">
          <span className="text-sm text-neutral-700">Your name</span>
          <input
            required
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className="mt-1 w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-vault-accent/30"
          />
        </label>

        <label className="block">
          <span className="text-sm text-neutral-700">Work email</span>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-vault-accent/30"
          />
        </label>

        <label className="block">
          <span className="text-sm text-neutral-700">Password (min 8 chars)</span>
          <input
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-vault-accent/30"
          />
        </label>

        {signup.isError && (
          <p className="text-sm text-red-600">
            {(signup.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Signup failed"}
          </p>
        )}

        <button
          type="submit"
          disabled={signup.isPending}
          className="w-full py-2 rounded-md bg-vault-ink text-white font-medium disabled:opacity-50"
        >
          {signup.isPending ? "Creating…" : "Create organisation"}
        </button>

        <p className="text-sm text-neutral-500 text-center">
          Already have one? <Link to="/login" className="text-vault-accent hover:underline">Sign in</Link>
        </p>
      </form>
    </div>
  );
}
