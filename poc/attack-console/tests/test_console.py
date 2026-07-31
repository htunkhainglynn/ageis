"""Tests for the local-only Aegis attack/defense console."""

from __future__ import annotations

import importlib.util
import json
import threading
import urllib.error
import urllib.request
from html.parser import HTMLParser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import ModuleType

CONSOLE_ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = CONSOLE_ROOT / "index.html"


def load_console_server() -> ModuleType:
    """Load the standalone launcher without making the POC a package."""
    server_path = CONSOLE_ROOT / "serve.py"
    spec = importlib.util.spec_from_file_location("aegis_attack_console", server_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load attack console server module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ElementCollector(HTMLParser):
    """Collect IDs and button labels from the self-contained console page."""

    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.button_ids: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        element_id = attributes.get("id")
        if element_id:
            self.ids.add(element_id)
            if tag == "button":
                self.button_ids.add(element_id)


class FakeProxyHandler(BaseHTTPRequestHandler):
    """Model the proxy statuses needed to verify the constrained relay."""

    def _respond(self, status: HTTPStatus, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path != "/api/echo":
            self._respond(HTTPStatus.NOT_FOUND, {"status": "error"})
            return
        key = self.headers.get("X-API-Key", "")
        if not key or key == "not-an-aegis-key":
            self._respond(HTTPStatus.UNAUTHORIZED, {"errorCode": "API_KEY_INVALID"})
        elif key == "test-revoked-key":
            self._respond(HTTPStatus.FORBIDDEN, {"errorCode": "API_KEY_REVOKED"})
        else:
            self._respond(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "timestamp": "2026-07-31T00:00:00+00:00",
                    "headers": {"X-Poc-Console": "attack-defense"},
                },
            )

    def log_message(self, message: str, *args: object) -> None:
        del message, args


def start_server(server: ThreadingHTTPServer) -> threading.Thread:
    """Start a test HTTP server and return its daemon thread."""
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread


def stop_server(server: ThreadingHTTPServer, thread: threading.Thread) -> None:
    """Stop and join a test HTTP server."""
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def test_single_page_contains_every_required_scenario_and_no_raw_credentials() -> None:
    """The static artifact exposes the complete UI without committing keys."""
    html = INDEX_PATH.read_text()
    collector = ElementCollector()
    collector.feed(html)

    assert collector.button_ids.issuperset(
        {
            "valid-request",
            "revoked-key",
            "no-api-key",
            "malformed-key",
            "flood-test",
            "cross-consumer",
            "clear-log",
        }
    )
    assert collector.ids.issuperset(
        {
            "proxy-url",
            "key-profile",
            "selected-key",
            "demo-jwt",
            "flood-progress",
            "pass-summary",
            "results-body",
        }
    )
    assert "expectedStatuses: [200]" in html
    assert "expectedStatuses: [403]" in html
    assert "expectedStatuses: [401]" in html
    assert "const expectedStatus = index <= 3 ? 200 : 429" in html
    assert "AEGIS_CONSUMER1_KEY" in html
    assert "AEGIS_CONSUMER1_REVOKED_KEY" in html
    assert "AEGIS_CONSUMER2_KEY" in html
    assert "AEGIS_DEMO_JWT" in html
    assert "ak_test" not in html
    assert "eyJhbGci" not in html


def test_relay_rejects_every_non_loopback_or_non_base_target() -> None:
    """The helper cannot be repurposed to target remote systems or arbitrary paths."""
    module = load_console_server()
    for url in (
        "https://example.com:8080",
        "http://localhost.evil.example:8080",
        "http://localhost:8080/admin",
        "http://user:pass@localhost:8080",
        "file:///tmp/socket",
    ):
        try:
            module.normalize_loopback_proxy_url(url)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Unsafe proxy target was accepted: {url}")

    assert module.normalize_loopback_proxy_url("http://127.0.0.1:8080/") == (
        "http://127.0.0.1:8080"
    )


def test_probe_preserves_defense_statuses_without_exposing_credentials() -> None:
    """The relay returns proxy decisions and the successful echo proof as JSON."""
    module = load_console_server()
    proxy = ThreadingHTTPServer(("127.0.0.1", 0), FakeProxyHandler)
    proxy_thread = start_server(proxy)
    base_url = f"http://127.0.0.1:{proxy.server_port}"
    try:
        valid = module.run_probe(base_url, "test-active-key", "test.jwt.value")
        revoked = module.run_probe(base_url, "test-revoked-key", "test.jwt.value")
        missing = module.run_probe(base_url, "", "test.jwt.value")
        malformed = module.run_probe(base_url, "not-an-aegis-key", "test.jwt.value")

        assert valid["proxy_status"] == 200
        assert valid["body"]["status"] == "ok"
        assert "X-API-Key" not in valid["body"]["headers"]
        assert "Authorization" not in valid["body"]["headers"]
        assert revoked["proxy_status"] == 403
        assert missing["proxy_status"] == 401
        assert malformed["proxy_status"] == 401
        assert "test-active-key" not in json.dumps(valid)
        assert "test.jwt.value" not in json.dumps(valid)
    finally:
        stop_server(proxy, proxy_thread)


def test_console_launcher_serves_page_and_same_origin_probe() -> None:
    """One command serves both the static page and its localhost-only probe."""
    module = load_console_server()
    proxy = ThreadingHTTPServer(("127.0.0.1", 0), FakeProxyHandler)
    console = module.create_server("127.0.0.1", 0)
    proxy_thread = start_server(proxy)
    console_thread = start_server(console)
    try:
        console_url = f"http://127.0.0.1:{console.server_port}"
        with urllib.request.urlopen(console_url, timeout=2) as response:
            page = response.read().decode()
        assert response.status == 200
        assert "Aegis attack / defense console" in page

        request_body = json.dumps(
            {
                "proxyBaseUrl": f"http://127.0.0.1:{proxy.server_port}",
                "apiKey": "test-revoked-key",
                "jwt": "test.jwt.value",
            }
        ).encode()
        request = urllib.request.Request(
            f"{console_url}/__aegis_probe",
            data=request_body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            result = json.load(response)
        assert response.status == 200
        assert result["relay"] is True
        assert result["proxy_status"] == 403
    finally:
        stop_server(console, console_thread)
        stop_server(proxy, proxy_thread)
