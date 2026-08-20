from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MatchSpec:
    argv_contains: tuple[str, ...] = ()
    executable: str | None = None
    ports: tuple[int, ...] = ()

    @property
    def configured(self) -> bool:
        return bool(self.argv_contains or self.executable or self.ports)


@dataclass(frozen=True)
class LaunchSpec:
    argv: tuple[str, ...]
    cwd: Path


@dataclass(frozen=True)
class VerificationSpec:
    argv: tuple[str, ...]
    cwd: Path


@dataclass(frozen=True)
class HealthSpec:
    url: str
    expected_status: int = 200
    expected_body: str | None = None
    expected_json_scalar: Any | None = None
    json_scalar_configured: bool = False
    timeout_ms: int = 1500


@dataclass(frozen=True)
class ServiceSpec:
    service_id: str
    label: str
    workspace: Path
    mutation_enabled: bool
    strategy: str
    match: MatchSpec
    launch: LaunchSpec | None = None
    health: HealthSpec | None = None
    verification: VerificationSpec | None = None


@dataclass(frozen=True)
class Adapter:
    path: Path
    digest: str
    schema_version: int
    services: tuple[ServiceSpec, ...]

    def service(self, service_id: str | None) -> ServiceSpec:
        if service_id is None:
            if len(self.services) == 1:
                return self.services[0]
            raise KeyError("service id required")
        for service in self.services:
            if service.service_id == service_id:
                return service
        raise KeyError(service_id)


@dataclass(frozen=True)
class ProcessCandidate:
    pid: int
    create_time: float | None
    executable: str | None
    argv: tuple[str, ...]
    cwd: str | None
    parent_pid: int | None
    listening_ports: tuple[int, ...] = ()
    evidence: tuple[str, ...] = field(default_factory=tuple)

    @staticmethod
    def _display_command(value: str | None) -> str | None:
        if not value:
            return None
        basename = Path(value).name
        safe = "".join(character if unicodedata.category(character)[0] != "C" else "?" for character in basename)
        return safe[:120]

    def public_dict(self) -> dict[str, Any]:
        encoded_argv = json.dumps(list(self.argv), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return {
            "pid": self.pid,
            "create_time": self.create_time,
            "executable": self.executable,
            "command": self._display_command(self.executable or (self.argv[0] if self.argv else None)),
            "argv_count": len(self.argv),
            "argv_digest": hashlib.sha256(encoded_argv).hexdigest(),
            "cwd": self.cwd,
            "parent_pid": self.parent_pid,
            "listening_ports": list(self.listening_ports),
            "evidence": list(self.evidence),
        }
