from __future__ import annotations

import platform
import uuid
from datetime import datetime, timezone
from typing import Any

from .errors import EXIT_REFUSED, OpsError
from .models import Adapter, ProcessCandidate, ServiceSpec
from .state import canonical_digest
from .discovery import psutil_available
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
            "certification": "disabled_by_adapter" if not service.mutation_enabled else "not_certified",
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


def plan_mutation(adapter: Adapter, service: ServiceSpec, action: str, candidates: list[ProcessCandidate]) -> dict[str, Any]:
    if action not in SUPPORTED_ACTIONS:
        raise OpsError("ACTION", f"Unsupported action: {action}", "Use start, stop, or restart.")
    if not service.mutation_enabled:
        raise OpsError("MUTATION_DISABLED", f"Mutation is disabled for service `{service.service_id}`.", "Review the adapter and keep using read-only status, or explicitly enable mutation after provider certification.", EXIT_REFUSED)
    raise OpsError(
        "CAPABILITY_NOT_CERTIFIED",
        f"No mutation provider is certified for `{service.strategy}.{action}` in Local Server Ops 0.1.1.",
        "Use `server-ops capabilities`; do not bypass the provider gate.",
        EXIT_REFUSED,
        {"strategy": service.strategy, "action": action},
    )
