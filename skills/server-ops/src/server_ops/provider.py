from __future__ import annotations

import hashlib
import os
import platform
import stat
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .discovery import match_candidates, psutil
from .errors import EXIT_MUTATION_FAILED, EXIT_RECOVERY_REQUIRED, EXIT_REFUSED, OpsError
from .models import Adapter, ProcessCandidate, ServiceSpec, argv_digest
from .state import (
    canonical_digest,
    workspace_lock,
    workspace_state,
    write_launch_receipt,
    write_result_receipt,
    write_transition,
)

MAX_EXECUTABLE_BYTES = 512 * 1024 * 1024
PROVIDER_LOG_LINE = (
    "server-ops provider: child stdout/stderr discarded; inspect structured receipts.\n"
)
WINDOWS_GENERIC_READ = 0x80000000
WINDOWS_FILE_SHARE_READ = 0x00000001
WINDOWS_OPEN_EXISTING = 3
WINDOWS_FILE_ATTRIBUTE_NORMAL = 0x00000080


def certified_start_available() -> bool:
    return platform.system() == "Windows" and psutil is not None


def _is_local_drive_path(path: Path) -> bool:
    return len(path.drive) == 2 and path.drive[1] == ":" and not str(path).startswith(chr(92) * 2)


def _contains_reparse_component(path: Path) -> bool:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    for part in absolute.parts[1:]:
        current /= part
        try:
            attributes = current.lstat()
        except FileNotFoundError:
            return False
        except OSError:
            return True
        if reparse_flag and getattr(attributes, "st_file_attributes", 0) & reparse_flag:
            return True
    return False


def _resolve_local_path(path: Path) -> Path:
    absolute = Path(os.path.abspath(path))
    if not _is_local_drive_path(absolute) or _contains_reparse_component(absolute):
        raise OpsError(
            "LAUNCH_EXECUTABLE_UNSAFE",
            "The certified provider accepts only non-reparse paths on a local Windows drive.",
            "Use a regular local executable path and request a fresh plan.",
            EXIT_REFUSED,
        )
    resolved = absolute.resolve()
    if not _is_local_drive_path(resolved) or _contains_reparse_component(resolved):
        raise OpsError(
            "LAUNCH_EXECUTABLE_UNSAFE",
            "Executable path resolution escaped the certified local drive boundary.",
            "Use a regular local executable path and request a fresh plan.",
            EXIT_REFUSED,
        )
    return resolved


def prove_listener_guard_free(service: ServiceSpec) -> tuple[int, ...]:
    if not service.match.ports:
        raise OpsError(
            "LISTENER_GUARD_REQUIRED",
            "The certified start cell requires at least one configured exclusive listener port.",
            "Add the service's exclusive listener port to match.ports and request a fresh plan.",
            EXIT_REFUSED,
        )
    assert psutil is not None
    try:
        connections = psutil.net_connections(kind="inet")
    except (psutil.AccessDenied, OSError) as exc:
        raise OpsError(
            "LISTENER_EVIDENCE_UNAVAILABLE",
            "Complete host listener evidence is unavailable, so the start guard cannot be proven free.",
            "Restore process-listener visibility and request a fresh plan; do not bypass the guard.",
            EXIT_REFUSED,
        ) from exc
    listening = {
        int(connection.laddr.port)
        for connection in connections
        if connection.status == psutil.CONN_LISTEN and connection.laddr
    }
    occupied = tuple(sorted(set(service.match.ports).intersection(listening)))
    if occupied:
        raise OpsError(
            "LISTENER_PORT_OCCUPIED",
            "A configured exclusive listener port is already occupied.",
            "Inspect the listener owner and service health; do not create another child.",
            EXIT_REFUSED,
            {"occupied_ports": list(occupied)},
        )
    return tuple(sorted(service.match.ports))


