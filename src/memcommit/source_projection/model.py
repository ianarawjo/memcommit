"""Operation-neutral facts behind one displayed Context or item source."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SourceReach(str, Enum):
    """How an occurrence was reached from the person's selected root."""

    DIRECT = "DIRECT"
    DESCENDANT = "DESCENDANT"


class SourceForm(str, Enum):
    """The durable or virtual shape represented by the displayed row."""

    CONTEXT = "CONTEXT"
    MEMORY = "MEMORY"


class SourceState(str, Enum):
    """Display-relevant availability state independent of authority."""

    READ_ONLY = "READ_ONLY"
    UNAVAILABLE = "UNAVAILABLE"
    CYCLE = "CYCLE"


@dataclass(frozen=True)
class SourceReferenceRow:
    """Operation-neutral facts for one compact, numbered Source row.

    The displayed ordinal is presentation identity; ``alias`` is an optional
    operation-owned display label such as Query's ``Memory 5``.
    """

    number: int
    content: str
    uid: str
    context_name: str
    alias: str | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.number, int)
            or isinstance(self.number, bool)
            or self.number < 1
        ):
            raise ValueError("Source Reference number must be a positive integer.")
        if not isinstance(self.content, str) or not self.content.strip():
            raise ValueError("Source Reference content must be nonblank text.")
        for label, value in (
            ("UID", self.uid),
            ("Context", self.context_name),
        ):
            if (
                not isinstance(value, str)
                or not value.strip()
                or any(character in value for character in "\r\n")
            ):
                raise ValueError(
                    f"Source Reference {label} must be nonblank one-line text."
                )
        if self.alias is not None and (
            not isinstance(self.alias, str)
            or not self.alias.strip()
            or any(character in self.alias for character in "\r\n")
        ):
            raise ValueError(
                "Source Reference alias must be nonblank one-line text when present."
            )


@dataclass(frozen=True)
class SourceDisplayFacts:
    """Typed source facts rendered by every CLI and TUI surface.

    Lexical reach, object kind, and availability remain independent facts.
    """

    reach: SourceReach = SourceReach.DIRECT
    form: SourceForm = SourceForm.CONTEXT
    states: tuple[SourceState, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.reach, SourceReach):
            raise TypeError("Source reach must be a SourceReach value.")
        if not isinstance(self.form, SourceForm):
            raise TypeError("Source form must be a SourceForm value.")
        if len(set(self.states)) != len(self.states):
            raise ValueError("Source display states must be distinct.")
        if any(not isinstance(value, SourceState) for value in self.states):
            raise TypeError("Source display states must be SourceState values.")
