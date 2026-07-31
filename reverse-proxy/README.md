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

## Policy synchronization and validation

The proxy bootstraps/falls back through the REST policy endpoint, then receives
authenticated server-streaming gRPC updates from the Control Plane on port
50051. If the stream disconnects, it continues enforcing the last valid
snapshot and reconnects with backoff.

```http
GET /api/v1/internal/proxy-config
X-Aegis-Internal-Token: <environment-provided shared token>
```

JWT validation supports HS256, RS256, and ES256, requires an expiration claim,
and enforces issuer and audience when configured. Policy also contains active
rate limits, exact IP blocks, and RE2 threat patterns.

## Distributed rate limiting

Active `fixed_window`, `sliding_window`, and `token_bucket` rules are enforced
with atomic Redis scripts. Matching precedence is API-key rule, then exact
route rule, then global rule. Rejected requests receive HTTP 429,
`Retry-After`, `X-RateLimit-Limit`, and `X-RateLimit-Remaining`. The proxy
fails closed with HTTP 503 if Redis enforcement is unavailable.

## Analytics

Every outcome is sanitized and placed on a bounded non-blocking queue for the
Control Plane. Events include only outcome, direct source IP, optional key/rule
IDs, method, path, and status—never credentials, bodies, query strings, or
arbitrary headers.
