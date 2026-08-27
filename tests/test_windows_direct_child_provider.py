from __future__ import annotations

import json
import os
import platform
import sys
from pathlib import Path

import psutil
import pytest

import server_ops.cli as cli
import server_ops.planner as planner
from server_ops.cli import main


pytestmark = pytest.mark.skipif(os.name != "nt", reason="certified Windows provider cell")


def json_output(capsys) -> dict:
    captured = capsys.readouterr()
    assert captured.err == ""
    return json.loads(captured.out)


def write_adapter(workspace: Path, *, mutation_enabled: bool = True) -> None:
    token = "server-ops-provider-integration-child"
    adapter = {
        "schema_version": 1,
        "services": [{
            "id": "demo-server",
            "label": "Demo Server",
            "workspace": ".",
            "mutation_enabled": mutation_enabled,
            "strategy": "direct_child",
            "match": {"argv_contains": [token]},
            "launch": {
                "argv": [sys.executable, "-c", "import time; time.sleep(30)", token],
                "cwd": ".",
            },
        }],
    }
    (workspace / ".server-ops.json").write_text(json.dumps(adapter), encoding="utf-8")


def test_capabilities_certify_only_windows_direct_child_start(tmp_path: Path, capsys) -> None:
    assert main(["--workspace", str(tmp_path), "--json", "capabilities"]) == 0
    output = json_output(capsys)
    cells = {(cell["strategy"], cell["action"]): cell["status"] for cell in output["cells"]}
    assert cells[("direct_child", "start")] == "certified"
    assert cells[("direct_child", "stop|restart")] == "planned_not_certified"
    assert output["mutation"] == "certified_start_only"


def test_start_plan_is_stored_expiring_and_digest_bound(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "owner-state"))
    write_adapter(tmp_path)
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
    assert plan["launch_intent"]["argv_count"] == 4
    assert "argv" not in plan["launch_intent"]
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


def test_plan_refuses_existing_target_before_side_effect(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "owner-state"))
    write_adapter(tmp_path)
    candidate = planner.ProcessCandidate(
        pid=123,
        create_time=1.0,
        executable=sys.executable,
        argv=(sys.executable, "server-ops-provider-integration-child"),
        cwd=str(tmp_path),
        parent_pid=1,
    )
    monkeypatch.setattr(cli, "discover_workspace", lambda *_args, **_kwargs: [candidate])
    assert main(["--workspace", str(tmp_path), "--json", "plan", "start", "demo-server"]) == 3
    refusal = json_output(capsys)
    assert refusal["error"]["code"] == "PROCESS_ALREADY_PRESENT"
    assert refusal["side_effect_occurred"] is False
