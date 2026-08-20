from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import stat
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .errors import EXIT_REFUSED, OpsError


MAX_RECEIPT_BYTES = 256 * 1024
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SERVICE_ID = re.compile(r"^[a-z][a-z0-9-]{0,62}$")
VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
RECEIPT_KEYS = {
    "schema_version", "product", "product_version", "operation_id", "created_at",
    "adapter_digest", "workspace", "service_workspace", "platform", "service_id", "action",
    "provider_cell", "verification_scope", "mutation_state",
    "verification_state", "process_state", "health_state",
    "side_effect_occurred", "target_candidates", "error", "next_action",
    "receipt_digest",
}
PROVIDER_KEYS = {"provider", "provider_available", "strategy", "action", "certification"}


def state_root() -> Path:
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "LocalServerOps" / "state"
    configured = os.environ.get("XDG_STATE_HOME")
    if configured:
        return Path(configured) / "server-ops"
    return Path.home() / ".local" / "state" / "server-ops"


def workspace_key(workspace: Path) -> str:
    canonical = os.path.normcase(str(workspace.resolve())).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()[:24]


def workspace_state(workspace: Path) -> Path:
    return state_root() / "workspaces" / workspace_key(workspace)


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        path.parent.chmod(0o700)
    encoded = (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if len(encoded) > MAX_RECEIPT_BYTES:
        raise OpsError("JOURNAL_TOO_LARGE", "Operation record exceeds the 256 KiB limit.", "Reduce bounded observations before retrying.", EXIT_REFUSED)
    handle, temporary_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        if os.name != "nt":
            os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, path)
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass


