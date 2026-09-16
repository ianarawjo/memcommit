"""Shared, presentation-neutral Memory change records.

The CLI diff and interactive Impact surfaces render the same semantic change
in different terminal layouts.  Keeping the frozen before/after/location
contract here prevents an Impact adapter from reconstructing a change by
flattening unrelated provenance blocks into one pseudo-Memory string.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

from memcommit.application.operations.update.model import AddOperation, EditOperation, RemoveOperation, UpdateOperation


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


@dataclass(frozen=True)
class MemoryDiffSpan:
    """One mechanically equal or changed text span in a rendered diff line."""

    text: str
    changed: bool

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise ValueError("Memory diff span text must be text.")
        if not isinstance(self.changed, bool):
            raise ValueError("Memory diff span change flag must be boolean.")


@dataclass(frozen=True)
class MemoryDiffLine:
    """One context, removal, addition, or equality line."""

    marker: str
    spans: tuple[MemoryDiffSpan, ...]

    def __post_init__(self) -> None:
        if self.marker not in {" ", "-", "+", "="}:
            raise ValueError("Invalid Memory diff line marker.")
        if not isinstance(self.spans, tuple) or not self.spans or any(
            not isinstance(span, MemoryDiffSpan) for span in self.spans
        ):
            raise ValueError("Memory diff line requires typed spans.")


def _line_spans(text: str, *, changed: bool) -> tuple[MemoryDiffSpan, ...]:
    return (MemoryDiffSpan(text=text, changed=changed),)


def _word_tokens(text: str) -> list[str]:
    return re.findall(r"\S+|\s+", text)


def _paired_word_spans(
    before: str,
    after: str,
) -> tuple[tuple[MemoryDiffSpan, ...], tuple[MemoryDiffSpan, ...]]:
    """Mark only mechanically unequal token spans; infer no semantic relation."""

    before_tokens = _word_tokens(before)
    after_tokens = _word_tokens(after)
    before_spans: list[MemoryDiffSpan] = []
    after_spans: list[MemoryDiffSpan] = []
    matcher = difflib.SequenceMatcher(
        None,
        before_tokens,
        after_tokens,
        autojunk=False,
    )
    for tag, before_start, before_end, after_start, after_end in matcher.get_opcodes():
        before_text = "".join(before_tokens[before_start:before_end])
        after_text = "".join(after_tokens[after_start:after_end])
        if before_text or not before_spans:
            before_spans.append(
                MemoryDiffSpan(text=before_text, changed=tag != "equal")
            )
        if after_text or not after_spans:
            after_spans.append(
                MemoryDiffSpan(text=after_text, changed=tag != "equal")
            )
    return tuple(before_spans), tuple(after_spans)


def memory_diff_lines(change: MemoryChange) -> tuple[MemoryDiffLine, ...]:
    """Derive a deterministic line/word diff from frozen before and after text."""

    if change.before is None:
        return tuple(
            MemoryDiffLine("+", _line_spans(line, changed=True))
            for line in change.after.splitlines() or [""]  # type: ignore[union-attr]
        )
    if change.after is None:
        return tuple(
            MemoryDiffLine("-", _line_spans(line, changed=True))
            for line in change.before.splitlines() or [""]
        )
    if change.before == change.after:
        return tuple(
            MemoryDiffLine("=", _line_spans(line, changed=False))
            for line in change.before.splitlines() or [""]
        )

    before_lines = change.before.splitlines() or [""]
    after_lines = change.after.splitlines() or [""]
    matcher = difflib.SequenceMatcher(
        None,
        before_lines,
        after_lines,
        autojunk=False,
    )
    rendered: list[MemoryDiffLine] = []
    for tag, before_start, before_end, after_start, after_end in matcher.get_opcodes():
        if tag == "equal":
            rendered.extend(
                MemoryDiffLine(" ", _line_spans(line, changed=False))
                for line in before_lines[before_start:before_end]
            )
            continue
        if tag == "replace":
            before_chunk = before_lines[before_start:before_end]
            after_chunk = after_lines[after_start:after_end]
            paired = min(len(before_chunk), len(after_chunk))
            for index in range(paired):
                before_spans, after_spans = _paired_word_spans(
                    before_chunk[index],
                    after_chunk[index],
                )
                rendered.extend(
                    (
                        MemoryDiffLine("-", before_spans),
                        MemoryDiffLine("+", after_spans),
                    )
                )
            rendered.extend(
                MemoryDiffLine("-", _line_spans(line, changed=True))
                for line in before_chunk[paired:]
            )
            rendered.extend(
                MemoryDiffLine("+", _line_spans(line, changed=True))
                for line in after_chunk[paired:]
            )
            continue
        marker = "-" if tag == "delete" else "+"
        lines = (
            before_lines[before_start:before_end]
            if tag == "delete"
            else after_lines[after_start:after_end]
        )
        rendered.extend(
            MemoryDiffLine(marker, _line_spans(line, changed=True))
            for line in lines
        )
    return tuple(rendered)


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
