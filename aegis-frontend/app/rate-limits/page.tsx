"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiRequest } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { RateLimitRule } from "../lib/types";
import { ProtectedPage } from "../ui/app-shell";
import { Badge, ConfirmDialog, EmptyState, Modal, PageHeader } from "../ui/primitives";

type RuleList = { items: RateLimitRule[]; total: number };

export default function RateLimitsPage() {
  const { accessToken } = useAuth();
  const [items, setItems] = useState<RateLimitRule[]>([]);
  const [editing, setEditing] = useState<RateLimitRule | "new" | null>(null);
  const [disabling, setDisabling] = useState<RateLimitRule | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    try {
      const data = await apiRequest<RuleList>("/rate-limit-rules?skip=0&limit=100", {}, accessToken);
      setItems(data.items); setError("");
    } catch (err) { setError(err instanceof Error ? err.message : "Could not load rules."); }
    finally { setLoading(false); }
  }, [accessToken]);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function disable() {
    if (!accessToken || !disabling) return;
    try {
      await apiRequest(`/rate-limit-rules/${disabling.id}`, { method: "DELETE" }, accessToken);
      setDisabling(null); await load();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not disable the rule."); setDisabling(null); }
  }

  return <ProtectedPage roles={["admin"]}>
    <PageHeader eyebrow="Traffic policy" title="Rate limits" description="Define how much traffic each scope can accept."
      action={<button className="btn btn-primary" onClick={() => setEditing("new")}>＋ Create rule</button>} />
    {error && <p className="error" role="alert">{error}</p>}
    <section className="card" style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 900 }}>
        <thead><tr>{["Scope", "Value", "Algorithm", "Limit", "Window", "Status", ""].map((h) =>
          <th key={h} style={head}>{h}</th>)}</tr></thead>
        <tbody>{items.map((rule) => <tr key={rule.id}>
          <td style={cell}><strong>{rule.scope_type.replace("_", " ")}</strong></td>
          <td style={cell}>{rule.scope_value ?? "All traffic"}</td>
          <td style={cell}>{rule.algorithm.replace("_", " ")}</td>
          <td style={cell}>{rule.limit_count.toLocaleString()}</td>
          <td style={cell}>{rule.window_seconds}s</td>
          <td style={cell}><Badge value={rule.status} /></td>
          <td style={{ ...cell, textAlign: "right" }}><div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <button className="btn btn-secondary" onClick={() => setEditing(rule)}>Edit</button>
            {rule.status === "active" && <button className="btn btn-danger" onClick={() => setDisabling(rule)}>Disable</button>}
          </div></td>
        </tr>)}</tbody>
      </table>
      {!loading && items.length === 0 && <EmptyState>No rate limit rules configured.</EmptyState>}
      {loading && <EmptyState>Loading rate limit rules…</EmptyState>}
    </section>
    {editing && <RuleModal initial={editing === "new" ? undefined : editing} accessToken={accessToken!}
      onClose={() => setEditing(null)} onSaved={() => { setEditing(null); void load(); }} />}
    {disabling && <ConfirmDialog title="Disable rate limit rule?" description={`"${disabling.name}" will no longer be distributed for enforcement.`}
      confirmLabel="Disable rule" destructive onClose={() => setDisabling(null)} onConfirm={disable} />}
  </ProtectedPage>;
}

const head: React.CSSProperties = { textAlign: "left", padding: "14px 16px", fontSize: 12, color: "#69736d", borderBottom: "1px solid var(--border)" };
const cell: React.CSSProperties = { padding: "14px 16px", borderBottom: "1px solid #edf0ee", fontSize: 14 };

function RuleModal({ initial, accessToken, onClose, onSaved }: {
  initial?: RateLimitRule; accessToken: string; onClose(): void; onSaved(): void;
}) {
  const [form, setForm] = useState({
    name: initial?.name ?? "", scope_type: initial?.scope_type ?? "global",
    scope_value: initial?.scope_value ?? "", algorithm: initial?.algorithm ?? "token_bucket",
    limit_count: initial?.limit_count ?? 100, window_seconds: initial?.window_seconds ?? 60,
    burst_allowance: initial?.burst_allowance?.toString() ?? "", status: initial?.status ?? "active",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const update = (field: string, value: string | number) => setForm((f) => ({ ...f, [field]: value }));

  async function submit(event: FormEvent) {
    event.preventDefault(); setLoading(true); setError("");
    const payload = {
      ...form,
      scope_value: form.scope_type === "global" ? null : form.scope_value,
      limit_count: Number(form.limit_count), window_seconds: Number(form.window_seconds),
      burst_allowance: form.burst_allowance ? Number(form.burst_allowance) : null,
    };
    try {
      await apiRequest(initial ? `/rate-limit-rules/${initial.id}` : "/rate-limit-rules", {
        method: initial ? "PATCH" : "POST", body: JSON.stringify(payload),
      }, accessToken);
      onSaved();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Could not save the rule.";
      setError(message.toLowerCase().includes("active") || message.toLowerCase().includes("duplicate")
        ? `A rule is already active for this scope. Disable or edit the existing rule first. ${message}` : message);
    } finally { setLoading(false); }
  }

  return <Modal title={initial ? "Edit rate limit rule" : "Create rate limit rule"} onClose={onClose}>
    <form onSubmit={submit} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
      <label className="label" style={{ gridColumn: "1 / -1" }}>Name<input className="input" required value={form.name} onChange={(e) => update("name", e.target.value)} /></label>
      <label className="label">Scope type<select className="input" value={form.scope_type} onChange={(e) => update("scope_type", e.target.value)}>
        <option value="global">Global</option><option value="api_key">API key</option><option value="route">Route</option>
      </select></label>
      <label className="label">Scope value<input className="input" disabled={form.scope_type === "global"} required={form.scope_type !== "global"}
        value={form.scope_value} onChange={(e) => update("scope_value", e.target.value)} placeholder={form.scope_type === "route" ? "/orders/*" : "Key ID"} /></label>
      <label className="label">Algorithm<select className="input" value={form.algorithm} onChange={(e) => update("algorithm", e.target.value)}>
        <option value="token_bucket">Token bucket</option><option value="sliding_window">Sliding window</option><option value="fixed_window">Fixed window</option>
      </select></label>
      <label className="label">Status<select className="input" value={form.status} onChange={(e) => update("status", e.target.value)}>
        <option value="active">Active</option><option value="disabled">Disabled</option>
      </select></label>
      <label className="label">Request limit<input className="input" type="number" min={1} required value={form.limit_count} onChange={(e) => update("limit_count", e.target.value)} /></label>
      <label className="label">Window (seconds)<input className="input" type="number" min={1} required value={form.window_seconds} onChange={(e) => update("window_seconds", e.target.value)} /></label>
      <label className="label" style={{ gridColumn: "1 / -1" }}>Burst allowance (optional)<input className="input" type="number" min={1} value={form.burst_allowance} onChange={(e) => update("burst_allowance", e.target.value)} /></label>
      {error && <div className="error" role="alert" style={{ gridColumn: "1 / -1", background: "#fff1f0", padding: 11, borderRadius: 8 }}>{error}</div>}
      <div style={{ gridColumn: "1 / -1", display: "flex", justifyContent: "flex-end", gap: 10 }}>
        <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn btn-primary" disabled={loading}>{loading ? "Saving…" : "Save rule"}</button>
      </div>
    </form>
  </Modal>;
}
