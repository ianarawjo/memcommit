"""Terminal-independent application contract for direct Context inspection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, TypeAlias

from memcommit.source_projection.model import SourceDisplayFacts


class ShowError(RuntimeError):
    """Base failure for one read-only Show request."""


class ShowInputError(ShowError):
    """The requested direct-item selector is malformed or ambiguous."""


class ShowItemNotFoundError(ShowInputError):
    """One selector matched no direct item in its selected owner."""


class ShowDirectItemScopeError(ShowInputError):
    """A direct-item target was combined with recursive Context reach."""


@dataclass(frozen=True, slots=True)
class ShowRequest:
    """One Context-scope or direct-item inspection request.

    ``current_context_name`` is a command-start snapshot. Relative Context
    locators and an omitted Context operand must never observe a later global
    current-pointer change.
    """

    context_name: str | None = None
    selector: str | None = None
    current_context_name: str | None = None
    include_descendants: bool = False
    follow_embeds: bool = False

    def __post_init__(self) -> None:
        for label, value in (
            ("Context name", self.context_name),
            ("Show selector", self.selector),
            ("Current Context name", self.current_context_name),
        ):
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ShowInputError(f"{label} must be nonblank text.")
        if type(self.include_descendants) is not bool:
            raise ShowInputError("Show descendant reach must be a boolean.")
        if type(self.follow_embeds) is not bool:
            raise ShowInputError("Show embed reach must be a boolean.")
        if self.selector is not None and (
            self.include_descendants or self.follow_embeds
        ):
            raise ShowDirectItemScopeError(
                "Recursive Show scope cannot be combined with a direct-item "
                "selector."
            )


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


ShowValue: TypeAlias = (
    ShowContextSnapshot | ShowMemory | ShowMemoryReference | ShowQueryView
)


@dataclass(frozen=True, slots=True)
class ShowResult:
    """One selected value plus the complete frozen Context scope behind it."""

    requested_context_name: str | None
    resolved_context_name: str
    selector: str | None
    value: ShowValue
    include_descendants: bool = False
    follow_embeds: bool = False
    contexts: tuple[ShowContextSnapshot, ...] = ()


class ShowPort(Protocol):
    """Authorize and freeze one readable Context graph for Show."""

    def load_contexts(
        self,
        context_name: str | None,
        *,
        current_context_name: str | None,
        include_descendants: bool,
        follow_embeds: bool,
    ) -> tuple[ShowContextSnapshot, ...]:
        """Return one ordered, authorized immutable Context scope."""


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
        raise ShowItemNotFoundError(
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
            (
                ShowEmbeddedContext(
                    uid=item.uid,
                    name=item.name,
                    source=item.source,
                    context=None,
                )
                if isinstance(item, ShowEmbeddedContext)
                else item
            )
            for item in context.items
        ),
        source=context.source,
    )


def show(request: ShowRequest, *, port: ShowPort) -> ShowResult:
    """Inspect one exact readable value without terminal or provider effects."""

    if not isinstance(request, ShowRequest):
        raise ShowInputError("Show requires a ShowRequest.")
    contexts = port.load_contexts(
        request.context_name,
        current_context_name=request.current_context_name,
        include_descendants=request.include_descendants,
        follow_embeds=request.follow_embeds,
    )
    if (
        not isinstance(contexts, tuple)
        or not contexts
        or any(not isinstance(context, ShowContextSnapshot) for context in contexts)
    ):
        raise ShowError("Show storage returned an invalid Context scope.")
    direct_contexts = tuple(_direct_snapshot(context) for context in contexts)
    context = contexts[0]
    value: ShowValue = direct_contexts[0]
    if request.selector is not None:
        value = _selected_value(context, request.selector)
    return ShowResult(
        requested_context_name=request.context_name,
        resolved_context_name=context.name,
        selector=request.selector,
        value=value,
        include_descendants=request.include_descendants,
        follow_embeds=request.follow_embeds,
        contexts=direct_contexts,
    )


__all__ = [
    "ShowContextSnapshot",
    "ShowEmbeddedContext",
    "ShowError",
    "ShowDirectItemScopeError",
    "ShowInputError",
    "ShowItemNotFoundError",
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
