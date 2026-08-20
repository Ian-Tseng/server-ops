from __future__ import annotations

import http.client
import json
import time
from dataclasses import asdict, dataclass
from urllib.parse import urlsplit

from .models import HealthSpec


MAX_BODY = 64 * 1024


@dataclass(frozen=True)
class HealthResult:
    state: str
    status: int | None
    elapsed_ms: int
    predicate: str
    detail: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def probe_health(spec: HealthSpec) -> HealthResult:
    parsed = urlsplit(spec.url)
    timeout = spec.timeout_ms / 1000.0
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    started = time.monotonic()
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=timeout)
    try:
        connection.request("GET", path, headers={"Connection": "close", "User-Agent": "local-server-ops/0.1"})
        response = connection.getresponse()
        body = response.read(MAX_BODY + 1)
        elapsed = int((time.monotonic() - started) * 1000)
        if len(body) > MAX_BODY:
            return HealthResult("unhealthy", response.status, elapsed, "body_limit", "response exceeded 64 KiB")
        if 300 <= response.status <= 399:
            return HealthResult("unhealthy", response.status, elapsed, "redirect", "redirect responses are not accepted")
        if response.status != spec.expected_status:
            return HealthResult("unhealthy", response.status, elapsed, "status", f"expected {spec.expected_status}")
        if spec.expected_body is not None:
            expected = spec.expected_body.encode("utf-8")
            if body != expected:
                return HealthResult("unhealthy", response.status, elapsed, "exact_body", "body did not match")
            return HealthResult("healthy", response.status, elapsed, "exact_body", "status and body matched")
        if spec.json_scalar_configured:
            try:
                actual = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return HealthResult("unhealthy", response.status, elapsed, "json_scalar", "body was not valid JSON")
            if isinstance(actual, (dict, list)) or type(actual) is not type(spec.expected_json_scalar) or actual != spec.expected_json_scalar:
                return HealthResult("unhealthy", response.status, elapsed, "json_scalar", "JSON scalar did not match")
            return HealthResult("healthy", response.status, elapsed, "json_scalar", "status and JSON scalar matched")
        return HealthResult("healthy", response.status, elapsed, "status", "status matched")
    except (OSError, http.client.HTTPException, TimeoutError) as exc:
        elapsed = int((time.monotonic() - started) * 1000)
        return HealthResult("unhealthy", None, elapsed, "connection", f"{type(exc).__name__}: {exc}")
    finally:
        connection.close()
