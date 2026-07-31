"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "../lib/auth";

export default function LoginPage() {
  const { login, user } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (user) router.replace("/dashboard");
  }, [router, user]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      await login(email, password);
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed. Check your credentials and try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={{ minHeight: "100vh", display: "grid", gridTemplateColumns: "minmax(320px, 1fr) minmax(420px, .8fr)" }}>
      <section className="desktop-only" style={{ padding: 64, display: "flex", flexDirection: "column", justifyContent: "space-between", background: "#14251e", color: "white" }}>
        <div style={{ fontWeight: 850, fontSize: 20 }}>Aegis</div>
        <div style={{ maxWidth: 600 }}>
          <div style={{ color: "#69d6ab", fontSize: 13, fontWeight: 800, letterSpacing: ".12em", textTransform: "uppercase" }}>Control Center</div>
          <h1 style={{ fontSize: "clamp(40px, 5vw, 72px)", lineHeight: 1, letterSpacing: "-.055em", margin: "18px 0 22px" }}>Policy in one place. Protection everywhere.</h1>
          <p style={{ color: "#b8c8c0", fontSize: 18, lineHeight: 1.6 }}>Manage API access, traffic policies, and token verification without exposing sensitive material.</p>
        </div>
        <div style={{ color: "#8aa097", fontSize: 13 }}>Aegis API Security & Management</div>
      </section>
      <section style={{ display: "grid", placeItems: "center", padding: 30 }}>
        <form onSubmit={submit} className="card" style={{ width: "min(430px, 100%)", padding: 34 }}>
          <div style={{ color: "#176b50", fontWeight: 800, fontSize: 13 }}>WELCOME BACK</div>
          <h2 style={{ fontSize: 29, margin: "8px 0" }}>Sign in to Aegis</h2>
          <p className="muted" style={{ margin: "0 0 26px" }}>Use your Control Plane account to continue.</p>
          <div style={{ display: "grid", gap: 18 }}>
            <label className="label">Email
              <input className="input" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
            </label>
            <label className="label">Password
              <input className="input" type="password" minLength={8} autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
            </label>
            {error && <div className="error" role="alert" style={{ background: "#fff1f0", padding: 11, borderRadius: 8 }}>{error}</div>}
            <button className="btn btn-primary" disabled={loading} style={{ width: "100%", padding: 11 }}>{loading ? "Signing in…" : "Sign in"}</button>
          </div>
          <p className="muted" style={{ fontSize: 12, lineHeight: 1.5, margin: "22px 0 0" }}>Your session is kept only in memory and is cleared when this tab reloads or you sign out.</p>
        </form>
      </section>
    </main>
  );
}
