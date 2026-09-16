"""Process-local result returned by the Ground workspace viewer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GroundWorkspaceViewerResult:
    """The last process-local workspace surface selected before close."""

    context_name: str


__all__ = ["GroundWorkspaceViewerResult"]
