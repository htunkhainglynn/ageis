"use client";

import { useEffect, useState } from "react";
import { apiRequest } from "../lib/api";
import { ProtectedPage } from "../ui/app-shell";
import { PageHeader } from "../ui/primitives";

type Health = {
  service: "up" | "down";
  database: "up" | "down";
  redis: "up" | "down";
};

export default function SystemPage() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const timer = window.setTimeout(async () => {
      try {
        setHealth(await apiRequest<Health>("/../../health"));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not reach the Control Plane.");
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  return (
    <ProtectedPage>
      <PageHeader eyebrow="Control Plane" title="System health" description="Live status from the Aegis service and its dependencies." />
      {error && <p className="error" role="alert">{error}</p>}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: 16 }}>
        {(["service", "database", "redis"] as const).map((name) => {
          const status = health?.[name] ?? "checking";
          const up = status === "up";
          return <section className="card" key={name} style={{ padding: 22 }}>
            <div className="muted" style={{ fontSize: 12, fontWeight: 750, textTransform: "uppercase", letterSpacing: ".09em" }}>{name}</div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 13 }}>
              <span style={{ width: 10, height: 10, borderRadius: 99, background: up ? "#1d9b69" : status === "down" ? "#d92d20" : "#98a29c" }} />
              <strong style={{ fontSize: 20, textTransform: "capitalize" }}>{status}</strong>
            </div>
          </section>;
        })}
      </div>
    </ProtectedPage>
  );
}
