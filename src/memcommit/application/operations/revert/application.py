"""Typed application boundary for checkpoint Revert."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from memcommit.application.capabilities.checkpoint_catalog import (
    ResolvedCheckpointUnit,
)
from memcommit.application.operations.revert.restoration import (
    CheckpointRestoration,
)


@dataclass(frozen=True)
class RevertRequest:
    """One reviewed checkpoint-unit restoration request."""

    unit: ResolvedCheckpointUnit
    keep_history: bool = True


class RevertPort(Protocol):
    """Effect boundary required by the Revert operation."""

    def restore(self, request: RevertRequest) -> CheckpointRestoration: ...


def run_revert(
    request: RevertRequest,
    *,
    port: RevertPort,
) -> CheckpointRestoration:
    """Apply one exact reviewed Revert request."""

    return port.restore(request)
