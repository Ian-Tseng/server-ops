from __future__ import annotations

import json
import hashlib
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib


ROOT = Path(__file__).parents[1]
VALIDATION = ROOT / "validation"
PACKAGE = ROOT / "skills" / "server-ops"


def test_release_evidence_contract_is_current() -> None:
    receipt = json.loads((VALIDATION / "release-candidate-test-receipt.json").read_text(encoding="utf-8"))
    manifest = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8"))
    assert receipt["version"] == manifest["version"] == "0.1.2"
    assert receipt["tests"] == {
        "command": "py -3 -X utf8 -m pytest -q",
        "tests_run": 58,
        "passed": 58,
        "failed": 0,
        "skipped": 0,
        "environment": "local Windows candidate",
        "status": "PASS",
    }
    assert receipt["package"]["manifest_digest"] == manifest["manifest_digest"]
    assert receipt["package"]["status"] == "PACKAGE_VERIFIED"
    assert receipt["official_skill_validator"] == {
        "command": "py -3 -X utf8 <skill-creator-root>/scripts/quick_validate.py skills/server-ops",
        "result": "Skill is valid!",
        "validator_sha256": "547af3cec2ae71ac2a4ef606365d23a8c58b586862211e9c7a9be7bfd0e30fbb",
        "status": "PASS",
    }
    workflow = (ROOT / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8")
    assert '"pytest==8.3.5" "jsonschema==4.23.0" "tomli==2.2.1"' in workflow
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["requires-python"] == ">=3.10,<4"

    accepted = json.loads((VALIDATION / "component-map" / "accepted-map.json").read_text(encoding="utf-8"))
    assert accepted["map_state"] == "accepted"
    package_snapshots = [
        item for item in accepted["source_snapshot"]
        if item["source"].startswith("skills/server-ops/")
    ]
    assert package_snapshots
    assert all(item["kind"] == "file" and item["exists"] for item in package_snapshots)
    for item in accepted["source_snapshot"]:
        assert item["kind"] == "file" and item["exists"]
        assert hashlib.sha256((ROOT / item["source"]).read_bytes()).hexdigest() == item["sha256"]

    records = sorted((VALIDATION / "history").glob("*.json"))
    assert records
    record = json.loads(records[-1].read_text(encoding="utf-8"))
    assert record["scan"]["accepted_map"]["map_id"] == accepted["map_id"]
    for evidence in record["evidence_items"]:
        source = evidence["source"]
        path = ROOT / source["path"]
        payload = path.read_bytes()
        assert len(payload) == source["byte_size"]
        assert hashlib.sha256(payload).hexdigest() == source["sha256"]
    digest = record["integrity"]["canonical_payload_sha256"]
    report = VALIDATION / "reports" / (records[-1].stem + ".md")
    assert report.is_file()
    assert digest in report.read_text(encoding="utf-8")
