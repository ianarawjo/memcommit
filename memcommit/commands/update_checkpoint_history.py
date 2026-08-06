"""Project a saved Update as location-owned checkpoint history."""
from __future__ import annotations

from collections import Counter

from prompt_toolkit.formatted_text.base import StyleAndTextTuples

from memcommit.commands.history_picker import (
    HistoryPickerEntry,
    HistoryPickerItem,
    choose_history,
)
from memcommit.commands.history_location_picker import choose_history_location
from memcommit.commands.tui_primitives import display_escape_text
from memcommit.memory_diff import memory_diff_lines, update_operation_change
from memcommit.update import UpdateSession


def _location_names(session: UpdateSession) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            operation.owner_context_name for operation in session.operations
        )
    )


def _checkpoint_by_location(session: UpdateSession) -> dict[str, str]:
    if session.application is None:
        return {}
    return {
        receipt.context_name: receipt.checkpoint_uid
        for receipt in session.application.checkpoints
    }


def update_location_annotations(session: UpdateSession) -> dict[str, str]:
    """Summarize each checkpoint location without flattening its operations."""
    checkpoints = _checkpoint_by_location(session)
    annotations: dict[str, str] = {}
    for name in _location_names(session):
        operations = [
            operation
            for operation in session.operations
            if operation.owner_context_name == name
        ]
        counts = Counter(operation.operation.upper() for operation in operations)
        checkpoint = checkpoints.get(name)
        lifecycle = (
            f"checkpoint {checkpoint[:8]}"
            if checkpoint is not None
            else "NOT CHECKPOINTED"
        )
        annotations[name] = (
            f"update · {len(operations)} "
            f"{'change' if len(operations) == 1 else 'changes'} · "
            f"{counts['EDIT']} EDIT · {counts['ADD']} ADD · "
            f"{counts['REMOVE']} REMOVE · {lifecycle}"
        )
    return annotations


def update_checkpoint_entry(
    session: UpdateSession,
    location: str,
) -> HistoryPickerEntry:
    operations = tuple(
        operation
        for operation in session.operations
        if operation.owner_context_name == location
    )
    if not operations:
        raise ValueError("The selected Update location has no changes.")
    checkpoint = _checkpoint_by_location(session).get(location)
    lifecycle = session.status.upper()
    description = (
        f"{lifecycle} semantic update · {len(operations)} target Memory "
        f"change{'s' if len(operations) != 1 else ''}"
    )
    return HistoryPickerEntry(
        uid=checkpoint or session.uid,
        timestamp=(
            session.application.applied_at
            if session.application is not None
            else session.created_at
        ),
        command="update",
        description=description,
        detail=(
            "Recorded Update checkpoint."
            if checkpoint is not None
            else "Staged Update · no checkpoint has been created."
        ),
    )


def update_checkpoint_detail_renderer(
    session: UpdateSession,
    location: str,
):
    """Return a History detail renderer with exact directional Memory changes."""
    operations = tuple(
        operation
        for operation in session.operations
        if operation.owner_context_name == location
    )

    def render(entry: HistoryPickerItem) -> StyleAndTextTuples:
        checkpoint = _checkpoint_by_location(session).get(location)
        fragments: StyleAndTextTuples = [
            ("class:report-label", " CHECKPOINT  "),
            (
                "class:report-neutral",
                (
                    display_escape_text(checkpoint)
                    if checkpoint is not None
                    else "(not created)"
                )
                + "\n",
            ),
            ("class:report-label", " SESSION     "),
            (
                "class:report-neutral",
                display_escape_text(session.uid) + "\n",
            ),
            ("class:report-label", " TIME        "),
            (
                "class:report-neutral",
                display_escape_text(entry.timestamp) + "\n",
            ),
            ("class:report-label", " ACTION      "),
            ("class:report-label", "update\n"),
            ("class:report-label", " LOCATION    "),
            ("class:report-neutral", display_escape_text(location) + "\n"),
            ("", "\n"),
        ]
        for index, operation in enumerate(operations, start=1):
            fragments.extend(
                [
                    (
                        "class:report-label",
                        f" {index}. UPDATE · {operation.operation.upper()} "
                        f"Memory [{display_escape_text(operation.memory_uid[:8])}]\n",
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
                fragments.append(
                    (f"class:memory-diff.{style_key}", f" {line.marker} ")
                )
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
        return fragments

    return render


def choose_update_checkpoint_history(session: UpdateSession) -> None:
    """Select an affected Context, then inspect its saved Update checkpoint."""
    locations = _location_names(session)
    if not locations:
        raise ValueError("No Update locations are available to inspect.")
    selected = choose_history_location(
        locations,
        current=session.target_name if session.target_name in locations else None,
        annotations=update_location_annotations(session),
        title="DIFF · SELECT A CHANGED CONTEXT",
        catalog_names=tuple(
            dict.fromkeys(
                (context.name for context in session.target_contexts)
            )
        ),
    )
    if selected is None:
        return
    choose_update_checkpoint_at_location(session, selected)


def choose_update_checkpoint_at_location(
    session: UpdateSession,
    location: str,
) -> None:
    """Inspect the recorded Update checkpoint for one already-selected location."""
    entry = update_checkpoint_entry(session, location)
    choose_history(
        (entry,),
        context_name=location,
        mode="log",
        initial_details_open=True,
        detail_renderer=update_checkpoint_detail_renderer(session, location),
    )
