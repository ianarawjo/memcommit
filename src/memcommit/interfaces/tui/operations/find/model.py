"""Process-local setup and close values for deterministic Find."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.application.operations.find.literal_application import LiteralFindResult
from memcommit.source_projection.presentation import SourceDisplayValue


@dataclass(frozen=True, slots=True)
class LiteralFindTuiSetup:
    names: tuple[str, ...]
    current_name: str
    initial_targets: tuple[str, ...]
    annotations: tuple[tuple[str, SourceDisplayValue], ...] = ()

    def __post_init__(self) -> None:
        if (
            not self.names
            or len(set(self.names)) != len(self.names)
            or any(not isinstance(name, str) or not name for name in self.names)
        ):
            raise ValueError("Find TUI requires a distinct readable catalog.")
        if self.current_name not in self.names:
            raise ValueError("Find TUI current Context is outside the catalog.")
        if (
            not self.initial_targets
            or len(set(self.initial_targets)) != len(self.initial_targets)
            or any(name not in self.names for name in self.initial_targets)
        ):
            raise ValueError("Find TUI targets are outside the catalog.")
        annotations = dict(self.annotations)
        if len(annotations) != len(self.annotations) or set(annotations) - set(
            self.names
        ):
            raise ValueError("Find TUI annotations are outside the catalog.")


@dataclass(frozen=True, slots=True)
class LiteralFindTuiOutcome:
    result: LiteralFindResult

    def __post_init__(self) -> None:
        if not isinstance(self.result, LiteralFindResult):
            raise ValueError("Find TUI requires one complete typed result.")


__all__ = ["LiteralFindTuiOutcome", "LiteralFindTuiSetup"]
