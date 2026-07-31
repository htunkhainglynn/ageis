# Aegis Project Guide

This is the canonical working context for the Aegis monorepo. Keep the
Current Build Status and Key Decisions sections synchronized with verified
code and test results.

## Product Scope

Aegis is a centralized API security and management system comprising:

1. `aegis-backend`: FastAPI Control Plane that defines policy.
2. `reverse-proxy`: Go data plane that enforces policy before forwarding.
3. `aegis-frontend`: React dashboard for operators and API consumers.

The Project Proposal at
`/Users/htunkhainglynn/Documents/kmd/Htun_Khaing_Lynn_001557481_Project_Proposal.pdf`
is authoritative for the aim and objectives. `docs/requirements.md` is
authoritative for MoSCoW scope, `docs/domain-model.md` for domain constraints,
and `docs/api-reference.md` for the current HTTP contract.

## Architecture Rules

- The Control Plane defines policy; the reverse proxy enforces it.
- All Control Plane APIs are async and versioned under `/api/v1`.
- Prefer soft deletion for policy/security resources.
- Raw API keys are returned only at creation. Hashes are never returned.
- JWT key material is encrypted at rest and only masked values are returned.
- Admin-only routes enforce authorization through FastAPI dependencies and
  retain service-level checks for defense in depth.
- Never place secrets or encryption keys in source control.

## Current Build Status

Verified on 2026-07-31 against the actual monorepo:

### Implemented and tested

- Control Plane user registration, login, refresh, logout, Redis-backed token
  lifecycle, and user CRUD.
- Persisted `admin`, `viewer`, and `api_consumer` roles with a forward Alembic
  migration, dependency-level RBAC, role-bearing JWTs, and explicit bootstrap
  admin allowlisting.
- API key creation (one-time raw value, bcrypt persistence), metadata CRUD,
  owner/Admin authorization, admin all-key listing, and soft revocation.
- Rate-limit rule CRUD/config validation, one-active-rule-per-scope behavior,
  authenticated reads, and Admin-only writes.
- JWT configuration CRUD, Fernet-encrypted signing keys, masked responses,
  one-active-config behavior, and Admin-only access.
- Manual exact-address IP block CRUD with IPv4/IPv6 canonicalization,
  one-active-block-per-address behavior, soft deletion, Admin-only Control
  Plane access, and an Admin-only dashboard page.
- Authenticated internal policy snapshot returning only active JWT validation
  material and active rate-limit rules for the reverse proxy.
- Dashboard login and configuration pages for users, API keys, rate limits,
  JWT configuration, system health, and an analytics placeholder. Navigation
  and route visibility follow the role matrix.
- Go reverse-proxy forwarding core, Control Plane API-key validation client,
  authenticated Control Plane API-key validation contract, local validation
  cache, and API-key middleware unit/integration tests.
- Reverse-proxy JWT validation for HS256/RS256/ES256 with algorithm pinning,
  required expiration, optional issuer/audience enforcement, credential
  stripping, and stale-safe Control Plane policy caching.
- Redis-backed distributed rate limiting with atomic fixed-window,
  sliding-window, and token-bucket scripts, burst support, standard response
  headers, and cross-instance counter tests.
- Reproducible full-stack Docker Compose runtime with generated, ignored
  secrets; idempotent environment-driven Admin bootstrap; and an isolated E2E
  test that exercises Control Plane configuration, proxy API-key/JWT
  enforcement, Redis rate limiting, and forwarding to a real HTTP upstream.

Current checkpoint verification:

- Control Plane: 36 pytest tests pass, none skipped; all migrations apply
  successfully to PostgreSQL.
- Dashboard: lint, production build, and 4 Node tests pass, none skipped.
- Reverse proxy baseline: `go test -race ./...` and `go vet ./...` pass.
- Full stack: the isolated `scripts/e2e.sh` test passes against fresh
  PostgreSQL and Redis volumes and real component containers.

### Partially implemented

- Manual IP block policy configuration is implemented; reverse-proxy
  enforcement and E2E verification are the next checkpoint.

### Not implemented

- Threat detection rules/pattern matching.
- Security-event persistence and analytics APIs/dashboard data.
- Control Plane-to-proxy gRPC configuration sync.
- Automatic IP blocking.

## Key Decisions & Rationale

- **Canonical monorepo documentation:** source documents supplied outside the
  repository are mirrored under `docs/`, and this root file replaces the stale
  backend-only status file as the project-wide source of working context.
- **Persisted roles:** authorization roles are stored on `users` instead of
  inferred from transient Python attributes. This makes role checks consistent
  across HTTP requests and token refreshes.
- **Safe registration:** public registration always creates an API Consumer,
  except emails explicitly listed in `BOOTSTRAP_ADMIN_EMAILS`. Administrators
  can subsequently assign roles through protected user management.
- **Rate-limit reads:** the documented API permits any authenticated role to
  read rate-limit rules; create/update/disable operations remain Admin-only.
- **Dashboard runtime:** although early documents say React + Vite + shadcn/ui,
  the existing implementation is React 19 on Vinext/Vite with established
  local UI primitives. Preserve that working structure rather than replacing
  it during feature work.
- **Initial proxy synchronization:** complete and prove REST-backed cached
  policy enforcement first. gRPC remains a Should Have optimization after all
  Must Haves work end-to-end.
- **Authenticated internal contracts:** reverse-proxy REST calls use the
  `X-Aegis-Internal-Token` header with an environment-only shared secret. This
  prevents public use of key-validation and future raw policy-material APIs.
- **Rate-limit matching:** when multiple active scopes match, the proxy uses
  the most specific rule (`api_key`, then exact `route`, then `global`).
  API-key counters are isolated by key ID; route and global scopes represent
  shared traffic buckets as their names imply.
- **Local bootstrap without committed credentials:** Compose generates a
  git-ignored `.env` with cryptographically random secrets and an initial
  Admin password. Bootstrap creates the allowlisted Admin only when absent and
  never resets an existing account, preserving data and operator changes.
- **Isolated integration verification:** the E2E script uses random ports,
  credentials, Compose project names, and disposable volumes so it neither
  depends on nor mutates a developer's normal local stack.
- **IP block address semantics:** manual blocks target one canonical exact IPv4
  or IPv6 address. CIDR ranges are intentionally excluded from the baseline to
  avoid accidental broad lockouts; source is immutable and operator-created
  rows are always marked `manual`.

## Testing and Checkpoints

- Python: add meaningful coverage and run the entire pytest suite after every
  backend checkpoint.
- Go: keep code gofmt-clean; run `go test -race ./...` and `go vet ./...`.
- Dashboard: run lint, production build, and the complete test suite.
- A checkpoint may be committed only when all relevant tests pass without
  failures or skips. Commit messages must name the feature and passing checks.
