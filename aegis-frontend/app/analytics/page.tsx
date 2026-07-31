"use client";

import { useCallback, useEffect, useState } from "react";
import { apiRequest } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { AnalyticsSummary, SecurityEvent } from "../lib/types";
import { ProtectedPage } from "../ui/app-shell";
import { EmptyState, PageHeader } from "../ui/primitives";

type EventList = { items: SecurityEvent[]; total: number };

export default function AnalyticsPage() {
  const { accessToken } = useAuth();
  const [hours, setHours] = useState(24);
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [events, setEvents] = useState<SecurityEvent[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    try {
      const [summaryData, eventData] = await Promise.all([
        apiRequest<AnalyticsSummary>(`/analytics/summary?hours=${hours}`, {}, accessToken),
        apiRequest<EventList>(`/analytics/events?hours=${hours}&limit=50`, {}, accessToken),
      ]);
      setSummary(summaryData);
      setEvents(eventData.items);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load analytics.");
    } finally {
      setLoading(false);
    }
  }, [accessToken, hours]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const metrics = [
    ["Total requests", summary?.total_requests ?? 0],
    ["Forwarded", summary?.forwarded_requests ?? 0],
    ["Blocked", summary?.blocked_requests ?? 0],
    ["Rate limited", summary?.rate_limited_requests ?? 0],
    ["Server errors", summary?.server_errors ?? 0],
  ] as const;
  const maxEventCount = Math.max(1, ...Object.values(summary?.events_by_type ?? {}));

  return <ProtectedPage roles={["admin", "viewer"]}>
    <PageHeader eyebrow="Observe" title="Analytics"
      description="Traffic outcomes and security events reported by the reverse proxy."
      action={<label className="label">Time range<select className="input" value={hours}
        onChange={(event) => setHours(Number(event.target.value))}>
        <option value={1}>Last hour</option><option value={24}>Last 24 hours</option>
        <option value={168}>Last 7 days</option><option value={720}>Last 30 days</option>
      </select></label>} />
    {error && <p className="error" role="alert">{error}</p>}
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(170px,1fr))", gap: 14 }}>
      {metrics.map(([label, value]) => <section className="card" key={label} style={{ padding: 20 }}>
        <div className="muted" style={{ fontSize: 12, fontWeight: 700 }}>{label}</div>
        <strong style={{ display: "block", fontSize: 28, marginTop: 9 }}>{value.toLocaleString()}</strong>
      </section>)}
    </div>
    <section className="card" style={{ padding: 22, marginTop: 18 }}>
      <h2 style={{ margin: "0 0 18px", fontSize: 18 }}>Events by outcome</h2>
      <div style={{ display: "grid", gap: 12 }}>
        {Object.entries(summary?.events_by_type ?? {}).sort((a, b) => b[1] - a[1]).map(([name, count]) =>
          <div key={name} style={{ display: "grid", gridTemplateColumns: "150px 1fr 50px", gap: 12, alignItems: "center" }}>
            <span style={{ fontSize: 13 }}>{name.replaceAll("_", " ")}</span>
            <div style={{ height: 10, background: "#edf1ef", borderRadius: 99, overflow: "hidden" }}>
              <div style={{ height: "100%", width: `${Math.max(2, count / maxEventCount * 100)}%`, background: "#1d9b69" }} />
            </div>
            <strong style={{ textAlign: "right" }}>{count}</strong>
          </div>)}
        {!loading && Object.keys(summary?.events_by_type ?? {}).length === 0 &&
          <EmptyState>No proxy events in this time range.</EmptyState>}
      </div>
    </section>
    <section className="card" style={{ overflowX: "auto", marginTop: 18 }}>
      <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 850 }}>
        <thead><tr>{["Time", "Outcome", "Request", "Source", "Status", "Key"].map((heading) =>
          <th key={heading} style={head}>{heading}</th>)}</tr></thead>
        <tbody>{events.map((event) => <tr key={event.id}>
          <td style={cell}>{new Date(event.created_at).toLocaleString()}</td>
          <td style={cell}>{event.event_type.replaceAll("_", " ")}</td>
          <td style={cell}><code>{event.method} {event.path}</code></td>
          <td style={cell}><code>{event.source_ip}</code></td>
          <td style={cell}>{event.status_code}</td>
          <td style={cell}>{event.api_key_id ?? "—"}</td>
        </tr>)}</tbody>
      </table>
      {loading && <EmptyState>Loading analytics…</EmptyState>}
      {!loading && events.length === 0 && <EmptyState>No events recorded.</EmptyState>}
    </section>
  </ProtectedPage>;
}

const head: React.CSSProperties = { textAlign: "left", padding: "14px 16px", fontSize: 12, color: "#69736d", borderBottom: "1px solid var(--border)" };
const cell: React.CSSProperties = { padding: "13px 16px", borderBottom: "1px solid #edf0ee", fontSize: 13 };
