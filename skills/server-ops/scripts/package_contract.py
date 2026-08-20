from __future__ import annotations

import hashlib
import os
import re
import stat
from pathlib import Path
from typing import Any


GITHUB_KEYS = {"github-path", "github-ref", "github-repo", "github-tree-sha"}
GITHUB_KEY = re.compile(r"^github-[a-z0-9-]+$")
TREE_SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST_SHA256 = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_PATH = "skills/server-ops"
EXPECTED_REPO = "https://github.com/Ian-Tseng/server-ops"
EXPECTED_REFS = {"refs/heads/main", "refs/tags/v0.1.2"}
TEXT_NAMES = {"LICENSE", "VERSION"}
TEXT_SUFFIXES = {".cff", ".json", ".md", ".py", ".toml", ".yaml", ".yml"}
IGNORED_NAMES = {".DS_Store", "Thumbs.db"}
IGNORED_PARTS = {"__pycache__"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}
MAX_PACKAGE_FILE_BYTES = 4 * 1024 * 1024


class PackageContractError(RuntimeError):
    pass


def safe_relative_path(value: Any) -> Path:
    if not isinstance(value, str) or not value or "\x00" in value or "\\" in value:
        raise PackageContractError("manifest path is not a canonical relative POSIX path")
    parts = value.split("/")
    path = Path(value)
    if (
        path.is_absolute()
        or path.drive
        or value.startswith("/")
        or any(part in {"", ".", ".."} for part in parts)
        or path.as_posix() != value
    ):
        raise PackageContractError("manifest path is not a canonical relative POSIX path")
    return path


