"""Operation-neutral values describing Context targets and lexical reach."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal


ContextSelectionMode = Literal["SINGLE", "MULTIPLE"]


@dataclass(frozen=True, slots=True)
class ExistingContextOperand:
    """One CLI operand whose semantic role is an existing Context locator.

    The value is intentionally still raw locator text.  Canonicalization needs
    the command-start current-Context snapshot and therefore remains a later
    resolution step shared by every operand in one invocation.
    """

    locator: str

    def __post_init__(self) -> None:
        if not isinstance(self.locator, str) or not self.locator:
            raise ValueError("An existing-Context operand requires a nonempty locator.")


@dataclass(frozen=True, slots=True)
class InlineTextOperand:
    """One CLI operand that cannot be mistaken for a Context locator.

    This value classifies syntax only.  The calling semantic operation still
    owns whether the text is evidence, an instruction, or unsupported input.
    """

    text: str

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("An inline-text operand requires nonblank text.")


@dataclass(frozen=True, slots=True)
class ContextTarget:
    """One canonical existing ordinary-local Context selected by an operand."""

    context_name: str

    def __post_init__(self) -> None:
        if not isinstance(self.context_name, str) or not self.context_name:
            raise ValueError("A Context target requires a canonical name.")


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


@dataclass(frozen=True, slots=True)
class DirectItemTarget:
    """One exact direct item plus the canonical Context that owns its row.

    Unlike :class:`DirectMemoryTarget`, this coordinate may identify a Memory,
    MemoryRef, embedded Context, or query view.  The common locator layer owns
    only the coordinate; read, mutation, and concealment semantics remain with
    the calling operation.
    """

    context_name: str
    item_uid: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.context_name, str)
            or not self.context_name
            or not isinstance(self.item_uid, str)
            or not self.item_uid
        ):
            raise ValueError(
                "A direct item target requires a Context name and exact uid."
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
