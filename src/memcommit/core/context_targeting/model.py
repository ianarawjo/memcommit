"""Operation-neutral values describing Context targets and lexical reach."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ContextSelectionMode = Literal["SINGLE", "MULTIPLE"]


@dataclass(frozen=True, slots=True)
class ContextSubtreeTarget:
    """One lexical Context subtree selected from a frozen target catalog.

    The value records semantic reach without retaining picker expansion,
    cursor, or presentation state. The calling operation remains responsible
    for expanding the canonical name against its frozen catalog.
    """

    name: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("A Context subtree target requires a canonical name.")

    @property
    def context_name(self) -> str:
        """Expose the target through the canonical Context-coordinate spelling."""

        return self.name


@dataclass(frozen=True, slots=True)
class CheckpointTarget:
    """One exact retained checkpoint plus its canonical ordinary-local owner."""

    context_name: str
    checkpoint_uid: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.context_name, str)
            or not self.context_name
            or not isinstance(self.checkpoint_uid, str)
            or not self.checkpoint_uid
        ):
            raise ValueError(
                "A checkpoint target requires a Context name and exact UID."
            )


@dataclass(frozen=True)
class DirectMemoryLocator:
    """One Memory selector with an optional explicitly named direct owner."""

    memory_selector: str
    context_locator: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.memory_selector, str) or not self.memory_selector:
            raise ValueError("A direct Memory locator requires a nonempty selector.")
        if self.context_locator is not None and (
            not isinstance(self.context_locator, str) or not self.context_locator
        ):
            raise ValueError(
                "A qualified direct Memory locator requires a nonempty Context."
            )
