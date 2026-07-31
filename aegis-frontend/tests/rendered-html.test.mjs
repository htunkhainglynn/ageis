import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function render(pathname) {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}-${pathname}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request(`http://localhost${pathname}`, {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("server-renders the Aegis login experience", async () => {
  const response = await render("/login");
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<title>Aegis Control Center<\/title>/i);
  assert.match(html, /Sign in to Aegis/);
  assert.match(html, /Control Plane account/);
  assert.match(html, /kept only in memory/i);
  assert.doesNotMatch(html, /localStorage|sessionStorage/);
});

test("role-gated navigation matches the permission matrix", async () => {
  const shell = await readFile(
    new URL("../app/ui/app-shell.tsx", import.meta.url),
    "utf8",
  );

  assert.ok(shell.includes('{ href: "/analytics", label: "Analytics", roles: ["admin", "viewer"]'));
  assert.ok(shell.includes('{ href: "/users", label: "Users", roles: ["admin"]'));
  assert.ok(shell.includes('{ href: "/api-keys", label: "API keys", roles: ["admin", "api_consumer"]'));
  assert.ok(shell.includes('{ href: "/rate-limits", label: "Rate limits", roles: ["admin"]'));
  assert.ok(shell.includes('{ href: "/ip-blocks", label: "IP blocks", roles: ["admin"]'));
  assert.ok(shell.includes('{ href: "/threat-rules", label: "Threat rules", roles: ["admin"]'));
  assert.ok(shell.includes('{ href: "/jwt-config", label: "JWT configuration", roles: ["admin"]'));
  assert.match(shell, /filter\(\(item\) => !item\.roles/);
  assert.match(shell, /roles\.includes\(user\.role\)/);
});

test("authentication state stays in React memory", async () => {
  const auth = await readFile(
    new URL("../app/lib/auth.tsx", import.meta.url),
    "utf8",
  );

  assert.match(auth, /useState<Tokens \| null>\(null\)/);
  assert.doesNotMatch(auth, /localStorage|sessionStorage|indexedDB/);
  assert.match(auth, /setTokens\(null\)/);
  assert.match(auth, /setUser\(null\)/);
});

test("IP block management remains Admin-only in the dashboard", async () => {
  const page = await readFile(
    new URL("../app/ip-blocks/page.tsx", import.meta.url),
    "utf8",
  );

  assert.match(page, /<ProtectedPage roles=\{\["admin"\]\}>/);
  assert.match(page, /apiRequest<IPBlockList>\("\/ip-blocks\?/);
  assert.match(page, /method: "DELETE"/);
  assert.match(page, /exact IPv4 or IPv6 address/i);
});

test("threat rule management remains Admin-only in the dashboard", async () => {
  const page = await readFile(
    new URL("../app/threat-rules/page.tsx", import.meta.url),
    "utf8",
  );
  assert.match(page, /<ProtectedPage roles=\{\["admin"\]\}>/);
  assert.match(page, /apiRequest<RuleList>\("\/threat-rules\?/);
  assert.match(page, /RE2-compatible patterns/i);
});
