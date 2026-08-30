from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
import pytest

from server_ops.adapter import MAX_ADAPTER_BYTES, find_adapter, load_adapter
from server_ops.errors import OpsError

from conftest import write_adapter


PACKAGE = Path(__file__).parents[1] / "skills" / "server-ops"


def test_runtime_and_schema_accept_valid_adapter(tmp_path: Path, adapter_document: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    path = write_adapter(tmp_path, adapter_document)
    adapter = load_adapter(path)
    schema = json.loads((PACKAGE / "schemas" / "adapter.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(adapter_document)
    assert adapter.services[0].service_id == "example-server"
    assert len(adapter.digest) == 64

    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b"x" * (MAX_ADAPTER_BYTES + 1))
    with pytest.raises(OpsError) as raised:
        load_adapter(oversized)
    assert raised.value.code == "ADAPTER_TOO_LARGE"

    linked = tmp_path / "linked.json"
    try:
        linked.symlink_to(path)
    except OSError:
        pass
    else:
        with pytest.raises(OpsError) as linked_error:
            load_adapter(linked)
        assert linked_error.value.code == "ADAPTER_LINK"
        with pytest.raises(OpsError) as discovery_error:
            find_adapter(tmp_path, str(linked))
        assert discovery_error.value.code == "ADAPTER_LINK"
        default_root = tmp_path / "default-linked"
        default_root.mkdir()
        default_link = default_root / ".server-ops.json"
        default_link.symlink_to(path)
        original_is_file = Path.is_file

        def refuse_follow(candidate: Path) -> bool:
            if candidate == default_link:
                raise AssertionError("find_adapter followed a linked adapter")
            return original_is_file(candidate)

        monkeypatch.setattr(Path, "is_file", refuse_follow)
        with pytest.raises(OpsError) as default_error:
            find_adapter(default_root)
        assert default_error.value.code == "ADAPTER_LINK"


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda value: value.update({"unknown": True}), "ADAPTER_UNKNOWN_FIELD"),
        (lambda value: value.update({"schema_version": 2}), "ADAPTER_VERSION"),
        (lambda value: value["services"][0].update({"id": "Bad ID"}), "SERVICE_ID"),
        (lambda value: value["services"][0]["health"].update({"url": "http://example.com:8090/health"}), "HEALTH_URL_NOT_LOOPBACK"),
        (lambda value: value["services"][0]["health"].update({"url": "http://localhost:8090/health"}), "HEALTH_URL_NOT_LOOPBACK"),
        (lambda value: value["services"][0]["health"].update({"expected_json_scalar": True}), "HEALTH_PREDICATE"),
    ],
)
def test_runtime_rejects_unsafe_or_unknown_adapter_fields(tmp_path: Path, adapter_document: dict, mutate, code: str) -> None:
    value = copy.deepcopy(adapter_document)
    mutate(value)
    with pytest.raises(OpsError) as raised:
        load_adapter(write_adapter(tmp_path, value))
    assert raised.value.code == code


def test_workspace_escape_is_rejected(tmp_path: Path, adapter_document: dict) -> None:
    adapter_document["services"][0]["workspace"] = ".."
    with pytest.raises(OpsError) as raised:
        load_adapter(write_adapter(tmp_path, adapter_document))
    assert raised.value.code == "PATH_OUTSIDE_WORKSPACE"


def test_duplicate_service_id_is_rejected(tmp_path: Path, adapter_document: dict) -> None:
    adapter_document["services"].append(copy.deepcopy(adapter_document["services"][0]))
    with pytest.raises(OpsError) as raised:
        load_adapter(write_adapter(tmp_path, adapter_document))
    assert raised.value.code == "SERVICE_DUPLICATE"


def test_schema_and_runtime_reject_duplicate_match_ports(tmp_path: Path, adapter_document: dict) -> None:
    adapter_document["services"][0]["match"]["ports"] = [8090, 8090]
    schema = json.loads((PACKAGE / "schemas" / "adapter.schema.json").read_text(encoding="utf-8"))
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(adapter_document)
    with pytest.raises(OpsError) as raised:
        load_adapter(write_adapter(tmp_path, adapter_document))
    assert raised.value.code == "MATCH_PORTS"


@pytest.mark.parametrize("invalid_port", [[], {}])
def test_schema_and_runtime_reject_non_hashable_match_ports(
    tmp_path: Path,
    adapter_document: dict,
    invalid_port: object,
) -> None:
    adapter_document["services"][0]["match"]["ports"] = [invalid_port]
    schema = json.loads((PACKAGE / "schemas" / "adapter.schema.json").read_text(encoding="utf-8"))
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(adapter_document)
    with pytest.raises(OpsError) as raised:
        load_adapter(write_adapter(tmp_path, adapter_document))
    assert raised.value.code == "MATCH_PORTS"


def test_adapter_discovery_does_not_walk_parent_directories(tmp_path: Path, adapter_document: dict) -> None:
    write_adapter(tmp_path, adapter_document)
    child = tmp_path / "child"
    child.mkdir()
    assert find_adapter(child) is None
    assert find_adapter(tmp_path) == tmp_path / ".server-ops.json"


def test_explicit_adapter_outside_workspace_is_rejected(tmp_path: Path, adapter_document: dict) -> None:
    requested = tmp_path / "requested"
    external = tmp_path / "external"
    requested.mkdir()
    external.mkdir()
    external_adapter = write_adapter(external, adapter_document)
    with pytest.raises(OpsError) as raised:
        find_adapter(requested, str(external_adapter))
    assert raised.value.code == "ADAPTER_OUTSIDE_WORKSPACE"


def test_schema_and_runtime_both_reject_unknown_health_field(tmp_path: Path, adapter_document: dict) -> None:
    adapter_document["services"][0]["health"]["follow_redirects"] = True
    schema = json.loads((PACKAGE / "schemas" / "adapter.schema.json").read_text(encoding="utf-8"))
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(adapter_document)
    with pytest.raises(OpsError) as raised:
        load_adapter(write_adapter(tmp_path, adapter_document))
    assert raised.value.code == "ADAPTER_UNKNOWN_FIELD"

    for unsafe_url in (
        "http://127.0.0.2:8090/health",
        "http://127.0.0.1:8090/health?access_token=secret",
    ):
        value = copy.deepcopy(adapter_document)
        value["services"][0]["health"].pop("follow_redirects")
        value["services"][0]["health"]["url"] = unsafe_url
        with pytest.raises(OpsError):
            load_adapter(write_adapter(tmp_path, value))

    redirect_status = copy.deepcopy(adapter_document)
    redirect_status["services"][0]["health"].pop("follow_redirects")
    redirect_status["services"][0]["health"]["expected_status"] = 302
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(redirect_status)
    with pytest.raises(OpsError) as redirect_error:
        load_adapter(write_adapter(tmp_path, redirect_status))
    assert redirect_error.value.code == "HEALTH_STATUS"
