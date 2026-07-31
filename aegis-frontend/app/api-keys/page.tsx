"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiRequest } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { ApiKeyItem } from "../lib/types";
import { ProtectedPage } from "../ui/app-shell";
import { Badge, ConfirmDialog, EmptyState, Modal, PageHeader } from "../ui/primitives";

type KeyList = { items: ApiKeyItem[]; total: number };
type CreatedKey = ApiKeyItem & { api_key: string };

export default function ApiKeysPage() {
  const { accessToken } = useAuth();
  const [items, setItems] = useState<ApiKeyItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [created, setCreated] = useState<CreatedKey | null>(null);
  const [editing, setEditing] = useState<ApiKeyItem | null>(null);
  const [revoke, setRevoke] = useState<ApiKeyItem | null>(null);

  const load = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    setError("");
    try {
      const data = await apiRequest<KeyList>("/api-keys?skip=0&limit=100", {}, accessToken);
      setItems(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load API keys.");
    } finally {
      setLoading(false);
    }
  }, [accessToken]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function revokeKey() {
    if (!accessToken || !revoke) return;
    try {
      await apiRequest(`/api-keys/${revoke.id}`, { method: "DELETE" }, accessToken);
      setRevoke(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not revoke the key.");
      setRevoke(null);
    }
  }

  return (
    <ProtectedPage roles={["admin", "api_consumer"]}>
      <PageHeader eyebrow="Access" title="API keys" description="Issue and revoke credentials used to call protected APIs."
        action={<button className="btn btn-primary" onClick={() => setShowCreate(true)}>＋ Create key</button>} />
      {error && <p className="error" role="alert">{error}</p>}
      <section className="card" style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 720 }}>
          <thead><tr>{["Name", "Key prefix", "Status", "Created", ""].map((h) =>
            <th key={h} style={{ textAlign: "left", padding: "14px 18px", fontSize: 12, color: "#69736d", borderBottom: "1px solid var(--border)" }}>{h}</th>)}</tr></thead>
          <tbody>
            {items.map((key) => <tr key={key.id}>
              <td style={cell}><strong>{key.name}</strong></td>
              <td style={cell}><code style={{ background: "#eef1ef", padding: "5px 7px", borderRadius: 6 }}>{key.key_prefix}</code></td>
              <td style={cell}><Badge value={key.status} /></td>
              <td style={cell}>{new Date(key.created_at).toLocaleDateString()}</td>
              <td style={{ ...cell, textAlign: "right" }}><div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
                <button className="btn btn-secondary" onClick={() => setEditing(key)}>Edit</button>
                {key.status === "active" && <button className="btn btn-danger" onClick={() => setRevoke(key)}>Revoke</button>}
              </div></td>
            </tr>)}
          </tbody>
        </table>
        {!loading && items.length === 0 && <EmptyState>No API keys yet. Create one when you are ready to connect a client.</EmptyState>}
        {loading && <EmptyState>Loading API keys…</EmptyState>}
      </section>
      {showCreate && <CreateKeyModal accessToken={accessToken!} onClose={() => setShowCreate(false)}
        onCreated={(key) => { setShowCreate(false); setCreated(key); void load(); }} />}
      {editing && <EditKeyModal keyItem={editing} accessToken={accessToken!} onClose={() => setEditing(null)}
        onSaved={() => { setEditing(null); void load(); }} />}
      {created && <Modal title="Save your API key now" description="This is the only time Aegis will show the full key. Copy it and store it in a secure secret manager." onClose={() => setCreated(null)}>
        <div style={{ display: "flex", gap: 10, alignItems: "center", padding: 14, background: "#f3f5f4", borderRadius: 9 }}>
          <code style={{ overflowWrap: "anywhere", flex: 1 }}>{created.api_key}</code>
          <button className="btn btn-secondary" onClick={() => navigator.clipboard.writeText(created.api_key)}>Copy</button>
        </div>
        <div style={{ marginTop: 18, padding: 13, borderRadius: 9, color: "#8a4b08", background: "#fff7e8", fontSize: 14 }}>Closing this dialog permanently hides the raw key. Aegis stores only its secure hash.</div>
      </Modal>}
      {revoke && <ConfirmDialog title="Revoke API key?" description={`"${revoke.name}" will stop working immediately. This action cannot be undone.`}
        confirmLabel="Revoke key" destructive onClose={() => setRevoke(null)} onConfirm={revokeKey} />}
    </ProtectedPage>
  );
}

function EditKeyModal({ keyItem, accessToken, onClose, onSaved }: {
  keyItem: ApiKeyItem; accessToken: string; onClose(): void; onSaved(): void;
}) {
  const [name, setName] = useState(keyItem.name);
  const [scopes, setScopes] = useState(keyItem.scopes.join(", "));
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      await apiRequest(`/api-keys/${keyItem.id}`, {
        method: "PATCH",
        body: JSON.stringify({ name, scopes: scopes.split(",").map((value) => value.trim()).filter(Boolean) }),
      }, accessToken);
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update the key.");
    } finally {
      setLoading(false);
    }
  }

  return <Modal title="Edit API key" description="Only metadata can be changed; the secret is never returned." onClose={onClose}>
    <form onSubmit={submit} style={{ display: "grid", gap: 18 }}>
      <label className="label">Key name<input className="input" required value={name} onChange={(e) => setName(e.target.value)} /></label>
      <label className="label">Scopes<input className="input" value={scopes} onChange={(e) => setScopes(e.target.value)} /></label>
      {error && <div className="error" role="alert">{error}</div>}
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
        <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn btn-primary" disabled={loading}>{loading ? "Saving…" : "Save changes"}</button>
      </div>
    </form>
  </Modal>;
}

const cell: React.CSSProperties = { padding: "15px 18px", borderBottom: "1px solid #edf0ee", fontSize: 14 };

function CreateKeyModal({ accessToken, onClose, onCreated }: {
  accessToken: string; onClose(): void; onCreated(value: CreatedKey): void;
}) {
  const [name, setName] = useState("");
  const [scopes, setScopes] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true); setError("");
    try {
      const key = await apiRequest<CreatedKey>("/api-keys", {
        method: "POST",
        body: JSON.stringify({ name, scopes: scopes.split(",").map((v) => v.trim()).filter(Boolean), expires_at: null }),
      }, accessToken);
      onCreated(key);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the key.");
    } finally { setLoading(false); }
  }

  return <Modal title="Create API key" description="Name the credential and optionally add comma-separated scopes." onClose={onClose}>
    <form onSubmit={submit} style={{ display: "grid", gap: 18 }}>
      <label className="label">Key name<input className="input" required maxLength={255} value={name} onChange={(e) => setName(e.target.value)} placeholder="Production service" /></label>
      <label className="label">Scopes<input className="input" value={scopes} onChange={(e) => setScopes(e.target.value)} placeholder="read:orders, write:orders" /></label>
      {error && <div className="error" role="alert">{error}</div>}
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
        <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn btn-primary" disabled={loading}>{loading ? "Creating…" : "Create key"}</button>
      </div>
    </form>
  </Modal>;
}
