from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "skills" / "server-ops"
INSTALLER = PACKAGE / "scripts" / "install_skill.py"
sys.path.insert(0, str(PACKAGE / "scripts"))

import install_skill as installer  # noqa: E402

sys.path.remove(str(PACKAGE / "scripts"))


def run_installer(destination: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(INSTALLER), "--destination", str(destination), "--json", *extra],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_manifest_verifies_and_fresh_install_is_rediscoverable(tmp_path: Path) -> None:
    destination = tmp_path / "skills" / "server-ops"
    result = run_installer(destination)
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["outcome"] == "installed"
    assert (destination / "SKILL.md").is_file()
    assert (destination / "scripts" / "server_ops.py").is_file()
    metadata = json.loads((destination / ".server-ops-install.json").read_text(encoding="utf-8"))
    assert metadata["version"] == "0.2.0"


def test_installer_refuses_unmanaged_or_modified_target(tmp_path: Path) -> None:
    unmanaged = tmp_path / "skills" / "unmanaged"
    unmanaged.mkdir(parents=True)
    refused = run_installer(unmanaged, "--update")
    assert refused.returncode == 3
    assert "not a managed" in refused.stderr

    managed = tmp_path / "skills" / "managed"
    assert run_installer(managed).returncode == 0
    (managed / "SKILL.md").write_text("changed", encoding="utf-8")
    modified = run_installer(managed, "--update")
    assert modified.returncode == 3
    assert "modified" in modified.stderr


def test_clean_update_preserves_rollback_backup(tmp_path: Path) -> None:
    destination = tmp_path / "skills" / "server-ops"
    assert run_installer(destination).returncode == 0
    updated = run_installer(destination, "--update")
    assert updated.returncode == 0, updated.stderr
    output = json.loads(updated.stdout)
    backup = Path(output["rollback_backup"])
    assert backup.is_dir()
    assert (backup / "SKILL.md").is_file()
    assert backup.parent == tmp_path / "backups" / "server-ops"
    assert not backup.is_relative_to(tmp_path / "skills")


def test_update_migrates_verified_legacy_backups_out_of_skill_registry(tmp_path: Path) -> None:
    destination = tmp_path / "skills" / "server-ops"
    assert run_installer(destination).returncode == 0
    legacy = destination.with_name("server-ops.backup-20260820T000000Z")
    shutil.copytree(destination, legacy)

    updated = run_installer(destination, "--update")

    assert updated.returncode == 0, updated.stderr
    output = json.loads(updated.stdout)
    migrated = output["migrated_legacy_backups"]
    assert len(migrated) == 1
    assert Path(migrated[0]["from"]) == legacy
    migrated_target = Path(migrated[0]["to"])
    assert migrated_target.parent == tmp_path / "backups" / "server-ops"
    assert (migrated_target / "SKILL.md").is_file()
    assert not legacy.exists()
    discoverable = sorted((tmp_path / "skills").glob("*/SKILL.md"))
    assert discoverable == [destination / "SKILL.md"]


def test_update_refuses_backup_root_inside_active_registry(tmp_path: Path) -> None:
    destination = tmp_path / "skills" / "server-ops"
    assert run_installer(destination).returncode == 0

    refused = run_installer(
        destination,
        "--update",
        "--backup-root",
        str(tmp_path / "skills" / "rollback"),
    )

    assert refused.returncode == 3
    assert "outside the active skill registry" in refused.stderr
    assert destination.is_dir()
    assert not (tmp_path / "skills" / "rollback").exists()


def test_update_refuses_unverified_legacy_backup_without_moving_it(tmp_path: Path) -> None:
    destination = tmp_path / "skills" / "server-ops"
    assert run_installer(destination).returncode == 0
    legacy = destination.with_name("server-ops.backup-20260820T000000Z")
    legacy.mkdir()
    (legacy / "SKILL.md").write_text("unmanaged", encoding="utf-8")

    refused = run_installer(destination, "--update")

    assert refused.returncode == 3
    assert "legacy rollback backup is not verified" in refused.stderr
    assert destination.is_dir()
    assert legacy.is_dir()
    assert not (tmp_path / "backups").exists()


