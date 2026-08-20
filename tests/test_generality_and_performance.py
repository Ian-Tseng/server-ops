from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "skills" / "server-ops"


def test_adapter_free_status_completes_under_two_seconds_on_certifying_host(tmp_path: Path) -> None:
    started = time.monotonic()
    result = subprocess.run(
        [sys.executable, str(PACKAGE / "scripts" / "server_ops.py"), "--workspace", str(tmp_path), "--json", "status"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=2.0,
        check=False,
    )
    elapsed = time.monotonic() - started
    assert result.returncode == 0, result.stderr
    assert elapsed < 2.0
    assert '"changed": "nothing"' in result.stdout


def test_reusable_core_has_no_case_study_identifiers() -> None:
    forbidden = {
        "concept_graph_and_question_generation",
        "logic" + "_guided_rag_experiment",
        "server_for_generate_question",
        "question-server",
    }
    scoped_files = [PACKAGE / "SKILL.md"]
    scoped_files.extend((PACKAGE / "src" / "server_ops").glob("*.py"))
    scoped_files.extend((PACKAGE / "schemas").glob("*.json"))
    scoped_files.extend((PACKAGE / "examples").glob("*.json"))
    combined = "\n".join(path.read_text(encoding="utf-8") for path in scoped_files).casefold()
    assert not forbidden.intersection(combined)
