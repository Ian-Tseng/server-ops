#!/usr/bin/env python3
"""Emit one content-free SkillOutcomeReceipt after substantive skill work."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

import update_policy


OWNER = "Ian-Tseng"
MARKER_PREFIX = "SKILL_OUTCOME_RECEIPT_V1:"
OUTCOMES = ("completed", "completed_with_limitations", "failed")
QUALITY_SIGNALS = (
    "claim_evidence_gap",
    "lifecycle_inconsistency",
    "documentation_mismatch",
    "internal_failure",
    "no_issue",
)
MAX_RECEIPT_BYTES = 3072
MAX_MARKER_BYTES = 4096


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def receipt_digest(value: Mapping[str, Any]) -> str:
    payload = dict(value)
    payload.pop("receipt_digest_sha256", None)
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def create_receipt(
    *,
    skill_root: Path,
    outcome: str,
    quality_signal: str,
    ttl_seconds: int,
) -> tuple[dict[str, Any], str]:
    if not 1 <= ttl_seconds <= 86400:
        raise ValueError("ttl-seconds must be between 1 and 86400")
    package_digest = update_policy.verify_package_manifest(skill_root)
    version = update_policy.package_version(skill_root)
    skill_name = skill_root.name
    now = datetime.now(timezone.utc).replace(microsecond=0)
    receipt: dict[str, Any] = {
        "schema_version": 1,
        "receipt_id": str(uuid.uuid4()),
        "producer": {
            "owner": OWNER,
            "repository": skill_name,
            "skill": skill_name,
            "version": version,
            "package_digest_sha256": package_digest,
            "identity_authority": "producer_declared_untrusted",
        },
        "outcome": outcome,
        "quality_signal": quality_signal,
        "requested_action": "none" if quality_signal == "no_issue" else "analyze_quality",
        "action_performed": False,
        "created_at_utc": utc_text(now),
        "expires_at_utc": utc_text(now + timedelta(seconds=ttl_seconds)),
        "causal_depth": 0,
        "prior_receipt_digest_sha256": None,
    }
    receipt["receipt_digest_sha256"] = receipt_digest(receipt)
    encoded = canonical_bytes(receipt)
    if len(encoded) > MAX_RECEIPT_BYTES:
        raise ValueError("receipt exceeds the v1 size limit")
    marker = MARKER_PREFIX + base64.urlsafe_b64encode(encoded).decode("ascii").rstrip("=")
    if len(marker.encode("utf-8")) > MAX_MARKER_BYTES:
        raise ValueError("receipt marker exceeds the v1 size limit")
    return receipt, marker


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--format", choices=("json", "text"), default="text")
    commands = result.add_subparsers(dest="command", required=True)
    emit = commands.add_parser("emit")
    emit.add_argument("--outcome", choices=OUTCOMES, required=True)
    emit.add_argument("--quality-signal", choices=QUALITY_SIGNALS, required=True)
    emit.add_argument("--ttl-seconds", type=int, default=3600)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        receipt, marker = create_receipt(
            skill_root=SCRIPT_DIRECTORY.parent,
            outcome=args.outcome,
            quality_signal=args.quality_signal,
            ttl_seconds=args.ttl_seconds,
        )
    except (OSError, ValueError, update_policy.PolicyError) as exc:
        error = {"status": "RECEIPT_ERROR", "message": str(exc), "outbound": "NONE"}
        print(json.dumps(error, sort_keys=True) if args.format == "json" else error["message"], file=sys.stderr)
        return 3
    result = {
        "status": "RECEIPT_READY",
        "package_digest_sha256": receipt["producer"]["package_digest_sha256"],
        "receipt": receipt,
        "marker": marker,
        "outbound": "NONE",
    }
    print(json.dumps(result, sort_keys=True) if args.format == "json" else marker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
