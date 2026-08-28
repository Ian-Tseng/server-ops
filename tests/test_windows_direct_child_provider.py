from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import socket
import sys
from pathlib import Path

import psutil
import pytest

import server_ops.cli as cli
import server_ops.planner as planner
import server_ops.provider as provider
import server_ops.state as state
from server_ops.cli import main
from server_ops.errors import EXIT_REFUSED, OpsError


pytestmark = pytest.mark.skipif(os.name != "nt", reason="certified Windows provider cell")


def json_output(capsys) -> dict:
    captured = capsys.readouterr()
    assert captured.err == ""
    return json.loads(captured.out)


def reserve_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def write_adapter(
    workspace: Path,
    *,
    mutation_enabled: bool = True,
    include_listener_guard: bool = True,
    launch_argv0: str | None = None,
) -> int:
    token = "server-ops-provider-integration-child"
    port = reserve_port()
    match = {"argv_contains": [token]}
    if include_listener_guard:
        match["ports"] = [port]
    adapter = {
        "schema_version": 1,
        "services": [{
            "id": "demo-server",
            "label": "Demo Server",
            "workspace": ".",
            "mutation_enabled": mutation_enabled,
            "strategy": "direct_child",
            "match": match,
            "launch": {
                "argv": [
                    launch_argv0 or sys.executable,
                    "-c",
                    (
                        "import socket,sys,time; "
                        "server=socket.socket(); "
                        "server.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); "
                        "server.bind(('127.0.0.1',int(sys.argv[1]))); "
                        "server.listen(); time.sleep(30)"
                    ),
                    str(port),
                    token,
                ],
                "cwd": ".",
            },
        }],
    }
    (workspace / ".server-ops.json").write_text(json.dumps(adapter), encoding="utf-8")
    return port


def test_capabilities_certify_only_windows_direct_child_start(tmp_path: Path, capsys) -> None:
    assert main(["--workspace", str(tmp_path), "--json", "capabilities"]) == 0
    output = json_output(capsys)
    cells = {(cell["strategy"], cell["action"]): cell["status"] for cell in output["cells"]}
    assert cells[("direct_child", "start")] == "certified"
    assert cells[("direct_child", "stop|restart")] == "planned_not_certified"
    assert output["mutation"] == "certified_start_only"


def test_start_plan_is_stored_expiring_and_digest_bound(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "owner-state"))
    port = write_adapter(tmp_path)
    monkeypatch.setattr(cli, "discover_workspace", lambda *_args, **_kwargs: [])

    assert main(["--workspace", str(tmp_path), "--json", "plan", "start", "demo-server"]) == 0
    plan = json_output(capsys)
    assert plan["outcome"] == "planned"
    assert plan["mutation_state"] == "planned"
    assert plan["provider_cell"] == {
        "provider": "psutil",
        "provider_available": True,
        "strategy": "direct_child",
        "action": "start",
        "certification": "certified",
    }
    assert plan["launch_intent"]["argv_count"] == 5
    assert plan["launch_intent"]["executable_sha256"] == hashlib.sha256(
        Path(sys.executable).read_bytes()
    ).hexdigest()
    assert "argv" not in plan["launch_intent"]
    assert plan["listener_guard"] == {
        "observation": "complete_global_listener_snapshot",
        "ports": [port],
        "state": "free_at_plan",
    }
    assert plan["process_state"] == "listener_free_before_launch"
    assert Path(plan["receipt"]).is_file()

    assert main([
        "--workspace", str(tmp_path), "--json", "apply", plan["operation_id"],
        "--expect-digest", "0" * 64,
    ]) == 3
    assert json_output(capsys)["error"]["code"] == "PLAN_DIGEST_MISMATCH"


@pytest.mark.parametrize("action", ["stop", "restart"])
def test_uncertified_direct_child_actions_remain_refused(
    tmp_path: Path,
    monkeypatch,
    capsys,
    action: str,
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "owner-state"))
    write_adapter(tmp_path)
    monkeypatch.setattr(cli, "discover_workspace", lambda *_args, **_kwargs: [])
    assert main(["--workspace", str(tmp_path), "--json", "plan", action, "demo-server"]) == 3
    refusal = json_output(capsys)
    assert refusal["error"]["code"] == "CAPABILITY_NOT_CERTIFIED"
    assert refusal["side_effect_occurred"] is False


def test_mutation_disabled_still_refuses_certified_cell(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "owner-state"))
    write_adapter(tmp_path, mutation_enabled=False)
    monkeypatch.setattr(cli, "discover_workspace", lambda *_args, **_kwargs: [])
    assert main(["--workspace", str(tmp_path), "--json", "plan", "start", "demo-server"]) == 3
    assert json_output(capsys)["error"]["code"] == "MUTATION_DISABLED"


