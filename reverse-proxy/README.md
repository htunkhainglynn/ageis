# Aegis Reverse Proxy

Go data plane for Aegis. Transparent HTTP forwarding is guarded by both
API-key and JWT validation.

## Run

Set the variables shown in `.env.example`, then:

```bash
go run ./cmd/proxy
```

Every proxied request must include `X-API-Key` (configurable with
`API_KEY_HEADER`) and `Authorization: Bearer <jwt>`. Both credentials are
removed before forwarding to the backend.

## Control Plane validation contract

The proxy calls:

```http
POST /api/v1/api-keys/validate
Content-Type: application/json
X-Aegis-Internal-Token: <environment-provided shared token>

{"api_key":"ak_..."}
```

Successful response:

```json
{
  "status": "success",
  "message": "API key is valid.",
  "data": {
    "id": 1,
    "key_prefix": "ak_abcd",
    "owner_id": 1,
    "scopes": ["read"],
    "status": "active",
    "expires_at": null
  }
}
```

Expected errors are `404` for an unknown key and `403` with
`API_KEY_REVOKED` or `API_KEY_EXPIRED`. The FastAPI Control Plane exposes this
private route only when `INTERNAL_API_TOKEN` is configured, and the proxy must
send the same value.

Validation results are cached in memory by a SHA-256 digest of the presented
key. Raw API keys are never used as cache map keys.

## JWT policy and validation

The proxy fetches the active JWT verification configuration and active
rate-limit rules from:

```http
GET /api/v1/internal/proxy-config
X-Aegis-Internal-Token: <environment-provided shared token>
```

Policy is cached locally. If refresh fails after an initial successful fetch,
the proxy continues enforcing the last known policy. JWT validation supports
HS256, RS256, and ES256, requires an expiration claim, and enforces issuer and
audience when configured.
