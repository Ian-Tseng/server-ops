from __future__ import annotations

import json
from pathlib import Path

import server_ops.cli as cli
import server_ops.planner as planner
from server_ops.cli import main
from server_ops.models import ProcessCandidate
from server_ops.state import canonical_digest


def json_output(capsys) -> dict:
    captured = capsys.readouterr()
    assert captured.err == ""
    return json.loads(captured.out)


def test_doctor_is_read_only_and_versioned(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "state"))
    code = main(["--workspace", str(tmp_path), "--json", "doctor"])
    output = json_output(capsys)
    assert code == 0
    assert output["schema_version"] == 1
    assert output["changed"] == "nothing"
    assert output["network_policy"].startswith("no outbound")

    secret = "do-not-echo-this-password"
    adapter = {
        "schema_version": 1,
        "services": [{
            "id": "demo",
            "health": {"url": f"http://user:{secret}@127.0.0.1:8090/health"},
        }],
    }
    (tmp_path / ".server-ops.json").write_text(json.dumps(adapter), encoding="utf-8")
    assert main(["--workspace", str(tmp_path), "--json", "doctor"]) == 2
    refusal = json_output(capsys)
    assert refusal["error"]["code"] == "HEALTH_URL_UNSAFE"
    assert secret not in json.dumps(refusal)
    assert "url" not in refusal["error"]["details"]

    malicious_field = "spoof\x1b]0;owned\x07"
    (tmp_path / ".server-ops.json").write_text(
        json.dumps({"schema_version": 1, "services": [{"id": "demo", malicious_field: True}]}),
        encoding="utf-8",
    )
    assert main(["--workspace", str(tmp_path), "validate"]) == 2
    human_refusal = capsys.readouterr()
    assert "\x1b" not in human_refusal.err
    assert "\x07" not in human_refusal.err


def test_draft_is_valid_read_only_and_never_overwrites(tmp_path: Path, capsys) -> None:
    args = ["--workspace", str(tmp_path), "--json", "init", "--draft", "--service", "demo-server"]
    assert main(args) == 0
    created = json_output(capsys)
    assert created["mutation"] == "disabled"
    assert main(args) == 3
    refused = json_output(capsys)
    assert refused["error"]["code"] == "ADAPTER_EXISTS"
    assert refused["side_effect_occurred"] is False


def test_validate_then_plan_writes_refusal_receipt(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "owner-state"))
    monkeypatch.setattr(planner, "psutil_available", lambda: False)
    assert main(["--workspace", str(tmp_path), "--json", "init", "--draft", "--service", "demo-server"]) == 0
    json_output(capsys)
    assert main(["--workspace", str(tmp_path), "--json", "validate"]) == 0
    valid = json_output(capsys)
    assert valid["outcome"] == "valid"
    assert main(["--workspace", str(tmp_path), "--json", "plan", "restart", "demo-server"]) == 3
    refused = json_output(capsys)
    assert refused["error"]["code"] == "MUTATION_DISABLED"
    receipt = Path(refused["error"]["details"]["receipt"])
    stored = json.loads(receipt.read_text(encoding="utf-8"))
    assert stored["mutation_state"] == "refused"
    assert stored["verification_state"] == "not_run"
    assert stored["side_effect_occurred"] is False
    assert stored["product"] == "server-ops"
    assert stored["product_version"] == "0.1.2"
    assert stored["workspace"] == str(tmp_path.resolve())
    assert stored["service_workspace"] == str(tmp_path.resolve())
    assert stored["provider_cell"]["provider"] == "none"
    assert stored["provider_cell"]["provider_available"] is False
    assert stored["verification_scope"] == "refusal_only_no_side_effect"

    apply_args = ["--workspace", str(tmp_path), "--json", "apply", stored["operation_id"], "--expect-digest", stored["receipt_digest"]]
    assert main(apply_args) == 3
    apply_refusal = json_output(capsys)
    assert apply_refusal["error"]["code"] == "OPERATION_NOT_APPLICABLE"


