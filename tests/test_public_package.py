from __future__ import annotations

import json
import hashlib
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "skills" / "server-ops"
SCRIPTS = PACKAGE / "scripts"
sys.path.insert(0, str(SCRIPTS))

from install_skill import copy_manifest_tree, load_manifest, verify_tree  # noqa: E402
import build_manifest  # noqa: E402
import install_skill  # noqa: E402
import package_contract  # noqa: E402
from package_contract import PackageContractError  # noqa: E402

sys.path.remove(str(SCRIPTS))


def github_installed_skill(
    repo: str = "https://github.com/Ian-Tseng/server-ops",
    ref: str = "refs/tags/v0.2.1",
    pinned: str | None = None,
) -> str:
    source = (PACKAGE / "SKILL.md").read_text(encoding="utf-8")
    body = source.split("---", 2)[2].lstrip()
    pinned_line = f"    github-pinned: {pinned}\n" if pinned is not None else ""
    return (
        "---\n"
        "description: Inspect, diagnose, validate, and safely plan operations for local workspace HTTP services. Use when a developer asks whether a local server is running, healthy, bound to the intended checkout, or should be started, stopped, or restarted. Excludes production, remote hosts, containers/orchestrators, databases, and operating-system services.\n"
        "license: MIT\n"
        "metadata:\n"
        "    github-path: skills/server-ops\n"
        f"{pinned_line}"
        f"    github-ref: {ref}\n"
        f"    github-repo: {repo}\n"
        "    github-tree-sha: 0123456789abcdef0123456789abcdef01234567\n"
        "    short-description: Evidence-bound local server operations\n"
        "name: server-ops\n"
        "---\n"
        f"{body}"
    )


def test_manifest_verifies_repository_package() -> None:
    assert verify_tree(PACKAGE, load_manifest()) == []


def test_expected_github_metadata_is_normalized(tmp_path: Path) -> None:
    installed = tmp_path / "server-ops"
    shutil.copytree(PACKAGE, installed)
    (installed / "SKILL.md").write_text(github_installed_skill(), encoding="utf-8", newline="\n")
    assert verify_tree(installed, load_manifest()) == []


def test_pinned_github_metadata_is_normalized_and_bound_to_ref(tmp_path: Path) -> None:
    installed = tmp_path / "server-ops"
    shutil.copytree(PACKAGE, installed)
    (installed / "SKILL.md").write_text(
        github_installed_skill(pinned="v0.2.1"),
        encoding="utf-8",
        newline="\n",
    )
    assert verify_tree(installed, load_manifest()) == []

    (installed / "SKILL.md").write_text(
        github_installed_skill(pinned="v0.1.2"),
        encoding="utf-8",
        newline="\n",
    )
    assert any(problem.startswith("invalid:SKILL.md:") for problem in verify_tree(installed, load_manifest()))


def test_wrong_github_origin_and_extra_files_are_rejected(tmp_path: Path) -> None:
    installed = tmp_path / "server-ops"
    shutil.copytree(PACKAGE, installed)
    (installed / "SKILL.md").write_text(
        github_installed_skill("https://github.com/attacker/server-ops"),
        encoding="utf-8",
        newline="\n",
    )
    problems = verify_tree(installed, load_manifest())
    assert any(problem.startswith("invalid:SKILL.md:") for problem in problems)

    (installed / "SKILL.md").write_bytes((PACKAGE / "SKILL.md").read_bytes())
    (installed / "unexpected.py").write_text("pass\n", encoding="utf-8")
    assert "extra:unexpected.py" in verify_tree(installed, load_manifest())

    malicious = json.loads(json.dumps(load_manifest()))
    malicious["files"]["../../README.md"] = "0" * 64
    body = {key: malicious[key] for key in ("schema_version", "product", "version", "files")}
    payload = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    malicious["manifest_digest"] = hashlib.sha256(payload).hexdigest()
    escaped = tmp_path / "README.md"
    assert any(problem.startswith("invalid:manifest:") for problem in verify_tree(installed, malicious))
    with pytest.raises(PackageContractError):
        copy_manifest_tree(tmp_path / "nested" / "destination", malicious)
    assert not escaped.exists()


