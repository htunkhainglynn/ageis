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

### Internal Reverse-Proxy Contract

All internal routes require `X-Aegis-Internal-Token`, whose value is supplied
to both components through the environment.

- `POST /api-keys/validate` — verifies a presented raw key against prefix
  candidates and bcrypt hashes; returns only enforcement metadata

## Not yet built
- Internal JWT/rate-limit policy snapshot endpoints
- Threat detection rule config endpoints
- IP blocking rule endpoints
- Metrics/analytics endpoints
- gRPC server (Control Plane -> Proxy config streaming)

## Reverse Proxy (Go)
- The forwarding core, Control Plane API-key client, local cache, and API-key
  middleware are implemented.
- End-to-end API-key validation awaits the internal Control Plane validation API.
- JWT validation, distributed rate limiting, threat detection, and IP blocking
  are not yet implemented.