def test_plan_requires_an_exclusive_listener_guard(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "owner-state"))
    write_adapter(tmp_path, include_listener_guard=False)
    monkeypatch.setattr(cli, "discover_workspace", lambda *_args, **_kwargs: [])

    assert main(["--workspace", str(tmp_path), "--json", "plan", "start", "demo-server"]) == 3
    refusal = json_output(capsys)
    assert refusal["error"]["code"] == "LISTENER_GUARD_REQUIRED"
    assert refusal["side_effect_occurred"] is False

    assert main(["--workspace", str(tmp_path), "--json", "status", "demo-server"]) == 0
    status = json_output(capsys)["services"][0]
    assert status["mutation"] == "not_configured_for_certified_start"


def test_plan_refuses_incomplete_listener_evidence(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "owner-state"))
    write_adapter(tmp_path)
    monkeypatch.setattr(cli, "discover_workspace", lambda *_args, **_kwargs: [])

    def deny_listener_evidence(*_args, **_kwargs):
        raise psutil.AccessDenied(pid=1)

    monkeypatch.setattr(provider.psutil, "net_connections", deny_listener_evidence)
    assert main(["--workspace", str(tmp_path), "--json", "plan", "start", "demo-server"]) == 3
    refusal = json_output(capsys)
    assert refusal["error"]["code"] == "LISTENER_EVIDENCE_UNAVAILABLE"
    assert refusal["side_effect_occurred"] is False


def test_apply_starts_one_child_and_persists_identity_receipts(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "owner-state"))
    write_adapter(tmp_path)
    assert platform.system() == "Windows"

    assert main(["--workspace", str(tmp_path), "--json", "plan", "start", "demo-server"]) == 0
    plan = json_output(capsys)
    child: psutil.Process | None = None
    try:
        assert main([
            "--workspace", str(tmp_path), "--json", "apply", plan["operation_id"],
            "--expect-digest", plan["receipt_digest"],
        ]) == 0
        result = json_output(capsys)
        assert result["outcome"] == "completed"
        assert result["mutation_state"] == "completed"
        assert result["verification_state"] == "passed"
        assert result["process_state"] == "running"
        assert result["side_effect_occurred"] is True
        assert result["provider_cell"]["certification"] == "certified"
        child = psutil.Process(result["process"]["pid"])
        assert child.is_running()
        assert Path(result["launch_receipt"]).is_file()
        assert Path(result["result_receipt"]).is_file()
        assert main(["--workspace", str(tmp_path), "--json", "diagnose", "demo-server"]) == 0
        diagnosed = json_output(capsys)["services"][0]
        assert diagnosed["identity"] == "owned"
        assert diagnosed["explanation"]["ownership_proven"] is True
        assert diagnosed["explanation"]["missing_evidence"] == []
    finally:
        if child is not None and child.is_running():
            child.terminate()
            child.wait(timeout=5)

    assert main([
        "--workspace", str(tmp_path), "--json", "apply", plan["operation_id"],
        "--expect-digest", plan["receipt_digest"],
    ]) == 3
    assert json_output(capsys)["error"]["code"] == "OPERATION_ALREADY_APPLIED"


def test_bare_path_command_is_resolved_and_launched_as_the_bound_executable(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "owner-state"))
    executable = Path(sys.executable).resolve()
    monkeypatch.setenv("PATH", str(executable.parent))
    write_adapter(tmp_path, launch_argv0=executable.name)

    assert main(["--workspace", str(tmp_path), "--json", "plan", "start", "demo-server"]) == 0
    plan = json_output(capsys)
    assert Path(plan["launch_intent"]["executable"]) == executable
    child: psutil.Process | None = None
    try:
        assert main([
            "--workspace", str(tmp_path), "--json", "apply", plan["operation_id"],
            "--expect-digest", plan["receipt_digest"],
        ]) == 0
        result = json_output(capsys)
        assert Path(result["process"]["executable"]) == executable
        child = psutil.Process(result["process"]["pid"])
    finally:
        if child is not None and child.is_running():
            child.terminate()
            child.wait(timeout=5)


