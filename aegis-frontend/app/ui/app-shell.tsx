"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "../lib/auth";
import type { Role } from "../lib/types";

const navItems = [
  { href: "/system", label: "System health" },
  { href: "/analytics", label: "Analytics", roles: ["admin", "viewer"] as Role[] },
  { href: "/users", label: "Users", roles: ["admin"] as Role[] },
  { href: "/api-keys", label: "API keys", roles: ["admin", "api_consumer"] as Role[] },
  { href: "/rate-limits", label: "Rate limits", roles: ["admin"] as Role[] },
  { href: "/ip-blocks", label: "IP blocks", roles: ["admin"] as Role[] },
  { href: "/jwt-config", label: "JWT configuration", roles: ["admin"] as Role[] },
];

export function RedirectHome() {
  const { user } = useAuth();
  const router = useRouter();
  useEffect(() => router.replace(user ? "/system" : "/login"), [router, user]);
  return null;
}

export function ProtectedPage({ roles, children }: { roles?: Role[]; children: React.ReactNode }) {
  const { user } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (!user) {
      router.replace("/login");
    } else if (roles && !roles.includes(user.role)) {
      router.replace("/system");
    }
  }, [roles, router, user]);
  if (!user || (roles && !roles.includes(user.role))) return null;
  return <AppShell>{children}</AppShell>;
}

function AppShell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  async function handleLogout() {
    await logout();
    router.replace("/login");
  }

  return (
    <div style={{ minHeight: "100vh", display: "grid", gridTemplateColumns: "240px minmax(0,1fr)" }}>
      <aside style={{ background: "#14251e", color: "white", padding: "26px 18px", position: "sticky", top: 0, height: "100vh" }}>
        <Link href="/" style={{ color: "white", textDecoration: "none", display: "flex", gap: 11, alignItems: "center", padding: "0 8px 30px" }}>
          <span style={{ width: 31, height: 31, borderRadius: 9, display: "grid", placeItems: "center", background: "#49b98d", color: "#10251c", fontWeight: 900 }}>A</span>
          <span style={{ fontWeight: 800, fontSize: 18 }}>Aegis</span>
        </Link>
        <nav aria-label="Primary navigation" style={{ display: "grid", gap: 6 }}>
          {navItems.filter((item) => !item.roles || (user && item.roles.includes(user.role))).map((item) => {
            const active = pathname === item.href;
            return <Link key={item.href} href={item.href} style={{
              color: active ? "white" : "#b8c8c0", background: active ? "#254638" : "transparent",
              textDecoration: "none", padding: "11px 12px", borderRadius: 9, fontWeight: 600, fontSize: 14,
            }}>{item.label}</Link>;
          })}
        </nav>
      </aside>
      <div style={{ minWidth: 0 }}>
        <header style={{ height: 72, display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 16, padding: "0 34px", borderBottom: "1px solid var(--border)", background: "rgba(255,255,255,.88)" }}>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: 13, fontWeight: 700 }}>{user?.email}</div>
            <div className="muted" style={{ fontSize: 12, textTransform: "capitalize" }}>{user?.role.replace("_", " ")}</div>
          </div>
          <button className="btn btn-secondary" onClick={handleLogout}>Log out</button>
        </header>
        <main style={{ padding: "34px", maxWidth: 1440, margin: "0 auto" }}>{children}</main>
      </div>
      <style>{`@media(max-width:780px){body>div>div{grid-template-columns:150px minmax(0,1fr)!important} aside{padding-inline:10px!important} main{padding:22px!important}}`}</style>
    </div>
  );
}