def test_github_update_refs_accept_main_and_reject_stale_release(tmp_path: Path) -> None:
    installed = tmp_path / "server-ops"
    shutil.copytree(PACKAGE, installed)
    (installed / "SKILL.md").write_text(
        github_installed_skill(ref="refs/heads/main"),
        encoding="utf-8",
        newline="\n",
    )
    assert verify_tree(installed, load_manifest()) == []

    (installed / "SKILL.md").write_text(
        github_installed_skill(ref="refs/tags/v0.1.2"),
        encoding="utf-8",
        newline="\n",
    )
    assert any(problem.startswith("invalid:SKILL.md:") for problem in verify_tree(installed, load_manifest()))


def test_manifest_ignores_generated_python_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    installed = tmp_path / "server-ops"
    shutil.copytree(PACKAGE, installed)
    generated = installed / "src" / "local_server_ops.egg-info"
    generated.mkdir()
    (generated / "PKG-INFO").write_text("generated", encoding="utf-8")
    assert verify_tree(installed, load_manifest()) == []

    outside = tmp_path / "outside-sensitive.txt"
    outside.write_text("must not be opened", encoding="utf-8")
    linked_manifest_file = installed / "README.md"
    linked_manifest_file.unlink()
    try:
        linked_manifest_file.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"file symlink creation unavailable: {exc}")
    original_canonical_bytes = package_contract.canonical_bytes

    def refuse_link_read(relative: str, path: Path) -> bytes:
        if relative == "README.md":
            raise AssertionError("linked manifested file was opened")
        return original_canonical_bytes(relative, path)

    monkeypatch.setattr(package_contract, "canonical_bytes", refuse_link_read)
    problems = package_contract.verify_tree(
        installed,
        load_manifest(),
        install_metadata=".server-ops-install.json",
    )
    assert "unsafe:README.md" in problems

    build_copy = tmp_path / "build-copy"
    shutil.copytree(PACKAGE, build_copy)
    outside_manifest = tmp_path / "outside-manifest.json"
    outside_manifest.write_text("unchanged", encoding="utf-8")
    linked_output = build_copy / "manifest.json"
    linked_output.unlink()
    linked_output.symlink_to(outside_manifest)
    monkeypatch.setattr(build_manifest, "ROOT", build_copy)
    monkeypatch.setattr(build_manifest, "OUTPUT", linked_output)
    with pytest.raises(PackageContractError):
        build_manifest.main()
    assert outside_manifest.read_text(encoding="utf-8") == "unchanged"

    source_manifest_link = tmp_path / "source-manifest.json"
    source_manifest_link.symlink_to(PACKAGE / "manifest.json")
    monkeypatch.setattr(install_skill, "MANIFEST_PATH", source_manifest_link)
    original_open = Path.open

    def refuse_manifest_open(path: Path, *args, **kwargs):
        if path == source_manifest_link:
            raise AssertionError("source manifest link was opened")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", refuse_manifest_open)
    with pytest.raises(install_skill.InstallRefusal):
        install_skill.load_manifest()


def test_public_install_docs_and_ci_contract() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "skills/server-ops/SKILL.md --agent codex" in readme
    assert "skills/server-ops/SKILL.md --agent claude-code" in readme
    assert "$server-ops" in readme and "/server-ops" in readme
    workflow = (ROOT / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8")
    assert "ubuntu-latest" in workflow
    assert "macos-latest" in workflow
    assert "windows-latest" in workflow
    assert "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1" in workflow
    assert "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97" in workflow
    assert '"pytest==8.3.5"' in workflow
    assert '"jsonschema==4.23.0"' in workflow


def test_manifest_declares_current_release_and_citation() -> None:
    manifest = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8"))
    citation = (PACKAGE / "CITATION.cff").read_text(encoding="utf-8")
    assert manifest["version"] == "0.2.1"
    assert "CITATION.cff" in manifest["files"]
    assert "version: 0.2.1" in citation
