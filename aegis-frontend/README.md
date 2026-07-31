# Aegis Dashboard

React + Vite dashboard for the Aegis Control Plane.

## Local development

Copy `.env.example` to `.env.local` if the API is not available at
`http://localhost:8000/api/v1`, then run:

```bash
npm install
npm run dev
```

Authentication tokens are stored only in React memory and are intentionally
cleared on reload.

## Role contract

The dashboard reads `role` from the access-token payload and supports `admin`,
`viewer`, and `api_consumer`. If the claim is absent it safely defaults to
`api_consumer`. The current Control Plane token schema only documents `sub` and
`type`, so Admin and Viewer navigation will become available when the backend
includes its documented role in the authentication contract.
