# Aegis

Aegis is a monorepo containing the FastAPI Control Plane, Go enforcement
proxy, and React operator dashboard.

## Run locally

Prerequisites: Docker with Compose, Python 3, and `openssl`.

```sh
make init
make credentials
make up
```

`make init` creates a git-ignored `.env` containing fresh local secrets. Use
the credentials printed by `make credentials` at
<http://localhost:3000/login>. The proxy listens on
<http://localhost:8080> and forwards accepted requests to the included sample
HTTP upstream.

Useful commands:

```sh
make check       # Python/Go coverage gates, race/vet, lint, dashboard tests
make e2e         # isolated real-process integration test
make stop        # stop containers and preserve data
make clean       # stop containers and remove local data volumes
```

Never commit the generated `.env`. If it is removed, `make init` generates a
new set of credentials; an existing database retains its existing Admin
password until its volume is removed.

Project scope and contracts live in [`docs`](docs), while
[`AGENTS.md`](AGENTS.md) records verified build status and engineering
decisions.