def validate_manifest_files(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or not value:
        raise PackageContractError("manifest files must be a non-empty object")
    for relative, expected_digest in value.items():
        safe_relative_path(relative)
        if not isinstance(expected_digest, str) or not DIGEST_SHA256.fullmatch(expected_digest):
            raise PackageContractError("manifest file digest is not lowercase SHA-256")
    return value


def _frontmatter_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _validate_github(values: dict[str, str]) -> None:
    if set(values) != GITHUB_KEYS:
        missing = sorted(GITHUB_KEYS - set(values))
        unknown = sorted(set(values) - GITHUB_KEYS)
        details = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if unknown:
            details.append("unknown " + ", ".join(unknown))
        raise PackageContractError("GitHub metadata is incomplete or unsupported: " + "; ".join(details))
    if values["github-path"] != EXPECTED_PATH:
        raise PackageContractError("GitHub metadata has an unexpected package path")
    if values["github-repo"] != EXPECTED_REPO:
        raise PackageContractError("GitHub metadata has an unexpected repository")
    if values["github-ref"] not in EXPECTED_REFS:
        raise PackageContractError("GitHub metadata has an unexpected ref")
    if not TREE_SHA.fullmatch(values["github-tree-sha"]):
        raise PackageContractError("GitHub metadata has an invalid tree SHA")


def normalized_skill_bytes(path: Path) -> bytes:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise PackageContractError("SKILL.md is not readable UTF-8") from exc
    keep_ending = text.endswith(("\n", "\r"))
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise PackageContractError("SKILL.md frontmatter is missing")
    try:
        end = next(index for index, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration as exc:
        raise PackageContractError("SKILL.md frontmatter is not closed") from exc
    blocks: list[tuple[str | None, list[str]]] = []
    index = 0
    frontmatter = lines[1:end]
    while index < len(frontmatter):
        line = frontmatter[index]
        if not line.strip():
            index += 1
            continue
        if line[:1].isspace():
            raise PackageContractError("SKILL.md frontmatter contains an orphaned value")
        match = re.match(r"^([A-Za-z0-9_-]+)\s*:", line)
        key = match.group(1) if match else None
        block = [line]
        index += 1
        while index < len(frontmatter):
            child = frontmatter[index]
            if child.strip() and not child[:1].isspace():
                break
            block.append(child)
            index += 1
        if key == "metadata":
            retained: list[str] = []
            github: dict[str, str] = {}
            for child in block[1:]:
                child_match = re.match(r"^\s+([A-Za-z0-9-]+)\s*:\s*(.*?)\s*$", child)
                if child_match and GITHUB_KEY.fullmatch(child_match.group(1)):
                    child_key = child_match.group(1)
                    if child_key in github:
                        raise PackageContractError(f"GitHub metadata repeats {child_key}")
                    github[child_key] = _frontmatter_scalar(child_match.group(2))
                elif child_match:
                    retained.append(f"  {child_match.group(1)}: {child_match.group(2)}")
                else:
                    retained.append(child)
            if github:
                _validate_github(github)
            block = [line, *retained]
            if not any(item.strip() for item in retained):
                continue
        elif key and GITHUB_KEY.fullmatch(key):
            raise PackageContractError("GitHub metadata must be inside the metadata block")
        blocks.append((key, block))
    priority = {"name": 0, "description": 1, "license": 2}
    ordered = sorted(enumerate(blocks), key=lambda item: (priority.get(item[1][0] or "", 3), item[0]))
    normalized = [line for _, (_, block) in ordered for line in block]
    while normalized and not normalized[-1].strip():
        normalized.pop()
    body = lines[end + 1 :]
    while body and not body[0].strip():
        body.pop(0)
    rebuilt = ["---", *normalized, "---"]
    if body:
        rebuilt.extend(["", *body])
    result = "\n".join(rebuilt)
    if keep_ending:
        result += "\n"
    return result.encode("utf-8")


def canonical_bytes(relative: str, path: Path) -> bytes:
    try:
        attributes = path.lstat()
    except OSError as exc:
        raise PackageContractError(f"{relative} is not a readable regular file") from exc
    if is_link_like(path) or not stat.S_ISREG(attributes.st_mode):
        raise PackageContractError(f"{relative} is not a regular file")
    if attributes.st_size > MAX_PACKAGE_FILE_BYTES:
        raise PackageContractError(f"{relative} exceeds the 4 MiB package-file limit")
    if relative == "SKILL.md":
        return normalized_skill_bytes(path)
    if path.name in TEXT_NAMES or path.suffix.lower() in TEXT_SUFFIXES:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise PackageContractError(f"{relative} is not readable UTF-8") from exc
        return ("\n".join(text.splitlines()) + ("\n" if text else "")).encode("utf-8")
    return path.read_bytes()


def digest(relative: str, path: Path) -> str:
    return hashlib.sha256(canonical_bytes(relative, path)).hexdigest()


def is_link_like(path: Path) -> bool:
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except OSError:
        return False
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return path.is_symlink() or bool(flag and attributes & flag)


def _ignored(relative: Path) -> bool:
    return (
        any(part in IGNORED_PARTS or part.endswith(".egg-info") for part in relative.parts)
        or relative.name in IGNORED_NAMES
        or relative.suffix.lower() in IGNORED_SUFFIXES
    )


def verify_tree(root: Path, manifest: dict[str, Any], *, install_metadata: str) -> list[str]:
    problems: list[str] = []
    try:
        files = validate_manifest_files(manifest.get("files"))
    except PackageContractError as exc:
        return [f"invalid:manifest:{exc}"]
    if is_link_like(root):
        return ["unsafe:package-root-link"]
    try:
        resolved = root.resolve(strict=True)
    except OSError:
        return ["missing:package-root"]
    if not resolved.is_dir():
        return ["invalid:package-root"]
    for candidate in resolved.rglob("*"):
        if is_link_like(candidate):
            problems.append("unsafe:" + candidate.relative_to(resolved).as_posix())
    if problems:
        return sorted(problems)
    expected = set(files)
    for relative, expected_digest in files.items():
        path = resolved / safe_relative_path(relative)
        if not path.is_file():
            problems.append(f"missing:{relative}")
            continue
        try:
            actual = digest(relative, path)
        except PackageContractError as exc:
            problems.append(f"invalid:{relative}:{exc}")
            continue
        if actual != expected_digest:
            problems.append(f"changed:{relative}")
    allowed_extra = {"manifest.json", install_metadata}
    actual_files = set()
    for path in resolved.rglob("*"):
        if not path.is_file():
            continue
        relative_path = path.relative_to(resolved)
        if _ignored(relative_path):
            continue
        actual_files.add(relative_path.as_posix())
    for relative in sorted(actual_files - expected - allowed_extra):
        problems.append(f"extra:{relative}")
    return problems
