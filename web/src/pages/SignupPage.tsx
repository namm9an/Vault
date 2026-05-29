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
          <h1 className="text-2xl font-bold text-[#0c0a08] text-center">Create your Vault</h1>
          <p className="text-sm text-[#6e6a68] text-center mt-1">You'll be the admin of this organisation.</p>
        </div>

        <label className="block">
          <span className="text-sm text-[#0c0a08] font-medium">Organisation name</span>
          <input
            required
            value={orgName}
            onChange={(e) => setOrgName(e.target.value)}
            className="mt-1 w-full px-3 py-2.5 border border-[#d2cecb] rounded-[6px] focus:outline-none focus:ring-2 focus:ring-solar/50 focus:border-solar"
          />
        </label>

        <label className="block">
          <span className="text-sm text-[#0c0a08] font-medium">Your name</span>
          <input
            required
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className="mt-1 w-full px-3 py-2.5 border border-[#d2cecb] rounded-[6px] focus:outline-none focus:ring-2 focus:ring-solar/50 focus:border-solar"
          />
        </label>

        <label className="block">
          <span className="text-sm text-[#0c0a08] font-medium">Work email</span>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full px-3 py-2.5 border border-[#d2cecb] rounded-[6px] focus:outline-none focus:ring-2 focus:ring-solar/50 focus:border-solar"
          />
        </label>

        <label className="block">
          <span className="text-sm text-[#0c0a08] font-medium">Password (min 8 chars)</span>
          <input
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full px-3 py-2.5 border border-[#d2cecb] rounded-[6px] focus:outline-none focus:ring-2 focus:ring-solar/50 focus:border-solar"
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
          className="w-full py-2.5 rounded-[6px] bg-solar text-[#0c0a08] font-semibold hover:bg-solar-light disabled:opacity-50 transition-colors"
        >
          {signup.isPending ? "Creating…" : "Create organisation"}
        </button>

        <p className="text-sm text-[#6e6a68] text-center">
          Already have one?{" "}
          <Link to="/login" className="text-[#0c0a08] underline">
            Sign in
          </Link>
        </p>
      </form>
    </div>
  );
}
