from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from typing import Any

from . import __version__
from .adapter import ADAPTER_NAME, find_adapter, load_adapter
from .discovery import discover_workspace, match_candidates, psutil_available
from .errors import EXIT_INTERNAL_ERROR, EXIT_REFUSED, EXIT_SUCCESS, EXIT_VERIFICATION_FAILED, OpsError
from .health import HealthResult, probe_health
from .models import Adapter, ServiceSpec
from .planner import plan_mutation, refusal_receipt
from .state import read_receipt, state_root, write_receipt


SCHEMA_VERSION = 1


def _terminal_safe(value: Any) -> str:
    text = str(value)
    return "".join(character if unicodedata.category(character)[0] != "C" else "?" for character in text)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="server-ops", description="Evidence-bound local workspace service inspection")
    parser.add_argument("--workspace", default=".", help="Exact workspace root; parent directories are not searched")
    parser.add_argument("--adapter", help="Explicit adapter path; defaults to WORKSPACE/.server-ops.json")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Emit versioned JSON")
    parser.add_argument("--no-color", action="store_true", help="Accepted for stable automation output")
    parser.add_argument("--debug", action="store_true", help="Show a bounded exception class for internal failures")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("doctor", help="Inspect dependencies, adapter discovery, and local policy")
    status = commands.add_parser("status", help="Inspect configured services or discover workspace candidates")
    status.add_argument("service", nargs="?")
    diagnose = commands.add_parser("diagnose", help="Explain service evidence and safe next actions")
    diagnose.add_argument("service", nargs="?")
    verify = commands.add_parser("verify", help="Require bounded consecutive healthy observations")
    verify.add_argument("service", nargs="?")
    verify.add_argument("--deadline-ms", type=int, default=5000)
    verify.add_argument("--interval-ms", type=int, default=250)
    verify.add_argument("--stable-successes", type=int, default=3)
    commands.add_parser("validate", help="Strictly validate the selected adapter")
    commands.add_parser("capabilities", help="Show exact supported and refused capability cells")

    initialize = commands.add_parser("init", help="Create a valid read-only adapter draft")
    initialize.add_argument("--draft", action="store_true", required=True)
    initialize.add_argument("--service", required=True)

    plan = commands.add_parser("plan", help="Plan one lifecycle action without applying it")
    plan.add_argument("action", choices=("start", "stop", "restart"))
    plan.add_argument("service")
    apply_command = commands.add_parser("apply", help="Apply one exact stored operation plan")
    apply_command.add_argument("operation_id")
    apply_command.add_argument("--expect-digest", required=True)
    restart = commands.add_parser("restart", help="Interactive facade over plan/apply")
    restart.add_argument("service")

    recover = commands.add_parser("recover", help="Inspect interrupted/refused local receipts")
    recover_commands = recover.add_subparsers(dest="recover_command", required=True)
    inspect = recover_commands.add_parser("inspect")
    inspect.add_argument("operation_id")

    migrate = commands.add_parser("migrate", help="Check adapter compatibility without changing it")
    migrate.add_argument("--check", action="store_true", required=True)
    return parser


def _workspace(args: argparse.Namespace) -> Path:
    return Path(args.workspace).resolve()


def _adapter(args: argparse.Namespace, *, required: bool) -> Adapter | None:
    path = find_adapter(_workspace(args), args.adapter)
    if path is None:
        if required:
            raise OpsError("ADAPTER_NOT_FOUND", f"No {ADAPTER_NAME} exists in the exact workspace root.", "Run `server-ops init --draft --service <id>` or pass `--adapter <path>`.")
        return None
    return load_adapter(path)


def _service(adapter: Adapter, service_id: str | None) -> ServiceSpec:
    try:
        return adapter.service(service_id)
    except KeyError:
        if service_id is None:
            raise OpsError("SERVICE_REQUIRED", "More than one service is configured; an explicit service ID is required.", "Run `server-ops status <service-id>`.")
        raise OpsError("SERVICE_NOT_FOUND", f"Adapter does not define service `{service_id}`.", "Run `server-ops validate` and choose a listed service ID.")


