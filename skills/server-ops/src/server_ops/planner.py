from __future__ import annotations

import platform
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from .errors import EXIT_REFUSED, OpsError
from .models import Adapter, ProcessCandidate, ServiceSpec
from .state import canonical_digest
from .discovery import psutil_available
from .provider import certified_start_available, launch_intent
from . import __version__


SUPPORTED_ACTIONS = {"start", "stop", "restart"}


def refusal_receipt(
    adapter: Adapter,
    service: ServiceSpec,
    action: str,
    candidates: list[ProcessCandidate],
    error: OpsError,
    workspace: str,
) -> dict[str, Any]:
    operation_id = str(uuid.uuid4())
    body: dict[str, Any] = {
        "schema_version": 1,
        "product": "server-ops",
        "product_version": __version__,
        "operation_id": operation_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "adapter_digest": adapter.digest,
        "workspace": workspace,
        "service_workspace": str(service.workspace.resolve()),
        "platform": platform.system().casefold(),
        "service_id": service.service_id,
        "action": action,
        "provider_cell": {
            "provider": "psutil" if service.match.configured and psutil_available() else "none",
            "provider_available": psutil_available(),
            "strategy": service.strategy,
            "action": action,
            "certification": (
                "disabled_by_adapter" if not service.mutation_enabled
                else "certified" if service.strategy == "direct_child" and action == "start" and certified_start_available()
                else "not_certified"
            ),
        },
        "verification_scope": "refusal_only_no_side_effect",
        "mutation_state": "refused",
        "verification_state": "not_run",
        "process_state": "observed" if candidates else "absent_or_unproven",
        "health_state": "not_checked",
        "side_effect_occurred": False,
        "target_candidates": [candidate.public_dict() for candidate in candidates[:8]],
        "error": error.as_dict()["error"],
        "next_action": error.next_action,
    }
    body["receipt_digest"] = canonical_digest(body)
    return body


def plan_mutation(adapter: Adapter, service: ServiceSpec, action: str, candidates: list[ProcessCandidate], workspace: str) -> dict[str, Any]:
    if action not in SUPPORTED_ACTIONS:
        raise OpsError("ACTION", f"Unsupported action: {action}", "Use start, stop, or restart.")
    if not service.mutation_enabled:
        raise OpsError("MUTATION_DISABLED", f"Mutation is disabled for service `{service.service_id}`.", "Review the adapter and keep using read-only status, or explicitly enable mutation after provider certification.", EXIT_REFUSED)
    if service.strategy != "direct_child" or action != "start" or not certified_start_available():
        raise OpsError(
            "CAPABILITY_NOT_CERTIFIED",
            f"No mutation provider is certified for `{service.strategy}.{action}` in this Local Server Ops build.",
            "Use `server-ops capabilities`; do not bypass the provider gate.",
            EXIT_REFUSED,
            {"strategy": service.strategy, "action": action},
        )
    if candidates:
        raise OpsError(
            "PROCESS_ALREADY_PRESENT",
            f"Service `{service.service_id}` is not absent, so start is refused.",
            "Inspect ownership and health; do not create a duplicate process.",
            EXIT_REFUSED,
            {"matched_candidates": len(candidates)},
        )
    created = datetime.now(timezone.utc)
    body: dict[str, Any] = {
        "schema_version": 2,
        "product": "server-ops",
        "product_version": __version__,
        "operation_id": str(uuid.uuid4()),
        "created_at": created.isoformat(),
        "expires_at": (created + timedelta(minutes=10)).isoformat(),
        "adapter_digest": adapter.digest,
        "workspace": workspace,
        "service_workspace": str(service.workspace.resolve()),
        "platform": "windows",
        "service_id": service.service_id,
        "action": action,
        "provider_cell": {
            "provider": "psutil",
            "provider_available": True,
            "strategy": "direct_child",
            "action": "start",
            "certification": "certified",
        },
        "launch_intent": launch_intent(service),
        "verification_scope": "process_identity_and_optional_health_after_apply",
        "mutation_state": "planned",
        "verification_state": "not_run",
        "process_state": "absent",
        "health_state": "not_checked",
        "side_effect_occurred": False,
        "target_candidates": [],
        "error": None,
        "next_action": "Review and approve this exact operation ID and receipt digest before apply.",
    }
    body["receipt_digest"] = canonical_digest(body)
    return body
