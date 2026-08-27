"""Tests for the standalone echo-service POC."""

from __future__ import annotations

import importlib.util
import json
import threading
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from types import ModuleType


def load_server_module() -> ModuleType:
    """Load the hyphenated POC directory without turning it into a package."""
    server_path = Path(__file__).resolve().parents[1] / "server.py"
    spec = importlib.util.spec_from_file_location("aegis_echo_poc", server_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load echo-service server module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_echo_route_returns_headers_and_timestamp() -> None:
    """The sole success route returns observable upstream request data."""
    module = load_server_module()
    server = module.create_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}/api/echo",
            headers={"X-POC-Marker": "reached-upstream"},
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            payload = json.load(response)

        assert response.status == 200
        assert payload["status"] == "ok"
        assert payload["resource"] == "echo"
        assert payload["method"] == "GET"
        assert payload["headers"]["X-Poc-Marker"] == "reached-upstream"
        assert datetime.fromisoformat(payload["timestamp"]).tzinfo is not None
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_echo_route_accepts_post_for_write_scope_demo() -> None:
    """POST /api/echo gives the proxy POC a write-scope upstream target."""
    module = load_server_module()
    server = module.create_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}/api/echo",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            payload = json.load(response)

        assert response.status == 200
        assert payload["status"] == "ok"
        assert payload["resource"] == "echo"
        assert payload["method"] == "POST"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_orders_route_returns_resource_marker() -> None:
    """GET /api/orders is a second resource for resource:action scope demos."""
    module = load_server_module()
    server = module.create_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{server.server_port}/api/orders",
            timeout=2,
        ) as response:
            payload = json.load(response)

        assert response.status == 200
        assert payload["status"] == "ok"
        assert payload["resource"] == "orders"
        assert payload["method"] == "GET"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_unknown_route_returns_json_404() -> None:
    """Any route outside the explicit POC surface is rejected."""
    module = load_server_module()
    server = module.create_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        try:
            urllib.request.urlopen(
                f"http://127.0.0.1:{server.server_port}/unknown",
                timeout=2,
            )
        except urllib.error.HTTPError as exc:
            payload = json.load(exc)
            assert exc.code == 404
            assert payload["status"] == "error"
        else:
            raise AssertionError("Unknown route unexpectedly succeeded.")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