def _health_map(services: list[ServiceSpec]) -> dict[str, HealthResult | None]:
    configured = [service for service in services if service.health is not None]
    output: dict[str, HealthResult | None] = {service.service_id: None for service in services}
    if not configured:
        return output
    with ThreadPoolExecutor(max_workers=min(8, len(configured))) as executor:
        futures = {executor.submit(probe_health, service.health): service.service_id for service in configured if service.health is not None}
        for future, service_id in futures.items():
            output[service_id] = future.result()
    return output


def _status(args: argparse.Namespace, *, diagnose: bool = False) -> dict[str, Any]:
    adapter = _adapter(args, required=False)
    workspace = _workspace(args)
    if adapter is None:
        candidates = discover_workspace(workspace)
        return {
            "outcome": "observed",
            "mode": "adapter_free_discovery",
            "workspace": str(workspace),
            "process_provider": "psutil" if psutil_available() else "unavailable",
            "candidates": [candidate.public_dict() for candidate in candidates],
            "mutation": "unavailable",
            "changed": "nothing",
            "next_action": "Create a mutation-disabled draft only after selecting a candidate." if candidates else "Add a valid adapter or install psutil for workspace discovery.",
        }

    selected = [_service(adapter, args.service)] if getattr(args, "service", None) else list(adapter.services)
    health = _health_map(selected)
    workspace_candidates: dict[Path, list[Any]] = {}
    rows: list[dict[str, Any]] = []
    for service in selected:
        candidates = []
        if service.match.configured:
            candidates = workspace_candidates.setdefault(
                service.workspace,
                discover_workspace(service.workspace, include_ports=True),
            )
        matched = match_candidates(candidates, service.match)
        if not service.match.configured:
            identity = "unbound"
            process = "unknown"
            next_action = f"Add bounded match evidence for `{service.service_id}`."
        elif len(matched) == 1:
            identity = "partial"
            process = "running"
            next_action = "Read-only match observed; ownership is not proven."
        elif len(matched) > 1:
            identity = "ambiguous"
            process = "multiple"
            next_action = f"Run `server-ops diagnose {service.service_id}` and refine match evidence."
        else:
            identity = "not_observed"
            process = "absent_or_hidden"
            next_action = "Check the launch command and permissions; no process was changed."
        health_result = health[service.service_id]
        row: dict[str, Any] = {
            "service": service.service_id,
            "label": service.label,
            "identity": identity,
            "process": process,
            "health": health_result.as_dict() if health_result else {"state": "unconfigured"},
            "mutation": "disabled" if not service.mutation_enabled else "not_certified",
            "verification": "not_run",
            "matched_candidates": [candidate.public_dict() for candidate in matched[:8]],
            "next_action": next_action,
        }
        if diagnose:
            row["explanation"] = {
                "ownership_proven": False,
                "matched_evidence": sorted({evidence for candidate in matched for evidence in candidate.evidence}),
                "missing_evidence": ["trusted launch receipt or attestation", "capability-cell certification"],
            }
        rows.append(row)
    return {
        "outcome": "observed",
        "mode": "configured",
        "adapter": str(adapter.path),
        "adapter_digest": adapter.digest,
        "services": rows,
        "changed": "nothing",
    }