def test_ctrl_c_during_identity_observation_terminates_the_exact_spawned_child(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "owner-state"))
    write_adapter(tmp_path)
    assert main(["--workspace", str(tmp_path), "--json", "plan", "start", "demo-server"]) == 0
    plan = json_output(capsys)
    spawned: list[object] = []
    real_popen = provider.subprocess.Popen

    def capture_popen(*args, **kwargs):
        child = real_popen(*args, **kwargs)
        spawned.append(child)
        return child

    def interrupt_observation(*_args, **_kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(provider.subprocess, "Popen", capture_popen)
    monkeypatch.setattr(provider, "_observe_started_child", interrupt_observation)

    assert main([
        "--workspace", str(tmp_path), "--json", "apply", plan["operation_id"],
        "--expect-digest", plan["receipt_digest"],
    ]) == 4
    failure = json_output(capsys)
    assert failure["error"]["code"] == "START_VERIFICATION_FAILED"
    assert failure["error"]["details"]["rollback"] == "terminated_exact_spawned_child"
    assert len(spawned) == 1
    assert spawned[0].poll() is not None


def test_ctrl_c_after_process_creation_before_assignment_retains_recovery_interlock(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "owner-state"))
    write_adapter(tmp_path)
    assert main(["--workspace", str(tmp_path), "--json", "plan", "start", "demo-server"]) == 0
    plan = json_output(capsys)
    spawned: list[object] = []
    real_popen = provider.subprocess.Popen

    def create_then_interrupt(*args, **kwargs):
        actual_child = real_popen(*args, **kwargs)
        spawned.append(actual_child)
        raise KeyboardInterrupt

    monkeypatch.setattr(provider.subprocess, "Popen", create_then_interrupt)
    try:
        assert main([
            "--workspace", str(tmp_path), "--json", "apply", plan["operation_id"],
            "--expect-digest", plan["receipt_digest"],
        ]) == 6
        failure = json_output(capsys)
        assert failure["error"]["code"] == "START_RECOVERY_REQUIRED"
        assert failure["side_effect_occurred"] is True
        assert failure["error"]["details"]["rollback"] == "launch_outcome_unproven"
        assert failure["error"]["details"]["spawned_pid"] is None

        assert main([
            "--workspace", str(tmp_path), "--json", "recover", "inspect", plan["operation_id"],
        ]) == 0
        recovery = json_output(capsys)
        assert recovery["recovery_interlock"]["state"] == "recovery_required"
        assert recovery["recovery_interlock"]["reason"] == "launch_outcome_unproven"
    finally:
        for actual_child in spawned:
            if actual_child.poll() is None:
                actual_child.terminate()
                actual_child.wait(timeout=5)


def test_exception_after_process_creation_before_assignment_retains_recovery_interlock(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "owner-state"))
    write_adapter(tmp_path)
    assert main(["--workspace", str(tmp_path), "--json", "plan", "start", "demo-server"]) == 0
    first_plan = json_output(capsys)
    assert main(["--workspace", str(tmp_path), "--json", "plan", "start", "demo-server"]) == 0
    second_plan = json_output(capsys)
    spawned: list[object] = []
    real_popen = provider.subprocess.Popen

    def create_then_fail(*args, **kwargs):
        actual_child = real_popen(*args, **kwargs)
        spawned.append(actual_child)
        raise OSError("simulated post-CreateProcess failure")

    monkeypatch.setattr(provider.subprocess, "Popen", create_then_fail)
    try:
        assert main([
            "--workspace", str(tmp_path), "--json", "apply", first_plan["operation_id"],
            "--expect-digest", first_plan["receipt_digest"],
        ]) == 6
        failure = json_output(capsys)
        assert failure["error"]["code"] == "START_RECOVERY_REQUIRED"
        assert failure["side_effect_occurred"] is True
        assert failure["error"]["details"]["rollback"] == "launch_outcome_unproven"
        assert failure["error"]["details"]["spawned_pid"] is None

        assert main([
            "--workspace", str(tmp_path), "--json", "recover", "inspect", first_plan["operation_id"],
        ]) == 0
        recovery = json_output(capsys)
        assert recovery["recovery_interlock"]["state"] == "recovery_required"
        assert recovery["recovery_interlock"]["reason"] == "launch_outcome_unproven"

        for actual_child in spawned:
            if actual_child.poll() is None:
                actual_child.terminate()
                actual_child.wait(timeout=5)

        blocked_launches: list[object] = []

        def unexpected_popen(*_args, **_kwargs):
            blocked_launches.append(object())
            raise AssertionError("the recovery interlock must refuse a later launch")

        monkeypatch.setattr(provider.subprocess, "Popen", unexpected_popen)
        assert main([
            "--workspace", str(tmp_path), "--json", "apply", second_plan["operation_id"],
            "--expect-digest", second_plan["receipt_digest"],
        ]) == 3
        refusal = json_output(capsys)
        assert refusal["error"]["code"] == "WORKSPACE_RECOVERY_REQUIRED"
        assert blocked_launches == []
    finally:
        for actual_child in spawned:
            if actual_child.poll() is None:
                actual_child.terminate()
                actual_child.wait(timeout=5)


