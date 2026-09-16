"""Operation-neutral direct-Memory deltas for canonical History."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Generic, Literal, TypeVar


MemoryDeltaKind = Literal["CREATED", "EDITED", "REMOVED"]
_StateT = TypeVar("_StateT")


@dataclass(frozen=True)
class DirectMemoryDelta(Generic[_StateT]):
    """One UID-stable difference between adjacent direct Context frames.

    A removal and an addition in the same operation remain independent here.
    Provenance may connect them only when recorded or deterministically
    reconstructable lineage metadata proves SPLIT, ABSORB, or translation.
    """

    kind: MemoryDeltaKind
    memory_uid: str
    before: _StateT | None
    after: _StateT | None


def direct_memory_deltas(
    before: Mapping[str, _StateT],
    after: Mapping[str, _StateT],
    *,
    before_order: Sequence[str],
    after_order: Sequence[str],
    content: Callable[[_StateT], str],
) -> tuple[DirectMemoryDelta[_StateT], ...]:
    """Return deterministic UID-based deltas without inventing lineage."""

    if set(before_order) != set(before) or set(after_order) != set(after):
        raise ValueError("Direct Memory frame order does not match its UID catalog.")
    ordered_uids = (*before_order, *(uid for uid in after_order if uid not in before))
    deltas: list[DirectMemoryDelta[_StateT]] = []
    for uid in ordered_uids:
        old = before.get(uid)
        new = after.get(uid)
        if old is not None and new is not None and content(old) == content(new):
            continue
        kind: MemoryDeltaKind
        if old is None:
            kind = "CREATED"
        elif new is None:
            kind = "REMOVED"
        else:
            kind = "EDITED"
        deltas.append(
            DirectMemoryDelta(
                kind=kind,
                memory_uid=uid,
                before=old,
                after=new,
            )
        )
    return tuple(deltas)
