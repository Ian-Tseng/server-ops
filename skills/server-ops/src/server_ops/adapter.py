from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import stat
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .errors import EXIT_INVALID_INPUT, OpsError
from .models import Adapter, HealthSpec, LaunchSpec, MatchSpec, ServiceSpec, VerificationSpec


ADAPTER_NAME = ".server-ops.json"
SERVICE_ID = re.compile(r"^[a-z][a-z0-9-]{0,62}$")
TOP_KEYS = {"schema_version", "services"}
SERVICE_KEYS = {
    "id", "label", "workspace", "mutation_enabled", "strategy", "match",
    "launch", "health", "verification",
}
MATCH_KEYS = {"argv_contains", "executable", "ports"}
LAUNCH_KEYS = {"argv", "cwd"}
HEALTH_KEYS = {"url", "expected_status", "expected_body", "expected_json_scalar", "timeout_ms"}
VERIFY_KEYS = {"argv", "cwd"}
STRATEGIES = {"read_only", "direct_child", "watchdog_child"}
MAX_ADAPTER_BYTES = 256 * 1024


def _is_link_like(path: Path) -> bool:
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except OSError:
        return False
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return path.is_symlink() or bool(reparse_flag and attributes & reparse_flag)


def _fail(code: str, message: str, next_action: str, **details: Any) -> OpsError:
    return OpsError(code, message, next_action, EXIT_INVALID_INPUT, details)


