from __future__ import annotations

import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Iterator

import pytest

from server_ops.health import MAX_BODY, probe_health
from server_ops.models import HealthSpec


@contextmanager
def server(status: int, body: bytes, *, headers: dict[str, str] | None = None) -> Iterator[str]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(status)
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args) -> None:
            return

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=lambda: httpd.serve_forever(poll_interval=0.01), daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}/health"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def test_exact_body_health_passes() -> None:
    with server(200, b"OK") as url:
        result = probe_health(HealthSpec(url, expected_body="OK"))
    assert result.state == "healthy"
    assert result.predicate == "exact_body"


def test_wrong_service_http_200_fails_exact_body() -> None:
    with server(200, b"SOME OTHER SERVICE") as url:
        result = probe_health(HealthSpec(url, expected_body="OK"))
    assert result.state == "unhealthy"
    assert result.predicate == "exact_body"


def test_redirect_is_not_followed() -> None:
    with server(302, b"", headers={"Location": "http://127.0.0.1:1/health"}) as url:
        result = probe_health(HealthSpec(url, expected_status=200))
        configured_redirect = probe_health(HealthSpec(url, expected_status=302))
    assert result.state == "unhealthy"
    assert result.status == 302
    assert configured_redirect.state == "unhealthy"
    assert configured_redirect.predicate == "redirect"


def test_oversized_response_fails_boundedly() -> None:
    with server(200, b"x" * (MAX_BODY + 1)) as url:
        result = probe_health(HealthSpec(url))
    assert result.state == "unhealthy"
    assert result.predicate == "body_limit"


@pytest.mark.parametrize(
    ("body", "expected", "healthy"),
    [(b"true", True, True), (b"1", True, False), (b'"ready"', "ready", True), (b"null", None, True)],
)
def test_json_scalar_requires_exact_type_and_value(body: bytes, expected, healthy: bool) -> None:
    with server(200, body) as url:
        result = probe_health(HealthSpec(url, expected_json_scalar=expected, json_scalar_configured=True))
    assert (result.state == "healthy") is healthy
