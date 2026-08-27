"""Owner-aware explicit items shared by read-only Memory reports.

The interactive selectors already return an exact owner coordinate. Explicit
CLI operands need the same property: a bare UID searches every ordinary local
owner without preferring current, while ``CONTEXT:UID`` freezes one owner.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from memcommit.authority.access import ContextAccess, resolve_context_access
from memcommit.context import Context, Memory
from memcommit.context_locator import resolve_context_locator
from memcommit.context_targeting.readable_catalog import (
    ReadableContextCatalog,
    freeze_profile_readable_context_catalog,
)
from memcommit.context_targeting.resolution import parse_direct_memory_locator
from memcommit.operations.profile.config import ProfileRegistry
from memcommit.retained_history.provenance import collect_trace_candidates
from memcommit.operations.reference.provenance import collect_reference_candidates
from memcommit.persistence.store import MemoryStore


MemoryReportTargetKind = Literal["MEMORY", "MEMORY_REFERENCE"]


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
    store: MemoryStore,
    context: Context,
) -> tuple[ResolvedMemoryReportTarget, ...]:
    memories = tuple(
        ResolvedMemoryReportTarget(
            context_name=context.name,
            uid=candidate.uid,
            kind="MEMORY",
            status=candidate.status,
        )
        for candidate in collect_trace_candidates(store, context)
    )
    references = tuple(
        ResolvedMemoryReportTarget(
            context_name=context.name,
            uid=candidate.state.uid,
            kind="MEMORY_REFERENCE",
            status=candidate.status,
        )
        for candidate in collect_reference_candidates(store, context)
    )
    return (*memories, *references)


def resolve_local_memory_report_target(
    store: MemoryStore,
    selector: str,
    *,
    current: str | None,
    context_locator: str | None,
) -> ResolvedMemoryReportTarget:
    """Resolve one local current-or-retained Memory or MemoryRef coordinate."""

    if context_locator is not None:
        context_name = resolve_context_locator(context_locator, current=current)
        if not store.context_exists(context_name):
            raise FileNotFoundError(f"Context {context_name!r} does not exist locally.")
        contexts = (store.load_direct(context_name),)
    else:
        contexts = store.load_direct_context_graph_strict()

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
    store: MemoryStore,
    *,
    current: str | None,
    registry: ProfileRegistry | None = None,
) -> ReadableContextCatalog | None:
    """Freeze the Profile-wide current-Memory namespace for a bare UID.

    An explicit bare UID used by a read-only report is independent of the
    current row, but the current row remains the authorization anchor needed
    to freeze the Profile catalog.  A Profile with readable Grants necessarily
    has a local attachment; when no current row exists, the first ordinary
    local Context supplies that neutral anchor.  An entirely empty store has
    no current Memories and therefore returns ``None`` for the caller's
    retained-history fallback.
    """

    if current is not None:
        selected_access = resolve_context_access(
            store,
            current,
            current_name=current,
            required_permission="READ",
            registry=registry,
        )
    else:
        local_names = tuple(sorted(store.list_context_names(), key=str.casefold))
        if not local_names:
            return None
        selected_name = local_names[0]
        selected_access = ContextAccess(
            store=store,
            context_name=selected_name,
            display_name=selected_name,
            attachment_name=None,
            permission="READ",
        )
    return freeze_profile_readable_context_catalog(
        store,
        selected_access,
        include_query_routes=False,
        registry=registry,
    )


def resolve_readable_memory_target(
    catalog: ReadableContextCatalog,
    selector: str,
) -> ResolvedReadableMemoryTarget:
    """Resolve one current Memory across local and READ-granted public owners.

    Only direct ordinary Memories enter this namespace.  Retained history,
    Memory references, embedded traversal, and QUERY-only sources remain
    operation-specific fallbacks or concealed routes.  Local and granted
    candidates have equal standing, so a collision always requires the
    displayed ``CONTEXT:UID`` coordinate instead of current-Context priority.
    """

    matches = tuple(
        (public_name, memory, catalog.access_for(public_name))
        for public_name in catalog.list_context_names()
        for memory in catalog.load_direct(public_name).iter_items()
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
        local_only = all(not access.is_granted for _name, _memory, access in matches)
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
