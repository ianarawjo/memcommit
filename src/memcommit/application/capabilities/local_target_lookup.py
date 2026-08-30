"""Look up exact local Context and direct-item target coordinates."""

from __future__ import annotations

import json
from typing import Protocol

from memcommit.core.context import Context, Information, Memory
from memcommit.application.capabilities.context_locator import resolve_context_locator
from memcommit.core.context_targeting.uid_locator import is_memory_uid_prefix
from memcommit.core.context_targeting.model import (
    ContextTarget,
    DirectItemTarget,
    DirectMemoryTarget,
    ExistingContextOperand,
)
from memcommit.core.context_targeting.resolution import (
    parse_auto_typed_context_memory_operand,
    parse_direct_memory_locator,
)


class LocalDirectMemoryLocatorStore(Protocol):
    """Complete ordinary-local surface used for exact Memory owner lookup."""

    def context_exists(self, name: str) -> bool: ...

    def load_direct(self, name: str) -> Context: ...

    def load_direct_context_graph_strict(self) -> tuple[Context, ...]: ...


class DirectItemLocatorError(ValueError):
    """One all-direct-item locator could not produce an exact owner coordinate."""


class DirectItemNotFoundError(DirectItemLocatorError):
    """No ordinary local direct item matched the requested selector."""


class DirectItemAmbiguityError(DirectItemLocatorError):
    """More than one ordinary local direct-item coordinate matched."""


class DirectMemoryLocatorError(ValueError):
    """One ordinary-local direct-Memory locator could not be resolved."""


class DirectMemoryNotFoundError(DirectMemoryLocatorError):
    """No ordinary local direct Memory matched the requested selector."""


class DirectMemoryAmbiguityError(DirectMemoryLocatorError):
    """More than one ordinary local direct-Memory coordinate matched."""


def _direct_memory_matches(
    context: Context,
    selector: str,
) -> tuple[Memory, ...]:
    return tuple(
        item
        for item in context.iter_items()
        if isinstance(item, Memory) and item.uid.startswith(selector)
    )


def _resolved_direct_memory_target(
    selector: str,
    matches: tuple[tuple[Context, Memory], ...],
    *,
    context_name: str | None,
) -> DirectMemoryTarget:
    if not matches:
        if context_name is not None:
            raise DirectMemoryNotFoundError(
                f"No directly owned Memory with uid starting with {selector!r} "
                f"exists in Context {context_name!r}."
            )
        raise DirectMemoryNotFoundError(
            f"No directly owned Memory with uid starting with {selector!r} "
            "was found in any local Context."
        )
    if len(matches) > 1:
        choices = "\n".join(
            f"  {context.name}:{memory.uid} "
            f"{json.dumps(memory.content, ensure_ascii=False)}"
            for context, memory in sorted(
                matches,
                key=lambda match: (match[0].name.casefold(), match[1].uid),
            )
        )
        raise DirectMemoryAmbiguityError(
            f"Memory prefix {selector!r} has multiple local matches "
            f"({len(matches)}):\n{choices}\n"
            "To select one, rerun with its CONTEXT:UID value shown above."
        )
    context, memory = matches[0]
    return DirectMemoryTarget(context.name, memory.uid)


def resolve_local_direct_memory_locator(
    store: LocalDirectMemoryLocatorStore,
    operand: object,
    *,
    current: str | None,
    explicit_context: str | None = None,
) -> DirectMemoryTarget:
    """Resolve one exact ordinary local owner without hidden current priority.

    A qualified locator searches only its canonical direct owner. A bare
    selector scans one strict snapshot of every ordinary local direct record;
    exactly one match is required even when one match happens to be current.
    MemoryRefs, snapshots, embedded traversal, and Grant content never enter
    this local ownership catalog.
    """

    locator = parse_direct_memory_locator(
        operand,
        explicit_context=explicit_context,
    )
    if locator.context_locator is not None:
        context_name = resolve_context_locator(
            locator.context_locator,
            current=current,
        )
        if not store.context_exists(context_name):
            raise FileNotFoundError(f"Context {context_name!r} does not exist locally.")
        context = store.load_direct(context_name)
        matches = tuple(
            (context, memory)
            for memory in _direct_memory_matches(
                context,
                locator.memory_selector,
            )
        )
        return _resolved_direct_memory_target(
            locator.memory_selector,
            matches,
            context_name=context_name,
        )

    matches = tuple(
        (context, memory)
        for context in store.load_direct_context_graph_strict()
        for memory in _direct_memory_matches(context, locator.memory_selector)
    )
    return _resolved_direct_memory_target(
        locator.memory_selector,
        matches,
        context_name=None,
    )


