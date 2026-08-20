from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


EXIT_SUCCESS = 0
EXIT_INVALID_INPUT = 2
EXIT_REFUSED = 3
EXIT_MUTATION_FAILED = 4
EXIT_VERIFICATION_FAILED = 5
EXIT_RECOVERY_REQUIRED = 6
EXIT_INTERNAL_ERROR = 7


@dataclass
class OpsError(Exception):
    code: str
    message: str
    next_action: str
    exit_code: int = EXIT_INVALID_INPUT
    details: dict[str, Any] = field(default_factory=dict)
    side_effect_occurred: bool = False

    def __str__(self) -> str:
        return self.message

    def as_dict(self) -> dict[str, Any]:
        return {
            "outcome": "refused" if self.exit_code == EXIT_REFUSED else "error",
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            },
            "side_effect_occurred": self.side_effect_occurred,
            "next_action": self.next_action,
        }