def test_plan_drift_error_after_process_creation_retains_recovery_interlock(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "owner-state"))
    write_adapter(tmp_path)
    assert main(["--workspace", str(tmp_path), "--json", "plan", "start", "demo-server"]) == 0
    first_plan = json_output(capsys)
    assert main(["--workspace", str(tmp_path), "--json", "plan", "start", "demo-server"]) == 0
    second_plan = json_output(capsys)
    spawned: list[object] = []
    real_popen = provider.subprocess.Popen

    def create_then_raise_drift(*args, **kwargs):
        actual_child = real_popen(*args, **kwargs)
        spawned.append(actual_child)
        raise OpsError(
            "PLAN_INPUT_DRIFT",
            "simulated post-CreateProcess drift exception",
            "retain recovery state",
            EXIT_REFUSED,
        )

    monkeypatch.setattr(provider.subprocess, "Popen", create_then_raise_drift)
    try:
        assert main([
            "--workspace", str(tmp_path), "--json", "apply", first_plan["operation_id"],
            "--expect-digest", first_plan["receipt_digest"],
        ]) == 6
        failure = json_output(capsys)
        assert failure["error"]["code"] == "START_RECOVERY_REQUIRED"
        assert failure["side_effect_occurred"] is True
        assert failure["error"]["details"]["rollback"] == "launch_outcome_unproven"

        for actual_child in spawned:
            if actual_child.poll() is None:
                actual_child.terminate()
                actual_child.wait(timeout=5)

        blocked_launches: list[object] = []

        def unexpected_popen(*_args, **_kwargs):
            blocked_launches.append(object())
            raise AssertionError("the recovery interlock must refuse a later launch")

        monkeypatch.setattr(provider.subprocess, "Popen", unexpected_popen)
        assert main([
            "--workspace", str(tmp_path), "--json", "apply", second_plan["operation_id"],
            "--expect-digest", second_plan["receipt_digest"],
        ]) == 3
        refusal = json_output(capsys)
        assert refusal["error"]["code"] == "WORKSPACE_RECOVERY_REQUIRED"
        assert blocked_launches == []
    finally:
        for actual_child in spawned:
            if actual_child.poll() is None:
                actual_child.terminate()
                actual_child.wait(timeout=5)


def test_system_exit_after_process_creation_before_assignment_retains_recovery_interlock(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "owner-state"))
    write_adapter(tmp_path)
    assert main(["--workspace", str(tmp_path), "--json", "plan", "start", "demo-server"]) == 0
    first_plan = json_output(capsys)
    assert main(["--workspace", str(tmp_path), "--json", "plan", "start", "demo-server"]) == 0
    second_plan = json_output(capsys)
    spawned: list[object] = []
    real_popen = provider.subprocess.Popen

    def create_then_exit(*args, **kwargs):
        actual_child = real_popen(*args, **kwargs)
        spawned.append(actual_child)
        raise SystemExit(73)

    monkeypatch.setattr(provider.subprocess, "Popen", create_then_exit)
    try:
        assert main([
            "--workspace", str(tmp_path), "--json", "apply", first_plan["operation_id"],
            "--expect-digest", first_plan["receipt_digest"],
        ]) == 6
        failure = json_output(capsys)
        assert failure["error"]["code"] == "START_RECOVERY_REQUIRED"
        assert failure["side_effect_occurred"] is True
        assert failure["error"]["details"]["rollback"] == "launch_outcome_unproven"
        assert failure["error"]["details"]["spawned_pid"] is None

        assert main([
            "--workspace", str(tmp_path), "--json", "recover", "inspect", first_plan["operation_id"],
        ]) == 0
        recovery = json_output(capsys)
        assert recovery["recovery_interlock"]["state"] == "recovery_required"
        assert recovery["recovery_interlock"]["reason"] == "launch_outcome_unproven"

        for actual_child in spawned:
            if actual_child.poll() is None:
                actual_child.terminate()
                actual_child.wait(timeout=5)

        blocked_launches: list[object] = []

        def unexpected_popen(*_args, **_kwargs):
            blocked_launches.append(object())
            raise AssertionError("the recovery interlock must refuse a later launch")

        monkeypatch.setattr(provider.subprocess, "Popen", unexpected_popen)
        assert main([
            "--workspace", str(tmp_path), "--json", "apply", second_plan["operation_id"],
            "--expect-digest", second_plan["receipt_digest"],
        ]) == 3
        refusal = json_output(capsys)
        assert refusal["error"]["code"] == "WORKSPACE_RECOVERY_REQUIRED"
        assert blocked_launches == []
    finally:
        for actual_child in spawned:
            if actual_child.poll() is None:
                actual_child.terminate()
                actual_child.wait(timeout=5)


