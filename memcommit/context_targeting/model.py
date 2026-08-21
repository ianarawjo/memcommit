"""Operation-neutral values describing Context targets and lexical reach."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal


ContextSelectionMode = Literal["SINGLE", "MULTIPLE"]


@dataclass(frozen=True)
class ContextScope:
    """One frozen set of Context names and its lexical descendant policy.

    Embedded-Context traversal is deliberately not part of this value.  It is
    a loading policy that some read operations expose independently, whereas
    lexical reach is shared by Find and saved-session operations.
    """

    target_names: tuple[str, ...]
    include_descendants: bool

    @classmethod
    def create(
        cls,
        target_names: Sequence[str],
        *,
        include_descendants: bool,
    ) -> "ContextScope":
        names = tuple(target_names)
        if (
            not names
            or len(set(names)) != len(names)
            or any(not isinstance(name, str) or not name for name in names)
        ):
            raise ValueError("Context scope requires distinct named targets.")
        if type(include_descendants) is not bool:
            raise ValueError("Context descendant scope must be a boolean.")
        return cls(names, include_descendants)


@dataclass(frozen=True)
class DirectMemoryTarget:
    """One exact direct Memory selected inside its owning Context.

    Hover and expansion are deliberately absent.  This value is the semantic
    receipt that a selector may hand to an operation after explicit choice.
    """

    context_name: str
    selector: str

    @property
    def memory_uid(self) -> str:
        """Expose the selector's semantic spelling to operation adapters."""

        return self.selector

    def __post_init__(self) -> None:
        if (
            not isinstance(self.context_name, str)
            or not self.context_name
            or not isinstance(self.selector, str)
            or not self.selector
        ):
            raise ValueError(
                "A direct Memory target requires a Context name and exact uid."
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