def _verify(args: argparse.Namespace) -> dict[str, Any]:
    deadline_ms = args.deadline_ms
    interval_ms = args.interval_ms
    stable_successes = args.stable_successes
    if (
        not 100 <= deadline_ms <= 60_000
        or not 10 <= interval_ms <= 5_000
        or interval_ms > deadline_ms
        or not 1 <= stable_successes <= 20
    ):
        raise OpsError(
            "VERIFICATION_BOUNDS",
            "Focused verification requires deadline 100..60000 ms, interval 10..5000 ms not exceeding the deadline, and 1..20 stable successes.",
            "Choose a bounded condition contract and retry.",
        )
    adapter = _adapter(args, required=True)
    assert adapter is not None
    service = _service(adapter, args.service)
    if service.health is None:
        raise OpsError(
            "HEALTH_UNCONFIGURED",
            f"Service `{service.service_id}` has no health predicate.",
            "Add one strict loopback health predicate, validate the adapter, then retry.",
        )

    started = time.monotonic()
    deadline_seconds = deadline_ms / 1000.0
    attempts = 0
    consecutive = 0
    last: HealthResult | None = None
    elapsed_ms = 0
    while True:
        elapsed_before_probe = time.monotonic() - started
        remaining_ms = int((deadline_seconds - elapsed_before_probe) * 1000)
        if remaining_ms <= 0:
            elapsed_ms = int(elapsed_before_probe * 1000)
            break
        attempts += 1
        bounded_health = replace(
            service.health,
            timeout_ms=min(service.health.timeout_ms, max(1, remaining_ms)),
        )
        last = probe_health(bounded_health)
        elapsed_seconds = time.monotonic() - started
        elapsed_ms = int(elapsed_seconds * 1000)
        within_deadline = elapsed_seconds <= deadline_seconds
        consecutive = consecutive + 1 if last.state == "healthy" and within_deadline else 0
        if consecutive >= stable_successes and within_deadline:
            return {
                "outcome": "verified",
                "service": service.service_id,
                "verification": "focused_health_stability",
                "predicate": "consecutive_healthy_observations",
                "required_consecutive_healthy": stable_successes,
                "consecutive_healthy": consecutive,
                "attempts": attempts,
                "elapsed_ms": elapsed_ms,
                "deadline_ms": deadline_ms,
                "interval_ms": interval_ms,
                "last_health": last.as_dict(),
                "mutation": "unavailable",
                "changed": "nothing",
            }
        remaining_ms = int((deadline_seconds - elapsed_seconds) * 1000)
        if remaining_ms <= 0:
            break
        time.sleep(min(interval_ms, remaining_ms) / 1000.0)

    raise OpsError(
        "HEALTH_NOT_STABLE",
        f"Service `{service.service_id}` did not satisfy the bounded stability condition.",
        "Inspect the last predicate, diagnose one hypothesis, then run a fresh focused verification.",
        EXIT_VERIFICATION_FAILED,
        {
            "service": service.service_id,
            "verification": "focused_health_stability",
            "attempts": attempts,
            "consecutive_healthy": consecutive,
            "required_consecutive_healthy": stable_successes,
            "elapsed_ms": elapsed_ms,
            "deadline_ms": deadline_ms,
            "interval_ms": interval_ms,
            "last_health": last.as_dict() if last is not None else {"state": "not_observed"},
        },
    )


def _doctor(args: argparse.Namespace) -> dict[str, Any]:
    workspace = _workspace(args)
    path = find_adapter(workspace, args.adapter)
    adapter_state = "absent"
    adapter_digest = None
    if path:
        adapter = load_adapter(path)
        adapter_state = "valid"
        adapter_digest = adapter.digest
    return {
        "outcome": "observed",
        "version": __version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "workspace": str(workspace),
        "adapter": {"state": adapter_state, "path": str(path) if path else None, "digest": adapter_digest},
        "process_provider": {"name": "psutil", "available": psutil_available()},
        "state_root": str(state_root()),
        "network_policy": "no outbound transmission; configured loopback health probes only",
        "mutation": "no certified providers in 0.2.0",
        "changed": "nothing",
    }


def _capabilities() -> dict[str, Any]:
    return {
        "outcome": "observed",
        "version": __version__,
        "cells": [
            {"os": "windows|macos|linux", "provider": "psutil", "strategy": "read_only", "action": "inspect", "status": "available" if psutil_available() else "dependency_missing"},
            {"os": "windows", "provider": "psutil", "strategy": "watchdog_child", "action": "restart", "status": "planned_not_certified"},
            {"os": "windows|macos|linux", "provider": "psutil", "strategy": "direct_child", "action": "start|stop|restart", "status": "planned_not_certified"},
        ],
        "mutation": "unavailable",
        "changed": "nothing",
    }