def test_dry_run_has_no_side_effect(tmp_path: Path) -> None:
    destination = tmp_path / "skills" / "server-ops"
    result = run_installer(destination, "--dry-run")
    assert result.returncode == 0
    assert json.loads(result.stdout)["changed"] == "nothing"
    assert not destination.exists()

    nonstandard = run_installer(tmp_path / "custom" / "server-ops", "--dry-run")
    assert nonstandard.returncode == 3
    assert "nonstandard destination requires --backup-root" in nonstandard.stderr


def test_installer_refuses_linked_destination_backup_and_staging_boundaries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    probe_target = tmp_path / "probe-target"
    probe_target.mkdir()
    probe_link = tmp_path / "probe-link"
    try:
        probe_link.symlink_to(probe_target, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlink creation unavailable: {exc}")
    probe_link.unlink()
    probe_target.rmdir()

    real_destination = tmp_path / "real" / "skills" / "server-ops"
    assert run_installer(real_destination).returncode == 0
    linked_destination = tmp_path / "linked" / "skills" / "server-ops"
    linked_destination.parent.mkdir(parents=True)
    linked_destination.symlink_to(real_destination, target_is_directory=True)
    refused_destination = run_installer(linked_destination, "--update", "--dry-run")
    assert refused_destination.returncode == 3
    assert "symlink or reparse-point" in refused_destination.stderr

    destination = tmp_path / "backup-case" / "skills" / "server-ops"
    assert run_installer(destination).returncode == 0
    real_backup = tmp_path / "real-backup"
    real_backup.mkdir()
    linked_backup = tmp_path / "linked-backup"
    linked_backup.symlink_to(real_backup, target_is_directory=True)
    refused_backup = run_installer(
        destination,
        "--update",
        "--backup-root",
        str(linked_backup),
        "--dry-run",
    )
    assert refused_backup.returncode == 3
    assert "symlink or reparse-point" in refused_backup.stderr

    staging_root = tmp_path / "staging-case"
    real_staging = tmp_path / "real-staging"
    real_staging.mkdir()
    staging_root.mkdir()
    (staging_root / ".staging").symlink_to(real_staging, target_is_directory=True)
    staging_destination = staging_root / "skills" / "server-ops"
    refused_staging = run_installer(staging_destination)
    assert refused_staging.returncode == 3
    assert "symlink or reparse-point" in refused_staging.stderr
    assert not staging_destination.exists()

    metadata = real_destination / installer.INSTALL_METADATA
    outside_metadata = tmp_path / "outside-metadata.json"
    outside_metadata.write_text("must not be opened", encoding="utf-8")
    metadata.unlink()
    metadata.symlink_to(outside_metadata)
    original_open = Path.open

    def refuse_metadata_open(path: Path, *args, **kwargs):
        if path == metadata:
            raise AssertionError("installed metadata link was opened")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", refuse_metadata_open)
    with pytest.raises(installer.InstallRefusal) as metadata_error:
        installer.installed_manifest(real_destination)
    assert "symlink or reparse point" in str(metadata_error.value)


def test_installer_reports_recovery_required_when_rollback_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    destination = tmp_path / "skills" / "server-ops"
    assert run_installer(destination).returncode == 0
    original_verify = installer.verify_tree
    destination_checks = 0

    def force_postcondition_failure(root: Path, manifest: dict[str, object]) -> list[str]:
        nonlocal destination_checks
        problems = original_verify(root, manifest)
        if Path(root) == destination:
            destination_checks += 1
            if destination_checks == 2:
                return ["forced:postcondition"]
        return problems

    original_rmtree = installer.shutil.rmtree

    def fail_destination_removal(path: Path, *args, **kwargs) -> None:
        if Path(path) == destination:
            raise OSError("forced rollback removal failure")
        original_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(installer, "verify_tree", force_postcondition_failure)
    monkeypatch.setattr(installer.shutil, "rmtree", fail_destination_removal)
    code = installer.main([
        "--destination",
        str(destination),
        "--update",
        "--json",
    ])
    output = json.loads(capsys.readouterr().err)
    assert code == 6
    assert output["outcome"] == "recovery_required"
    assert output["error"]["code"] == "INSTALL_RECOVERY_REQUIRED"
    assert output["changed"] == "unknown; manual recovery required; do not retry"
    assert destination.exists()
