"""Typed process-local values for Update endpoint setup."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.source_projection.presentation import SourceDisplayValue


@dataclass(frozen=True)
class UpdateEndpointSetup:
    """Frozen readable catalog and initial Source/Target choices."""

    names: tuple[str, ...]
    source_name: str
    target_name: str
    current_context: str | None = None
    annotations: tuple[tuple[str, SourceDisplayValue], ...] = ()

    def __post_init__(self) -> None:
        if (
            len(self.names) < 2
            or len(set(self.names)) != len(self.names)
            or any(not isinstance(name, str) or not name for name in self.names)
        ):
            raise ValueError("Update setup requires two distinct readable names.")
        if (
            self.source_name not in self.names
            or self.target_name not in self.names
            or self.source_name == self.target_name
        ):
            raise ValueError("Update setup requires distinct available A/B defaults.")
        labels = dict(self.annotations)
        if len(labels) != len(self.annotations) or set(labels) - set(self.names):
            raise ValueError("Update setup annotations are outside its catalog.")


@dataclass(frozen=True)
class UpdateEndpointSelection:
    """One reviewed Update scope returned without planning or application."""

    source_name: str
    target_name: str
    source_descendants: bool = False
    target_descendants: bool = False
    source_memory_uid: str | None = None
    target_memory_uid: str | None = None
