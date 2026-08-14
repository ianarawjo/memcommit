"""Small, interface-neutral Help contract for one public operation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ExecutionKind(str, Enum):
    """How an operation reaches its substantive result.

    This deliberately describes only the public execution contract. Semantic
    operations still surround provider inference with deterministic authority,
    validation, receipt, and apply checks.
    """

    DETERMINISTIC = "DETERMINISTIC"
    SEMANTIC = "SEMANTIC"
    MIXED = "MIXED"


@dataclass(frozen=True)
class OperationHelp:
    """Stable meaning shared by CLI, TUI, Python, and future tool adapters.

    Flag spellings, defaults, current authority, and cache outcomes are not
    repeated here. Their owning adapters or runtime receipts remain the source
    of truth for those changeable details.
    """

    name: str
    summary: str
    flow: str
    execution: ExecutionKind
    effect: str
    range: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("name", "summary", "flow", "effect"):
            value = getattr(self, field_name)
            if not value.strip():
                raise ValueError(f"Operation Help {field_name} must be nonblank.")
        if self.range is not None and not self.range.strip():
            raise ValueError("Operation Help range must be nonblank when present.")
