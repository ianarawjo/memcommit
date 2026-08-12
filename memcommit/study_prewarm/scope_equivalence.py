"""Shared evidence checks for equal and deletion-only Study Context scopes."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Hashable, Literal

from memcommit.context import Context, Memory


ScopeEvidenceRelation = Literal["EQUAL", "SUBSET"]


def ordered_scope_evidence_relation(
    prepared_evidence: Iterable[Hashable],
    current_evidence: Iterable[Hashable],
) -> ScopeEvidenceRelation | None:
    """Classify one unchanged ordered ledger as equal or deletion-only.

    Locator depth and descendant flags are presentation choices.  A Study
    cache lookup instead needs to know whether every provider-visible current
    row is the exact row that appeared in the prepared basis, in the same
    relative order.  Additions, edits, duplicated identities, and reordering
    all fail closed.  Operation adapters remain responsible for including
    every field that affects their own semantics in each hashable row.
    """

    prepared = tuple(prepared_evidence)
    current = tuple(current_evidence)
    if len(set(prepared)) != len(prepared) or len(set(current)) != len(current):
        return None
    current_set = set(current)
    prepared_set = set(prepared)
    if any(row not in prepared_set for row in current):
        return None
    if tuple(row for row in prepared if row in current_set) != current:
        return None
    return "EQUAL" if current == prepared else "SUBSET"


def lexical_scope_alias(left: str, right: str) -> bool:
    """Return whether two distinct roots are on one lexical ancestor chain."""

    return left != right and (
        left.startswith(right + "/") or right.startswith(left + "/")
    )


def transparent_scope_evidence_matches(
    *,
    prepared_root: str,
    current_root: str,
    prepared_evidence: Iterable[Hashable],
    current_evidence: Iterable[Hashable],
) -> bool:
    """Match one re-rooted scope without permitting filtering or additions.

    Callers must include every operation-relevant field in each evidence row,
    including durable Memory identity, content, order, and owner when the
    operation preserves owner placement.  Tuple equality then proves that the
    ancestor or descendant contributes no different semantic evidence.
    """

    return lexical_scope_alias(prepared_root, current_root) and tuple(
        prepared_evidence
    ) == tuple(current_evidence)


def _owned_memory_evidence(root: Context) -> tuple[tuple[object, ...], ...]:
    rows: list[tuple[object, ...]] = []
    visited: set[str] = set()

    def visit(context: Context) -> None:
        if context.uid in visited:
            return
        visited.add(context.uid)
        for position, item in enumerate(context.iter_items()):
            if isinstance(item, Memory):
                rows.append(
                    (
                        context.uid,
                        context.name,
                        item.uid,
                        position,
                        item.content,
                    )
                )
            elif isinstance(item, Context):
                visit(item)

    visit(root)
    return tuple(rows)


def transparent_context_scope_matches(prepared: Context, current: Context) -> bool:
    """Prove that two loaded scopes have one owner-identical Memory ledger.

    The complete owner-aware Memory ledger must remain byte-for-byte equal.
    This is stronger than comparing flattened Compare frames, whose recursive
    projection decorates content with owner names depending on the chosen root.
    Empty wrappers and empty side branches are intentionally ignored: they
    were not provider-visible evidence and cannot change the cached result.
    """

    return bool(
        lexical_scope_alias(prepared.name, current.name)
        and _owned_memory_evidence(prepared) == _owned_memory_evidence(current)
    )
