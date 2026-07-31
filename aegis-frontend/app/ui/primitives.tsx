"use client";

import { useEffect } from "react";

export function Badge({ value }: { value: string }) {
  const active = value === "active";
  return (
    <span style={{
      display: "inline-flex", borderRadius: 999, padding: "4px 9px", fontSize: 12,
      fontWeight: 700, color: active ? "#126346" : "#59635d",
      background: active ? "#e8f5ef" : "#eef1ef",
    }}>{value}</span>
  );
}

export function Modal({
  title, description, children, onClose,
}: {
  title: string; description?: string; children: React.ReactNode; onClose(): void;
}) {
  useEffect(() => {
    const handler = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <div role="presentation" onMouseDown={(e) => e.target === e.currentTarget && onClose()}
      style={{ position: "fixed", inset: 0, zIndex: 50, background: "rgba(15,24,19,.48)", display: "grid", placeItems: "center", padding: 20 }}>
      <section role="dialog" aria-modal="true" aria-labelledby="modal-title" className="card"
        style={{ width: "min(620px, 100%)", maxHeight: "90vh", overflow: "auto", padding: 24 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 20 }}>
          <div>
            <h2 id="modal-title" style={{ margin: 0, fontSize: 20 }}>{title}</h2>
            {description && <p className="muted" style={{ margin: "7px 0 0", lineHeight: 1.5 }}>{description}</p>}
          </div>
          <button className="btn btn-secondary" aria-label="Close dialog" onClick={onClose}>×</button>
        </div>
        <div style={{ marginTop: 22 }}>{children}</div>
      </section>
    </div>
  );
}

export function ConfirmDialog({
  title, description, confirmLabel, destructive, onConfirm, onClose,
}: {
  title: string; description: string; confirmLabel: string; destructive?: boolean;
  onConfirm(): void | Promise<void>; onClose(): void;
}) {
  return (
    <Modal title={title} description={description} onClose={onClose}>
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
        <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
        <button className={`btn ${destructive ? "btn-danger" : "btn-primary"}`} onClick={onConfirm}>{confirmLabel}</button>
      </div>
    </Modal>
  );
}

export function PageHeader({ eyebrow, title, description, action }: {
  eyebrow: string; title: string; description: string; action?: React.ReactNode;
}) {
  return (
    <header style={{ display: "flex", justifyContent: "space-between", alignItems: "end", gap: 20, marginBottom: 24, flexWrap: "wrap" }}>
      <div>
        <div style={{ color: "#176b50", fontWeight: 750, fontSize: 12, letterSpacing: ".12em", textTransform: "uppercase" }}>{eyebrow}</div>
        <h1 style={{ fontSize: 28, letterSpacing: "-.03em", margin: "6px 0" }}>{title}</h1>
        <p className="muted" style={{ margin: 0 }}>{description}</p>
      </div>
      {action}
    </header>
  );
}

export function EmptyState({ children }: { children: React.ReactNode }) {
  return <div className="muted" style={{ padding: 44, textAlign: "center" }}>{children}</div>;
}
