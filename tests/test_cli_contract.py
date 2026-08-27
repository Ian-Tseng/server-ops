from __future__ import annotations

import json
from pathlib import Path

import pytest

import server_ops.cli as cli
import server_ops.planner as planner
from server_ops.cli import main
from server_ops.health import HealthResult
from server_ops.models import ProcessCandidate
from server_ops.state import canonical_digest


def json_output(capsys) -> dict:
    captured = capsys.readouterr()
    assert captured.err == ""
    return json.loads(captured.out)


def write_health_adapter(workspace: Path, *, services: int = 1, health: bool = True) -> None:
    configured = []
    for index in range(services):
        service = {
            "id": f"demo-{index + 1}",
            "workspace": ".",
            "mutation_enabled": False,
            "strategy": "read_only",
            "match": {},
        }
        if health:
            service["health"] = {
                "url": f"http://127.0.0.1:{8090 + index}/health",
                "expected_status": 200,
            }
        configured.append(service)
    (workspace / ".server-ops.json").write_text(
        json.dumps({"schema_version": 1, "services": configured}),
        encoding="utf-8",
    )


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
    assert stored["product_version"] == "0.3.0"
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


def test_capabilities_advertise_only_the_certified_start_cell(tmp_path: Path, capsys) -> None:
    assert main(["--workspace", str(tmp_path), "--json", "capabilities"]) == 0
    output = json_output(capsys)
    assert output["mutation"] == "certified_start_only"
    certified = [cell for cell in output["cells"] if cell["status"] == "certified"]
    assert certified == [{
        "os": "windows",
        "provider": "psutil",
        "strategy": "direct_child",
        "action": "start",
        "status": "certified",
    }]


def test_focused_verify_requires_consecutive_healthy_observations(tmp_path: Path, monkeypatch, capsys) -> None:
    adapter = {
        "schema_version": 1,
        "services": [{
            "id": "demo",
            "workspace": ".",
            "mutation_enabled": False,
            "strategy": "read_only",
            "match": {},
            "health": {"url": "http://127.0.0.1:8090/health", "expected_status": 200},
        }],
    }
    (tmp_path / ".server-ops.json").write_text(json.dumps(adapter), encoding="utf-8")
    observations = iter([
        HealthResult("healthy", 200, 1, "status", "status matched"),
        HealthResult("unhealthy", 503, 1, "status", "expected 200"),
        HealthResult("healthy", 200, 1, "status", "status matched"),
        HealthResult("healthy", 200, 1, "status", "status matched"),
    ])
    monkeypatch.setattr(cli, "probe_health", lambda _spec: next(observations))

    code = main([
        "--workspace", str(tmp_path), "--json", "verify", "demo",
        "--deadline-ms", "1000", "--interval-ms", "10", "--stable-successes", "2",
    ])
    output = json_output(capsys)
    assert code == 0
    assert output["outcome"] == "verified"
    assert output["verification"] == "focused_health_stability"
    assert output["attempts"] == 4
    assert output["consecutive_healthy"] == 2
    assert output["last_health"]["state"] == "healthy"
    assert output["changed"] == "nothing"


def test_focused_verify_rejects_unbounded_poll_contract(tmp_path: Path, capsys) -> None:
    code = main([
        "--workspace", str(tmp_path), "--json", "verify", "demo",
        "--deadline-ms", "100", "--interval-ms", "200",
    ])
    output = json_output(capsys)
    assert code == 2
    assert output["error"]["code"] == "VERIFICATION_BOUNDS"
    assert output["side_effect_occurred"] is False


@pytest.mark.parametrize(
    "arguments",
    [
        ["--deadline-ms", "99"],
        ["--deadline-ms", "60001"],
        ["--interval-ms", "9"],
        ["--interval-ms", "5001"],
        ["--stable-successes", "0"],
        ["--stable-successes", "21"],
        ["--deadline-ms", "100", "--interval-ms", "101"],
    ],
)
def test_focused_verify_rejects_each_invalid_bound(tmp_path: Path, capsys, arguments: list[str]) -> None:
    code = main(["--workspace", str(tmp_path), "--json", "verify", "demo-1", *arguments])
    output = json_output(capsys)
    assert code == 2
    assert output["error"]["code"] == "VERIFICATION_BOUNDS"
    assert output["side_effect_occurred"] is False


