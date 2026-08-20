from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from package_contract import PackageContractError, canonical_bytes, is_link_like

ROOT = Path(__file__).absolute().parents[1]
OUTPUT = ROOT / "manifest.json"
INCLUDE_ROOT_FILES = {
    "SKILL.md", "VERSION", "README.md", "PRIVACY.md", "CHANGELOG.md", "LICENSE", "CITATION.cff",
}
INCLUDE_DIRECTORIES = {"agents", "examples", "references", "schemas", "src"}
INCLUDE_SCRIPTS = {
    "scripts/server_ops.py",
    "scripts/install_skill.py",
    "scripts/build_manifest.py",
    "scripts/package_contract.py",
    "scripts/verify_package.py",
}


def included(path: Path) -> bool:
    relative = path.relative_to(ROOT).as_posix()
    if (
        "__pycache__" in path.parts
        or any(part.endswith(".egg-info") for part in path.parts)
        or path.suffix in {".pyc", ".pyo"}
    ):
        return False
    if relative in INCLUDE_ROOT_FILES or relative in INCLUDE_SCRIPTS:
        return True
    return relative.split("/", 1)[0] in INCLUDE_DIRECTORIES


def safe_package_files() -> list[Path]:
    if is_link_like(ROOT):
        raise PackageContractError("refusing to build through a linked package root")
    files: list[Path] = []
    pending = [ROOT]
    while pending:
        directory = pending.pop()
        try:
            with os.scandir(directory) as scanned:
                entries = sorted(scanned, key=lambda entry: entry.name)
        except OSError as exc:
            raise PackageContractError(f"package directory is not readable: {directory}") from exc
        for entry in entries:
            path = Path(entry.path)
            if is_link_like(path):
                raise PackageContractError(f"refusing to build through linked package entry: {path.relative_to(ROOT)}")
            if entry.is_dir(follow_symlinks=False):
                pending.append(path)
            elif entry.is_file(follow_symlinks=False):
                files.append(path)
    return sorted(files, key=lambda value: value.as_posix())


def build() -> dict[str, object]:
    files: dict[str, str] = {}
    for path in safe_package_files():
        if path == OUTPUT or not included(path):
            continue
        relative = path.relative_to(ROOT).as_posix()
        files[relative] = hashlib.sha256(canonical_bytes(relative, path)).hexdigest()
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    manifest: dict[str, object] = {
        "schema_version": 1,
        "product": "server-ops",
        "version": version,
        "files": files,
    }
    payload = json.dumps(manifest, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    manifest["manifest_digest"] = hashlib.sha256(payload).hexdigest()
    return manifest


def main() -> int:
    manifest = build()
    if is_link_like(OUTPUT):
        raise PackageContractError("refusing to overwrite a linked manifest.json")
    OUTPUT.write_text(json.dumps(manifest, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