def test_system_exit_during_exact_child_termination_retains_recovery_interlock(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "owner-state"))
    write_adapter(tmp_path)
    assert main(["--workspace", str(tmp_path), "--json", "plan", "start", "demo-server"]) == 0
    plan = json_output(capsys)
    spawned: list[tuple[object, object]] = []
    real_popen = provider.subprocess.Popen

    def child_with_interrupted_termination(*args, **kwargs):
        actual_child = real_popen(*args, **kwargs)
        original_terminate = actual_child.terminate
        actual_child.terminate = lambda: (_ for _ in ()).throw(SystemExit(74))
        spawned.append((actual_child, original_terminate))
        return actual_child

    monkeypatch.setattr(provider.subprocess, "Popen", child_with_interrupted_termination)
    monkeypatch.setattr(
        provider,
        "_observe_started_child",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("unverified")),
    )
    try:
        assert main([
            "--workspace", str(tmp_path), "--json", "apply", plan["operation_id"],
            "--expect-digest", plan["receipt_digest"],
        ]) == 6
        failure = json_output(capsys)
        assert failure["error"]["code"] == "START_RECOVERY_REQUIRED"
        assert failure["side_effect_occurred"] is True
        assert failure["error"]["details"]["rollback"] == "termination_unproven"
        assert failure["error"]["details"]["spawned_pid"] == spawned[0][0].pid

        assert main([
            "--workspace", str(tmp_path), "--json", "recover", "inspect", plan["operation_id"],
        ]) == 0
        recovery = json_output(capsys)
        assert recovery["recovery_interlock"]["state"] == "recovery_required"
        assert recovery["recovery_interlock"]["reason"] == "termination_unproven"
    finally:
        for actual_child, original_terminate in spawned:
            if actual_child.poll() is None:
                original_terminate()
                actual_child.wait(timeout=5)


def test_system_exit_during_failure_journal_retains_recovery_interlock(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "owner-state"))
    write_adapter(tmp_path)
    assert main(["--workspace", str(tmp_path), "--json", "plan", "start", "demo-server"]) == 0
    plan = json_output(capsys)
    spawned: list[object] = []
    real_popen = provider.subprocess.Popen

    def capture_popen(*args, **kwargs):
        actual_child = real_popen(*args, **kwargs)
        spawned.append(actual_child)
        return actual_child

    monkeypatch.setattr(provider.subprocess, "Popen", capture_popen)
    monkeypatch.setattr(
        provider,
        "_observe_started_child",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("unverified")),
    )
    monkeypatch.setattr(
        provider,
        "write_result_receipt",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(SystemExit(75)),
    )

    assert main([
        "--workspace", str(tmp_path), "--json", "apply", plan["operation_id"],
        "--expect-digest", plan["receipt_digest"],
    ]) == 6
    failure = json_output(capsys)
    assert failure["error"]["code"] == "START_RECOVERY_REQUIRED"
    assert failure["side_effect_occurred"] is True
    assert failure["error"]["details"]["rollback"] == "terminated_exact_spawned_child"
    assert failure["error"]["details"]["result_persistence"] == "failed"
    assert failure["error"]["details"]["spawned_pid"] == spawned[0].pid
    assert spawned[0].poll() is not None

    assert main([
        "--workspace", str(tmp_path), "--json", "recover", "inspect", plan["operation_id"],
    ]) == 0
    recovery = json_output(capsys)
    assert recovery["recovery_interlock"]["state"] == "recovery_required"
    assert recovery["recovery_interlock"]["reason"] == "result_persistence_failed"


def test_system_exit_during_recovery_marker_write_retains_raw_interlock(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "owner-state"))
    write_adapter(tmp_path)
    monkeypatch.setattr(cli, "discover_workspace", lambda *_args, **_kwargs: [])
    assert main(["--workspace", str(tmp_path), "--json", "plan", "start", "demo-server"]) == 0
    plan = json_output(capsys)

    class UnstoppableChild:
        pid = 9876

        @staticmethod
        def poll():
            return None

        @staticmethod
        def terminate():
            raise OSError("simulated termination failure")

    original_atomic_write_json = state.atomic_write_json

    def interrupt_marker(path, value):
        if path.name == "mutation.lock":
            raise SystemExit(76)
        return original_atomic_write_json(path, value)

    monkeypatch.setattr(provider.subprocess, "Popen", lambda *_args, **_kwargs: UnstoppableChild())
    monkeypatch.setattr(
        provider,
        "_observe_started_child",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("unverified")),
    )
    monkeypatch.setattr(state, "atomic_write_json", interrupt_marker)

    assert main([
        "--workspace", str(tmp_path), "--json", "apply", plan["operation_id"],
        "--expect-digest", plan["receipt_digest"],
    ]) == 6
    failure = json_output(capsys)
    assert failure["error"]["code"] == "START_RECOVERY_REQUIRED"
    assert failure["side_effect_occurred"] is True
    assert failure["error"]["details"]["recovery_interlock_persisted"] is False

    assert main([
        "--workspace", str(tmp_path), "--json", "recover", "inspect", plan["operation_id"],
    ]) == 0
    recovery = json_output(capsys)
    assert recovery["recovery_interlock"]["state"] == "active_or_unreconciled"
    assert recovery["recovery_interlock"]["operation_id"] == plan["operation_id"]


