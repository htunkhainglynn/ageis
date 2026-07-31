# Backend Agent Context

The canonical project instructions, verified Current Build Status, and Key
Decisions are maintained in the monorepo root at `../AGENTS.md`.

Backend-specific invariants:

- The FastAPI Control Plane defines policy; it does not enforce proxy traffic.
- All APIs are async and versioned under `/api/v1`.
- Admin-only routes enforce roles through dependencies and service-level checks.
- API keys and passwords use bcrypt. JWT configuration secrets use Fernet with
  key material supplied through the environment.
- Never return API-key hashes or unmasked JWT key material.
- Add a forward Alembic migration for schema changes; never edit migration
  history to retrofit a feature.
- Run the complete pytest suite with no failures or skips before committing.
