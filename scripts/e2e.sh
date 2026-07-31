#!/bin/sh
set -eu

REPO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
COMPOSE_FILE="$REPO_ROOT/compose.yaml"
RUN_ID=$$
PORT_BASE=$((20000 + RUN_ID % 10000))
TMP_DIR=$(mktemp -d "${TMPDIR:-/tmp}/aegis-e2e.XXXXXX")

export COMPOSE_PROJECT_NAME="aegis_e2e_${RUN_ID}"
export POSTGRES_PASSWORD
POSTGRES_PASSWORD=$(openssl rand -hex 24)
export REDIS_PASSWORD
REDIS_PASSWORD=$(openssl rand -hex 24)
export JWT_SECRET_KEY
JWT_SECRET_KEY=$(openssl rand -hex 32)
export JWT_CONFIG_ENCRYPTION_KEY
JWT_CONFIG_ENCRYPTION_KEY=$(python3 -c 'import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())')
export INTERNAL_API_TOKEN
INTERNAL_API_TOKEN=$(openssl rand -hex 32)
export BOOTSTRAP_ADMIN_EMAILS="e2e-admin-${RUN_ID}@example.com"
export BOOTSTRAP_ADMIN_PASSWORD
BOOTSTRAP_ADMIN_PASSWORD="Aa1!$(openssl rand -hex 12)"
export BOOTSTRAP_ADMIN_FULL_NAME="E2E Administrator"
export E2E_JWT_SIGNING_KEY
E2E_JWT_SIGNING_KEY=$(openssl rand -hex 32)
export POSTGRES_PORT=$PORT_BASE
export REDIS_PORT=$((PORT_BASE + 1))
export CONTROL_PLANE_PORT=$((PORT_BASE + 2))
export PROXY_PORT=$((PORT_BASE + 3))
export DASHBOARD_PORT=$((PORT_BASE + 4))
export VALIDATION_CACHE_TTL=1s
export VALIDATION_NEGATIVE_CACHE_TTL=1s
export POLICY_CACHE_TTL=1s

compose() {
  docker compose -f "$COMPOSE_FILE" "$@"
}

