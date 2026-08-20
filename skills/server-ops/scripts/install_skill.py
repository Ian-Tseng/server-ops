from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from package_contract import (
    PackageContractError,
    is_link_like,
    safe_relative_path,
    validate_manifest_files,
    verify_tree as verify_package_tree,
)

ROOT = Path(__file__).absolute().parents[1]
MANIFEST_PATH = ROOT / "manifest.json"
INSTALL_METADATA = ".server-ops-install.json"
LEGACY_BACKUP_MARKER = ".backup-"
MAX_MANIFEST_BYTES = 1024 * 1024


class InstallRefusal(RuntimeError):
    pass


class InstallRecoveryRequired(RuntimeError):
    pass


def default_destination() -> Path:
    base = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    return base / "skills" / "server-ops"


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def safe_boundary(path: Path, label: str) -> Path:
    absolute = Path(os.path.abspath(os.path.expanduser(path)))
    for candidate in (absolute, *absolute.parents):
        if is_link_like(candidate):
            raise InstallRefusal(f"{label} crosses a symlink or reparse-point boundary: {candidate}")
    return absolute


def _read_regular_json(path: Path, label: str) -> Any:
    try:
        attributes = path.lstat()
    except FileNotFoundError as exc:
        raise InstallRefusal(f"{label} is missing") from exc
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    file_attributes = getattr(attributes, "st_file_attributes", 0)
    if path.is_symlink() or bool(flag and file_attributes & flag):
        raise InstallRefusal(f"{label} must not be a symlink or reparse point")
    if not stat.S_ISREG(attributes.st_mode):
        raise InstallRefusal(f"{label} is not a regular file")
    if attributes.st_size > MAX_MANIFEST_BYTES:
        raise InstallRefusal(f"{label} exceeds the 1 MiB limit")
    with path.open("rb") as stream:
        raw = stream.read(MAX_MANIFEST_BYTES + 1)
    if len(raw) > MAX_MANIFEST_BYTES:
        raise InstallRefusal(f"{label} exceeds the 1 MiB limit")
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InstallRefusal(f"{label} is not valid UTF-8 JSON") from exc


def _terminal_safe(value: Any) -> str:
    return "".join(
        character if unicodedata.category(character)[0] != "C" else "?"
        for character in str(value)
    )


def resolve_backup_root(destination: Path, requested: Path | None) -> Path:
    registry_root = safe_boundary(destination.parent, "active skill registry")
    if requested is None:
        if registry_root.name.casefold() != "skills":
            raise InstallRefusal(
                "nonstandard destination requires --backup-root outside its active skill registry"
            )
        backup_root = registry_root.parent / "backups" / destination.name
    else:
        backup_root = requested
    backup_root = safe_boundary(backup_root, "rollback backup root")
    if _is_within(backup_root, registry_root):
        raise InstallRefusal("rollback backup root must be outside the active skill registry")
    return backup_root


def load_manifest() -> dict[str, Any]:
    value = _read_regular_json(MANIFEST_PATH, "manifest.json")
    return validate_manifest(value, "manifest.json")


