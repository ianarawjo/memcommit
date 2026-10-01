"""Project a saved Update as location-owned terminal checkpoint history."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from prompt_toolkit.formatted_text.base import StyleAndTextTuples

from memcommit.adapters.console.terminal.components.history.picker import choose_history
from memcommit.adapters.console.terminal.components.history.model import (
    HistoryBackNavigation,
    HistoryDetailView,
    HistoryPickerEntry,
    HistoryPickerItem,
)
from memcommit.adapters.console.terminal.components.checkpoint_location import (
    choose_history_location,
)
from memcommit.adapters.console.terminal.core.text import (
    display_escape_text,
)
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    semantic_action_style,
)
from memcommit.application.capabilities.reviewing.memory_diff import (
    memory_diff_lines,
    update_operation_change,
)
from memcommit.application.operations.update.model import UpdateReceipt


@dataclass(frozen=True)
class UpdateSubtreeCheckpointEntry(HistoryPickerEntry):
    """One location-owned checkpoint projected into a subtree history."""

    location: str


def _location_names(receipt: UpdateReceipt) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            operation.owner_context_name for operation in receipt.plan.operations
        )
    )


def _checkpoint_by_location(receipt: UpdateReceipt) -> dict[str, str]:
    return {
        checkpoint.context_name: checkpoint.checkpoint_uid
        for checkpoint in receipt.application.checkpoints
    }


def update_location_annotations(receipt: UpdateReceipt) -> dict[str, str]:
    """Summarize each checkpoint location without flattening its operations."""
    checkpoints = _checkpoint_by_location(receipt)
    annotations: dict[str, str] = {}
    for name in _location_names(receipt):
        operations = [
            operation
            for operation in receipt.plan.operations
            if operation.owner_context_name == name
        ]
        counts = Counter(operation.operation.upper() for operation in operations)
        checkpoint = checkpoints[name]
        lifecycle = f"checkpoint {checkpoint[:8]}"
        annotations[name] = (
            f"update · {len(operations)} "
            f"{'change' if len(operations) == 1 else 'changes'} · "
            f"{counts['EDIT']} EDIT · {counts['ADD']} ADD · "
            f"{counts['REMOVE']} REMOVE · {lifecycle}"
        )
    return annotations


def update_checkpoint_entry(
    receipt: UpdateReceipt,
    location: str,
) -> HistoryPickerEntry:
    operations = tuple(
        operation
        for operation in receipt.plan.operations
        if operation.owner_context_name == location
    )
    if not operations:
        raise ValueError("The selected Update location has no changes.")
    checkpoint = _checkpoint_by_location(receipt)[location]
    lifecycle = "APPLIED"
    description = (
        f"{lifecycle} semantic update · {len(operations)} target Memory "
        f"change{'s' if len(operations) != 1 else ''}"
    )
    return HistoryPickerEntry(
        uid=checkpoint,
        timestamp=receipt.application.applied_at,
        command="update",
        description=description,
        detail="Recorded Update checkpoint.",
    )


def update_subtree_locations(
    receipt: UpdateReceipt,
    root: str,
) -> tuple[str, ...]:
    """Return changed owners at or lexically below one frozen catalog root."""

    prefix = root + "/"
    return tuple(
        location
        for location in _location_names(receipt)
        if location == root or location.startswith(prefix)
    )


def update_subtree_checkpoint_entries(
    receipt: UpdateReceipt,
    root: str,
) -> tuple[UpdateSubtreeCheckpointEntry, ...]:
    """Project every available changed owner into one inspectable list."""

    entries: list[UpdateSubtreeCheckpointEntry] = []
    for location in update_subtree_locations(receipt, root):
        entry = update_checkpoint_entry(receipt, location)
        entries.append(
            UpdateSubtreeCheckpointEntry(
                uid=entry.uid,
                timestamp=entry.timestamp,
                command=entry.command,
                description=f"{location} · {entry.description}",
                detail=entry.detail,
                location=location,
            )
        )
    return tuple(entries)


def update_checkpoint_detail_renderer(
    receipt: UpdateReceipt,
    location: str,
):
    """Return a History detail renderer with exact directional Memory changes."""
    operations = tuple(
        operation
        for operation in receipt.plan.operations
        if operation.owner_context_name == location
    )

    def render(entry: HistoryPickerItem) -> HistoryDetailView:
        checkpoint = _checkpoint_by_location(receipt)[location]
        fragments: StyleAndTextTuples = [
            ("class:report-label", " CHECKPOINT  "),
            (
                "class:report-neutral",
                display_escape_text(checkpoint) + "\n",
            ),
            ("class:report-label", " OPERATION   "),
            (
                "class:report-neutral",
                display_escape_text(receipt.uid) + "\n",
            ),
            ("class:report-label", " TIME        "),
            (
                "class:report-neutral",
                display_escape_text(entry.timestamp) + "\n",
            ),
            ("class:report-label", " ACTION      "),
            (
                semantic_action_style("update", fallback="class:report-label"),
                "update\n",
            ),
            ("class:report-label", " LOCATION    "),
            ("class:report-neutral", display_escape_text(location) + "\n"),
            ("", "\n"),
        ]
        unit_start_lines: list[int] = []
        for index, operation in enumerate(operations, start=1):
            treatment = operation.operation.upper()
            unit_start_lines.append(sum(text.count("\n") for _style, text in fragments))
            fragments.extend(
                [
                    ("class:report-neutral", f" {index}. "),
                    ("class:report-label", "UPDATE"),
                    ("class:report-neutral", " · "),
                    (
                        semantic_action_style(
                            treatment,
                            fallback="class:report-label",
                        ),
                        treatment,
                    ),
                    (
                        "class:report-neutral",
                        f" Memory [{display_escape_text(operation.memory_uid[:8])}]\n",
                    ),
                ]
            )
            change = update_operation_change(operation)
            for line in memory_diff_lines(change):
                style_key = {
                    "-": "remove",
                    "+": "add",
                    "=": "equal",
                    " ": "equal",
                }[line.marker]
                fragments.append((f"class:memory-diff.{style_key}", f" {line.marker} "))
                for span in line.spans:
                    fragments.append(
                        (
                            f"class:memory-diff.{style_key}"
                            + (".changed" if span.changed else ""),
                            display_escape_text(span.text),
                        )
                    )
                fragments.append(("", "\n"))
            fragments.extend(
                [
                    ("class:report-label", "   REASON  "),
                    (
                        "class:report-neutral",
                        display_escape_text(operation.reason) + "\n",
                    ),
                    ("", "\n"),
                ]
            )
        return HistoryDetailView(
            content=fragments,
            unit_start_lines=tuple(unit_start_lines),
        )

    return render


def choose_update_checkpoint_history(receipt: UpdateReceipt) -> None:
    """Select an affected Context, then inspect its saved Update checkpoint."""
    locations = _location_names(receipt)
    if not locations:
        raise ValueError("No Update locations are available to inspect.")
    selected = choose_history_location(
        locations,
        current=receipt.inputs.target_name
        if receipt.inputs.target_name in locations
        else None,
        annotations=update_location_annotations(receipt),
        title="DIFF · SELECT A CHANGED CONTEXT",
        catalog_names=tuple(
            dict.fromkeys((context.name for context in receipt.inputs.target_contexts))
        ),
    )
    if selected is None:
        return
    if not isinstance(selected, str):
        raise ValueError("This Update history does not expose a subtree scope.")
    choose_update_checkpoint_at_location(receipt, selected)


def choose_update_checkpoint_at_location(
    receipt: UpdateReceipt,
    location: str,
    *,
    back_navigation: bool = False,
    title: str | None = None,
) -> HistoryBackNavigation | None:
    """Inspect the recorded Update checkpoint for one already-selected location."""
    entry = update_checkpoint_entry(receipt, location)
    result = choose_history(
        (entry,),
        context_name=location,
        initial_details_open=True,
        detail_renderer=update_checkpoint_detail_renderer(receipt, location),
        back_navigation=back_navigation,
        title=title,
    )
    return result if isinstance(result, HistoryBackNavigation) else None


def choose_update_checkpoint_subtree(
    receipt: UpdateReceipt,
    root: str,
    *,
    back_navigation: bool = False,
) -> HistoryBackNavigation | None:
    """Inspect all Update checkpoints owned at or below one catalog root."""

    entries = update_subtree_checkpoint_entries(receipt, root)
    if not entries:
        raise ValueError("The selected Update subtree has no changed Contexts.")

    def render(entry: HistoryPickerItem) -> StyleAndTextTuples:
        if not isinstance(entry, UpdateSubtreeCheckpointEntry):
            raise ValueError("Update subtree history received an invalid entry.")
        return update_checkpoint_detail_renderer(
            receipt,
            entry.location,
        )(entry)

    result = choose_history(
        entries,
        context_name=f"{root} · CHANGED SUBTREE",
        initial_details_open=True,
        detail_renderer=render,
        back_navigation=back_navigation,
    )
    return result if isinstance(result, HistoryBackNavigation) else None
