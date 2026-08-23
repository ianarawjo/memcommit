"""Owner-aware explicit items shared by read-only Memory reports.

The interactive selectors already return an exact owner coordinate. Explicit
CLI operands need the same property: a bare UID searches every ordinary local
owner without preferring current, while ``CONTEXT:UID`` freezes one owner.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from memcommit.context import Context
from memcommit.context_locator import resolve_context_locator
from memcommit.context_targeting.resolution import parse_direct_memory_locator
from memcommit.provenance import collect_trace_candidates
from memcommit.reference_provenance import collect_reference_candidates
from memcommit.store import MemoryStore


MemoryReportTargetKind = Literal["MEMORY", "MEMORY_REFERENCE"]


@dataclass(frozen=True)
class ResolvedMemoryReportTarget:
    """One exact reportable identity and its ordinary local owner."""

    context_name: str
    uid: str
    kind: MemoryReportTargetKind
    status: Literal["CURRENT", "HISTORICAL"]


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
            f"({len(matches)}): {choices}. Use one qualified CONTEXT:UID locator."
        )
    return matches[0]


__all__ = [
    "MemoryReportTargetKind",
    "ResolvedMemoryReportTarget",
    "parse_memory_report_locator",
    "resolve_local_memory_report_target",
]
