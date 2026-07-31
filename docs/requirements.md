# Aegis — Requirements Summary (MoSCoW)

Condensed from the project report (Chapter 6). Full prose version with
justifications is in the report; this is the quick-reference for development.

## Must Have
- User auth (register, login, refresh, logout) with JWT + Redis token revocation
- API key management (generate once, hash+prefix, ownership-scoped CRUD, soft revoke)
- Rate limit rule configuration (global/api_key/route scope, single-active-per-scope)
- JWT signing configuration (encrypted at rest, single active config, Admin-only)
- Reverse Proxy: API key + JWT validation on every request before forwarding
- Reverse Proxy: rate limit enforcement via Redis-backed distributed counter
- Role-based access control on all configuration endpoints

## Should Have
- Threat detection pattern matching (Reverse Proxy)
- Analytics dashboard (React) — usage, security events, system health
- gRPC config sync (Control Plane -> Proxy), replacing REST polling once core
  enforcement is proven

## Could Have
- Automatic IP blocking based on repeated rule violations (manual blocking is
  the Must-have baseline)
- (gRPC itself is Should-have; treat as Could-have if timeline is tight)

## Won't Have (explicitly out of scope)
- Non-HTTP protocol support
- Offline / air-gapped deployment
- Native mobile admin app

## Non-Functional Requirements (quick reference)
- Security: bcrypt for passwords/keys, Fernet encryption for JWT signing keys,
  server-side validation on all critical ops, no secret re-exposure
- Scalability: rate limit + session state shared via Redis, not per-instance memory
- Performance: minimal added latency at the proxy; avoid per-request DB hits
  on the hot path (cache config locally)
- Availability: proxy should keep enforcing cached config if Control Plane is
  briefly down
- Usability: dashboard usable without deep security expertise; mask secrets
  visually rather than hiding config entirely
- Maintainability: strict Control Plane (policy) / Data Plane (enforcement) split
- Portability: must run via Docker Compose on modest hardware

## User Roles
| Capability | Admin | Viewer | API Consumer |
|---|---|---|---|
| Manage users | Yes | No | No |
| Manage own API keys | Yes | No | Yes |
| Manage rate limit rules | Yes | No | No |
| Manage JWT config | Yes | No | No |
| Manage threat rules / IP blocks | Yes | No | No |
| View analytics dashboard | Yes | Yes | No |
| Auth via API key to call proxied APIs | Yes | No | Yes |