cleanup() {
  compose down --volumes --remove-orphans >/dev/null 2>&1 || true
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT INT TERM

fail() {
  echo "E2E failure: $1" >&2
  exit 1
}

request() {
  output_file=$1
  shift
  curl --silent --show-error --output "$output_file" --write-out "%{http_code}" "$@"
}

wait_for_http() {
  url=$1
  attempts=30
  while [ "$attempts" -gt 0 ]; do
    if curl --silent --show-error --fail --output /dev/null "$url" 2>/dev/null; then
      return 0
    fi
    attempts=$((attempts - 1))
    sleep 1
  done
  return 1
}

echo "Building and starting isolated Aegis stack..."
if ! compose up --detach --build --wait >"$TMP_DIR/compose.log" 2>&1; then
  tail -n 200 "$TMP_DIR/compose.log" >&2
  compose ps >&2 || true
  compose logs --no-color --tail 100 >&2 || true
  fail "Docker Compose stack did not become healthy"
fi

CONTROL_URL="http://localhost:${CONTROL_PLANE_PORT}"
PROXY_URL="http://localhost:${PROXY_PORT}"
DASHBOARD_URL="http://localhost:${DASHBOARD_PORT}"

wait_for_http "$DASHBOARD_URL/login" ||
  fail "Dashboard did not become ready within 30 seconds"

health_code=$(request "$TMP_DIR/health.json" "$CONTROL_URL/health")
[ "$health_code" = "200" ] || fail "Control Plane health returned HTTP $health_code"
jq -e '.data.database == "up" and .data.redis == "up"' "$TMP_DIR/health.json" >/dev/null ||
  fail "Control Plane dependencies are not healthy"

dashboard_code=$(request "$TMP_DIR/dashboard.html" "$DASHBOARD_URL/login")
[ "$dashboard_code" = "200" ] || fail "Dashboard login returned HTTP $dashboard_code"
grep -q "Sign in to Aegis" "$TMP_DIR/dashboard.html" ||
  fail "Dashboard login content is missing"

login_payload=$(jq -n \
  --arg email "$BOOTSTRAP_ADMIN_EMAILS" \
  --arg password "$BOOTSTRAP_ADMIN_PASSWORD" \
  '{email:$email,password:$password}')
login_code=$(request "$TMP_DIR/login.json" \
  -H "Content-Type: application/json" \
  -d "$login_payload" \
  "$CONTROL_URL/api/v1/auth/login")
[ "$login_code" = "200" ] || fail "Admin login returned HTTP $login_code"
ACCESS_TOKEN=$(jq -er '.data.access_token' "$TMP_DIR/login.json")

api_key_code=$(request "$TMP_DIR/api-key.json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"E2E key","scopes":["upstream:read"]}' \
  "$CONTROL_URL/api/v1/api-keys")
[ "$api_key_code" = "201" ] || fail "API-key creation returned HTTP $api_key_code"
RAW_API_KEY=$(jq -er '.data.api_key' "$TMP_DIR/api-key.json")

revoked_key_code=$(request "$TMP_DIR/revoked-key.json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"E2E revoked key","scopes":[]}' \
  "$CONTROL_URL/api/v1/api-keys")
[ "$revoked_key_code" = "201" ] || fail "Revocation key creation returned HTTP $revoked_key_code"
REVOKED_API_KEY=$(jq -er '.data.api_key' "$TMP_DIR/revoked-key.json")
REVOKED_KEY_ID=$(jq -er '.data.id' "$TMP_DIR/revoked-key.json")
revoke_code=$(request "$TMP_DIR/revoke.json" \
  -X DELETE \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  "$CONTROL_URL/api/v1/api-keys/$REVOKED_KEY_ID")
[ "$revoke_code" = "200" ] || fail "API-key revocation returned HTTP $revoke_code"

jwt_payload=$(jq -n \
  --arg key "$E2E_JWT_SIGNING_KEY" \
  '{
    name:"E2E JWT",
    algorithm:"HS256",
    signing_key:$key,
    public_key:null,
    issuer:"aegis-e2e",
    audience:"aegis-upstream",
    access_token_ttl_seconds:900,
    refresh_token_ttl_seconds:3600
  }')
jwt_config_code=$(request "$TMP_DIR/jwt-config.json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$jwt_payload" \
  "$CONTROL_URL/api/v1/jwt-configs")
[ "$jwt_config_code" = "201" ] || fail "JWT config creation returned HTTP $jwt_config_code"
JWT_CONFIG_ID=$(jq -er '.data.id' "$TMP_DIR/jwt-config.json")
activate_code=$(request "$TMP_DIR/activate.json" \
  -X POST \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  "$CONTROL_URL/api/v1/jwt-configs/$JWT_CONFIG_ID/activate")
[ "$activate_code" = "200" ] || fail "JWT activation returned HTTP $activate_code"

CLIENT_JWT=$(compose exec -T \
  -e E2E_JWT_SIGNING_KEY="$E2E_JWT_SIGNING_KEY" \
  control-plane \
  python -c 'import os,time; from jose import jwt; print(jwt.encode({"sub":"e2e-client","iss":"aegis-e2e","aud":"aegis-upstream","exp":int(time.time())+300}, os.environ["E2E_JWT_SIGNING_KEY"], algorithm="HS256"))')

sleep 2

PROXY_CLIENT_IP=$(compose exec -T control-plane \
  python -c 'import socket; print(socket.gethostbyname(socket.gethostname()))')
block_payload=$(jq -n \
  --arg ip_address "$PROXY_CLIENT_IP" \
  '{ip_address:$ip_address,reason:"E2E manual block"}')
block_code=$(request "$TMP_DIR/ip-block.json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$block_payload" \
  "$CONTROL_URL/api/v1/ip-blocks")
[ "$block_code" = "201" ] || fail "IP-block creation returned HTTP $block_code"
IP_BLOCK_ID=$(jq -er '.data.id' "$TMP_DIR/ip-block.json")

sleep 2

BLOCKED_RESULT=$(compose exec -T \
  -e E2E_API_KEY="$RAW_API_KEY" \
  -e E2E_CLIENT_JWT="$CLIENT_JWT" \
  control-plane \
  python -c '
import json
import os
import urllib.error
import urllib.request

request = urllib.request.Request(
    "http://reverse-proxy:8080/",
    headers={
        "X-Forwarded-For": "198.51.100.200",
        "X-API-Key": os.environ["E2E_API_KEY"],
        "Authorization": "Bearer " + os.environ["E2E_CLIENT_JWT"],
    },
)
try:
    response = urllib.request.urlopen(request)
    result = {"code": response.status, "body": json.loads(response.read())}
except urllib.error.HTTPError as error:
    result = {"code": error.code, "body": json.loads(error.read())}
print(json.dumps(result))
')
blocked_code=$(printf "%s" "$BLOCKED_RESULT" | jq -r '.code')
printf "%s" "$BLOCKED_RESULT" | jq '.body' >"$TMP_DIR/blocked.json"
[ "$blocked_code" = "403" ] || fail "Blocked direct peer returned HTTP $blocked_code"
jq -e '.errorCode == "IP_BLOCKED"' "$TMP_DIR/blocked.json" >/dev/null ||
  fail "IP-block error contract is incorrect"

unblock_code=$(request "$TMP_DIR/unblock.json" \
  -X DELETE \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  "$CONTROL_URL/api/v1/ip-blocks/$IP_BLOCK_ID")
[ "$unblock_code" = "200" ] || fail "IP-block disable returned HTTP $unblock_code"

rate_code=$(request "$TMP_DIR/rate.json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"E2E global","scope_type":"global","scope_value":null,"algorithm":"fixed_window","limit_count":2,"window_seconds":60,"status":"active"}' \
  "$CONTROL_URL/api/v1/rate-limit-rules")
[ "$rate_code" = "201" ] || fail "Rate-rule creation returned HTTP $rate_code"

sleep 2

invalid_key_code=$(request "$TMP_DIR/invalid-key.json" \
  -H "X-API-Key: ak_invalid_e2e_key" \
  -H "Authorization: Bearer $CLIENT_JWT" \
  "$PROXY_URL/")
[ "$invalid_key_code" = "401" ] || fail "Invalid API key returned HTTP $invalid_key_code"

invalid_jwt_code=$(request "$TMP_DIR/invalid-jwt.json" \
  -H "X-API-Key: $RAW_API_KEY" \
  -H "Authorization: Bearer invalid.jwt.value" \
  "$PROXY_URL/")
[ "$invalid_jwt_code" = "401" ] || fail "Invalid JWT returned HTTP $invalid_jwt_code"

revoked_code=$(request "$TMP_DIR/revoked.json" \
  -H "X-API-Key: $REVOKED_API_KEY" \
  -H "Authorization: Bearer $CLIENT_JWT" \
  "$PROXY_URL/")
[ "$revoked_code" = "403" ] || fail "Revoked API key returned HTTP $revoked_code"

first_code=$(request "$TMP_DIR/first.html" \
  -H "X-API-Key: $RAW_API_KEY" \
  -H "Authorization: Bearer $CLIENT_JWT" \
  "$PROXY_URL/")
second_code=$(request "$TMP_DIR/second.html" \
  -H "X-API-Key: $RAW_API_KEY" \
  -H "Authorization: Bearer $CLIENT_JWT" \
  "$PROXY_URL/")
third_code=$(request "$TMP_DIR/third.json" \
  -H "X-API-Key: $RAW_API_KEY" \
  -H "Authorization: Bearer $CLIENT_JWT" \
  "$PROXY_URL/")

[ "$first_code" = "200" ] || fail "First proxied request returned HTTP $first_code"
[ "$second_code" = "200" ] || fail "Second proxied request returned HTTP $second_code"
[ "$third_code" = "429" ] || fail "Rate-limited request returned HTTP $third_code"
jq -e '.errorCode == "RATE_LIMIT_EXCEEDED"' "$TMP_DIR/third.json" >/dev/null ||
  fail "Rate-limit error contract is incorrect"

echo "E2E passed: Control Plane -> reverse proxy -> upstream, including auth, IP blocking, and Redis rate limiting."
