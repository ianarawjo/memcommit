"""Process-local setup values for the deterministic Replace workbench."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReplaceTuiSetup:
    names: tuple[str, ...]
    current_name: str
    initial_targets: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            not self.names
            or len(set(self.names)) != len(self.names)
            or any(not isinstance(name, str) or not name for name in self.names)
        ):
            raise ValueError("Replace TUI requires a distinct local catalog.")
        if self.current_name not in self.names:
            raise ValueError("Replace TUI current Context is outside the catalog.")
        if (
            not self.initial_targets
            or len(set(self.initial_targets)) != len(self.initial_targets)
            or any(name not in self.names for name in self.initial_targets)
        ):
            raise ValueError("Replace TUI targets are outside the local catalog.")


__all__ = ["ReplaceTuiSetup"]
