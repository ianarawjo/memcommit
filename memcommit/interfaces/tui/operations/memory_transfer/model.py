"""Typed setup state for interactive direct-Memory Copy and Move."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryTransferTuiSetup:
    """Frozen ordinary-local Source and Target catalog for one launch."""

    context_names: tuple[str, ...]
    current_context: str | None = None

    def __post_init__(self) -> None:
        if (
            not self.context_names
            or len(set(self.context_names)) != len(self.context_names)
            or any(not isinstance(name, str) or not name for name in self.context_names)
        ):
            raise ValueError(
                "Interactive Memory transfer requires distinct local Contexts."
            )
        if (
            self.current_context is not None
            and self.current_context not in self.context_names
        ):
            raise ValueError(
                "Memory transfer current Context is outside the local catalog."
            )


__all__ = ["MemoryTransferTuiSetup"]
