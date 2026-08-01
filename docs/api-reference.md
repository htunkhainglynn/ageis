# Aegis — Control Plane API Reference

Base path: `/api/v1/`. Keep this synchronized with the generated OpenAPI schema.

## Public (no auth)
- `GET /health`
- `POST /users` — register as API Consumer unless email is explicitly in the
  bootstrap Admin allowlist
- `POST /auth/login` — returns access_token + refresh_token
- `POST /auth/refresh` — returns refreshed access_token
- `POST /auth/logout` — revokes access token in Redis

## Protected (Authorization: Bearer <access_token>)

### Users (Admin)
- `GET /users?skip&limit`
- `GET /users/{user_id}`
- `PUT /users/{user_id}`
- `DELETE /users/{user_id}` — soft deactivates the account

### API Keys (Admin or API Consumer; Viewer denied)
- `POST /api-keys` — create; returns raw key ONCE + metadata
- `GET /api-keys?skip&limit` — own keys for API Consumer, all keys for Admin
- `GET /api-keys/{id}` — metadata only, no raw key/hash
- `PATCH /api-keys/{id}` — metadata only
- `DELETE /api-keys/{id}` — soft revoke (status=revoked)
- Ownership/Admin check enforced on GET/PATCH/DELETE single-key routes

### Rate Limit Rules
- `POST /rate-limit-rules` — Admin only
- `GET /rate-limit-rules` — any authenticated user; filterable by scope_type, status
- `GET /rate-limit-rules/{id}` — any authenticated user
- `PATCH /rate-limit-rules/{id}` — Admin only
- `DELETE /rate-limit-rules/{id}` — soft delete (status=disabled), Admin only

### JWT Config (Admin)
- `POST /jwt-configs` — does NOT auto-activate
- `GET /jwt-configs` — contains masked key material
- `GET /jwt-configs/{id}`
- `PATCH /jwt-configs/{id}` — non-key fields only (ttl, issuer, audience)
- `POST /jwt-configs/{id}/activate` — deactivates previous active config
- `DELETE /jwt-configs/{id}` — soft delete; rejects the active config

### IP Blocks (Admin)
- `POST /ip-blocks` — manually block one exact IPv4 or IPv6 address
- `GET /ip-blocks?skip&limit&status` — list active and historical blocks
- `GET /ip-blocks/{id}`
- `PATCH /ip-blocks/{id}` — update reason/status; address and source immutable
- `DELETE /ip-blocks/{id}` — soft delete (status=disabled)
- Automatic blocks are created after the configured number of recent
  `threat_detected`/`rate_limited` events and appear with `source=auto` and no
  human `created_by`.

### Threat Rules (Admin)
- `POST /threat-rules` — create an RE2-compatible request-target pattern
- `GET /threat-rules?skip&limit&status`
- `GET /threat-rules/{id}`
- `PATCH /threat-rules/{id}`
- `DELETE /threat-rules/{id}` — soft delete (status=disabled)

### Route Permissions (Admin)
- `POST /route-permissions` — create an exact method/path scope policy
- `GET /route-permissions?skip&limit&status` — list policies
- `GET /route-permissions/{id}`
- `PATCH /route-permissions/{id}`
- `DELETE /route-permissions/{id}` — soft delete (status=disabled)

`method` is a supported HTTP method, `path_pattern` is an exact path beginning
with `/` (wildcards and query strings are rejected), and `required_scope` uses
`resource:action` format.

### Analytics (Admin or Viewer)
- `GET /analytics/summary?hours` — outcome totals and event-type counts
- `GET /analytics/events?hours&skip&limit` — recent sanitized proxy outcomes

### Internal Reverse-Proxy Contract

All internal routes require `X-Aegis-Internal-Token`, whose value is supplied
to both components through the environment.

- `POST /api-keys/validate` — verifies a presented raw key against prefix
  candidates and bcrypt hashes; returns only enforcement metadata
- `GET /internal/proxy-config` — returns active JWT verification, rate-limit,
  IP-block, threat-rule, and route-permission policy. HS256 requires decrypted shared verification
  material; RS256/ES256 return only the public verification key.
- `POST /internal/security-events` — ingest one sanitized proxy outcome; raw
  credentials, request bodies, and arbitrary headers are forbidden

## Internal gRPC Policy Sync
- `aegis.policy.v1.PolicySync/Subscribe` is a server-streaming RPC on internal
  port 50051.
- Clients authenticate with `x-aegis-internal-token` metadata.
- Each protobuf envelope carries the versioned policy snapshot; the proxy uses
  REST for bootstrap/fallback, then applies stream updates immediately and
  retains the last valid snapshot across disconnects.

## Reverse Proxy (Go)
- Forwarding, authenticated API-key validation, JWT validation, Redis-backed
  distributed rate limiting, credential stripping, and cached REST policy
  synchronization are implemented and covered by an isolated real-process E2E
  test.
- Exact-address IP blocking evaluates the direct network peer before
  credentials and ignores untrusted forwarding headers.
- Active threat rules are matched against method plus path/query using Go RE2;
  matching requests are rejected before forwarding.
- Active route permissions are matched by exact method and path. Matching
  requests require the exact `required_scope` in the validated API key scopes;
  unmatched requests are allowed by default.
- Sanitized outcome events are delivered asynchronously through a bounded
  queue, keeping Control Plane/database latency off the forwarding hot path.