def test_digest_mismatch_refuses_apply(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "owner-state"))
    assert main(["--workspace", str(tmp_path), "--json", "init", "--draft", "--service", "demo-server"]) == 0
    json_output(capsys)
    assert main(["--workspace", str(tmp_path), "--json", "plan", "restart", "demo-server"]) == 3
    refusal = json_output(capsys)
    operation_id = refusal["error"]["details"]["operation_id"]
    assert main(["--workspace", str(tmp_path), "--json", "apply", operation_id, "--expect-digest", "0" * 64]) == 3
    mismatch = json_output(capsys)
    assert mismatch["error"]["code"] == "PLAN_DIGEST_MISMATCH"


def test_stored_receipt_tampering_is_rejected_before_recovery_or_apply(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "owner-state"))
    assert main(["--workspace", str(tmp_path), "--json", "init", "--draft", "--service", "demo-server"]) == 0
    json_output(capsys)
    assert main(["--workspace", str(tmp_path), "--json", "plan", "restart", "demo-server"]) == 3
    refusal = json_output(capsys)
    receipt_path = Path(refusal["error"]["details"]["receipt"])
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    original_next_action = receipt["next_action"]
    receipt["next_action"] = "tampered"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    recover_args = ["--workspace", str(tmp_path), "--json", "recover", "inspect", receipt["operation_id"]]
    assert main(recover_args) == 3
    recovery = json_output(capsys)
    assert recovery["error"]["code"] == "RECEIPT_DIGEST_MISMATCH"

    apply_args = ["--workspace", str(tmp_path), "--json", "apply", receipt["operation_id"], "--expect-digest", receipt["receipt_digest"]]
    assert main(apply_args) == 3
    apply_refusal = json_output(capsys)
    assert apply_refusal["error"]["code"] == "RECEIPT_DIGEST_MISMATCH"

    receipt["next_action"] = original_next_action
    receipt["action"] = []
    body = dict(receipt)
    body.pop("receipt_digest")
    receipt["receipt_digest"] = canonical_digest(body)
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    assert main(recover_args) == 3
    malformed = json_output(capsys)
    assert malformed["error"]["code"] == "RECEIPT_SCHEMA"

    outside_receipt = tmp_path / "outside-receipt.json"
    outside_receipt.write_text(json.dumps(receipt), encoding="utf-8")
    receipt_path.unlink()
    receipt_path.symlink_to(outside_receipt)
    original_is_file = Path.is_file

    def refuse_follow(candidate: Path) -> bool:
        if candidate == receipt_path:
            raise AssertionError("read_receipt followed a linked receipt")
        return original_is_file(candidate)

    monkeypatch.setattr(Path, "is_file", refuse_follow)
    assert main(recover_args) == 3
    linked = json_output(capsys)
    assert linked["error"]["code"] == "RECEIPT_LINK"


def test_process_output_redacts_arguments_and_terminal_controls(tmp_path: Path, monkeypatch, capsys) -> None:
    secret = "do-not-print-token"
    candidate = ProcessCandidate(
        pid=101,
        create_time=1.0,
        executable="unsafe\x1b[31m-server.py",
        argv=("unsafe\x1b[31m-server.py", f"--token={secret}"),
        cwd=str(tmp_path),
        parent_pid=1,
        listening_ports=(8090,),
        evidence=("cwd_within_workspace",),
    )
    monkeypatch.setattr(cli, "discover_workspace", lambda workspace: [candidate])

    assert main(["--workspace", str(tmp_path), "--json", "status"]) == 0
    output = json_output(capsys)
    serialized = json.dumps(output)
    public = output["candidates"][0]
    assert secret not in serialized
    assert "\x1b" not in serialized
    assert "argv" not in public
    assert public["argv_count"] == 2
    assert len(public["argv_digest"]) == 64

    assert main(["--workspace", str(tmp_path), "status"]) == 0
    human = capsys.readouterr()
    assert secret not in human.out
    assert "\x1b" not in human.out


def test_capabilities_never_advertise_mutation(tmp_path: Path, capsys) -> None:
    assert main(["--workspace", str(tmp_path), "--json", "capabilities"]) == 0
    output = json_output(capsys)
    assert output["mutation"] == "unavailable"
    assert all(cell["status"] != "certified" for cell in output["cells"] if cell["action"] != "inspect")
