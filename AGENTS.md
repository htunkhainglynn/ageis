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

Current checkpoint verification:

- Control Plane: 31 pytest tests pass, none skipped; the role migration applies
  successfully to PostgreSQL.
- Dashboard: lint, production build, and 3 Node tests pass, none skipped.
- Reverse proxy baseline: `go test -race ./...` and `go vet ./...` pass.

### Partially implemented

- Reverse-proxy API-key enforcement is implemented at both components, but the
  real multi-process Compose E2E path has not yet been exercised.
- Docker Compose provisions PostgreSQL and Redis, but does not yet run the full
  Control Plane -> proxy -> sample backend stack.

### Not implemented

- Redis-backed distributed rate limiting in the reverse proxy (the Control
  Plane policy contract is ready).
- Manual IP blocking baseline.
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

## Testing and Checkpoints

- Python: add meaningful coverage and run the entire pytest suite after every
  backend checkpoint.
- Go: keep code gofmt-clean; run `go test -race ./...` and `go vet ./...`.
- Dashboard: run lint, production build, and the complete test suite.
- A checkpoint may be committed only when all relevant tests pass without
  failures or skips. Commit messages must name the feature and passing checks.
