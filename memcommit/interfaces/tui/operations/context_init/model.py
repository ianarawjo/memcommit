"""Frozen setup values for the Context Init terminal adapter."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ContextInitTuiSetup:
    """Host-provided namespace and validator for one exact name edit."""

    expected_current: str | None
    context_names: tuple[str, ...]
    validate_name: Callable[[str], object] = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if (
            len(set(self.context_names)) != len(self.context_names)
            or any(not isinstance(name, str) or not name for name in self.context_names)
        ):
            raise ValueError("Context Init TUI requires a distinct local catalog.")
        if self.expected_current is not None and (
            not isinstance(self.expected_current, str)
            or not self.expected_current
        ):
            raise ValueError("Context Init TUI current Context is invalid.")
        if not callable(self.validate_name):
            raise TypeError("Context Init TUI requires a name validator.")
