from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def adapter_document() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "services": [{
            "id": "example-server",
            "label": "Example Server",
            "workspace": ".",
            "mutation_enabled": False,
            "strategy": "read_only",
            "match": {"argv_contains": ["server.py"], "ports": [8090]},
            "health": {
                "url": "http://127.0.0.1:8090/health",
                "expected_status": 200,
                "expected_body": "OK",
                "timeout_ms": 500,
            },
        }],
    }


def write_adapter(root: Path, value: dict[str, Any]) -> Path:
    path = root / ".server-ops.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path