def _init_draft(args: argparse.Namespace) -> dict[str, Any]:
    service_id = args.service
    if not service_id or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in service_id) or not service_id[0].isalpha():
        raise OpsError("SERVICE_ID", "Draft service ID must use lowercase letters, digits, and hyphens.", "Choose an ID such as `web-server`.")
    target = _workspace(args) / ADAPTER_NAME
    draft = {
        "schema_version": 1,
        "services": [{
            "id": service_id,
            "label": service_id.replace("-", " ").title(),
            "workspace": ".",
            "mutation_enabled": False,
            "strategy": "read_only",
            "match": {},
        }],
    }
    try:
        with target.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(draft, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    except FileExistsError as exc:
        raise OpsError("ADAPTER_EXISTS", f"Refusing to overwrite existing adapter: {target}", "Run `server-ops validate` or choose a different workspace.", EXIT_REFUSED) from exc
    adapter = load_adapter(target)
    return {
        "outcome": "created",
        "path": str(target),
        "adapter_digest": adapter.digest,
        "mutation": "disabled",
        "next_action": "Review the draft, add bounded match/health evidence, then run `server-ops validate`.",
    }


def _validate(args: argparse.Namespace) -> dict[str, Any]:
    adapter = _adapter(args, required=True)
    assert adapter is not None
    return {
        "outcome": "valid",
        "path": str(adapter.path),
        "schema_version": adapter.schema_version,
        "adapter_digest": adapter.digest,
        "services": [service.service_id for service in adapter.services],
        "mutation_enabled_services": [service.service_id for service in adapter.services if service.mutation_enabled],
        "changed": "nothing",
    }


def _plan(args: argparse.Namespace, action: str, service_id: str) -> dict[str, Any]:
    adapter = _adapter(args, required=True)
    assert adapter is not None
    service = _service(adapter, service_id)
    candidates = []
    if service.match.configured:
        candidates = match_candidates(
            discover_workspace(service.workspace, include_ports=True),
            service.match,
        )
    try:
        return plan_mutation(adapter, service, action, candidates)
    except OpsError as error:
        workspace = _workspace(args)
        receipt = refusal_receipt(adapter, service, action, candidates, error, str(workspace))
        path = write_receipt(workspace, receipt["operation_id"], receipt)
        error.details.update({"operation_id": receipt["operation_id"], "receipt": str(path), "receipt_digest": receipt["receipt_digest"]})
        raise


def _apply(args: argparse.Namespace) -> dict[str, Any]:
    receipt = read_receipt(_workspace(args), args.operation_id)
    actual = receipt.get("receipt_digest")
    if actual != args.expect_digest:
        raise OpsError("PLAN_DIGEST_MISMATCH", "Expected digest does not match the stored operation receipt.", "Inspect the receipt and request a fresh plan.", EXIT_REFUSED, {"operation_id": args.operation_id})
    raise OpsError("OPERATION_NOT_APPLICABLE", "The stored operation is a refusal receipt, not an executable mutation plan.", "Use `server-ops capabilities`; Local Server Ops 0.2.0 has no certified mutation provider.", EXIT_REFUSED, {"operation_id": args.operation_id})


def _recover(args: argparse.Namespace) -> dict[str, Any]:
    return {"outcome": "observed", "receipt": read_receipt(_workspace(args), args.operation_id), "changed": "nothing"}


def _migrate(args: argparse.Namespace) -> dict[str, Any]:
    adapter = _adapter(args, required=False)
    return {
        "outcome": "compatible" if adapter else "no_adapter",
        "reader_schema_versions": [1],
        "adapter_schema_version": adapter.schema_version if adapter else None,
        "changed": "nothing",
    }


def dispatch(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "doctor":
        return _doctor(args)
    if args.command == "status":
        return _status(args)
    if args.command == "diagnose":
        return _status(args, diagnose=True)
    if args.command == "verify":
        return _verify(args)
    if args.command == "validate":
        return _validate(args)
    if args.command == "capabilities":
        return _capabilities()
    if args.command == "init":
        return _init_draft(args)
    if args.command == "plan":
        return _plan(args, args.action, args.service)
    if args.command == "restart":
        return _plan(args, "restart", args.service)
    if args.command == "apply":
        return _apply(args)
    if args.command == "recover" and args.recover_command == "inspect":
        return _recover(args)
    if args.command == "migrate":
        return _migrate(args)
    raise OpsError("COMMAND", "Unsupported command.", "Run `server-ops --help`.")


def _human_status(data: dict[str, Any]) -> str:
    lines = ["LOCAL SERVER OPS - READ-ONLY"]
    if data["mode"] == "adapter_free_discovery":
        lines.append(f"Workspace: {_terminal_safe(data['workspace'])}")
        lines.append(f"Candidates: {len(data['candidates'])}")
        for candidate in data["candidates"][:10]:
            command = candidate["command"] or "unknown"
            ports = ",".join(str(port) for port in candidate["listening_ports"]) or "-"
            lines.append(f"  PID {candidate['pid']} | ports {ports} | {_terminal_safe(command)}")
        lines.extend(["Mutation: unavailable", "Changed: nothing", f"Next: {_terminal_safe(data['next_action'])}"])
        return "\n".join(lines)
    rows = data["services"]
    if len(rows) == 1:
        row = rows[0]
        lines.extend([
            f"Service: {row['service']}",
            f"Identity: {row['identity']}",
            f"Process: {row['process']}",
            f"Health: {row['health']['state']}",
            f"Mutation: {row['mutation']}",
            f"Verification: {row['verification']}",
            "Changed: nothing",
            f"Next: {row['next_action']}",
        ])
        return "\n".join(lines)
    lines.append("Service | Identity | Process | Health | Mutation | Verify | Next")
    for row in rows:
        lines.append(f"{row['service']} | {row['identity']} | {row['process']} | {row['health']['state']} | {row['mutation']} | {row['verification']} | {row['next_action']}")
    lines.append("Changed: nothing")
    return "\n".join(lines)


def render_human(command: str, data: dict[str, Any]) -> str:
    if command in {"status", "diagnose"}:
        return _human_status(data)
    if command == "doctor":
        return "\n".join([
            "LOCAL SERVER OPS DOCTOR",
            f"Version: {data['version']}",
            f"Workspace: {_terminal_safe(data['workspace'])}",
            f"Adapter: {data['adapter']['state']}",
            f"psutil: {'available' if data['process_provider']['available'] else 'missing'}",
            f"Mutation: {data['mutation']}",
            "Network: no outbound transmission",
            "Changed: nothing",
        ])
    if command == "capabilities":
        lines = ["LOCAL SERVER OPS CAPABILITIES"]
        lines.extend(f"{cell['os']} | {cell['provider']} | {cell['strategy']} | {cell['action']} | {cell['status']}" for cell in data["cells"])
        lines.extend(["Mutation: unavailable", "Changed: nothing"])
        return "\n".join(lines)
    if command == "verify":
        return "\n".join([
            "LOCAL SERVER OPS - FOCUSED VERIFICATION",
            f"Service: {_terminal_safe(data['service'])}",
            f"Outcome: {_terminal_safe(data['outcome'])}",
            f"Condition: {data['consecutive_healthy']}/{data['required_consecutive_healthy']} consecutive healthy",
            f"Attempts: {data['attempts']}",
            f"Elapsed: {data['elapsed_ms']} ms",
            "Mutation: unavailable",
            "Changed: nothing",
        ])
    return json.dumps(data, ensure_ascii=False, indent=2)


def emit(args: argparse.Namespace, data: dict[str, Any]) -> None:
    if args.json_output:
        envelope = {"schema_version": SCHEMA_VERSION, "command": args.command, **data}
        print(json.dumps(envelope, ensure_ascii=False, sort_keys=True))
    else:
        print(render_human(args.command, data))


def emit_error(args: argparse.Namespace, error: OpsError) -> None:
    if args.json_output:
        envelope = {"schema_version": SCHEMA_VERSION, "command": args.command, **error.as_dict()}
        print(json.dumps(envelope, ensure_ascii=False, sort_keys=True))
        return
    print(f"REFUSED [{_terminal_safe(error.code)}]" if error.exit_code == EXIT_REFUSED else f"ERROR [{_terminal_safe(error.code)}]", file=sys.stderr)
    print(_terminal_safe(error.message), file=sys.stderr)
    if error.details:
        safe_details = {key: value for key, value in error.details.items() if key in {"operation_id", "receipt", "receipt_digest", "strategy", "action"}}
        for key, value in safe_details.items():
            print(f"{key.replace('_', ' ').title()}: {_terminal_safe(value)}", file=sys.stderr)
    print(f"No process was changed: {str(not error.side_effect_occurred).lower()}.", file=sys.stderr)
    print(f"Next: {_terminal_safe(error.next_action)}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        emit(args, dispatch(args))
        return EXIT_SUCCESS
    except OpsError as error:
        emit_error(args, error)
        return error.exit_code
    except Exception as error:  # fail closed; detailed traceback is intentionally omitted
        detail = f" ({type(error).__name__})" if args.debug else ""
        internal = OpsError("INTERNAL_ERROR", f"Local Server Ops failed safely{detail}.", "Rerun with `--debug`, inspect local state, and report the bounded error class.", EXIT_INTERNAL_ERROR)
        emit_error(args, internal)
        return EXIT_INTERNAL_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