def test_focused_verify_requires_adapter_exact_target_and_health(tmp_path: Path, capsys) -> None:
    assert main(["--workspace", str(tmp_path), "--json", "verify", "demo-1"]) == 2
    assert json_output(capsys)["error"]["code"] == "ADAPTER_NOT_FOUND"

    write_health_adapter(tmp_path, services=2)
    assert main(["--workspace", str(tmp_path), "--json", "verify"]) == 2
    assert json_output(capsys)["error"]["code"] == "SERVICE_REQUIRED"
    assert main(["--workspace", str(tmp_path), "--json", "verify", "unknown"]) == 2
    assert json_output(capsys)["error"]["code"] == "SERVICE_NOT_FOUND"

    write_health_adapter(tmp_path, health=False)
    assert main(["--workspace", str(tmp_path), "--json", "verify", "demo-1"]) == 2
    assert json_output(capsys)["error"]["code"] == "HEALTH_UNCONFIGURED"


def test_focused_verify_reports_not_stable_with_exit_five(tmp_path: Path, monkeypatch, capsys) -> None:
    write_health_adapter(tmp_path)
    clock = {"now": 0.0}

    def monotonic() -> float:
        return clock["now"]

    def probe(_spec) -> HealthResult:
        clock["now"] += 0.04
        return HealthResult("unhealthy", 503, 40, "status", "expected 200")

    monkeypatch.setattr(cli.time, "monotonic", monotonic)
    monkeypatch.setattr(cli.time, "sleep", lambda seconds: clock.__setitem__("now", clock["now"] + seconds))
    monkeypatch.setattr(cli, "probe_health", probe)
    code = main([
        "--workspace", str(tmp_path), "--json", "verify", "demo-1",
        "--deadline-ms", "100", "--interval-ms", "50", "--stable-successes", "2",
    ])
    output = json_output(capsys)
    assert code == 5
    assert output["error"]["code"] == "HEALTH_NOT_STABLE"
    assert output["error"]["details"]["attempts"] == 2
    assert output["error"]["details"]["elapsed_ms"] >= 100
    assert output["side_effect_occurred"] is False


def test_focused_verify_does_not_count_a_late_healthy_probe(tmp_path: Path, monkeypatch, capsys) -> None:
    write_health_adapter(tmp_path)
    clock = {"now": 0.0}
    monkeypatch.setattr(cli.time, "monotonic", lambda: clock["now"])

    def late_probe(spec) -> HealthResult:
        assert spec.timeout_ms <= 100
        clock["now"] = 0.101
        return HealthResult("healthy", 200, 101, "status", "status matched")

    monkeypatch.setattr(cli, "probe_health", late_probe)
    code = main([
        "--workspace", str(tmp_path), "--json", "verify", "demo-1",
        "--deadline-ms", "100", "--interval-ms", "10", "--stable-successes", "1",
    ])
    output = json_output(capsys)
    assert code == 5
    assert output["error"]["code"] == "HEALTH_NOT_STABLE"
    assert output["error"]["details"]["consecutive_healthy"] == 0


def test_focused_verify_reports_timeout_if_deadline_expires_before_first_probe(tmp_path: Path, monkeypatch, capsys) -> None:
    write_health_adapter(tmp_path)
    clock = iter([0.0, 0.101])
    monkeypatch.setattr(cli.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(
        cli,
        "probe_health",
        lambda _spec: (_ for _ in ()).throw(AssertionError("probe started after deadline")),
    )
    code = main([
        "--workspace", str(tmp_path), "--json", "verify", "demo-1",
        "--deadline-ms", "100", "--interval-ms", "10", "--stable-successes", "1",
    ])
    output = json_output(capsys)
    assert code == 5
    assert output["error"]["code"] == "HEALTH_NOT_STABLE"
    assert output["error"]["details"]["attempts"] == 0
    assert output["error"]["details"]["last_health"] == {"state": "not_observed"}


def test_focused_verify_defaults_and_human_output(tmp_path: Path, monkeypatch, capsys) -> None:
    write_health_adapter(tmp_path)
    observed_timeouts: list[int] = []

    def healthy(spec) -> HealthResult:
        observed_timeouts.append(spec.timeout_ms)
        return HealthResult("healthy", 200, 1, "status", "status matched")

    monkeypatch.setattr(cli, "probe_health", healthy)
    monkeypatch.setattr(cli.time, "sleep", lambda _seconds: None)
    code = main(["--workspace", str(tmp_path), "verify", "demo-1"])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.err == ""
    assert "FOCUSED VERIFICATION" in captured.out
    assert "Condition: 3/3 consecutive healthy" in captured.out
    assert "Changed: nothing" in captured.out
    assert len(observed_timeouts) == 3
    assert all(timeout <= 1500 for timeout in observed_timeouts)


def test_version_flag_reports_current_product_version(capsys) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["--version"])
    captured = capsys.readouterr()
    assert raised.value.code == 0
    assert captured.out.strip() == "server-ops 0.3.0"
    assert captured.err == ""