def _resolve_executable(command: str, cwd: Path) -> Path:
    normalized_command = command.replace("/", chr(92))
    if normalized_command.startswith(chr(92) * 2):
        raise OpsError(
            "LAUNCH_EXECUTABLE_UNSAFE",
            "UNC and Windows device-namespace executables are outside the certified local provider boundary.",
            "Use an executable on a local drive and request a fresh plan.",
            EXIT_REFUSED,
        )
    requested = Path(command)
    if requested.is_absolute():
        resolved = _resolve_local_path(requested)
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
        if raw_directory.replace("/", chr(92)).startswith(chr(92) * 2):
            continue
        try:
            directory = _resolve_local_path(Path(raw_directory))
        except (OSError, OpsError):
            continue
        if directory == cwd.resolve():
            continue
        for suffix in suffixes:
            try:
                candidate = _resolve_local_path(directory / f"{command}{suffix}")
            except (OSError, OpsError):
                continue
            if candidate.is_file() and candidate.suffix.casefold() in {".exe", ".com"}:
                return candidate
    raise OpsError(
        "LAUNCH_EXECUTABLE_NOT_FOUND",
        "The launch executable was not found on the trusted PATH.",
        "Use an existing absolute executable path and request a fresh plan.",
        EXIT_REFUSED,
    )


def _executable_sha256(executable: Path) -> str:
    try:
        if executable.stat().st_size > MAX_EXECUTABLE_BYTES:
            raise OpsError(
                "LAUNCH_EXECUTABLE_TOO_LARGE",
                "The launch executable exceeds the certified 512 MiB evidence bound.",
                "Use a bounded local executable and request a fresh plan.",
                EXIT_REFUSED,
            )
        digest = hashlib.sha256()
        with executable.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()
    except OpsError:
        raise
    except OSError as exc:
        raise OpsError(
            "LAUNCH_EXECUTABLE_EVIDENCE_UNAVAILABLE",
            "The launch executable could not be read completely for content binding.",
            "Restore local executable visibility and request a fresh plan.",
            EXIT_REFUSED,
        ) from exc


def launch_intent(service: ServiceSpec) -> dict[str, Any]:
    if service.launch is None:
        raise OpsError(
            "LAUNCH_UNCONFIGURED",
            f"Service `{service.service_id}` has no launch intent.",
            "Add a bounded launch argv/cwd, validate the adapter, and request a fresh plan.",
            EXIT_REFUSED,
        )
    executable = _resolve_executable(service.launch.argv[0], service.launch.cwd)
    effective_argv = (str(executable), *service.launch.argv[1:])
    return {
        "executable": str(executable),
        "executable_sha256": _executable_sha256(executable),
        "command": executable.name,
        "argv_count": len(effective_argv),
        "argv_digest": argv_digest(effective_argv),
        "cwd": str(service.launch.cwd.resolve()),
    }


def _launch_bound_child(
    service: ServiceSpec,
    intent: dict[str, Any],
    launch_state: dict[str, Any],
) -> subprocess.Popen[bytes]:
    assert service.launch is not None
    if os.name != "nt":
        raise OpsError(
            "CAPABILITY_NOT_CERTIFIED",
            "Executable locking is available only in the certified Windows provider cell.",
            "Run `server-ops capabilities`; do not bypass the provider gate.",
            EXIT_REFUSED,
        )
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL
    handle = create_file(
        intent["executable"],
        WINDOWS_GENERIC_READ,
        WINDOWS_FILE_SHARE_READ,
        None,
        WINDOWS_OPEN_EXISTING,
        WINDOWS_FILE_ATTRIBUTE_NORMAL,
        None,
    )
    if handle == wintypes.HANDLE(-1).value:
        raise OpsError(
            "LAUNCH_EXECUTABLE_LOCK_UNAVAILABLE",
            "The executable could not be locked against replacement before launch.",
            "Close conflicting handles and request a fresh plan; do not bypass executable binding.",
            EXIT_REFUSED,
            {"winerror": ctypes.get_last_error()},
        )
    spawned: subprocess.Popen[bytes] | None = None
    try:
        if launch_intent(service) != intent:
            raise OpsError(
                "PLAN_INPUT_DRIFT",
                "The executable content or launch intent changed after planning.",
                "Discard the plan, restore the reviewed executable, and request a fresh plan.",
                EXIT_REFUSED,
        )
        try:
            launch_state["outcome_unproven"] = True
            spawned = subprocess.Popen(
                [intent["executable"], *service.launch.argv[1:]],
                executable=intent["executable"],
                cwd=service.launch.cwd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False,
                close_fds=True,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW,
            )
            launch_state["child"] = spawned
            launch_state["outcome_unproven"] = False
            return spawned
        except BaseException:
            if spawned is not None:
                launch_state["child"] = spawned
                launch_state["outcome_unproven"] = False
            raise
    finally:
        close_handle(handle)


