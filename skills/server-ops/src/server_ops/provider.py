from __future__ import annotations

import os
import platform
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .discovery import match_candidates, psutil
from .errors import EXIT_MUTATION_FAILED, EXIT_REFUSED, OpsError
from .models import Adapter, ProcessCandidate, ServiceSpec, argv_digest
from .state import (
    canonical_digest,
    workspace_lock,
    workspace_state,
    write_launch_receipt,
    write_result_receipt,
    write_transition,
)


def certified_start_available() -> bool:
    return platform.system() == "Windows" and psutil is not None


def _resolve_executable(command: str, cwd: Path) -> Path:
    requested = Path(command)
    if requested.is_absolute():
        resolved = requested.resolve()
        if not resolved.is_file() or resolved.suffix.casefold() not in {".exe", ".com"}:
            raise OpsError(
                "LAUNCH_EXECUTABLE_UNSAFE",
                "The Windows launch executable must be an existing absolute .exe or .com file.",
                "Use an absolute executable path and request a fresh plan.",
                EXIT_REFUSED,
            )
        return resolved
    if requested.parent != Path(".") or requested.drive or "/" in command or chr(92) in command:
        raise OpsError(
            "LAUNCH_EXECUTABLE_UNSAFE",
            "Relative executable paths are not accepted by the certified provider.",
            "Use an absolute executable path or a bare command from the trusted PATH.",
            EXIT_REFUSED,
        )
    suffixes = [""] if requested.suffix.casefold() in {".exe", ".com"} else [".com", ".exe"]
    for raw_directory in os.environ.get("PATH", os.defpath).split(os.pathsep):
        if not raw_directory:
            continue
        try:
            directory = Path(raw_directory).resolve()
        except OSError:
            continue
        if directory == cwd.resolve():
            continue
        for suffix in suffixes:
            candidate = (directory / f"{command}{suffix}").resolve()
            if candidate.is_file() and candidate.suffix.casefold() in {".exe", ".com"}:
                return candidate
    raise OpsError(
        "LAUNCH_EXECUTABLE_NOT_FOUND",
        "The launch executable was not found on the trusted PATH.",
        "Use an existing absolute executable path and request a fresh plan.",
        EXIT_REFUSED,
    )


def launch_intent(service: ServiceSpec) -> dict[str, Any]:
    if service.launch is None:
        raise OpsError(
            "LAUNCH_UNCONFIGURED",
            f"Service `{service.service_id}` has no launch intent.",
            "Add a bounded launch argv/cwd, validate the adapter, and request a fresh plan.",
            EXIT_REFUSED,
        )
    executable = _resolve_executable(service.launch.argv[0], service.launch.cwd)
    return {
        "executable": str(executable),
        "command": executable.name,
        "argv_count": len(service.launch.argv),
        "argv_digest": argv_digest(service.launch.argv),
        "cwd": str(service.launch.cwd.resolve()),
    }


def _candidate_from_process(process: Any) -> ProcessCandidate:
    return ProcessCandidate(
        pid=int(process.pid),
        create_time=float(process.create_time()),
        executable=process.exe(),
        argv=tuple(process.cmdline()),
        cwd=process.cwd(),
        parent_pid=process.ppid(),
        evidence=("certified_direct_child_launch", "pid_create_time_executable_argv_cwd"),
    )


def _observe_started_child(pid: int, service: ServiceSpec, intent: dict[str, Any]) -> ProcessCandidate:
    assert psutil is not None
    deadline = time.monotonic() + 2.0
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            candidate = _candidate_from_process(psutil.Process(pid))
            if os.path.normcase(str(Path(candidate.executable or "").resolve())) != os.path.normcase(intent["executable"]):
                raise RuntimeError("resolved executable mismatch")
            if os.path.normcase(str(Path(candidate.cwd or "").resolve())) != os.path.normcase(intent["cwd"]):
                raise RuntimeError("working directory mismatch")
            if not match_candidates([candidate], service.match):
                raise RuntimeError("launched child does not match the adapter identity predicate")
            return candidate
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError, RuntimeError) as exc:
            last_error = exc
            time.sleep(0.05)
    raise RuntimeError(str(last_error or "child identity was not observable"))


