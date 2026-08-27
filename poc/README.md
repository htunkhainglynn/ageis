# Aegis Reverse Proxy POC

This disposable echo service proves that a request passes through the Aegis
Reverse Proxy and reaches a real upstream. It is development tooling, not part
of the Control Plane or proxy runtime.

The proxy requires both `X-API-Key` and a valid Bearer JWT. It removes those
credentials before forwarding, so a successful echo response should contain
neither header.

## 1. Start dependencies and the Control Plane

From the repository root:

```bash
cd /Users/htunkhainglynn/Projects/aegis
make init
docker compose up -d --wait postgres redis

set -a
. ./.env
set +a
export APP_ENV=development
export ENVIRONMENT=development
export DATABASE_URL="postgresql+asyncpg://aegis:${POSTGRES_PASSWORD}@localhost:${POSTGRES_PORT}/aegis"
export REDIS_HOST=localhost

cd aegis-backend
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m uvicorn app.main:app \
  --host 0.0.0.0 --port "${CONTROL_PLANE_PORT}"
```

Leave that terminal running.

## 2. Seed and inspect development data

In a second terminal:

```bash
cd /Users/htunkhainglynn/Projects/aegis
set -a
. ./.env
set +a
export APP_ENV=development
export ENVIRONMENT=development
export DATABASE_URL="postgresql+asyncpg://aegis:${POSTGRES_PASSWORD}@localhost:${POSTGRES_PORT}/aegis"

./aegis-backend/.venv/bin/python scripts/seed_dev_data.py
./aegis-backend/.venv/bin/python scripts/list_dev_data.py
```

The seed command rotates the three seeded API-key values and prints four
`export` commands. Copy and run them in every terminal where the curl examples
below will be used. The values are printed once at runtime and are not written
to a file or database. The demo JWT expires after one hour; rerun the
idempotent seed command to rotate the keys and create a fresh token.

The script refuses to run unless both `ENVIRONMENT=development` and
`APP_ENV=development` are set. When environment-backed dev passwords are not
provided, it prints a prominent warning before using clearly labelled,
insecure password fallbacks. API keys and signing material are randomly
generated unless explicitly supplied through the corresponding
`AEGIS_DEV_*` environment variables.

## 3. Start the echo service

In a third terminal:

```bash
cd /Users/htunkhainglynn/Projects/aegis
ECHO_PORT=9000 python3 poc/echo-service/server.py
```

Direct health-style check:

```bash
curl -i http://localhost:9000/api/echo
```

## 4. Start the Reverse Proxy

In a fourth terminal:

```bash
cd /Users/htunkhainglynn/Projects/aegis
set -a
. ./.env
set +a
export BACKEND_URL="http://localhost:9000"
export CONTROL_PLANE_URL="http://localhost:${CONTROL_PLANE_PORT}"
export REDIS_ADDR="localhost:${REDIS_PORT}"
export LISTEN_ADDR=":${PROXY_PORT:-8080}"

cd reverse-proxy
go run ./cmd/proxy
```

Wait about two seconds for the initial policy snapshot. The following commands
assume the default proxy address:

```bash
export AEGIS_PROXY_URL="http://localhost:${PROXY_PORT:-8080}"
```

If another local service occupies port 8080, set `PROXY_PORT=8082` (or the
port printed by `make run`) and update the Postman `proxy_base_url` variable to
the same URL.

## 5. Manual verification

You can run the same POC checks from Postman by importing:

```text
poc/aegis-poc.postman_collection.json
```

Run **0. Prepare Demo Data / Seed / Rotate Dev Data** first. That request
stores fresh `consumer1_key`, `consumer1_revoked_key`, `consumer2_key`, and
`demo_jwt` collection variables automatically. Then run the scope, defense,
and rate-limit folders in order.

### Valid consumer1 key reaches the echo service

```bash
curl -i \
  -H "X-API-Key: ${AEGIS_CONSUMER1_KEY}" \
  -H "Authorization: Bearer ${AEGIS_DEMO_JWT}" \
  -H "X-POC-Marker: consumer1-valid" \
  "${AEGIS_PROXY_URL}/api/echo"
```

Expected: HTTP `200`, a current `timestamp`, and `X-POC-Marker` in the echoed
headers. `X-API-Key` and `Authorization` must not appear because the proxy
strips credentials before forwarding.

### Revoked consumer1 key is rejected before forwarding

```bash
curl -i \
  -H "X-API-Key: ${AEGIS_CONSUMER1_REVOKED_KEY}" \
  -H "Authorization: Bearer ${AEGIS_DEMO_JWT}" \
  "${AEGIS_PROXY_URL}/api/echo"
```

Expected: HTTP `403` with `API_KEY_REVOKED`. The echo service terminal must not
show a corresponding request.

### Missing API key is rejected

```bash
curl -i \
  -H "Authorization: Bearer ${AEGIS_DEMO_JWT}" \
  "${AEGIS_PROXY_URL}/api/echo"
```

Expected: HTTP `401` with `API_KEY_MISSING`, and no echo-service request.

### Consumer1 triggers its 3 requests / 10 seconds rule

Wait 10 seconds after any earlier consumer1 request, then run:

```bash
for request_number in 1 2 3 4 5; do
  printf "consumer1 request %s -> " "${request_number}"
  curl -sS -o /dev/null -w "HTTP %{http_code}\n" \
    -H "X-API-Key: ${AEGIS_CONSUMER1_KEY}" \
    -H "Authorization: Bearer ${AEGIS_DEMO_JWT}" \
    "${AEGIS_PROXY_URL}/api/echo"
done
```

Expected: the first three requests return `200`; later requests return `429`.
The counter lives in Redis, so the result is shared by proxy instances.

### Consumer2 is isolated from consumer1's per-key rule

```bash
for request_number in 1 2 3 4 5; do
  printf "consumer2 request %s -> " "${request_number}"
  curl -sS -o /dev/null -w "HTTP %{http_code}\n" \
    -H "X-API-Key: ${AEGIS_CONSUMER2_KEY}" \
    -H "Authorization: Bearer ${AEGIS_DEMO_JWT}" \
    "${AEGIS_PROXY_URL}/api/echo"
done
```

Expected: all five return `200`. Consumer2 does not match consumer1's
API-key-scoped rule; it uses the separate `/api/echo` route rule
(`10 requests / 10 seconds`).

## Stop the POC

Press `Ctrl+C` in the Control Plane, echo-service, and proxy terminals, then:

```bash
cd /Users/htunkhainglynn/Projects/aegis
docker compose stop postgres redis
```
