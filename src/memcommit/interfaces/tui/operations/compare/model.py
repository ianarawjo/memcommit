"""Typed process-local values for Compare endpoint setup."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.source_projection.presentation import SourceDisplayValue


@dataclass(frozen=True)
class CompareTuiSetup:
    """Frozen readable catalog and initial A/B choices supplied by Compare."""

    names: tuple[str, ...]
    reference_name: str
    peer_name: str
    current_context: str | None = None
    annotations: tuple[tuple[str, SourceDisplayValue], ...] = ()

    def __post_init__(self) -> None:
        if (
            len(self.names) < 2
            or len(set(self.names)) != len(self.names)
            or any(not isinstance(name, str) or not name for name in self.names)
        ):
            raise ValueError("Compare setup requires two distinct readable names.")
        if (
            self.reference_name not in self.names
            or self.peer_name not in self.names
            or self.reference_name == self.peer_name
        ):
            raise ValueError("Compare setup requires distinct available A/B defaults.")
        labels = dict(self.annotations)
        if len(labels) != len(self.annotations) or set(labels) - set(self.names):
            raise ValueError("Compare setup annotations are outside its catalog.")


@dataclass(frozen=True)
class CompareEndpointSelection:
    """One reviewed Compare scope returned without running the operation."""

    reference_name: str
    peer_name: str
    reference_descendants: bool = False
    peer_descendants: bool = False
    reference_memory_uid: str | None = None
    peer_memory_uid: str | None = None