def _object(value: Any, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _fail("ADAPTER_TYPE", f"{location} must be an object.", "Repair the adapter and run `server-ops validate`.", location=location)
    return value


def _known_keys(value: dict[str, Any], allowed: set[str], location: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise _fail("ADAPTER_UNKNOWN_FIELD", f"{location} contains unsupported fields: {', '.join(unknown)}.", "Remove the fields or migrate the adapter.", location=location, fields=unknown)


def _text(value: Any, location: str, *, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or "\x00" in value:
        raise _fail("ADAPTER_STRING", f"{location} must be a non-empty string of at most {maximum} characters.", "Repair the field and rerun validation.", location=location)
    return value


def _argv(value: Any, location: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not 1 <= len(value) <= 64:
        raise _fail("ADAPTER_ARGV", f"{location} must contain 1-64 arguments.", "Use a JSON argument array; shell strings are not accepted.", location=location)
    return tuple(_text(part, f"{location}[{index}]") for index, part in enumerate(value))


def _inside(root: Path, value: str, location: str) -> Path:
    candidate = (root / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
    try:
        if os.path.commonpath((str(root), str(candidate))) != str(root):
            raise ValueError
    except ValueError:
        raise _fail("PATH_OUTSIDE_WORKSPACE", f"{location} resolves outside the adapter workspace.", "Choose a path inside the workspace.", location=location)
    return candidate


def validate_health_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != "http" or parsed.username or parsed.password or parsed.fragment or parsed.query:
        raise _fail("HEALTH_URL_UNSAFE", "Health URL must be credential-free HTTP without a query or fragment.", "Use a literal loopback HTTP URL.")
    try:
        host = ipaddress.ip_address(parsed.hostname or "")
    except ValueError:
        raise _fail("HEALTH_URL_NOT_LOOPBACK", "Health URL must use literal 127.0.0.1 or ::1; DNS names are not accepted.", "Replace the hostname with a literal loopback address.")
    if str(host) not in {"127.0.0.1", "::1"}:
        raise _fail("HEALTH_URL_NOT_LOOPBACK", "Remote health targets are outside Local Server Ops v1.", "Use a literal loopback address.")
    try:
        port = parsed.port
    except ValueError:
        port = None
    if port is None or not 1 <= port <= 65535:
        raise _fail("HEALTH_URL_PORT", "Health URL must contain an explicit valid port.", "Add the local service port.")


def find_adapter(workspace: Path, explicit: str | None = None) -> Path | None:
    root = workspace.resolve()
    if explicit:
        path = Path(os.path.abspath(explicit))
        try:
            relative = path.relative_to(root)
        except ValueError:
            raise _fail("ADAPTER_OUTSIDE_WORKSPACE", "Explicit adapter is outside the exact workspace root.", "Copy the reviewed adapter into the workspace or select its containing workspace.")
        current = root
        for part in relative.parts:
            current = current / part
            if _is_link_like(current):
                raise _fail("ADAPTER_LINK", "Explicit adapter path must not cross a symlink or reparse point.", "Copy the reviewed adapter into the exact workspace root.")
        if not path.is_file():
            raise _fail("ADAPTER_NOT_FOUND", f"Adapter does not exist: {path}", "Provide an existing adapter path.", path=str(path))
        resolved = path.resolve(strict=True)
        if os.path.commonpath((str(root), str(resolved))) != str(root):
            raise _fail("ADAPTER_OUTSIDE_WORKSPACE", "Explicit adapter is outside the exact workspace root.", "Copy the reviewed adapter into the workspace or select its containing workspace.")
        return path
    path = root / ADAPTER_NAME
    if _is_link_like(path):
        raise _fail("ADAPTER_LINK", "Adapter must be a regular file, not a symlink or reparse point.", "Copy the reviewed adapter into the exact workspace root.")
    return path if path.is_file() else None


def load_adapter(path: Path) -> Adapter:
    if _is_link_like(path):
        raise _fail("ADAPTER_LINK", "Adapter must be a regular file, not a symlink or reparse point.", "Copy the reviewed adapter into the exact workspace root.")
    with path.open("rb") as stream:
        raw = stream.read(MAX_ADAPTER_BYTES + 1)
    if len(raw) > MAX_ADAPTER_BYTES:
        raise _fail("ADAPTER_TOO_LARGE", "Adapter exceeds the 256 KiB limit.", "Reduce the adapter to bounded declarative fields.", size=len(raw))
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _fail("ADAPTER_JSON", f"Adapter is not valid UTF-8 JSON: {exc}", "Repair the JSON and rerun validation.") from exc
    document = _object(document, "adapter")
    _known_keys(document, TOP_KEYS, "adapter")
    if document.get("schema_version") != 1:
        raise _fail("ADAPTER_VERSION", "Only adapter schema_version 1 is supported.", "Run `server-ops migrate --check` or set schema_version to 1.")
    values = document.get("services")
    if not isinstance(values, list) or not 1 <= len(values) <= 64:
        raise _fail("ADAPTER_SERVICES", "services must contain 1-64 service objects.", "Add at least one bounded service definition.")

    adapter_root = path.parent.resolve()
    services: list[ServiceSpec] = []
    seen: set[str] = set()
    for index, raw_service in enumerate(values):
        location = f"services[{index}]"
        service = _object(raw_service, location)
        _known_keys(service, SERVICE_KEYS, location)
        service_id = _text(service.get("id"), f"{location}.id", maximum=63)
        if not SERVICE_ID.fullmatch(service_id):
            raise _fail("SERVICE_ID", f"{location}.id must use lowercase letters, digits, and hyphens.", "Choose an ID such as `web-server`.")
        if service_id in seen:
            raise _fail("SERVICE_DUPLICATE", f"Duplicate service id: {service_id}", "Make every service id unique.")
        seen.add(service_id)
        label = _text(service.get("label", service_id), f"{location}.label", maximum=120)
        workspace = _inside(adapter_root, _text(service.get("workspace", "."), f"{location}.workspace"), f"{location}.workspace")
        mutation_enabled = service.get("mutation_enabled", False)
        if not isinstance(mutation_enabled, bool):
            raise _fail("MUTATION_FLAG", f"{location}.mutation_enabled must be true or false.", "Use a JSON boolean.")
        strategy = service.get("strategy", "read_only")
        if strategy not in STRATEGIES:
            raise _fail("STRATEGY", f"Unsupported lifecycle strategy: {strategy}", "Use read_only, direct_child, or watchdog_child.")

        match_raw = _object(service.get("match", {}), f"{location}.match")
        _known_keys(match_raw, MATCH_KEYS, f"{location}.match")
        argv_contains_raw = match_raw.get("argv_contains", [])
        if not isinstance(argv_contains_raw, list) or len(argv_contains_raw) > 16:
            raise _fail("MATCH_ARGV", f"{location}.match.argv_contains must contain at most 16 strings.", "Reduce the matcher.")
        argv_contains = tuple(_text(item, f"{location}.match.argv_contains", maximum=256) for item in argv_contains_raw)
        executable = match_raw.get("executable")
        if executable is not None:
            executable = _text(executable, f"{location}.match.executable")
        ports_raw = match_raw.get("ports", [])
        if (
            not isinstance(ports_raw, list)
            or len(ports_raw) > 16
            or any(type(port) is not int or not 1 <= port <= 65535 for port in ports_raw)
            or len(set(ports_raw)) != len(ports_raw)
        ):
            raise _fail("MATCH_PORTS", f"{location}.match.ports must contain at most 16 unique valid ports.", "Repair the port list.")
        match = MatchSpec(argv_contains, executable, tuple(ports_raw))

        launch = None
        if "launch" in service:
            launch_raw = _object(service["launch"], f"{location}.launch")
            _known_keys(launch_raw, LAUNCH_KEYS, f"{location}.launch")
            launch = LaunchSpec(_argv(launch_raw.get("argv"), f"{location}.launch.argv"), _inside(workspace, _text(launch_raw.get("cwd", "."), f"{location}.launch.cwd"), f"{location}.launch.cwd"))

        health = None
        if "health" in service:
            health_raw = _object(service["health"], f"{location}.health")
            _known_keys(health_raw, HEALTH_KEYS, f"{location}.health")
            url = _text(health_raw.get("url"), f"{location}.health.url", maximum=2048)
            validate_health_url(url)
            expected_status = health_raw.get("expected_status", 200)
            if type(expected_status) is not int or not 200 <= expected_status <= 299:
                raise _fail("HEALTH_STATUS", f"{location}.health.expected_status is invalid.", "Use a non-redirecting HTTP success status from 200 to 299.")
            body = health_raw.get("expected_body")
            scalar_present = "expected_json_scalar" in health_raw
            scalar = health_raw.get("expected_json_scalar")
            if body is not None:
                body = _text(body, f"{location}.health.expected_body", maximum=65536)
            if body is not None and scalar_present:
                raise _fail("HEALTH_PREDICATE", f"{location}.health must choose expected_body or expected_json_scalar.", "Remove one predicate.")
            if scalar_present and isinstance(scalar, (dict, list)):
                raise _fail("HEALTH_JSON_SCALAR", "expected_json_scalar cannot be an object or array.", "Use an exact string, number, boolean, or null.")
            timeout_ms = health_raw.get("timeout_ms", 1500)
            if type(timeout_ms) is not int or not 100 <= timeout_ms <= 2000:
                raise _fail("HEALTH_TIMEOUT", "health.timeout_ms must be between 100 and 2000.", "Use a bounded local timeout.")
            health = HealthSpec(url, expected_status, body, scalar if scalar_present else None, scalar_present, timeout_ms)

        verification = None
        if "verification" in service:
            verify_raw = _object(service["verification"], f"{location}.verification")
            _known_keys(verify_raw, VERIFY_KEYS, f"{location}.verification")
            verification = VerificationSpec(_argv(verify_raw.get("argv"), f"{location}.verification.argv"), _inside(workspace, _text(verify_raw.get("cwd", "."), f"{location}.verification.cwd"), f"{location}.verification.cwd"))

        services.append(ServiceSpec(service_id, label, workspace, mutation_enabled, strategy, match, launch, health, verification))

    return Adapter(path.resolve(), hashlib.sha256(raw).hexdigest(), 1, tuple(services))
