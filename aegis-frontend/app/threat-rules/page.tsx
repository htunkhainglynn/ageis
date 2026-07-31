"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiRequest } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { ThreatRule } from "../lib/types";
import { ProtectedPage } from "../ui/app-shell";
import { Badge, ConfirmDialog, EmptyState, Modal, PageHeader } from "../ui/primitives";

type RuleList = { items: ThreatRule[]; total: number };

export default function ThreatRulesPage() {
  const { accessToken } = useAuth();
  const [items, setItems] = useState<ThreatRule[]>([]);
  const [editing, setEditing] = useState<ThreatRule | "new" | null>(null);
  const [disabling, setDisabling] = useState<ThreatRule | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    try {
      const data = await apiRequest<RuleList>("/threat-rules?skip=0&limit=100", {}, accessToken);
      setItems(data.items); setError("");
    } catch (err) { setError(err instanceof Error ? err.message : "Could not load threat rules."); }
    finally { setLoading(false); }
  }, [accessToken]);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function disable() {
    if (!accessToken || !disabling) return;
    try {
      await apiRequest(`/threat-rules/${disabling.id}`, { method: "DELETE" }, accessToken);
      setDisabling(null); await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not disable the rule.");
      setDisabling(null);
    }
  }

  return <ProtectedPage roles={["admin"]}>
    <PageHeader eyebrow="Request inspection" title="Threat rules"
      description="Reject request targets matching safe, RE2-compatible patterns."
      action={<button className="btn btn-primary" onClick={() => setEditing("new")}>＋ Create rule</button>} />
    {error && <p className="error" role="alert">{error}</p>}
    <section className="card" style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 800 }}>
        <thead><tr>{["Name", "Pattern", "Severity", "Status", ""].map((heading) =>
          <th key={heading} style={head}>{heading}</th>)}</tr></thead>
        <tbody>{items.map((rule) => <tr key={rule.id}>
          <td style={cell}><strong>{rule.name}</strong></td>
          <td style={{ ...cell, maxWidth: 420 }}><code style={{ overflowWrap: "anywhere" }}>{rule.pattern}</code></td>
          <td style={{ ...cell, textTransform: "capitalize" }}>{rule.severity}</td>
          <td style={cell}><Badge value={rule.status} /></td>
          <td style={{ ...cell, textAlign: "right" }}><div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
            <button className="btn btn-secondary" onClick={() => setEditing(rule)}>Edit</button>
            {rule.status === "active" && <button className="btn btn-danger" onClick={() => setDisabling(rule)}>Disable</button>}
          </div></td>
        </tr>)}</tbody>
      </table>
      {loading && <EmptyState>Loading threat rules…</EmptyState>}
      {!loading && items.length === 0 && <EmptyState>No threat rules configured.</EmptyState>}
    </section>
    {editing && <RuleModal initial={editing === "new" ? undefined : editing} accessToken={accessToken!}
      onClose={() => setEditing(null)} onSaved={() => { setEditing(null); void load(); }} />}
    {disabling && <ConfirmDialog title="Disable threat rule?"
      description={`"${disabling.name}" will stop blocking matching requests after policy caches refresh.`}
      confirmLabel="Disable rule" destructive onClose={() => setDisabling(null)} onConfirm={disable} />}
  </ProtectedPage>;
}

const head: React.CSSProperties = { textAlign: "left", padding: "14px 16px", fontSize: 12, color: "#69736d", borderBottom: "1px solid var(--border)" };
const cell: React.CSSProperties = { padding: "14px 16px", borderBottom: "1px solid #edf0ee", fontSize: 14 };

function RuleModal({ initial, accessToken, onClose, onSaved }: {
  initial?: ThreatRule; accessToken: string; onClose(): void; onSaved(): void;
}) {
  const [form, setForm] = useState({
    name: initial?.name ?? "", pattern: initial?.pattern ?? "",
    severity: initial?.severity ?? "medium", status: initial?.status ?? "active",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setLoading(true); setError("");
    try {
      await apiRequest(initial ? `/threat-rules/${initial.id}` : "/threat-rules", {
        method: initial ? "PATCH" : "POST", body: JSON.stringify(form),
      }, accessToken);
      onSaved();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not save the rule."); }
    finally { setLoading(false); }
  }
  return <Modal title={initial ? "Edit threat rule" : "Create threat rule"}
    description="Patterns inspect the HTTP method plus path and query string. Go RE2 syntax prevents catastrophic backtracking."
    onClose={onClose}>
    <form onSubmit={submit} style={{ display: "grid", gap: 16 }}>
      <label className="label">Name<input className="input" required maxLength={255} value={form.name}
        onChange={(event) => setForm({ ...form, name: event.target.value })} /></label>
      <label className="label">RE2 pattern<textarea className="input" required maxLength={1000} rows={3}
        value={form.pattern} onChange={(event) => setForm({ ...form, pattern: event.target.value })}
        placeholder={"(?i)(\\.\\./|%2e%2e)"} /></label>
      <label className="label">Severity<select className="input" value={form.severity}
        onChange={(event) => setForm({ ...form, severity: event.target.value as ThreatRule["severity"] })}>
        <option value="low">Low</option><option value="medium">Medium</option>
        <option value="high">High</option><option value="critical">Critical</option>
      </select></label>
      <label className="label">Status<select className="input" value={form.status}
        onChange={(event) => setForm({ ...form, status: event.target.value as ThreatRule["status"] })}>
        <option value="active">Active</option><option value="disabled">Disabled</option>
      </select></label>
      {error && <div className="error" role="alert">{error}</div>}
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
        <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn btn-primary" disabled={loading}>{loading ? "Saving…" : "Save rule"}</button>
      </div>
    </form>
  </Modal>;
}
