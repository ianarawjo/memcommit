"""Resolve exact owner-aware targets for read-only Memory reports.

The interactive selectors already return an exact owner coordinate. Explicit
CLI operands need the same property: a bare UID searches every ordinary local
owner without preferring current, while ``CONTEXT:UID`` freezes one owner.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from memcommit.application.context_access.access import (
    ContextAccess,
    resolve_context_access,
)
from memcommit.models.context import Context
from memcommit.models.memory import Memory
from memcommit.application.capabilities.context_locator import resolve_context_locator
from memcommit.application.context_access.readable_contexts import (
    ReadableContextCatalog,
    freeze_profile_readable_context_catalog,
)
from memcommit.core.context_targeting.resolution import parse_direct_memory_locator
from memcommit.application.capabilities.history.query.memory_history_slicing import (
    collect_memory_history_candidates,
)
from memcommit.persistence.store import ProfileStore


MemoryReportTargetKind = Literal["MEMORY"]


@dataclass(frozen=True)
class ResolvedMemoryReportTarget:
    """One exact reportable identity and its ordinary local owner."""

    context_name: str
    uid: str
    kind: MemoryReportTargetKind
    status: Literal["CURRENT", "HISTORICAL"]


@dataclass(frozen=True)
class ResolvedReadableMemoryTarget:
    """One current ordinary Memory and its exact readable authority route."""

    context_name: str
    uid: str
    access: ContextAccess


class ReadableMemoryTargetNotFoundError(ValueError):
    """No current ordinary Memory matched in the readable Profile catalog."""


class ReadableMemoryTargetAmbiguityError(ValueError):
    """Multiple current ordinary Memories matched in the readable catalog."""


def parse_memory_report_locator(
    selector: str,
    *,
    explicit_context: str | None,
) -> tuple[str | None, str]:
    """Return an optional owner locator and the UID selector spelling."""

    locator = parse_direct_memory_locator(
        selector,
        explicit_context=explicit_context,
    )
    return locator.context_locator, locator.memory_selector


def _context_targets(
    store: ProfileStore,
    context: Context,
) -> tuple[ResolvedMemoryReportTarget, ...]:
    memories = tuple(
        ResolvedMemoryReportTarget(
            context_name=context.name,
            uid=candidate.uid,
            kind="MEMORY",
            status=candidate.status,
        )
        for candidate in collect_memory_history_candidates(store, context)
    )
    return memories


def resolve_local_memory_report_target(
    store: ProfileStore,
    selector: str,
    *,
    current: str | None,
    context_locator: str | None,
) -> ResolvedMemoryReportTarget:
    """Resolve one local current-or-retained Memory coordinate."""

    if context_locator is not None:
        context_name = resolve_context_locator(context_locator, current=current)
        if not store.context_exists(context_name):
            raise FileNotFoundError(f"Context {context_name!r} does not exist locally.")
        contexts = (store.load_direct(context_name),)
    else:
        contexts = store.load_all_contexts()

    matches = tuple(
        target
        for context in contexts
        for target in _context_targets(store, context)
        if target.uid.startswith(selector)
    )
    exact = tuple(target for target in matches if target.uid == selector)
    if exact:
        matches = exact
    if not matches:
        boundary = (
            f"Context {contexts[0].name!r} or its retained history"
            if context_locator is not None
            else "any local Context or retained history"
        )
        raise ValueError(
            f"No reportable Memory or Memory reference with uid starting with "
            f"{selector!r} exists in {boundary}."
        )
    coordinates = {
        (target.context_name, target.uid, target.kind): target for target in matches
    }
    matches = tuple(coordinates.values())
    if len(matches) != 1:
        choices = "; ".join(
            f"{target.context_name}:{target.uid} ({target.kind})"
            for target in sorted(
                matches,
                key=lambda item: (item.context_name.casefold(), item.uid, item.kind),
            )
        )
        raise ValueError(
            f"Report selector {selector!r} has multiple local matches "
            f"({len(matches)}): {choices}. To select one, rerun with its "
            "CONTEXT:UID value shown above."
        )
    return matches[0]


def freeze_memory_report_readable_catalog(
    store: ProfileStore,
    *,
    current: str | None,
) -> ReadableContextCatalog | None:
    """Freeze the local Context catalog used for Memory report targets."""

    if current is not None:
        selected_access = resolve_context_access(
            store,
            current,
            current_name=current,
        )
    else:
        local_names = tuple(store.list_context_names(sort_order="alphabetical"))
        if not local_names:
            return None
        selected_name = local_names[0]
        selected_access = ContextAccess(
            store=store,
            context_name=selected_name,
            access_name=selected_name,
        )
    return freeze_profile_readable_context_catalog(
        store,
        selected_access,
    )


def resolve_readable_memory_target(
    catalog: ReadableContextCatalog,
    selector: str,
) -> ResolvedReadableMemoryTarget:
    """Resolve a current local Memory across direct owners. Collisions require the displayed CONTEXT:UID coordinate."""

    matches = tuple(
        (public_name, memory, catalog.access_for(public_name))
        for public_name in catalog.list_context_names()
        for memory in catalog.load_direct(public_name).iter_memories()
        if isinstance(memory, Memory) and memory.uid.startswith(selector)
    )
    exact = tuple(match for match in matches if match[1].uid == selector)
    if exact:
        matches = exact
    coordinates = {
        (public_name, memory.uid): (public_name, memory, access)
        for public_name, memory, access in matches
    }
    matches = tuple(coordinates.values())
    if not matches:
        raise ReadableMemoryTargetNotFoundError(
            f"No current readable Memory with uid starting with {selector!r} "
            "was found in this Profile."
        )
    if len(matches) != 1:
        local_only = all(True for _name, _memory, access in matches)
        choices = "; ".join(
            f"{public_name}:{memory.uid} (MEMORY)"
            for public_name, memory, _access in sorted(
                matches,
                key=lambda match: (match[0].casefold(), match[1].uid),
            )
        )
        raise ReadableMemoryTargetAmbiguityError(
            f"Report selector {selector!r} has multiple "
            f"{'local' if local_only else 'current readable'} "
            f"matches ({len(matches)}): {choices}. To select one, rerun with "
            "its CONTEXT:UID value shown above."
        )
    public_name, memory, access = matches[0]
    return ResolvedReadableMemoryTarget(
        context_name=public_name,
        uid=memory.uid,
        access=access,
    )


__all__ = [
    "MemoryReportTargetKind",
    "ReadableMemoryTargetAmbiguityError",
    "ReadableMemoryTargetNotFoundError",
    "ResolvedMemoryReportTarget",
    "ResolvedReadableMemoryTarget",
    "freeze_memory_report_readable_catalog",
    "parse_memory_report_locator",
    "resolve_local_memory_report_target",
    "resolve_readable_memory_target",
]