def validate_manifest(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InstallRefusal(f"{context} is not an object")
    if set(value) != {"schema_version", "product", "version", "files", "manifest_digest"}:
        raise InstallRefusal(f"{context} has unsupported fields")
    if value.get("schema_version") != 1 or value.get("product") != "server-ops":
        raise InstallRefusal(f"{context} has an unsupported shape")
    if not isinstance(value.get("version"), str) or not value["version"]:
        raise InstallRefusal(f"{context} has no version")
    try:
        validate_manifest_files(value.get("files"))
    except PackageContractError as exc:
        raise InstallRefusal(f"{context} has unsafe files: {exc}") from exc
    body = {key: value[key] for key in ("schema_version", "product", "version", "files")}
    payload = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if hashlib.sha256(payload).hexdigest() != value.get("manifest_digest"):
        raise InstallRefusal(f"{context} digest is invalid")
    return value


def verify_tree(root: Path, manifest: dict[str, Any]) -> list[str]:
    return verify_package_tree(root, manifest, install_metadata=INSTALL_METADATA)


def installed_manifest(destination: Path) -> dict[str, Any]:
    metadata_path = destination / INSTALL_METADATA
    try:
        metadata = _read_regular_json(metadata_path, "installed metadata")
    except InstallRefusal as exc:
        raise InstallRefusal(
            f"destination exists but is not a managed Local Server Ops installation: {exc}"
        ) from exc
    if not isinstance(metadata, dict):
        raise InstallRefusal("installed metadata is not an object")
    if set(metadata) != {"schema_version", "product", "version", "source", "installed_at", "manifest"}:
        raise InstallRefusal("installed metadata has unsupported fields")
    if metadata.get("schema_version") != 1 or metadata.get("product") != "server-ops":
        raise InstallRefusal("installed metadata has an unsupported identity")
    manifest = metadata.get("manifest")
    validated = validate_manifest(manifest, "installed manifest")
    if metadata.get("version") != validated["version"]:
        raise InstallRefusal("installed metadata version does not match its manifest")
    return validated


def copy_manifest_tree(destination: Path, manifest: dict[str, Any]) -> None:
    files = validate_manifest_files(manifest.get("files"))
    destination = safe_boundary(destination, "install destination")
    for relative in files:
        safe_relative = safe_relative_path(relative)
        source = ROOT / safe_relative
        target = destination / safe_relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    metadata = {
        "schema_version": 1,
        "product": "server-ops",
        "version": manifest["version"],
        "source": str(ROOT),
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "manifest": manifest,
    }
    (destination / INSTALL_METADATA).write_text(json.dumps(metadata, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _legacy_backup_plan(destination: Path, backup_root: Path) -> list[tuple[Path, Path]]:
    prefix = f"{destination.name}{LEGACY_BACKUP_MARKER}"
    planned: list[tuple[Path, Path]] = []
    for legacy in sorted(destination.parent.glob(f"{prefix}*"), key=lambda path: path.name):
        target = backup_root / legacy.name
        try:
            if is_link_like(legacy) or not legacy.is_dir():
                raise InstallRefusal("legacy path is not a regular managed directory")
            manifest = installed_manifest(legacy)
            problems = verify_tree(legacy, manifest)
            if problems:
                raise InstallRefusal(", ".join(problems[:8]))
        except (InstallRefusal, OSError, ValueError, json.JSONDecodeError) as exc:
            raise InstallRefusal(f"legacy rollback backup is not verified: {legacy}: {exc}") from exc
        if is_link_like(target) or target.exists():
            raise InstallRefusal(f"legacy rollback migration target already exists: {target}")
        planned.append((legacy, target))
    return planned


def install(
    destination: Path,
    *,
    update: bool,
    dry_run: bool,
    backup_root: Path | None = None,
) -> dict[str, Any]:
    manifest = load_manifest()
    source_problems = verify_tree(ROOT, manifest)
    if source_problems:
        raise InstallRefusal("source does not match manifest: " + ", ".join(source_problems[:8]))
    destination = safe_boundary(destination, "install destination")
    existing = destination.exists()
    backup: Path | None = None
    resolved_backup_root: Path | None = None
    legacy_plan: list[tuple[Path, Path]] = []
    if existing:
        if not update:
            raise InstallRefusal("destination already exists; use --update only after verifying it is managed and unchanged")
        prior_manifest = installed_manifest(destination)
        destination_problems = verify_tree(destination, prior_manifest)
        if destination_problems:
            raise InstallRefusal("installed copy was modified; refusing overwrite: " + ", ".join(destination_problems[:8]))
        resolved_backup_root = resolve_backup_root(destination, backup_root)
        legacy_plan = _legacy_backup_plan(destination, resolved_backup_root)
    if resolved_backup_root is None:
        resolved_backup_root = resolve_backup_root(destination, backup_root)
    if destination.parent.name.casefold() == "skills":
        staging_parent = destination.parent.parent / ".staging"
    else:
        staging_parent = resolved_backup_root.parent / ".staging"
    staging_parent = safe_boundary(staging_parent, "staging root")
    if dry_run:
        return {
            "outcome": "would_update" if existing else "would_install",
            "destination": str(destination),
            "version": manifest["version"],
            "rollback_root": str(resolved_backup_root),
            "would_migrate_legacy_backups": [str(source) for source, _target in legacy_plan],
            "changed": "nothing",
        }

    destination.parent.mkdir(parents=True, exist_ok=True)
    staging_parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix="server-ops-install-", dir=staging_parent))
    migrated: list[dict[str, str]] = []
    activated = False
    try:
        copy_manifest_tree(temporary, manifest)
        copied_problems = verify_tree(temporary, manifest)
        if copied_problems:
            raise InstallRefusal("temporary installed copy failed verification: " + ", ".join(copied_problems[:8]))
        if existing:
            resolved_backup_root.mkdir(parents=True, exist_ok=True)
            for legacy, target in legacy_plan:
                legacy.rename(target)
                migrated.append({"from": str(legacy), "to": str(target)})
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup = resolved_backup_root / f"{destination.name}{LEGACY_BACKUP_MARKER}{stamp}"
            if is_link_like(backup) or backup.exists():
                raise InstallRefusal(f"rollback backup already exists: {backup}")
            destination.rename(backup)
        temporary.rename(destination)
        activated = True
        problems = verify_tree(destination, manifest)
        if problems:
            raise InstallRefusal("installed postcondition failed: " + ", ".join(problems[:8]))
    except Exception as failure:
        rollback_errors: list[str] = []
        if activated and destination.exists():
            try:
                shutil.rmtree(destination)
            except OSError as exc:
                rollback_errors.append(f"remove activated destination: {exc}")
        if backup is not None and backup.exists():
            if destination.exists():
                rollback_errors.append("restore backup: destination is still occupied")
            else:
                try:
                    backup.rename(destination)
                except OSError as exc:
                    rollback_errors.append(f"restore backup: {exc}")
        for legacy, target in reversed(legacy_plan):
            if target.exists() and not legacy.exists():
                try:
                    target.rename(legacy)
                except OSError as exc:
                    rollback_errors.append(f"restore legacy backup {legacy}: {exc}")
        if temporary.exists():
            try:
                shutil.rmtree(temporary)
            except OSError as exc:
                rollback_errors.append(f"remove staging directory: {exc}")
        if rollback_errors:
            raise InstallRecoveryRequired(
                "installation outcome is uncertain; do not retry. "
                f"Inspect destination={destination}, backup={backup}, staging={temporary}. "
                + "; ".join(rollback_errors)
            ) from failure
        raise
    cleanup_warning = None
    if temporary.exists():
        try:
            shutil.rmtree(temporary)
        except OSError as exc:
            cleanup_warning = f"installed successfully but staging cleanup failed: {exc}"
    try:
        staging_parent.rmdir()
    except OSError:
        pass

    result = {
        "outcome": "updated" if existing else "installed",
        "destination": str(destination),
        "version": manifest["version"],
        "manifest_digest": manifest["manifest_digest"],
        "rollback_backup": str(backup) if backup else None,
        "rollback_root": str(resolved_backup_root),
        "migrated_legacy_backups": migrated,
        "active": "next Codex session",
    }
    if cleanup_warning:
        result["cleanup_warning"] = cleanup_warning
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install the verified Local Server Ops skill tree")
    parser.add_argument("--destination", type=Path, default=default_destination())
    parser.add_argument("--backup-root", type=Path)
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args(argv)
    try:
        result = install(
            args.destination,
            update=args.update,
            dry_run=args.dry_run,
            backup_root=args.backup_root,
        )
        print(json.dumps(result, sort_keys=True) if args.json_output else "\n".join(f"{key}: {_terminal_safe(value)}" for key, value in result.items()))
        return 0
    except InstallRecoveryRequired as exc:
        result = {
            "outcome": "recovery_required",
            "error": {"code": "INSTALL_RECOVERY_REQUIRED", "message": str(exc)},
            "changed": "unknown; manual recovery required; do not retry",
        }
        print(json.dumps(result, sort_keys=True) if args.json_output else f"RECOVERY REQUIRED [INSTALL_RECOVERY_REQUIRED]\n{_terminal_safe(exc)}", file=sys.stderr)
        return 6
    except (InstallRefusal, PackageContractError, OSError, ValueError, json.JSONDecodeError) as exc:
        result = {"outcome": "refused", "error": {"code": "INSTALL_REFUSED", "message": str(exc)}, "changed": "nothing; rollback completed if mutation began"}
        print(json.dumps(result, sort_keys=True) if args.json_output else f"REFUSED [INSTALL_REFUSED]\n{_terminal_safe(exc)}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