def _resolved_direct_item_target(
    selector: str,
    matches: tuple[tuple[Context, Information], ...],
    *,
    context_name: str | None,
) -> DirectItemTarget:
    if not matches:
        if context_name is not None:
            raise DirectItemNotFoundError(
                f"No direct item with uid starting with {selector!r} exists in "
                f"Context {context_name!r}."
            )
        raise DirectItemNotFoundError(
            f"No direct item with uid starting with {selector!r} was found in "
            "any local Context."
        )
    exact = tuple(match for match in matches if match[1].uid == selector)
    if exact:
        matches = exact
    coordinates = {
        (context.name, item.uid): (context, item) for context, item in matches
    }
    matches = tuple(coordinates.values())
    if len(matches) > 1:
        choices = "; ".join(
            f"{context.name}:{item.uid}"
            for context, item in sorted(
                matches,
                key=lambda match: (match[0].name.casefold(), match[1].uid),
            )
        )
        raise DirectItemAmbiguityError(
            f"Direct-item prefix {selector!r} has multiple local matches "
            f"({len(matches)}): {choices}. To select one, rerun with its "
            "CONTEXT:UID value shown above."
        )
    context, item = matches[0]
    return DirectItemTarget(context.name, item.uid)


def resolve_local_direct_item_locator(
    store: LocalDirectMemoryLocatorStore,
    operand: object,
    *,
    current: str | None,
    explicit_context: str | None = None,
) -> DirectItemTarget:
    """Resolve one exact local direct-item UID without opening nested content.

    This is the all-direct-item sibling of the Memory-only locator.  Bare
    selectors scan every strict ordinary-local direct record and require one
    owner coordinate.  Qualified selectors search only their canonical owner.
    Name-based embedded/query selection remains operation-specific because a
    name can also be a public Context locator.
    """

    locator = parse_direct_memory_locator(
        operand,
        explicit_context=explicit_context,
    )
    if locator.context_locator is not None:
        context_name = resolve_context_locator(
            locator.context_locator,
            current=current,
        )
        if not store.context_exists(context_name):
            raise FileNotFoundError(f"Context {context_name!r} does not exist locally.")
        context = store.load_direct(context_name)
        matches = tuple(
            (context, item)
            for item in context.iter_items()
            if item.uid.startswith(locator.memory_selector)
        )
        return _resolved_direct_item_target(
            locator.memory_selector,
            matches,
            context_name=context_name,
        )

    matches = tuple(
        (context, item)
        for context in store.load_direct_context_graph_strict()
        for item in context.iter_items()
        if item.uid.startswith(locator.memory_selector)
    )
    return _resolved_direct_item_target(
        locator.memory_selector,
        matches,
        context_name=None,
    )


def resolve_local_context_memory_target(
    store: LocalDirectMemoryLocatorStore,
    operand: object,
    *,
    current: str | None,
) -> ContextTarget | DirectMemoryTarget:
    """Resolve one auto-typed local Context or directly owned Memory target.

    This is the reusable local-storage completion of the pure shared operand
    parser.  It is intentionally not Grant-aware: operations that accept public
    Grant owners compose the parser with their authority-specific access port.
    """

    parsed = parse_auto_typed_context_memory_operand(operand)
    if isinstance(parsed, ExistingContextOperand):
        context_name = resolve_context_locator(parsed.locator, current=current)
        if store.context_exists(context_name):
            return ContextTarget(context_name)
        short_memory = try_resolve_short_local_direct_memory_locator(
            store,
            parsed.locator,
            current=current,
        )
        if short_memory is not None:
            return short_memory
        raise FileNotFoundError(f"Context {context_name!r} does not exist locally.")
    return resolve_local_direct_memory_locator(
        store,
        operand,
        current=current,
    )


def try_resolve_short_local_direct_memory_locator(
    store: LocalDirectMemoryLocatorStore,
    operand: object,
    *,
    current: str | None,
) -> DirectMemoryTarget | None:
    """Resolve a short bare UID only after an exact Context has missed.

    The pure overloaded-operand parser deliberately reserves only the public
    eight-character UID shape.  Shorter hexadecimal text can still be an
    existing Context name or literal operation input, so storage-backed
    adapters call this fallback only after preserving that stronger meaning.
    A real ambiguity remains an error; only an empty local match returns
    ``None`` so the calling operation can retain its established missing-name
    or literal fallback.
    """

    if (
        not isinstance(operand, str)
        or not is_memory_uid_prefix(operand)
        or len(operand) >= 8
    ):
        return None
    try:
        return resolve_local_direct_memory_locator(
            store,
            operand,
            current=current,
        )
    except DirectMemoryNotFoundError:
        return None
