"""Stable group-preserving partitioning under a vector budget."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TypeVar

from memcommit.application.semantic_execution.model import BudgetLimits, BudgetVector


T = TypeVar("T")


class PartitionError(RuntimeError):
    """A semantic item cannot fit without an operation-owned content strategy."""


def pack_grouped_items(
    values: Iterable[T],
    *,
    group_key: Callable[[T], str],
    measure: Callable[[tuple[T, ...]], BudgetVector],
    limits: BudgetLimits,
) -> tuple[tuple[T, ...], ...]:
    """Pack whole groups first, splitting a group only when it cannot fit alone.

    ``measure`` receives the complete candidate batch, so callers account for
    exact JSON punctuation and fixed prompt fields instead of summing an
    approximation. A single oversized item fails visibly and is never truncated.
    """

    items = tuple(values)
    if not items:
        return ()
    groups: dict[str, list[T]] = {}
    order: list[str] = []
    for item in items:
        key = group_key(item)
        if not isinstance(key, str) or not key:
            raise PartitionError("Semantic partition group keys must be nonempty text.")
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(item)

    def fits(candidate: tuple[T, ...]) -> bool:
        return not limits.exceeded_axes(measure(candidate))

    batches: list[tuple[T, ...]] = []
    current: tuple[T, ...] = ()

    def flush() -> None:
        nonlocal current
        if current:
            batches.append(current)
            current = ()

    for key in order:
        group = tuple(groups[key])
        combined = (*current, *group)
        if fits(combined):
            current = combined
            continue
        flush()
        if fits(group):
            current = group
            continue

        # The Context/group is itself oversized. Preserve item boundaries and
        # use the same exact batch measurement while subdividing it.
        for item in group:
            single = (item,)
            if not fits(single):
                raise PartitionError(
                    "One semantic input item exceeds the staged request budget."
                )
            combined = (*current, item)
            if fits(combined):
                current = combined
            else:
                flush()
                current = single
        flush()
    flush()
    return tuple(batches)
