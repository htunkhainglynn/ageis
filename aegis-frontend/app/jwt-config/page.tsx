"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiRequest } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { JwtConfig } from "../lib/types";
import { ProtectedPage } from "../ui/app-shell";
import { Badge, ConfirmDialog, EmptyState, Modal, PageHeader } from "../ui/primitives";

type ConfigList = { items: JwtConfig[]; total: number };

export default function JwtConfigPage() {
  const { accessToken } = useAuth();
  const [items, setItems] = useState<JwtConfig[]>([]);
  const [create, setCreate] = useState(false);
  const [editing, setEditing] = useState<JwtConfig | null>(null);
  const [activating, setActivating] = useState<JwtConfig | null>(null);
  const [disabling, setDisabling] = useState<JwtConfig | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    try {
      const data = await apiRequest<ConfigList>("/jwt-configs?skip=0&limit=100", {}, accessToken);
      setItems(data.items); setError("");
    } catch (err) { setError(err instanceof Error ? err.message : "Could not load JWT configurations."); }
    finally { setLoading(false); }
  }, [accessToken]);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function activate() {
    if (!accessToken || !activating) return;
    try {
      await apiRequest(`/jwt-configs/${activating.id}/activate`, { method: "POST" }, accessToken);
      setActivating(null); await load();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not activate the configuration."); setActivating(null); }
  }

  async function disable() {
    if (!accessToken || !disabling) return;
    try {
      await apiRequest(`/jwt-configs/${disabling.id}`, { method: "DELETE" }, accessToken);
      setDisabling(null); await load();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not disable the configuration."); setDisabling(null); }
  }

  return <ProtectedPage roles={["admin"]}>
    <PageHeader eyebrow="Token security" title="JWT configuration" description="Manage the system-wide signing and verification policy."
      action={<button className="btn btn-primary" onClick={() => setCreate(true)}>＋ New configuration</button>} />
    <div style={{ padding: 13, borderRadius: 10, background: "#fff7e8", color: "#74420b", fontSize: 14, marginBottom: 18 }}>
      Sensitive key material is encrypted by the Control Plane. This screen only displays the masked values returned by the API.
    </div>
    {error && <p className="error" role="alert">{error}</p>}
    <section className="card" style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 1050 }}>
        <thead><tr>{["Name", "Algorithm", "Signing key", "Public key", "Issuer", "Access TTL", "Status", ""].map((h) =>
          <th key={h} style={head}>{h}</th>)}</tr></thead>
        <tbody>{items.map((config) => <tr key={config.id}>
          <td style={cell}><strong>{config.name}</strong></td>
          <td style={cell}>{config.algorithm}</td>
          <td style={cell}><code>{config.signing_key_masked}</code></td>
          <td style={cell}><code>{config.public_key_masked ?? "Not used"}</code></td>
          <td style={cell}>{config.issuer ?? "—"}</td>
          <td style={cell}>{config.access_token_ttl_seconds}s</td>
          <td style={cell}><Badge value={config.status} /></td>
          <td style={{ ...cell, textAlign: "right" }}><div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <button className="btn btn-secondary" onClick={() => setEditing(config)}>Edit</button>
            {config.status !== "active" && <>
              <button className="btn btn-primary" onClick={() => setActivating(config)}>Activate</button>
              <button className="btn btn-danger" onClick={() => setDisabling(config)}>Disable</button>
            </>}
          </div></td>
        </tr>)}</tbody>
      </table>
      {!loading && items.length === 0 && <EmptyState>No JWT configurations created.</EmptyState>}
      {loading && <EmptyState>Loading JWT configurations…</EmptyState>}
    </section>
    {create && <CreateConfigModal accessToken={accessToken!} onClose={() => setCreate(false)}
      onCreated={() => { setCreate(false); void load(); }} />}
    {editing && <EditConfigModal config={editing} accessToken={accessToken!} onClose={() => setEditing(null)}
      onSaved={() => { setEditing(null); void load(); }} />}
    {activating && <ConfirmDialog title="Activate JWT configuration?"
      description={`Activating "${activating.name}" will deactivate the current active configuration. Newly issued and verified tokens will use this policy.`}
      confirmLabel="Activate configuration" onClose={() => setActivating(null)} onConfirm={activate} />}
    {disabling && <ConfirmDialog title="Disable JWT configuration?"
      description={`"${disabling.name}" will be disabled. Active configurations cannot be disabled until another one is activated.`}
      confirmLabel="Disable configuration" destructive onClose={() => setDisabling(null)} onConfirm={disable} />}
  </ProtectedPage>;
}

