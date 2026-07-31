#!/usr/bin/env python3
"""Minimal disposable upstream used to demonstrate Aegis proxy forwarding."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class EchoHandler(BaseHTTPRequestHandler):
    """Serve one JSON echo endpoint without external dependencies."""

    server_version = "AegisEchoPOC/1.0"

    def _write_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, sort_keys=True).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path != "/api/echo":
            self._write_json(
                HTTPStatus.NOT_FOUND,
                {
                    "status": "error",
                    "message": "Only GET /api/echo is available.",
                },
            )
            return

        self._write_json(
            HTTPStatus.OK,
            {
                "status": "ok",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "headers": dict(self.headers.items()),
            },
        )

    def log_message(self, message: str, *args: object) -> None:
        """Keep standard request logs while never logging request headers."""
        print(f"{self.address_string()} - {message % args}")


def create_server(host: str, port: int) -> ThreadingHTTPServer:
    """Create the HTTP server separately so tests can bind an ephemeral port."""
    return ThreadingHTTPServer((host, port), EchoHandler)


def main() -> None:
    host = os.getenv("ECHO_HOST", "0.0.0.0")
    port = int(os.getenv("ECHO_PORT", "9000"))
    server = create_server(host, port)
    print(f"Aegis echo-service POC listening on http://{host}:{port}/api/echo")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping echo-service POC.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
