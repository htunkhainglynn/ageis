#!/usr/bin/env python3
"""Serve the local Aegis console with a tightly scoped same-origin probe relay."""

from __future__ import annotations

import json
import os
import subprocess
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

INDEX_PATH = Path(__file__).with_name("index.html")
REPO_ROOT = INDEX_PATH.parents[2]
PYTHON = REPO_ROOT / "aegis-backend" / ".venv" / "bin" / "python"
MAX_REQUEST_BYTES = 32_768
MAX_RESPONSE_BYTES = 65_536


class NoRedirectHandler(HTTPRedirectHandler):
    """Prevent a local proxy response from redirecting the relay elsewhere."""

    def redirect_request(
        self,
        request: Request,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> None:
        del request, file_pointer, code, message, headers, new_url
        return None


def normalize_loopback_proxy_url(raw_url: str) -> str:
    """Accept only an HTTP(S) base URL with an explicit loopback hostname."""
    parsed = urlsplit(raw_url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Proxy URL must use http or https.")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Proxy URL must not contain credentials.")
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Only localhost Reverse Proxy targets are allowed.")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("Proxy URL must be a base URL without path, query, or fragment.")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Proxy URL contains an invalid port.") from exc
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("Proxy URL contains an invalid port.")
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", "")).rstrip("/")


def run_probe(
    proxy_base_url: str,
    api_key: str,
    jwt_token: str,
    method: str = "GET",
    timeout_seconds: float = 5,
) -> dict[str, Any]:
    """Send the console's one permitted request to the local Reverse Proxy."""
    base_url = normalize_loopback_proxy_url(proxy_base_url)
    method = method.upper()
    if method not in {"GET", "POST"}:
        raise ValueError("Probe method must be GET or POST.")
    headers = {"Accept": "application/json", "X-POC-Console": "attack-defense"}
    if api_key:
        headers["X-API-Key"] = api_key
    if jwt_token:
        headers["Authorization"] = f"Bearer {jwt_token}"
    data = b'{"poc":"write-scope"}' if method == "POST" else None
    if data is not None:
        headers["Content-Type"] = "application/json"

    request = Request(f"{base_url}/api/echo", data=data, headers=headers, method=method)
    opener = build_opener(NoRedirectHandler())
    status = 0
    response_headers: dict[str, str] = {}
    raw_body = b""
    error_message: str | None = None
    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            status = response.status
            response_headers = dict(response.headers.items())
            raw_body = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        status = exc.code
        response_headers = dict(exc.headers.items())
        raw_body = exc.read(MAX_RESPONSE_BYTES + 1)
    except (URLError, TimeoutError, OSError) as exc:
        error_message = f"Local proxy request failed: {exc.reason if isinstance(exc, URLError) else exc}"

    if len(raw_body) > MAX_RESPONSE_BYTES:
        raw_body = raw_body[:MAX_RESPONSE_BYTES]
        error_message = "Proxy response was truncated at 64 KiB."

    try:
        body: Any = json.loads(raw_body) if raw_body else None
    except json.JSONDecodeError:
        body = {"unparsed_body": raw_body.decode(errors="replace")}

    return {
        "relay": True,
        "proxy_status": status,
        "body": body,
        "response_content_type": response_headers.get("Content-Type", ""),
        "error": error_message,
    }


def run_dev_script(script_name: str) -> dict[str, Any]:
    """Run one approved dev-only helper script with the current local env."""
    if script_name not in {"seed_dev_data.py", "list_dev_data.py"}:
        raise ValueError("Unsupported dev helper script.")
    python = PYTHON if PYTHON.exists() else Path("python3")
    env = os.environ.copy()
    env.setdefault("APP_ENV", "development")
    env.setdefault("ENVIRONMENT", "development")
    if env.get("APP_ENV") != "development" or env.get("ENVIRONMENT") != "development":
        raise ValueError("Dev helper scripts require APP_ENV=development and ENVIRONMENT=development.")

    result = subprocess.run(
        [str(python), str(REPO_ROOT / "scripts" / script_name)],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    stderr = filter_helper_stderr(result.stderr)
    return {
        "ok": result.returncode == 0,
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": stderr,
    }


def filter_helper_stderr(stderr: str) -> str:
    """Hide noisy passlib/bcrypt compatibility chatter from presenter output."""
    if "error reading bcrypt version" not in stderr:
        return stderr
    lines = stderr.splitlines()
    filtered: list[str] = []
    skipping = False
    for line in lines:
        if "(trapped) error reading bcrypt version" in line:
            skipping = True
            continue
        if skipping and line.startswith("AttributeError:"):
            skipping = False
            continue
        if not skipping:
            filtered.append(line)
    return "\n".join(filtered).strip()


class ConsoleHandler(BaseHTTPRequestHandler):
    """Serve only the console page and its constrained probe endpoint."""

    server_version = "AegisAttackConsolePOC/1.0"

    def _write_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path == "/__aegis_list":
            try:
                result = run_dev_script("list_dev_data.py")
            except (ValueError, subprocess.TimeoutExpired) as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            self._write_json(HTTPStatus.OK if result["ok"] else HTTPStatus.BAD_GATEWAY, result)
            return

        if self.path not in {"/", "/index.html"}:
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return
        body = INDEX_PATH.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path == "/__aegis_seed":
            try:
                result = run_dev_script("seed_dev_data.py")
            except (ValueError, subprocess.TimeoutExpired) as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            self._write_json(HTTPStatus.OK if result["ok"] else HTTPStatus.BAD_GATEWAY, result)
            return

        if self.path != "/__aegis_probe":
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            content_length = 0
        if not 0 < content_length <= MAX_REQUEST_BYTES:
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid request size."})
            return

        try:
            payload = json.loads(self.rfile.read(content_length))
            if not isinstance(payload, dict):
                raise ValueError("Request body must be a JSON object.")
            result = run_probe(
                proxy_base_url=str(payload.get("proxyBaseUrl", "")),
                api_key=str(payload.get("apiKey", "")),
                jwt_token=str(payload.get("jwt", "")),
                method=str(payload.get("method", "GET")),
            )
        except (json.JSONDecodeError, ValueError) as exc:
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        self._write_json(HTTPStatus.OK, result)

    def log_message(self, message: str, *args: object) -> None:
        """Log request lines only; credentials are never included."""
        print(f"{self.address_string()} - {message % args}")


def create_server(host: str, port: int) -> ThreadingHTTPServer:
    """Create a loopback-only console server for runtime and tests."""
    if host not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Attack console must bind to a loopback host.")
    return ThreadingHTTPServer((host, port), ConsoleHandler)


def main() -> None:
    host = os.getenv("ATTACK_CONSOLE_HOST", "127.0.0.1")
    port = int(os.getenv("ATTACK_CONSOLE_PORT", "9100"))
    server = create_server(host, port)
    print(f"Aegis attack console: http://{host}:{server.server_port}")
    print("The relay accepts only local Reverse Proxy /api/echo probes.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Aegis attack console.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