def test_unc_and_device_namespace_executables_are_refused_without_access(tmp_path: Path) -> None:
    for command in (r"\\server\share\server.exe", r"\\?\C:\server.exe", r"\\.\pipe\server.exe"):
        with pytest.raises(OpsError) as captured:
            provider._resolve_executable(command, tmp_path)
        assert captured.value.code == "LAUNCH_EXECUTABLE_UNSAFE"


def test_reparse_executable_is_refused_before_resolution(tmp_path: Path) -> None:
    target = tmp_path / "target.exe"
    target.write_bytes(b"not executed")
    linked = tmp_path / "linked.exe"
    try:
        linked.symlink_to(target)
    except OSError as exc:
        pytest.skip(f"file symlink creation unavailable: {exc}")
    with pytest.raises(OpsError) as captured:
        provider._resolve_executable(str(linked), tmp_path)
    assert captured.value.code == "LAUNCH_EXECUTABLE_UNSAFE"


def test_apply_refuses_adapter_drift_before_side_effect(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "owner-state"))
    write_adapter(tmp_path)
    monkeypatch.setattr(cli, "discover_workspace", lambda *_args, **_kwargs: [])
    assert main(["--workspace", str(tmp_path), "--json", "plan", "start", "demo-server"]) == 0
    plan = json_output(capsys)
    adapter_path = tmp_path / ".server-ops.json"
    adapter = json.loads(adapter_path.read_text(encoding="utf-8"))
    adapter["services"][0]["label"] = "Changed after planning"
    adapter_path.write_text(json.dumps(adapter), encoding="utf-8")

    assert main([
        "--workspace", str(tmp_path), "--json", "apply", plan["operation_id"],
        "--expect-digest", plan["receipt_digest"],
    ]) == 3
    refusal = json_output(capsys)
    assert refusal["error"]["code"] == "PLAN_INPUT_DRIFT"
    assert refusal["side_effect_occurred"] is False


def test_apply_refuses_replaced_executable_before_side_effect(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "owner-state"))
    executable = tmp_path / "python-copy.exe"
    shutil.copy2(sys.executable, executable)
    write_adapter(tmp_path, launch_argv0=str(executable))
    monkeypatch.setattr(cli, "discover_workspace", lambda *_args, **_kwargs: [])

    assert main(["--workspace", str(tmp_path), "--json", "plan", "start", "demo-server"]) == 0
    plan = json_output(capsys)
    original = bytearray(executable.read_bytes())
    original[-1] ^= 1
    executable.write_bytes(original)
    launches: list[object] = []

    def unexpected_popen(*_args, **_kwargs):
        launches.append(object())
        raise AssertionError("a drifted executable must not launch")

    monkeypatch.setattr(provider.subprocess, "Popen", unexpected_popen)
    assert main([
        "--workspace", str(tmp_path), "--json", "apply", plan["operation_id"],
        "--expect-digest", plan["receipt_digest"],
    ]) == 3
    refusal = json_output(capsys)
    assert refusal["error"]["code"] == "PLAN_INPUT_DRIFT"
    assert refusal["side_effect_occurred"] is False
    assert launches == []


def test_executable_replacement_is_locked_through_process_creation(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "owner-state"))
    executable = tmp_path / "python-copy.exe"
    shutil.copy2(sys.executable, executable)
    write_adapter(tmp_path, launch_argv0=str(executable))
    monkeypatch.setattr(cli, "discover_workspace", lambda *_args, **_kwargs: [])
    assert main(["--workspace", str(tmp_path), "--json", "plan", "start", "demo-server"]) == 0
    plan = json_output(capsys)
    replacement_attempts: list[str] = []

    def probe_locked_popen(*_args, **_kwargs):
        try:
            executable.write_bytes(b"replacement")
        except PermissionError:
            replacement_attempts.append("blocked")
        raise OSError("simulated process creation failure")

    monkeypatch.setattr(provider.subprocess, "Popen", probe_locked_popen)
    assert main([
        "--workspace", str(tmp_path), "--json", "apply", plan["operation_id"],
        "--expect-digest", plan["receipt_digest"],
    ]) == 6
    failure = json_output(capsys)
    assert failure["error"]["code"] == "START_RECOVERY_REQUIRED"
    assert failure["side_effect_occurred"] is True
    assert failure["error"]["details"]["rollback"] == "launch_outcome_unproven"
    assert replacement_attempts == ["blocked"]


