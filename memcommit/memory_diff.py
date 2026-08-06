"""Shared, presentation-neutral Memory change records.

The CLI diff and interactive Impact surfaces render the same semantic change
in different terminal layouts.  Keeping the frozen before/after/location
contract here prevents an Impact adapter from reconstructing a change by
flattening unrelated provenance blocks into one pseudo-Memory string.
"""
from __future__ import annotations

from dataclasses import dataclass

from memcommit.update import AddOperation, EditOperation, RemoveOperation, UpdateOperation


@dataclass(frozen=True)
class MemoryChange:
    """One located Memory transition suitable for diff-style presentation."""

    marker: str
    treatment: str
    location: str
    memory_uid: str
    before: str | None
    after: str | None
    reason: str = ""
    rules: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for label, value in (
            ("change marker", self.marker),
            ("change treatment", self.treatment),
            ("change location", self.location),
            ("change Memory uid", self.memory_uid),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Memory {label} must be nonempty text.")
        if self.before is None and self.after is None:
            raise ValueError("A Memory change requires a before or after value.")
        if self.before is not None and not isinstance(self.before, str):
            raise ValueError("Memory change before value must be text or None.")
        if self.after is not None and not isinstance(self.after, str):
            raise ValueError("Memory change after value must be text or None.")
        if not isinstance(self.reason, str):
            raise ValueError("Memory change reason must be text.")
        if not isinstance(self.rules, tuple) or any(
            not isinstance(rule, str) or not rule.strip() for rule in self.rules
        ):
            raise ValueError("Memory change rules must be nonempty text.")


def update_operation_change(operation: UpdateOperation) -> MemoryChange:
    """Project one validated Update operation without losing its owner."""

    if isinstance(operation, EditOperation):
        marker = "~"
        before = operation.old_content
        after = operation.new_content
    elif isinstance(operation, AddOperation):
        marker = "+"
        before = None
        after = operation.new_content
    elif isinstance(operation, RemoveOperation):
        marker = "−"
        before = operation.old_content
        after = None
    else:  # pragma: no cover - the UpdateOperation alias is intentionally closed.
        raise TypeError("Unsupported Update operation.")
    return MemoryChange(
        marker=marker,
        treatment=operation.operation.upper(),
        location=operation.owner_context_name,
        memory_uid=operation.memory_uid,
        before=before,
        after=after,
        reason=operation.reason,
    )
