"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiRequest } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { IPBlock } from "../lib/types";
import { ProtectedPage } from "../ui/app-shell";
import { Badge, ConfirmDialog, EmptyState, Modal, PageHeader } from "../ui/primitives";

type IPBlockList = { items: IPBlock[]; total: number };

export default function IPBlocksPage() {
  const { accessToken } = useAuth();
  const [items, setItems] = useState<IPBlock[]>([]);
  const [editing, setEditing] = useState<IPBlock | "new" | null>(null);
  const [disabling, setDisabling] = useState<IPBlock | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    try {
      const data = await apiRequest<IPBlockList>("/ip-blocks?skip=0&limit=100", {}, accessToken);
      setItems(data.items);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load IP blocks.");
    } finally {
      setLoading(false);
    }
  }, [accessToken]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function disable() {
    if (!accessToken || !disabling) return;
    try {
      await apiRequest(`/ip-blocks/${disabling.id}`, { method: "DELETE" }, accessToken);
      setDisabling(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not disable the IP block.");
      setDisabling(null);
    }
  }

  return <ProtectedPage roles={["admin"]}>
    <PageHeader
      eyebrow="Access control"
      title="IP blocks"
      description="Stop requests from exact IPv4 or IPv6 addresses at the proxy edge."
      action={<button className="btn btn-primary" onClick={() => setEditing("new")}>＋ Block address</button>}
    />
    {error && <p className="error" role="alert">{error}</p>}
    <section className="card" style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 800 }}>
        <thead><tr>{["IP address", "Reason", "Source", "Status", "Created", ""].map((heading) =>
          <th key={heading} style={head}>{heading}</th>)}</tr></thead>
        <tbody>{items.map((block) => <tr key={block.id}>
          <td style={cell}><code>{block.ip_address}</code></td>
          <td style={{ ...cell, maxWidth: 360 }}>{block.reason}</td>
          <td style={{ ...cell, textTransform: "capitalize" }}>{block.source}</td>
          <td style={cell}><Badge value={block.status} /></td>
          <td style={cell}>{new Date(block.created_at).toLocaleString()}</td>
          <td style={{ ...cell, textAlign: "right" }}>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <button className="btn btn-secondary" onClick={() => setEditing(block)}>Edit</button>
              {block.status === "active" &&
                <button className="btn btn-danger" onClick={() => setDisabling(block)}>Unblock</button>}
            </div>
          </td>
        </tr>)}</tbody>
      </table>
      {loading && <EmptyState>Loading IP blocks…</EmptyState>}
      {!loading && items.length === 0 && <EmptyState>No IP addresses are blocked.</EmptyState>}
    </section>
    {editing && <IPBlockModal
      initial={editing === "new" ? undefined : editing}
      accessToken={accessToken!}
      onClose={() => setEditing(null)}
      onSaved={() => { setEditing(null); void load(); }}
    />}
    {disabling && <ConfirmDialog
      title="Unblock this IP address?"
      description={`${disabling.ip_address} will be allowed through the proxy again as soon as policy caches refresh.`}
      confirmLabel="Unblock address"
      destructive
      onClose={() => setDisabling(null)}
      onConfirm={disable}
    />}
  </ProtectedPage>;
}

const head: React.CSSProperties = {
  textAlign: "left",
  padding: "14px 16px",
  fontSize: 12,
  color: "#69736d",
  borderBottom: "1px solid var(--border)",
};
const cell: React.CSSProperties = {
  padding: "14px 16px",
  borderBottom: "1px solid #edf0ee",
  fontSize: 14,
};

function IPBlockModal({ initial, accessToken, onClose, onSaved }: {
  initial?: IPBlock;
  accessToken: string;
  onClose(): void;
  onSaved(): void;
}) {
  const [ipAddress, setIPAddress] = useState(initial?.ip_address ?? "");
  const [reason, setReason] = useState(initial?.reason ?? "");
  const [statusValue, setStatusValue] = useState(initial?.status ?? "active");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const payload = initial
        ? { reason, status: statusValue }
        : { ip_address: ipAddress, reason, status: statusValue };
      await apiRequest(initial ? `/ip-blocks/${initial.id}` : "/ip-blocks", {
        method: initial ? "PATCH" : "POST",
        body: JSON.stringify(payload),
      }, accessToken);
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the IP block.");
    } finally {
      setLoading(false);
    }
  }

  return <Modal
    title={initial ? "Edit IP block" : "Block an IP address"}
    description="Blocks apply to the direct network peer seen by Aegis. Enter one exact IPv4 or IPv6 address."
    onClose={onClose}
  >
    <form onSubmit={submit} style={{ display: "grid", gap: 16 }}>
      <label className="label">IP address
        <input
          className="input"
          required
          disabled={Boolean(initial)}
          value={ipAddress}
          onChange={(event) => setIPAddress(event.target.value)}
          placeholder="203.0.113.10"
        />
      </label>
      <label className="label">Reason
        <textarea
          className="input"
          required
          maxLength={500}
          rows={3}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        />
      </label>
      <label className="label">Status
        <select className="input" value={statusValue} onChange={(event) => setStatusValue(event.target.value as IPBlock["status"])}>
          <option value="active">Active</option>
          <option value="disabled">Disabled</option>
        </select>
      </label>
      {error && <div className="error" role="alert" style={{ background: "#fff1f0", padding: 11, borderRadius: 8 }}>{error}</div>}
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
        <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn btn-primary" disabled={loading}>{loading ? "Saving…" : "Save block"}</button>
      </div>
    </form>
  </Modal>;
}