def test_failed_identity_verification_rolls_back_exact_spawned_child(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "owner-state"))
    write_adapter(tmp_path)
    adapter_path = tmp_path / ".server-ops.json"
    adapter = json.loads(adapter_path.read_text(encoding="utf-8"))
    adapter["services"][0]["match"]["argv_contains"] = ["identity-token-not-in-launch"]
    adapter_path.write_text(json.dumps(adapter), encoding="utf-8")
    monkeypatch.setattr(cli, "discover_workspace", lambda *_args, **_kwargs: [])

    assert main(["--workspace", str(tmp_path), "--json", "plan", "start", "demo-server"]) == 0
    plan = json_output(capsys)
    assert main([
        "--workspace", str(tmp_path), "--json", "apply", plan["operation_id"],
        "--expect-digest", plan["receipt_digest"],
    ]) == 4
    failure = json_output(capsys)
    assert failure["error"]["code"] == "START_VERIFICATION_FAILED"
    assert failure["error"]["details"]["rollback"] == "terminated_exact_spawned_child"
    assert failure["side_effect_occurred"] is True
    result = json.loads(Path(failure["error"]["details"]["result_receipt"]).read_text(encoding="utf-8"))
    assert result["mutation_state"] == "failed"
    assert result["verification_state"] == "failed"
    assert result["rollback"] == "terminated_exact_spawned_child"


def test_rollback_failure_is_truthful_recovery_required(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "owner-state"))
    write_adapter(tmp_path)
    monkeypatch.setattr(cli, "discover_workspace", lambda *_args, **_kwargs: [])
    assert main(["--workspace", str(tmp_path), "--json", "plan", "start", "demo-server"]) == 0
    plan = json_output(capsys)

    class UnstoppableChild:
        pid = 9876

        @staticmethod
        def poll():
            return None

        @staticmethod
        def terminate():
            raise OSError("simulated termination failure")

    monkeypatch.setattr(provider.subprocess, "Popen", lambda *_args, **_kwargs: UnstoppableChild())
    monkeypatch.setattr(provider, "_observe_started_child", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("unverified")))

    assert main([
        "--workspace", str(tmp_path), "--json", "apply", plan["operation_id"],
        "--expect-digest", plan["receipt_digest"],
    ]) == 6
    failure = json_output(capsys)
    assert failure["error"]["code"] == "START_RECOVERY_REQUIRED"
    assert failure["side_effect_occurred"] is True
    assert failure["error"]["details"]["rollback"] == "termination_unproven"
    assert failure["error"]["details"]["result_persistence"] == "persisted"
    assert failure["error"]["details"]["spawned_pid"] == 9876


def test_recovery_required_interlocks_later_plans_and_applies(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "owner-state"))
    write_adapter(tmp_path)
    monkeypatch.setattr(cli, "discover_workspace", lambda *_args, **_kwargs: [])
    assert main(["--workspace", str(tmp_path), "--json", "plan", "start", "demo-server"]) == 0
    first_plan = json_output(capsys)
    assert main(["--workspace", str(tmp_path), "--json", "plan", "start", "demo-server"]) == 0
    second_plan = json_output(capsys)

    launches: list[int] = []

    class UnstoppableChild:
        pid = 9876

        def __init__(self) -> None:
            launches.append(self.pid)

        @staticmethod
        def poll():
            return None

        @staticmethod
        def terminate():
            raise OSError("simulated termination failure")

    monkeypatch.setattr(provider.subprocess, "Popen", lambda *_args, **_kwargs: UnstoppableChild())
    monkeypatch.setattr(provider, "_observe_started_child", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("unverified")))

    assert main([
        "--workspace", str(tmp_path), "--json", "apply", first_plan["operation_id"],
        "--expect-digest", first_plan["receipt_digest"],
    ]) == 6
    failure = json_output(capsys)
    assert failure["error"]["code"] == "START_RECOVERY_REQUIRED"
    assert launches == [9876]

    assert main([
        "--workspace", str(tmp_path), "--json", "recover", "inspect", first_plan["operation_id"],
    ]) == 0
    recovery = json_output(capsys)
    assert recovery["recovery_interlock"]["state"] == "recovery_required"
    assert recovery["recovery_interlock"]["operation_id"] == first_plan["operation_id"]
    assert recovery["changed"] == "nothing"

    assert main(["--workspace", str(tmp_path), "--json", "plan", "start", "demo-server"]) == 3
    plan_refusal = json_output(capsys)
    assert plan_refusal["error"]["code"] == "WORKSPACE_RECOVERY_REQUIRED"

    assert main([
        "--workspace", str(tmp_path), "--json", "apply", second_plan["operation_id"],
        "--expect-digest", second_plan["receipt_digest"],
    ]) == 3
    apply_refusal = json_output(capsys)
    assert apply_refusal["error"]["code"] == "WORKSPACE_RECOVERY_REQUIRED"
    assert launches == [9876]