function EditConfigModal({ config, accessToken, onClose, onSaved }: {
  config: JwtConfig; accessToken: string; onClose(): void; onSaved(): void;
}) {
  const [issuer, setIssuer] = useState(config.issuer ?? "");
  const [audience, setAudience] = useState(config.audience ?? "");
  const [accessTtl, setAccessTtl] = useState(config.access_token_ttl_seconds);
  const [refreshTtl, setRefreshTtl] = useState(config.refresh_token_ttl_seconds);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true); setError("");
    try {
      await apiRequest(`/jwt-configs/${config.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          issuer: issuer || null, audience: audience || null,
          access_token_ttl_seconds: Number(accessTtl),
          refresh_token_ttl_seconds: Number(refreshTtl),
        }),
      }, accessToken);
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update the configuration.");
    } finally { setLoading(false); }
  }

  return <Modal title="Edit JWT configuration" description="Key material and algorithm cannot be changed after creation." onClose={onClose}>
    <form onSubmit={submit} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
      <label className="label">Issuer<input className="input" value={issuer} onChange={(e) => setIssuer(e.target.value)} /></label>
      <label className="label">Audience<input className="input" value={audience} onChange={(e) => setAudience(e.target.value)} /></label>
      <label className="label">Access token TTL<input className="input" type="number" min={1} value={accessTtl} onChange={(e) => setAccessTtl(Number(e.target.value))} /></label>
      <label className="label">Refresh token TTL<input className="input" type="number" min={1} value={refreshTtl} onChange={(e) => setRefreshTtl(Number(e.target.value))} /></label>
      {error && <div className="error" role="alert" style={{ gridColumn: "1 / -1" }}>{error}</div>}
      <div style={{ gridColumn: "1 / -1", display: "flex", justifyContent: "flex-end", gap: 10 }}>
        <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn btn-primary" disabled={loading}>{loading ? "Saving…" : "Save changes"}</button>
      </div>
    </form>
  </Modal>;
}

const head: React.CSSProperties = { textAlign: "left", padding: "14px 16px", fontSize: 12, color: "#69736d", borderBottom: "1px solid var(--border)" };
const cell: React.CSSProperties = { padding: "14px 16px", borderBottom: "1px solid #edf0ee", fontSize: 14 };

function CreateConfigModal({ accessToken, onClose, onCreated }: {
  accessToken: string; onClose(): void; onCreated(): void;
}) {
  const [form, setForm] = useState({
    name: "", algorithm: "HS256", signing_key: "", public_key: "", issuer: "", audience: "",
    access_token_ttl_seconds: 900, refresh_token_ttl_seconds: 604800,
  });
  const [error, setError] = useState(""); const [loading, setLoading] = useState(false);
  const update = (field: string, value: string | number) => setForm((f) => ({ ...f, [field]: value }));
  async function submit(event: FormEvent) {
    event.preventDefault(); setLoading(true); setError("");
    try {
      await apiRequest("/jwt-configs", { method: "POST", body: JSON.stringify({
        ...form, public_key: form.algorithm === "HS256" ? null : form.public_key || null,
        issuer: form.issuer || null, audience: form.audience || null,
        access_token_ttl_seconds: Number(form.access_token_ttl_seconds),
        refresh_token_ttl_seconds: Number(form.refresh_token_ttl_seconds),
      }) }, accessToken);
      onCreated();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not create the configuration."); }
    finally { setLoading(false); }
  }
  const asymmetric = form.algorithm !== "HS256";
  return <Modal title="Create JWT configuration" description="Creating a configuration does not activate it." onClose={onClose}>
    <form onSubmit={submit} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
      <label className="label">Name<input className="input" required value={form.name} onChange={(e) => update("name", e.target.value)} /></label>
      <label className="label">Algorithm<select className="input" value={form.algorithm} onChange={(e) => update("algorithm", e.target.value)}>
        <option>HS256</option><option>RS256</option><option>ES256</option>
      </select></label>
      <label className="label" style={{ gridColumn: "1 / -1" }}>Signing key<textarea className="input" rows={4} required value={form.signing_key} onChange={(e) => update("signing_key", e.target.value)} /></label>
      {asymmetric && <label className="label" style={{ gridColumn: "1 / -1" }}>Public key<textarea className="input" rows={4} required value={form.public_key} onChange={(e) => update("public_key", e.target.value)} /></label>}
      <label className="label">Issuer<input className="input" value={form.issuer} onChange={(e) => update("issuer", e.target.value)} /></label>
      <label className="label">Audience<input className="input" value={form.audience} onChange={(e) => update("audience", e.target.value)} /></label>
      <label className="label">Access token TTL (seconds)<input className="input" type="number" min={1} required value={form.access_token_ttl_seconds} onChange={(e) => update("access_token_ttl_seconds", e.target.value)} /></label>
      <label className="label">Refresh token TTL (seconds)<input className="input" type="number" min={1} required value={form.refresh_token_ttl_seconds} onChange={(e) => update("refresh_token_ttl_seconds", e.target.value)} /></label>
      {error && <div className="error" role="alert" style={{ gridColumn: "1 / -1" }}>{error}</div>}
      <div style={{ gridColumn: "1 / -1", display: "flex", justifyContent: "flex-end", gap: 10 }}>
        <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn btn-primary" disabled={loading}>{loading ? "Creating…" : "Create configuration"}</button>
      </div>
    </form>
  </Modal>;
}
