"""Terminal-independent application contract for direct Context inspection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, TypeAlias

from memcommit.source_projection.model import SourceDisplayFacts


class ShowError(RuntimeError):
    """Base failure for one read-only Show request."""


class ShowInputError(ShowError):
    """The requested direct-item selector is malformed or ambiguous."""


@dataclass(frozen=True, slots=True)
class ShowRequest:
    """One exact Context-or-direct-item inspection request.

    ``current_context_name`` is a command-start snapshot. Relative Context
    locators and an omitted Context operand must never observe a later global
    current-pointer change.
    """

    context_name: str | None = None
    selector: str | None = None
    current_context_name: str | None = None

    def __post_init__(self) -> None:
        for label, value in (
            ("Context name", self.context_name),
            ("Show selector", self.selector),
            ("Current Context name", self.current_context_name),
        ):
            if value is not None and (
                not isinstance(value, str) or not value.strip()
            ):
                raise ShowInputError(f"{label} must be nonblank text.")


@dataclass(frozen=True, slots=True)
class ShowMemory:
    """One ordinary Memory with its complete visible content."""

    uid: str
    content: str
    source: SourceDisplayFacts


@dataclass(frozen=True, slots=True)
class ShowMemoryReference:
    """One read-only Memory reference and an optional resolved content copy."""

    uid: str
    target_context_uid: str
    target_context_name: str
    target_memory_uid: str
    content: str | None
    source: SourceDisplayFacts

    @property
    def resolved(self) -> bool:
        return self.content is not None


@dataclass(frozen=True, slots=True)
class ShowQueryView:
    """Opaque query-only metadata; concealed source content is never present."""

    uid: str
    name: str
    source: SourceDisplayFacts


@dataclass(frozen=True, slots=True)
class ShowEmbeddedContext:
    """One direct embedded-Context row plus a port-private selection snapshot."""

    uid: str
    name: str
    source: SourceDisplayFacts
    context: ShowContextSnapshot | None


ShowItem: TypeAlias = (
    ShowMemory | ShowMemoryReference | ShowQueryView | ShowEmbeddedContext
)


@dataclass(frozen=True, slots=True)
class ShowContextSnapshot:
    """Frozen direct contents of one readable Context."""

    uid: str
    name: str
    items: tuple[ShowItem, ...]
    source: SourceDisplayFacts


ShowValue: TypeAlias = ShowContextSnapshot | ShowMemory | ShowMemoryReference | ShowQueryView


@dataclass(frozen=True, slots=True)
class ShowResult:
    """One selected read-only value and its exact parent Context binding."""

    requested_context_name: str | None
    resolved_context_name: str
    selector: str | None
    value: ShowValue


class ShowPort(Protocol):
    """Authorize and freeze one readable Context graph for Show."""

    def load_context(
        self,
        context_name: str | None,
        *,
        current_context_name: str | None,
    ) -> ShowContextSnapshot:
        """Return one authorized immutable Context snapshot."""


def _selected_value(
    context: ShowContextSnapshot,
    selector: str,
) -> ShowValue:
    matches = tuple(
        item
        for item in context.items
        if item.uid.startswith(selector)
        or (
            isinstance(item, (ShowEmbeddedContext, ShowQueryView))
            and item.name == selector
        )
    )
    if not matches:
        raise ShowInputError(
            f"No direct item matching '{selector}' in context '{context.name}'."
        )
    if len(matches) > 1:
        raise ShowInputError(
            f"Ambiguous selector '{selector}' matches {len(matches)} items: "
            + ", ".join(item.uid[:8] for item in matches)
        )
    selected = matches[0]
    if isinstance(selected, ShowEmbeddedContext):
        if selected.context is None:
            raise ShowError("The selected embedded Context was not loaded.")
        return _direct_snapshot(selected.context)
    return selected


def _direct_snapshot(context: ShowContextSnapshot) -> ShowContextSnapshot:
    """Remove loaded descendant bodies from one returned direct Context value."""

    return ShowContextSnapshot(
        uid=context.uid,
        name=context.name,
        items=tuple(
            ShowEmbeddedContext(
                uid=item.uid,
                name=item.name,
                source=item.source,
                context=None,
            )
            if isinstance(item, ShowEmbeddedContext)
            else item
            for item in context.items
        ),
        source=context.source,
    )


def show(request: ShowRequest, *, port: ShowPort) -> ShowResult:
    """Inspect one exact readable value without terminal or provider effects."""

    if not isinstance(request, ShowRequest):
        raise ShowInputError("Show requires a ShowRequest.")
    context = port.load_context(
        request.context_name,
        current_context_name=request.current_context_name,
    )
    if not isinstance(context, ShowContextSnapshot):
        raise ShowError("Show storage returned an invalid Context snapshot.")
    value: ShowValue = _direct_snapshot(context)
    if request.selector is not None:
        value = _selected_value(context, request.selector)
    return ShowResult(
        requested_context_name=request.context_name,
        resolved_context_name=context.name,
        selector=request.selector,
        value=value,
    )


__all__ = [
    "ShowContextSnapshot",
    "ShowEmbeddedContext",
    "ShowError",
    "ShowInputError",
    "ShowItem",
    "ShowMemory",
    "ShowMemoryReference",
    "ShowPort",
    "ShowQueryView",
    "ShowRequest",
    "ShowResult",
    "ShowValue",
    "show",
]
