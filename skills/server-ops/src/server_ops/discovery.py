from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .models import MatchSpec, ProcessCandidate

try:
    import psutil  # type: ignore
except ImportError:  # pragma: no cover - exercised through capability tests
    psutil = None


def psutil_available() -> bool:
    return psutil is not None


def _inside(path: str | None, root: Path) -> bool:
    if not path:
        return False
    try:
        return os.path.commonpath((str(root), str(Path(path).resolve()))) == str(root)
    except (OSError, ValueError):
        return False


def _listener_map() -> dict[int, tuple[int, ...]]:
    if psutil is None:
        return {}
    try:
        connections = psutil.net_connections(kind="inet")
    except (psutil.AccessDenied, OSError):
        return {}
    ports: dict[int, set[int]] = {}
    for connection in connections:
        if connection.pid is None or connection.status != psutil.CONN_LISTEN or not connection.laddr:
            continue
        ports.setdefault(int(connection.pid), set()).add(int(connection.laddr.port))
    return {pid: tuple(sorted(values)) for pid, values in ports.items()}


def discover_workspace(workspace: Path, *, limit: int = 128, include_ports: bool = True) -> list[ProcessCandidate]:
    if psutil is None:
        return []
    root = workspace.resolve()
    attributes = ["pid", "ppid", "create_time", "exe", "cmdline", "cwd"]
    listener_map = _listener_map() if include_ports else {}
    if include_ports:
        process_refs = sorted(listener_map)[:limit * 2]
    else:
        process_refs = psutil.process_iter(attrs=attributes, ad_value=None)

    candidates: list[ProcessCandidate] = []
    for process_ref in process_refs:
        try:
            if include_ports:
                # Windows metadata lookup is materially more expensive than the
                # listener table. Check only cwd first, then enrich the small set
                # already proven to be inside the exact workspace.
                process = psutil.Process(process_ref)
                cwd = process.cwd()
                if not _inside(cwd, root):
                    continue
                info = process.as_dict(attrs=attributes, ad_value=None)
                info["cwd"] = cwd
            else:
                process = process_ref
                info = process.info
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            continue
        if not _inside(info.get("cwd"), root):
            continue
        listening_ports = listener_map.get(int(info["pid"]), ())
        evidence = ["cwd_within_workspace"]
        if listening_ports:
            evidence.append("local_listener_observed")
        candidates.append(ProcessCandidate(
            pid=int(info["pid"]),
            create_time=info.get("create_time"),
            executable=info.get("exe"),
            argv=tuple(info.get("cmdline") or ()),
            cwd=info.get("cwd"),
            parent_pid=info.get("ppid"),
            listening_ports=listening_ports,
            evidence=tuple(evidence),
        ))
        if len(candidates) >= limit:
            break
    return sorted(candidates, key=lambda candidate: candidate.pid)


def match_candidates(candidates: list[ProcessCandidate], match: MatchSpec) -> list[ProcessCandidate]:
    if not match.configured:
        return []
    matched: list[ProcessCandidate] = []
    for candidate in candidates:
        argv_text = "\x00".join(candidate.argv).casefold()
        if match.argv_contains and not all(token.casefold() in argv_text for token in match.argv_contains):
            continue
        if match.executable:
            if not candidate.executable or Path(candidate.executable).resolve() != Path(match.executable).resolve():
                continue
        if match.ports and not set(match.ports).intersection(candidate.listening_ports):
            continue
        matched.append(candidate)
    return matched
