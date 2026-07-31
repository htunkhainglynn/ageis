import { ProtectedPage } from "../ui/app-shell";
import { PageHeader } from "../ui/primitives";

export default function AnalyticsPage() {
  return (
    <ProtectedPage roles={["admin", "viewer"]}>
      <PageHeader eyebrow="Observe" title="Analytics" description="Traffic and security event reporting is planned for a future release." />
      <section className="card" style={{ padding: "72px 24px", textAlign: "center" }}>
        <div style={{ width: 46, height: 46, display: "grid", placeItems: "center", borderRadius: 14, background: "#e8f5ef", color: "#176b50", margin: "0 auto 16px", fontWeight: 900 }}>↗</div>
        <h2 style={{ margin: "0 0 8px" }}>Coming soon</h2>
        <p className="muted" style={{ margin: "0 auto", maxWidth: 480, lineHeight: 1.6 }}>Analytics will appear here when the Control Plane metrics endpoints are available.</p>
      </section>
    </ProtectedPage>
  );
}
