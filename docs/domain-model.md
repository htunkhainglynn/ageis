# Aegis — Domain Model

Reference for the Control Plane's data model. Source of truth is the actual
Alembic migrations in the repo — this file is a map/summary, not canonical.

## Entities

### User
- id, email (unique), full_name, hashed_password (bcrypt), is_active
- role (admin | viewer | api_consumer, indexed)
- created_at, updated_at

### APIKey
- id, key_hash (bcrypt), key_prefix (plain, non-sensitive, indexed)
- owner_id (FK -> User.id, indexed)
- name, scopes (JSON), status (active | revoked, indexed)
- expires_at, last_used_at, created_at, updated_at
- Raw key is shown ONCE at creation, never persisted or re-exposed

### RateLimitRule
- id, scope_type (global | api_key | route), scope_value (nullable, required
  unless scope_type=global)
- algorithm (token_bucket | sliding_window | fixed_window)
- limit_count, window_seconds, burst_allowance (nullable)
- status (active | disabled), created_by (FK -> User.id)
- Constraint: only ONE active rule per (scope_type, scope_value) combination

### JWTConfig
- id, algorithm (HS256 | RS256 | ES256)
- signing_key (Fernet-encrypted, NOT hashed — must be decryptable)
- public_key (nullable, required only for RS256/ES256)
- issuer, audience (nullable), access_token_ttl_seconds, refresh_token_ttl_seconds
- status (active | disabled), created_by
- Constraint: only ONE active config system-wide; activating a new one
  deactivates the previous one in the same transaction
- Operator-facing API responses NEVER return raw signing_key/public_key —
  masked values only. The authenticated internal proxy contract returns the
  minimum verification key required for enforcement; asymmetric private keys
  are never returned.

### ThreatRule (planned, not yet built)
- id, pattern, severity, status, created_by

### IPBlock
- id, ip_address (canonical exact IPv4 or IPv6 address), reason
- source (manual | auto), status (active | disabled), created_by
- Constraint: only one active block for an address; historical disabled rows
  are retained

### SecurityEvent (planned, not yet built)
- id, event_type, source_ip, api_key_id (nullable), rule_triggered, created_at

## Relationships
- User 1 --- * APIKey (owns)
- APIKey 0..1 --- * RateLimitRule (a rule may optionally scope to a specific key)
- ThreatRule / IPBlock --- * SecurityEvent (event linkage planned)

## Key Constraints to Preserve
- One active RateLimitRule per scope (scope_type + scope_value)
- One active JWTConfig system-wide
- Soft delete everywhere (status flag), never hard delete — proxy caches may
  reference a row mid-sync
- Ownership checks on every APIKey read/write (owner or Admin only)
