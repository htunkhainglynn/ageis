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
export POLICY_CACHE_TTL=5m
export GRPC_SYNC_INTERVAL_SECONDS=0.25
export GRPC_RECONNECT_DELAY=0.25s
export AUTO_IP_BLOCK_ENABLED=true
export AUTO_IP_BLOCK_THRESHOLD=2
export AUTO_IP_BLOCK_WINDOW_SECONDS=300

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
echo "[PASS] Health: Control Plane 200; PostgreSQL=up; Redis=up"

dashboard_code=$(request "$TMP_DIR/dashboard.html" "$DASHBOARD_URL/login")
[ "$dashboard_code" = "200" ] || fail "Dashboard login returned HTTP $dashboard_code"
grep -q "Sign in to Aegis" "$TMP_DIR/dashboard.html" ||
  fail "Dashboard login content is missing"
echo "[PASS] Dashboard: login page returned 200 with expected content"

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
echo "[PASS] Identity: valid admin login returned 200 and an access token"

api_key_code=$(request "$TMP_DIR/api-key.json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"E2E key","scopes":["upstream:read"]}' \
  "$CONTROL_URL/api/v1/api-keys")
[ "$api_key_code" = "201" ] || fail "API-key creation returned HTTP $api_key_code"
RAW_API_KEY=$(jq -er '.data.api_key' "$TMP_DIR/api-key.json")
echo "[PASS] API key: create returned 201 with scope upstream:read and one-time secret"

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
echo "[PASS] API key: a second key was created and revoked through the Control Plane"

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
echo "[PASS] JWT policy: HS256 configuration created and activated"

threat_code=$(request "$TMP_DIR/threat-rule.json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"E2E traversal","pattern":"e2e-threat","severity":"high","status":"active"}' \
  "$CONTROL_URL/api/v1/threat-rules")
[ "$threat_code" = "201" ] || fail "Threat-rule creation returned HTTP $threat_code"
echo "[PASS] Threat policy: active request-target rule created"

CLIENT_JWT=$(compose exec -T \
  -e E2E_JWT_SIGNING_KEY="$E2E_JWT_SIGNING_KEY" \
  control-plane \
  python -c 'import os,time; from jose import jwt; print(jwt.encode({"sub":"e2e-client","iss":"aegis-e2e","aud":"aegis-upstream","exp":int(time.time())+300}, os.environ["E2E_JWT_SIGNING_KEY"], algorithm="HS256"))')

sleep 2

PROXY_CLIENT_IP=$(compose exec -T control-plane \
  python -c 'import socket; print(socket.gethostbyname(socket.gethostname()))')
grpc_prime_code=$(compose exec -T \
  -e E2E_API_KEY="$RAW_API_KEY" \
  -e E2E_CLIENT_JWT="$CLIENT_JWT" \
  control-plane \
  python -c '
import os
import urllib.request

request = urllib.request.Request(
    "http://reverse-proxy:8080/",
    headers={
        "X-API-Key": os.environ["E2E_API_KEY"],
        "Authorization": "Bearer " + os.environ["E2E_CLIENT_JWT"],
    },
)
print(urllib.request.urlopen(request).status)
')
[ "$grpc_prime_code" = "200" ] ||
  fail "gRPC policy priming request returned HTTP $grpc_prime_code"
echo "[PASS] Policy distribution: authenticated gRPC snapshot enabled a 200 upstream response"

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

sleep 1

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
echo "[PASS] IP enforcement: exact direct-peer block returned 403 IP_BLOCKED"

unblock_code=$(request "$TMP_DIR/unblock.json" \
  -X DELETE \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  "$CONTROL_URL/api/v1/ip-blocks/$IP_BLOCK_ID")
[ "$unblock_code" = "200" ] || fail "IP-block disable returned HTTP $unblock_code"

sleep 2

threat_match_code=$(request "$TMP_DIR/threat-match.json" \
  -H "X-API-Key: $RAW_API_KEY" \
  -H "Authorization: Bearer $CLIENT_JWT" \
  "$PROXY_URL/e2e-threat")
[ "$threat_match_code" = "403" ] || fail "Threat-matching request returned HTTP $threat_match_code"
jq -e '.errorCode == "THREAT_DETECTED"' "$TMP_DIR/threat-match.json" >/dev/null ||
  fail "Threat detection error contract is incorrect"
echo "[PASS] Threat enforcement: matching request returned 403 THREAT_DETECTED"

rate_code=$(request "$TMP_DIR/rate.json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"E2E global","scope_type":"global","scope_value":null,"algorithm":"fixed_window","limit_count":2,"window_seconds":60,"status":"active"}' \
  "$CONTROL_URL/api/v1/rate-limit-rules")
[ "$rate_code" = "201" ] || fail "Rate-rule creation returned HTTP $rate_code"
echo "[PASS] Rate policy: global fixed-window rule (2 requests / 60 seconds) created"

sleep 2

invalid_key_code=$(request "$TMP_DIR/invalid-key.json" \
  -H "X-API-Key: ak_invalid_e2e_key" \
  -H "Authorization: Bearer $CLIENT_JWT" \
  "$PROXY_URL/")
[ "$invalid_key_code" = "401" ] || fail "Invalid API key returned HTTP $invalid_key_code"
echo "[PASS] Authentication: invalid API key returned 401"

invalid_jwt_code=$(request "$TMP_DIR/invalid-jwt.json" \
  -H "X-API-Key: $RAW_API_KEY" \
  -H "Authorization: Bearer invalid.jwt.value" \
  "$PROXY_URL/")
[ "$invalid_jwt_code" = "401" ] || fail "Invalid JWT returned HTTP $invalid_jwt_code"
echo "[PASS] Authentication: invalid JWT returned 401"

revoked_code=$(request "$TMP_DIR/revoked.json" \
  -H "X-API-Key: $REVOKED_API_KEY" \
  -H "Authorization: Bearer $CLIENT_JWT" \
  "$PROXY_URL/")
[ "$revoked_code" = "403" ] || fail "Revoked API key returned HTTP $revoked_code"
echo "[PASS] Authorisation: revoked API key returned 403"

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
echo "[PASS] Rate enforcement: request statuses were 200, 200, 429 RATE_LIMIT_EXCEEDED"

analytics_attempts=30
while [ "$analytics_attempts" -gt 0 ]; do
  analytics_code=$(request "$TMP_DIR/analytics.json" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    "$CONTROL_URL/api/v1/analytics/summary?hours=1")
  if [ "$analytics_code" = "200" ] &&
    jq -e '
      .data.total_requests >= 8 and
      .data.events_by_type.ip_blocked >= 1 and
      .data.events_by_type.threat_detected >= 1 and
      .data.events_by_type.request_forwarded >= 2 and
      .data.events_by_type.rate_limited >= 1
    ' "$TMP_DIR/analytics.json" >/dev/null; then
    break
  fi
  analytics_attempts=$((analytics_attempts - 1))
  sleep 1
done
[ "$analytics_attempts" -gt 0 ] ||
  fail "Proxy events did not appear in analytics within 30 seconds"
echo "[PASS] Analytics: forwarded, blocked, threat and rate-limit events were aggregated"

sleep 1

auto_block_code=$(request "$TMP_DIR/auto-blocked.json" \
  -H "X-API-Key: $RAW_API_KEY" \
  -H "Authorization: Bearer $CLIENT_JWT" \
  "$PROXY_URL/")
[ "$auto_block_code" = "403" ] ||
  fail "Automatically blocked source returned HTTP $auto_block_code"
jq -e '.errorCode == "IP_BLOCKED"' "$TMP_DIR/auto-blocked.json" >/dev/null ||
  fail "Automatic IP-block enforcement contract is incorrect"
echo "[PASS] Automatic protection: repeated violations produced 403 IP_BLOCKED"

blocks_code=$(request "$TMP_DIR/ip-blocks.json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  "$CONTROL_URL/api/v1/ip-blocks?status=active&limit=100")
[ "$blocks_code" = "200" ] || fail "IP-block listing returned HTTP $blocks_code"
jq -e '.data.items | any(.source == "auto" and .status == "active")' \
  "$TMP_DIR/ip-blocks.json" >/dev/null ||
  fail "Automatic IP block was not persisted by the Control Plane"
echo "[PASS] Persistence: the automatic active IP block appears in Control Plane data"

echo "E2E passed: Control Plane -> gRPC policy sync -> reverse proxy -> upstream, including auth, threat/manual/automatic IP blocking, Redis rate limiting, and analytics."
