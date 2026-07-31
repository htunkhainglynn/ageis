# Aegis Attack / Defense Console

This is a local, defensive proof-of-concept for your own Aegis Reverse Proxy.
It sends only `GET /api/echo` requests to explicit loopback addresses and is
never part of the React Dashboard or a production deployment.

## Prerequisites

Complete the setup in [`poc/README.md`](../README.md):

1. Start PostgreSQL, Redis, and the Control Plane in development mode.
2. Run `scripts/seed_dev_data.py` and keep its four `export AEGIS_...` lines.
3. Start `poc/echo-service/server.py` on port `9000`.
4. Start the Go Reverse Proxy with `BACKEND_URL=http://localhost:9000`.

Keep `AUTO_IP_BLOCK_ENABLED=false` while demonstrating rate-scope isolation,
or leave the console's flood count at its safe default of five. Larger floods
can correctly activate the project's automatic IP-block defense, which would
also block the consumer2 follow-up from the same local address.

## Run the console

From the repository root:

```bash
python3 poc/attack-console/serve.py
```

Open [http://127.0.0.1:9100](http://127.0.0.1:9100), paste the latest seed
script output, and click **Load seed values**. No installation or build is
required.

The small launcher is needed because browsers normally hide cross-origin
`401`, `403`, and `429` responses when the proxy does not attach CORS headers.
It serves the one static HTML file and provides a same-origin relay constrained
to loopback proxy URLs and the fixed `/api/echo` route. It cannot target remote
hosts, change the HTTP method, or choose arbitrary paths. Credentials remain in
browser memory and are not written or logged.

You can open `index.html` directly, but browser CORS rules may turn blocked
responses into an unhelpful network error. The launcher above is the reliable
one-line option.

## What each button proves

| Button | Expected result | Defense demonstrated |
|---|---:|---|
| Valid Request | `200` | A valid consumer1 API key and JWT reach the echo service; credentials are stripped before forwarding. |
| Revoked Key | `403` | A soft-revoked API key is rejected before reaching the backend. |
| No API Key | `401` | The proxy requires an API key. |
| Malformed Key | `401` | An unknown garbage key cannot authenticate. |
| Flood | First three `200`, then `429` | Consumer1's `3 requests / 10 seconds` Redis-backed rule is enforced. |
| Cross-Consumer Check | `200` | Consumer2 is not charged against consumer1's API-key-scoped counter. |

The flood waits for a clean 10-second consumer1 rate window when the console
has sent a recent consumer1 request. Run **Cross-Consumer Check** immediately
after it finishes.

## Stop

Press `Ctrl+C` in the console, echo-service, Control Plane, and Reverse Proxy
terminals. Stop PostgreSQL and Redis as described in the parent POC README.