def test_failure_receipt_write_failure_is_truthful_recovery_required(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "owner-state"))
    write_adapter(tmp_path)
    monkeypatch.setattr(cli, "discover_workspace", lambda *_args, **_kwargs: [])
    assert main(["--workspace", str(tmp_path), "--json", "plan", "start", "demo-server"]) == 0
    plan = json_output(capsys)

    class ContainedChild:
        pid = 6789
        running = True

        def poll(self):
            return None if self.running else 0

        def terminate(self):
            self.running = False

        def wait(self, timeout):
            return 0

    monkeypatch.setattr(provider.subprocess, "Popen", lambda *_args, **_kwargs: ContainedChild())
    monkeypatch.setattr(provider, "_observe_started_child", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("unverified")))
    monkeypatch.setattr(provider, "write_result_receipt", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("simulated journal failure")))

    assert main([
        "--workspace", str(tmp_path), "--json", "apply", plan["operation_id"],
        "--expect-digest", plan["receipt_digest"],
    ]) == 6
    failure = json_output(capsys)
    assert failure["error"]["code"] == "START_RECOVERY_REQUIRED"
    assert failure["side_effect_occurred"] is True
    assert failure["error"]["details"]["rollback"] == "terminated_exact_spawned_child"
    assert failure["error"]["details"]["result_persistence"] == "failed"


def test_prelaunch_and_failure_receipt_failures_retain_truthful_interlock(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "owner-state"))
    write_adapter(tmp_path)
    monkeypatch.setattr(cli, "discover_workspace", lambda *_args, **_kwargs: [])
    assert main(["--workspace", str(tmp_path), "--json", "plan", "start", "demo-server"]) == 0
    plan = json_output(capsys)

    monkeypatch.setattr(provider.subprocess, "Popen", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("simulated create failure")))
    monkeypatch.setattr(provider, "write_result_receipt", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("simulated journal failure")))

    assert main([
        "--workspace", str(tmp_path), "--json", "apply", plan["operation_id"],
        "--expect-digest", plan["receipt_digest"],
    ]) == 6
    failure = json_output(capsys)
    assert failure["error"]["code"] == "START_RECOVERY_REQUIRED"
    assert failure["side_effect_occurred"] is True
    assert failure["error"]["details"]["spawned_pid"] is None
    assert failure["error"]["details"]["rollback"] == "launch_outcome_unproven"
    assert failure["error"]["details"]["result_persistence"] == "failed"
    assert failure["error"]["details"]["recovery_interlock_persisted"] is True

    assert main([
        "--workspace", str(tmp_path), "--json", "recover", "inspect", plan["operation_id"],
    ]) == 0
    recovery = json_output(capsys)
    assert recovery["recovery_interlock"]["state"] == "recovery_required"
    assert recovery["recovery_interlock"]["reason"] == "launch_outcome_unproven"


def test_plan_refuses_existing_target_before_side_effect(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "owner-state"))
    port = write_adapter(tmp_path)
    candidate = planner.ProcessCandidate(
        pid=123,
        create_time=1.0,
        executable=sys.executable,
        argv=(sys.executable, "server-ops-provider-integration-child"),
        cwd=str(tmp_path),
        parent_pid=1,
        listening_ports=(port,),
    )
    monkeypatch.setattr(cli, "discover_workspace", lambda *_args, **_kwargs: [candidate])
    assert main(["--workspace", str(tmp_path), "--json", "plan", "start", "demo-server"]) == 3
    refusal = json_output(capsys)
    assert refusal["error"]["code"] == "PROCESS_ALREADY_PRESENT"
    assert refusal["side_effect_occurred"] is False


def test_apply_rechecks_listener_guard_after_acquiring_workspace_lock(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "owner-state"))
    port = write_adapter(tmp_path)
    monkeypatch.setattr(cli, "discover_workspace", lambda *_args, **_kwargs: [])
    assert main(["--workspace", str(tmp_path), "--json", "plan", "start", "demo-server"]) == 0
    plan = json_output(capsys)

    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", port))
        occupied.listen()
        assert main([
            "--workspace", str(tmp_path), "--json", "apply", plan["operation_id"],
            "--expect-digest", plan["receipt_digest"],
        ]) == 3
        refusal = json_output(capsys)
        assert refusal["error"]["code"] == "LISTENER_PORT_OCCUPIED"
        assert refusal["side_effect_occurred"] is False