def canonical_digest(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _valid_operation_id(operation_id: str) -> bool:
    try:
        return str(uuid.UUID(operation_id)) == operation_id
    except (ValueError, AttributeError):
        return False


def _receipt_error(code: str, message: str) -> OpsError:
    return OpsError(
        code,
        message,
        "Discard the local receipt and request a fresh plan.",
        EXIT_REFUSED,
    )


def _one_of(value: Any, allowed: set[str]) -> bool:
    return isinstance(value, str) and value in allowed


def validate_receipt(
    value: Any,
    *,
    operation_id: str,
    workspace: Path,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != RECEIPT_KEYS:
        raise _receipt_error("RECEIPT_SCHEMA", "Stored receipt fields do not match schema version 1.")
    if value["schema_version"] != 1 or value["product"] != "server-ops":
        raise _receipt_error("RECEIPT_IDENTITY", "Stored receipt product identity is unsupported.")
    if not isinstance(value["product_version"], str) or not VERSION.fullmatch(value["product_version"]):
        raise _receipt_error("RECEIPT_IDENTITY", "Stored receipt product version is invalid.")
    if value["operation_id"] != operation_id or not _valid_operation_id(value["operation_id"]):
        raise _receipt_error("RECEIPT_IDENTITY", "Stored receipt operation identity is invalid.")
    try:
        created_at = datetime.fromisoformat(value["created_at"])
    except (TypeError, ValueError):
        raise _receipt_error("RECEIPT_SCHEMA", "Stored receipt timestamp is invalid.")
    if created_at.tzinfo is None:
        raise _receipt_error("RECEIPT_SCHEMA", "Stored receipt timestamp must include a timezone.")
    if not isinstance(value["adapter_digest"], str) or not SHA256.fullmatch(value["adapter_digest"]):
        raise _receipt_error("RECEIPT_SCHEMA", "Stored receipt adapter digest is invalid.")
    expected_workspace = str(workspace.resolve())
    if value["workspace"] != expected_workspace:
        raise _receipt_error("RECEIPT_WORKSPACE_MISMATCH", "Stored receipt belongs to a different canonical workspace.")
    if not isinstance(value["service_workspace"], str):
        raise _receipt_error("RECEIPT_SCHEMA", "Stored receipt service workspace is invalid.")
    try:
        service_workspace = str(Path(value["service_workspace"]).resolve())
        if os.path.commonpath((expected_workspace, service_workspace)) != expected_workspace:
            raise ValueError
    except (OSError, ValueError):
        raise _receipt_error("RECEIPT_WORKSPACE_MISMATCH", "Stored receipt service workspace is outside its request workspace.")
    if value["service_workspace"] != service_workspace:
        raise _receipt_error("RECEIPT_WORKSPACE_MISMATCH", "Stored receipt service workspace is not canonical.")
    if not _one_of(value["platform"], {"windows", "linux", "darwin"}):
        raise _receipt_error("RECEIPT_SCHEMA", "Stored receipt platform is invalid.")
    if not isinstance(value["service_id"], str) or not SERVICE_ID.fullmatch(value["service_id"]):
        raise _receipt_error("RECEIPT_SCHEMA", "Stored receipt service identity is invalid.")
    if not _one_of(value["action"], {"start", "stop", "restart"}):
        raise _receipt_error("RECEIPT_SCHEMA", "Stored receipt action is invalid.")
    provider = value["provider_cell"]
    if (
        not isinstance(provider, dict)
        or set(provider) != PROVIDER_KEYS
        or not _one_of(provider["provider"], {"none", "psutil"})
        or type(provider["provider_available"]) is not bool
        or (provider["provider"] == "psutil" and not provider["provider_available"])
        or not _one_of(provider["strategy"], {"read_only", "direct_child", "watchdog_child"})
        or provider["action"] != value["action"]
        or not _one_of(provider["certification"], {"disabled_by_adapter", "not_certified"})
    ):
        raise _receipt_error("RECEIPT_SCHEMA", "Stored receipt provider cell is invalid.")
    if value["verification_scope"] != "refusal_only_no_side_effect":
        raise _receipt_error("RECEIPT_SCHEMA", "Stored receipt verification scope is invalid.")
    if value["mutation_state"] != "refused" or value["verification_state"] != "not_run":
        raise _receipt_error("RECEIPT_SCHEMA", "Stored receipt lifecycle states are invalid.")
    if not _one_of(value["process_state"], {"observed", "absent_or_unproven"}) or value["health_state"] != "not_checked":
        raise _receipt_error("RECEIPT_SCHEMA", "Stored receipt observation states are invalid.")
    if value["side_effect_occurred"] is not False:
        raise _receipt_error("RECEIPT_SCHEMA", "Stored refusal receipt has an invalid side-effect state.")
    if (
        not isinstance(value["target_candidates"], list)
        or len(value["target_candidates"]) > 8
        or any(not isinstance(candidate, dict) for candidate in value["target_candidates"])
    ):
        raise _receipt_error("RECEIPT_SCHEMA", "Stored receipt candidates are invalid.")
    error = value["error"]
    if (
        not isinstance(error, dict)
        or set(error) != {"code", "message", "details"}
        or not isinstance(error["code"], str)
        or not isinstance(error["message"], str)
        or not isinstance(error["details"], dict)
    ):
        raise _receipt_error("RECEIPT_SCHEMA", "Stored receipt error is invalid.")
    if not isinstance(value["next_action"], str):
        raise _receipt_error("RECEIPT_SCHEMA", "Stored receipt next action is invalid.")
    supplied_digest = value["receipt_digest"]
    if not isinstance(supplied_digest, str) or not SHA256.fullmatch(supplied_digest):
        raise _receipt_error("RECEIPT_DIGEST_INVALID", "Stored receipt digest is invalid.")
    body = dict(value)
    body.pop("receipt_digest")
    if not hmac.compare_digest(canonical_digest(body), supplied_digest):
        raise _receipt_error("RECEIPT_DIGEST_MISMATCH", "Stored receipt content does not match its digest.")
    return value


def write_receipt(workspace: Path, operation_id: str, value: dict[str, Any]) -> Path:
    if not _valid_operation_id(operation_id):
        raise _receipt_error("OPERATION_ID", "Operation ID is invalid.")
    validate_receipt(value, operation_id=operation_id, workspace=workspace)
    path = workspace_state(workspace) / "receipts" / f"{operation_id}.json"
    atomic_write_json(path, value)
    return path


def read_receipt(workspace: Path, operation_id: str) -> dict[str, Any]:
    if not _valid_operation_id(operation_id):
        raise OpsError("OPERATION_ID", "Operation ID is invalid.", "Copy the exact operation ID from a prior receipt.")
    path = workspace_state(workspace) / "receipts" / f"{operation_id}.json"
    try:
        attributes = path.lstat()
    except FileNotFoundError:
        raise OpsError("RECEIPT_NOT_FOUND", f"No local receipt exists for {operation_id}.", "Run `server-ops status` or provide the correct workspace.")
    file_attributes = getattr(attributes, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if path.is_symlink() or bool(reparse_flag and file_attributes & reparse_flag):
        raise _receipt_error("RECEIPT_LINK", "Stored receipt must be a regular file, not a link or reparse point.")
    if not stat.S_ISREG(attributes.st_mode):
        raise _receipt_error("RECEIPT_NOT_REGULAR", "Stored receipt must be a regular file.")
    with path.open("rb") as stream:
        raw = stream.read(MAX_RECEIPT_BYTES + 1)
    if len(raw) > MAX_RECEIPT_BYTES:
        raise _receipt_error("RECEIPT_TOO_LARGE", "Stored receipt exceeds the 256 KiB limit.")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise _receipt_error("RECEIPT_JSON", "Stored receipt is not valid UTF-8 JSON.")
    return validate_receipt(value, operation_id=operation_id, workspace=workspace)
