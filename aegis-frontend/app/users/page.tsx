"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiRequest } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { UserItem } from "../lib/types";
import { ProtectedPage } from "../ui/app-shell";
import { ConfirmDialog, EmptyState, Modal, PageHeader } from "../ui/primitives";

type UserList = { items: UserItem[]; skip: number; limit: number; total: number };

export default function UsersPage() {
  const { accessToken } = useAuth();
  const [items, setItems] = useState<UserItem[]>([]);
  const [editing, setEditing] = useState<UserItem | "new" | null>(null);
  const [removing, setRemoving] = useState<UserItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    try {
      const data = await apiRequest<UserList>("/users?skip=0&limit=100", {}, accessToken);
      setItems(data.items);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load users.");
    } finally {
      setLoading(false);
    }
  }, [accessToken]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function removeUser() {
    if (!accessToken || !removing) return;
    try {
      await apiRequest(`/users/${removing.id}`, { method: "DELETE" }, accessToken);
      setRemoving(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete the user.");
      setRemoving(null);
    }
  }

  return (
    <ProtectedPage roles={["admin"]}>
      <PageHeader eyebrow="Identity" title="Users" description="Create and manage Control Plane accounts."
        action={<button className="btn btn-primary" onClick={() => setEditing("new")}>＋ Create user</button>} />
      {error && <p className="error" role="alert">{error}</p>}
      <section className="card" style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 760 }}>
          <thead><tr>{["Name", "Email", "Status", "Created", ""].map((heading) =>
            <th key={heading} style={head}>{heading}</th>)}</tr></thead>
          <tbody>{items.map((user) => <tr key={user.id}>
            <td style={cell}><strong>{user.full_name}</strong></td>
            <td style={cell}>{user.email}</td>
            <td style={cell}><span style={{ color: user.is_active ? "#176b50" : "#69736d", fontWeight: 700 }}>{user.is_active ? "Active" : "Inactive"}</span></td>
            <td style={cell}>{new Date(user.created_at).toLocaleDateString()}</td>
            <td style={{ ...cell, textAlign: "right" }}>
              <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
                <button className="btn btn-secondary" onClick={() => setEditing(user)}>Edit</button>
                <button className="btn btn-danger" onClick={() => setRemoving(user)}>Delete</button>
              </div>
            </td>
          </tr>)}</tbody>
        </table>
        {loading && <EmptyState>Loading users…</EmptyState>}
        {!loading && items.length === 0 && <EmptyState>No users found.</EmptyState>}
      </section>
      {editing && <UserModal initial={editing === "new" ? undefined : editing} accessToken={accessToken!}
        onClose={() => setEditing(null)} onSaved={() => { setEditing(null); void load(); }} />}
      {removing && <ConfirmDialog title="Delete user?" description={`"${removing.email}" will no longer be able to sign in.`}
        confirmLabel="Delete user" destructive onClose={() => setRemoving(null)} onConfirm={removeUser} />}
    </ProtectedPage>
  );
}

const head: React.CSSProperties = { textAlign: "left", padding: "14px 18px", fontSize: 12, color: "#69736d", borderBottom: "1px solid var(--border)" };
const cell: React.CSSProperties = { padding: "15px 18px", borderBottom: "1px solid #edf0ee", fontSize: 14 };

function UserModal({ initial, accessToken, onClose, onSaved }: {
  initial?: UserItem; accessToken: string; onClose(): void; onSaved(): void;
}) {
  const [fullName, setFullName] = useState(initial?.full_name ?? "");
  const [email, setEmail] = useState(initial?.email ?? "");
  const [password, setPassword] = useState("");
  const [active, setActive] = useState(initial?.is_active ?? true);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      if (initial) {
        await apiRequest(`/users/${initial.id}`, {
          method: "PUT",
          body: JSON.stringify({
            full_name: fullName,
            password: password || null,
            is_active: active,
          }),
        }, accessToken);
      } else {
        await apiRequest("/users", {
          method: "POST",
          body: JSON.stringify({ email, full_name: fullName, password }),
        });
      }
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the user.");
    } finally {
      setLoading(false);
    }
  }

  return <Modal title={initial ? "Edit user" : "Create user"} onClose={onClose}>
    <form onSubmit={submit} style={{ display: "grid", gap: 16 }}>
      <label className="label">Full name<input className="input" required maxLength={255} value={fullName} onChange={(e) => setFullName(e.target.value)} /></label>
      <label className="label">Email<input className="input" type="email" required disabled={Boolean(initial)} value={email} onChange={(e) => setEmail(e.target.value)} /></label>
      <label className="label">{initial ? "New password (optional)" : "Password"}
        <input className="input" type="password" minLength={8} required={!initial} value={password} onChange={(e) => setPassword(e.target.value)} />
      </label>
      {initial && <label style={{ display: "flex", gap: 9, alignItems: "center", fontSize: 14 }}>
        <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} /> Active account
      </label>}
      {error && <div className="error" role="alert">{error}</div>}
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
        <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn btn-primary" disabled={loading}>{loading ? "Saving…" : "Save user"}</button>
      </div>
    </form>
  </Modal>;
}