def _candidate_from_process(process: Any, *, include_ports: bool) -> ProcessCandidate:
    listening_ports: tuple[int, ...] = ()
    if include_ports:
        net_connections = getattr(process, "net_connections", None)
        connections = (
            net_connections(kind="inet")
            if net_connections is not None
            else process.connections(kind="inet")
        )
        listening_ports = tuple(sorted({
            int(connection.laddr.port)
            for connection in connections
            if connection.status == psutil.CONN_LISTEN and connection.laddr
        }))
    return ProcessCandidate(
        pid=int(process.pid),
        create_time=float(process.create_time()),
        executable=process.exe(),
        argv=tuple(process.cmdline()),
        cwd=process.cwd(),
        parent_pid=process.ppid(),
        listening_ports=listening_ports,
        evidence=("certified_direct_child_launch", "pid_create_time_executable_argv_cwd"),
    )


def _observe_started_child(pid: int, service: ServiceSpec, intent: dict[str, Any]) -> ProcessCandidate:
    assert psutil is not None
    deadline = time.monotonic() + 2.0
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            candidate = _candidate_from_process(psutil.Process(pid), include_ports=bool(service.match.ports))
            if os.path.normcase(str(Path(candidate.executable or "").resolve())) != os.path.normcase(intent["executable"]):
                raise RuntimeError("resolved executable mismatch")
            if os.path.normcase(str(Path(candidate.cwd or "").resolve())) != os.path.normcase(intent["cwd"]):
                raise RuntimeError("working directory mismatch")
            if argv_digest(candidate.argv) != intent["argv_digest"]:
                raise RuntimeError("launch argv digest mismatch")
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
        raise OpsError("PROCESS_ALREADY_PRESENT", "A matching target process is already observed.", "Inspect current ownership and request a fresh plan.", EXIT_REFUSED)
    intent = launch_intent(service)
    expected_guard = {
        "observation": "complete_global_listener_snapshot",
        "ports": list(sorted(service.match.ports)),
        "state": "free_at_plan",
    }
    if (
        intent != plan["launch_intent"]
        or expected_guard != plan["listener_guard"]
        or adapter.digest != plan["adapter_digest"]
    ):
        raise OpsError("PLAN_INPUT_DRIFT", "Adapter or launch intent changed after planning.", "Discard the plan, validate the adapter, and request a fresh plan.", EXIT_REFUSED)
    expires_at = datetime.fromisoformat(plan["expires_at"])
    if datetime.now(timezone.utc) >= expires_at:
        raise OpsError("PLAN_EXPIRED", "The immutable start plan has expired.", "Request and approve a fresh plan.", EXIT_REFUSED)

    operation_id = plan["operation_id"]
    with workspace_lock(workspace, operation_id) as mutation_lock:
        transition_target = workspace_state(workspace) / "transitions" / f"{operation_id}.json"
        if transition_target.exists():
            raise OpsError(
                "OPERATION_ALREADY_APPLIED",
                "This immutable operation already has an apply transition.",
                "Inspect its result or recovery receipt; request a fresh plan for any new action.",
                EXIT_REFUSED,
            )
        prove_listener_guard_free(service)
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
        launch_state: dict[str, Any] = {"child": None, "outcome_unproven": False}
        try:
            with log_path.open("x", encoding="utf-8", newline="\n") as provider_log:
                provider_log.write(PROVIDER_LOG_LINE)
            child = _launch_bound_child(service, intent, launch_state)
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
        except BaseException as exc:
            # Retain the raw lock before any recovery work. If rollback,
            # journaling, or marker persistence is itself interrupted, later
            # mutations must still fail closed on this unreconciled operation.
            mutation_lock.retained = True
            if child is None and launch_state["child"] is not None:
                child = launch_state["child"]
            launch_outcome_unproven = child is None and launch_state["outcome_unproven"]
            if (
                isinstance(exc, OpsError)
                and exc.code == "PLAN_INPUT_DRIFT"
                and child is None
                and not launch_outcome_unproven
            ):
                mutation_lock.retained = False
                raise
            rollback = "launch_outcome_unproven" if launch_outcome_unproven else "not_needed"
            rollback_error_class: str | None = None
            if child is not None:
                try:
                    if child.poll() is None:
                        child.terminate()
                        try:
                            child.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            child.kill()
                            child.wait(timeout=3)
                        rollback = "terminated_exact_spawned_child"
                    else:
                        rollback = "exact_spawned_child_already_exited"
                except BaseException as rollback_error:
                    rollback = "termination_unproven"
                    rollback_error_class = type(rollback_error).__name__
            failure = {
                "schema_version": 1,
                "product": "server-ops",
                "operation_id": operation_id,
                "plan_digest": plan["receipt_digest"],
                "provider_cell": plan["provider_cell"],
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "mutation_state": "failed",
                "verification_state": "failed",
                "process_state": (
                    "launch_outcome_unproven" if launch_outcome_unproven
                    else "not_started" if child is None
                    else "termination_unproven" if rollback == "termination_unproven"
                    else "exited"
                ),
                "health_state": "not_checked",
                "side_effect_occurred": child is not None or launch_outcome_unproven,
                "spawned_pid": int(child.pid) if child is not None else None,
                "rollback": rollback,
                "rollback_error_class": rollback_error_class,
                "error_class": type(exc).__name__,
            }
            failure["result_digest"] = canonical_digest(failure)
            result_path: Path | None = None
            result_persistence = "persisted"
            persistence_error_class: str | None = None
            try:
                result_path = write_result_receipt(workspace, operation_id, failure)
            except BaseException as persistence_error:
                result_persistence = "failed"
                persistence_error_class = type(persistence_error).__name__
            details = {
                "operation_id": operation_id,
                "transition_receipt": str(transition_path),
                "log": str(log_path),
                "rollback": rollback,
                "result_persistence": result_persistence,
                "spawned_pid": int(child.pid) if child is not None else None,
            }
            if result_path is not None:
                details["result_receipt"] = str(result_path)
            if rollback_error_class is not None:
                details["rollback_error_class"] = rollback_error_class
            if persistence_error_class is not None:
                details["persistence_error_class"] = persistence_error_class
            if launch_outcome_unproven or rollback == "termination_unproven" or result_persistence == "failed":
                recovery_reason = (
                    "launch_outcome_unproven"
                    if launch_outcome_unproven
                    else "termination_unproven"
                    if rollback == "termination_unproven"
                    else "result_persistence_failed"
                )
                interlock_persisted = mutation_lock.retain_for_recovery(
                    reason=recovery_reason,
                    details=details,
                )
                details["recovery_interlock"] = str(mutation_lock.path)
                details["recovery_interlock_persisted"] = interlock_persisted
                raise OpsError(
                    "START_RECOVERY_REQUIRED",
                    "The child start failed and cleanup or result persistence is not fully proven.",
                    "Preserve the transition and log, inspect the exact child identity, and reconcile manually before retrying.",
                    EXIT_RECOVERY_REQUIRED,
                    details,
                    side_effect_occurred=child is not None or launch_outcome_unproven,
                ) from exc
            mutation_lock.retained = False
            raise OpsError(
                "START_VERIFICATION_FAILED",
                "The child start did not produce complete certified identity evidence.",
                "Inspect the local result receipt and logs; request a fresh plan only after the cause is understood.",
                EXIT_MUTATION_FAILED,
                details,
                side_effect_occurred=child is not None,
            ) from exc