def apply_start_plan(
    *,
    workspace: Path,
    adapter: Adapter,
    service: ServiceSpec,
    plan: dict[str, Any],
    current_candidates: list[ProcessCandidate],
) -> dict[str, Any]:
    if not certified_start_available():
        raise OpsError("CAPABILITY_NOT_CERTIFIED", "The Windows direct-child start provider is unavailable.", "Run `server-ops capabilities`.", EXIT_REFUSED)
    if current_candidates:
        raise OpsError("PROCESS_ALREADY_PRESENT", "The target service is no longer absent.", "Inspect current ownership and request a fresh plan.", EXIT_REFUSED)
    intent = launch_intent(service)
    if intent != plan["launch_intent"] or adapter.digest != plan["adapter_digest"]:
        raise OpsError("PLAN_INPUT_DRIFT", "Adapter or launch intent changed after planning.", "Discard the plan, validate the adapter, and request a fresh plan.", EXIT_REFUSED)
    expires_at = datetime.fromisoformat(plan["expires_at"])
    if datetime.now(timezone.utc) >= expires_at:
        raise OpsError("PLAN_EXPIRED", "The immutable start plan has expired.", "Request and approve a fresh plan.", EXIT_REFUSED)

    operation_id = plan["operation_id"]
    with workspace_lock(workspace, operation_id):
        transition_target = workspace_state(workspace) / "transitions" / f"{operation_id}.json"
        if transition_target.exists():
            raise OpsError(
                "OPERATION_ALREADY_APPLIED",
                "This immutable operation already has an apply transition.",
                "Inspect its result or recovery receipt; request a fresh plan for any new action.",
                EXIT_REFUSED,
            )
        transition = {
            "schema_version": 1,
            "operation_id": operation_id,
            "plan_digest": plan["receipt_digest"],
            "mutation_state": "applying",
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "side_effect_occurred": False,
        }
        transition["transition_digest"] = canonical_digest(transition)
        transition_path = write_transition(workspace, operation_id, transition)

        assert service.launch is not None
        log_path = workspace_state(workspace) / "logs" / f"{service.service_id}-{operation_id}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        child: subprocess.Popen[bytes] | None = None
        try:
            with log_path.open("ab", buffering=0) as log_stream:
                child = subprocess.Popen(
                    list(service.launch.argv),
                    cwd=service.launch.cwd,
                    stdin=subprocess.DEVNULL,
                    stdout=log_stream,
                    stderr=log_stream,
                    shell=False,
                    close_fds=True,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW,
                )
            candidate = _observe_started_child(child.pid, service, intent)
            launched_at = datetime.now(timezone.utc).isoformat()
            launch_receipt = {
                "schema_version": 1,
                "product": "server-ops",
                "operation_id": operation_id,
                "service_id": service.service_id,
                "adapter_digest": adapter.digest,
                "provider_cell": plan["provider_cell"],
                "launched_at": launched_at,
                "pid": candidate.pid,
                "create_time": candidate.create_time,
                "executable": str(Path(candidate.executable or "").resolve()),
                "argv_digest": argv_digest(candidate.argv),
                "cwd": str(Path(candidate.cwd or "").resolve()),
            }
            launch_receipt["receipt_digest"] = canonical_digest(launch_receipt)
            launch_path = write_launch_receipt(workspace, service.service_id, launch_receipt)
            result = {
                "schema_version": 1,
                "product": "server-ops",
                "operation_id": operation_id,
                "plan_digest": plan["receipt_digest"],
                "provider_cell": plan["provider_cell"],
                "completed_at": launched_at,
                "mutation_state": "completed",
                "verification_state": "passed",
                "process_state": "running",
                "health_state": "not_checked",
                "side_effect_occurred": True,
                "process": candidate.public_dict(),
                "launch_receipt_digest": launch_receipt["receipt_digest"],
            }
            result["result_digest"] = canonical_digest(result)
            result_path = write_result_receipt(workspace, operation_id, result)
            return {
                "outcome": "completed",
                **{key: value for key, value in result.items() if key not in {"schema_version", "product"}},
                "launch_receipt": str(launch_path),
                "result_receipt": str(result_path),
                "transition_receipt": str(transition_path),
                "log": str(log_path),
                "next_action": "Run focused verification or inspect the configured local UI before making any downstream claim.",
            }
        except Exception as exc:
            rollback = "not_needed"
            if child is not None and child.poll() is None:
                rollback = "terminated_exact_spawned_child"
                child.terminate()
                try:
                    child.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=3)
            failure = {
                "schema_version": 1,
                "product": "server-ops",
                "operation_id": operation_id,
                "plan_digest": plan["receipt_digest"],
                "provider_cell": plan["provider_cell"],
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "mutation_state": "failed",
                "verification_state": "failed",
                "process_state": "exited_or_unproven",
                "health_state": "not_checked",
                "side_effect_occurred": child is not None,
                "rollback": rollback,
                "error_class": type(exc).__name__,
            }
            failure["result_digest"] = canonical_digest(failure)
            result_path = write_result_receipt(workspace, operation_id, failure)
            raise OpsError(
                "START_VERIFICATION_FAILED",
                "The child start did not produce complete certified identity evidence.",
                "Inspect the local result receipt and logs; request a fresh plan only after the cause is understood.",
                EXIT_MUTATION_FAILED,
                {"operation_id": operation_id, "result_receipt": str(result_path), "rollback": rollback},
                side_effect_occurred=child is not None,
            ) from exc
