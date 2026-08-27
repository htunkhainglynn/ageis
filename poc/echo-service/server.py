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
    """Serve tiny JSON endpoints without external dependencies."""

    server_version = "AegisEchoPOC/1.0"

    def _write_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, sort_keys=True).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_echo(self, resource: str) -> None:
        if self.path not in {"/api/echo", "/api/orders"}:
            self._write_json(
                HTTPStatus.NOT_FOUND,
                {
                    "status": "error",
                    "message": "Only GET/POST /api/echo or GET /api/orders is available.",
                },
            )
            return

        self._write_json(
            HTTPStatus.OK,
            {
                "resource": resource,
                "status": "ok",
                "method": self.command,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "headers": dict(self.headers.items()),
            },
        )

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        resource = "orders" if self.path == "/api/orders" else "echo"
        self._handle_echo(resource)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        self._handle_echo("echo")

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
