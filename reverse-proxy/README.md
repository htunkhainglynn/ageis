# Aegis Reverse Proxy

Go data plane for Aegis. This stage implements transparent HTTP forwarding
guarded by API-key validation.

## Run

Set the variables shown in `.env.example`, then:

```bash
go run ./cmd/proxy
```

Every proxied request must include `X-API-Key` (configurable with
`API_KEY_HEADER`). The credential is removed before forwarding to the backend.

## Control Plane validation contract

The proxy calls:

```http
POST /api/v1/api-keys/validate
Content-Type: application/json

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

Expected errors are `404` or `401` for an unknown key and `403` with
`API_KEY_REVOKED` or `API_KEY_EXPIRED`. The current FastAPI Control Plane does
not yet expose this validation route; adding it is a separate backend change.

Validation results are cached in memory by a SHA-256 digest of the presented
key. Raw API keys are never used as cache map keys.
