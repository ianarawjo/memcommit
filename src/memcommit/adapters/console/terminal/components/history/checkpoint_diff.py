"""Exact, provider-free checkpoint transition presentation."""

from __future__ import annotations

import difflib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from prompt_toolkit.formatted_text.base import StyleAndTextTuples
from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.adapters.console.terminal.components.history.model import (
    HistoryDetailView,
    HistoryPickerItem,
)
from memcommit.adapters.console.terminal.components.plain_text_clipboard import (
    plain_text_from_fragments,
)
from memcommit.adapters.console.terminal.components.read_only_viewer import (
    run_read_only_viewer,
)
from memcommit.adapters.console.terminal.core.text import (
    display_escape_text,
)
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import semantic_action_style
from memcommit.adapters.console.terminal.components.context_diff import render_context_item_change
from memcommit.application.capabilities.reviewing.context_diff import (
    ContextItemChange,
    context_item_changes,
    context_item_text,
)
from memcommit.application.capabilities.history.query.checkpoint_history_slicing import (
    CheckpointHistorySlice,
)


def _before_snapshots(
    checkpoints: Sequence[Mapping[str, Any]],
) -> dict[str, object]:
    ordered = sorted(
        checkpoints,
        key=lambda value: (str(value.get("timestamp", "")), str(value.get("uid", ""))),
    )
    previous: object = {"memories": {}, "order": []}
    result: dict[str, object] = {}
    for checkpoint in ordered:
        uid = checkpoint.get("uid")
        if not isinstance(uid, str):
            continue
        command_before = checkpoint.get("command_before")
        result[uid] = (
            command_before if isinstance(command_before, Mapping) else previous
        )
        previous = checkpoint.get("snapshot")
    return result


def _direct_item_count(count: int) -> str:
    return f"{count} DIRECT ITEM{'S' if count != 1 else ''}"


def _revision_projection(
    checkpoints: Sequence[Mapping[str, Any]] | CheckpointHistorySlice,
    entry: HistoryPickerItem,
) -> tuple[
    Mapping[str, Any],
    tuple[ContextItemChange, ...],
    int,
    bool,
]:
    checkpoint_records = (
        checkpoints.physical_entries
        if isinstance(checkpoints, CheckpointHistorySlice)
        else checkpoints
    )
    records = {
        checkpoint["uid"]: checkpoint
        for checkpoint in checkpoint_records
        if isinstance(checkpoint.get("uid"), str)
    }
    checkpoint = records[entry.uid]
    if isinstance(checkpoints, CheckpointHistorySlice):
        revision = checkpoints.revision(entry.uid)
        before_snapshot = revision.before_snapshot
        after_snapshot = revision.after_snapshot
    else:
        before_snapshot = _before_snapshots(checkpoints)[entry.uid]
        after_snapshot = checkpoint.get("snapshot")
    changes, result_count, reordered = context_item_changes(
        before_snapshot,
        after_snapshot,
    )
    return checkpoint, changes, result_count, reordered


def checkpoint_revision_document_fragments(
    checkpoints: Sequence[Mapping[str, Any]] | CheckpointHistorySlice,
    entry: HistoryPickerItem,
    *,
    context_name: str,
    verbose: bool = False,
) -> StyleAndTextTuples:
    """Project one checkpoint as a compact, semantically colored document.

    Diff answers one question: what changed at this checkpoint?  Retained
    Memories remain part of the exact result count, but their rows stay out of
    the default scan path.  ``--verbose`` restores those rows and full UIDs.
    """

    checkpoint, changes, result_count, reordered = _revision_projection(
        checkpoints,
        entry,
    )
    counts = {
        treatment: sum(change.treatment == treatment for change in changes)
        for treatment in ("KEEP", "ADD", "EDIT", "REMOVE")
    }
    action_value = checkpoint.get("command")
    action = (
        action_value
        if isinstance(action_value, str) and action_value
        else "checkpoint"
    )
    checkpoint_uid = entry.uid if verbose else entry.uid[:8]
    changed_count = counts["ADD"] + counts["EDIT"] + counts["REMOVE"]
    fragments: StyleAndTextTuples = [
        ("class:report-label", "DIFF"),
        ("class:report-neutral", f" · {display_escape_text(context_name)}\n"),
        ("class:history-receipt", f"[CHECKPOINT {display_escape_text(checkpoint_uid)}]"),
        ("class:report-neutral", " · "),
        (
            semantic_action_style(action, fallback="class:report-neutral"),
            display_escape_text(action),
        ),
        (
            "class:report-neutral",
            f" · {changed_count} CHANGE{'S' if changed_count != 1 else ''}"
            f" · {result_count} RESULT "
            f"MEMOR{'IES' if result_count != 1 else 'Y'}\n",
        ),
        (
            "class:report-neutral",
            f"{counts['EDIT']} edited · {counts['ADD']} added · "
            f"{counts['REMOVE']} removed",
        ),
    ]
    if not verbose and counts["KEEP"]:
        fragments.append(
            (
                "class:report-neutral",
                f" · {counts['KEEP']} unchanged hidden",
            )
        )
    fragments.append(("class:report-neutral", "\n"))
    description = entry.description.strip()
    if description:
        fragments.extend(
            (
                ("class:report-neutral", display_escape_text(description)),
                ("class:report-neutral", "\n"),
            )
        )
    fragments.append(("", "\n"))

    visible_changes = (
        changes
        if verbose
        else tuple(change for change in changes if change.treatment != "KEEP")
    )
    if visible_changes:
        for change in visible_changes:
            fragments.extend(
                render_context_item_change(
                    change,
                    location=entry.uid,
                    verbose_uid=verbose,
                )
            )
    else:
        fragments.append(
            ("class:report-neutral", "No direct Memory content changed.\n")
        )
    if reordered:
        fragments.append(
            (
                "class:report-neutral",
                "\nORDER · retained direct items changed position; result "
                "order is authoritative.\n",
            )
        )
    if not verbose and counts["KEEP"]:
        fragments.append(
            (
                "class:report-neutral",
                "\nUse --verbose to include unchanged Memories and full UIDs.\n",
            )
        )
    return fragments


def format_checkpoint_revision_report(
    checkpoints: Sequence[Mapping[str, Any]] | CheckpointHistorySlice,
    entry: HistoryPickerItem,
    *,
    context_name: str,
    verbose: bool = False,
) -> str:
    """Return the ANSI-free equivalent of the read-only Diff document."""

    return plain_text_from_fragments(
        checkpoint_revision_document_fragments(
            checkpoints,
            entry,
            context_name=context_name,
            verbose=verbose,
        ),
        whole_document=True,
    )


def open_checkpoint_revision_viewer(
    checkpoints: Sequence[Mapping[str, Any]] | CheckpointHistorySlice,
    entry: HistoryPickerItem,
    *,
    context_name: str,
    verbose: bool = False,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> None:
    """Open one frozen checkpoint document in the shared read-only Viewer."""

    run_read_only_viewer(
        checkpoint_revision_document_fragments(
            checkpoints,
            entry,
            context_name=context_name,
            verbose=verbose,
        ),
        title="DIFF REPORT",
        frame_title="CHECKPOINT REVISION",
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )


def checkpoint_revision_detail_renderer(
    checkpoints: Sequence[Mapping[str, Any]] | CheckpointHistorySlice,
    *,
    verbose_uids: bool = False,
):
    """Render one revision diff together with its complete resulting state."""
    checkpoint_records = (
        checkpoints.physical_entries
        if isinstance(checkpoints, CheckpointHistorySlice)
        else checkpoints
    )
    records = {
        checkpoint["uid"]: checkpoint
        for checkpoint in checkpoint_records
        if isinstance(checkpoint.get("uid"), str)
    }
    before_by_uid = (
        None
        if isinstance(checkpoints, CheckpointHistorySlice)
        else _before_snapshots(checkpoints)
    )

    def render(entry: HistoryPickerItem) -> StyleAndTextTuples | HistoryDetailView:
        checkpoint = records[entry.uid]
        if isinstance(checkpoints, CheckpointHistorySlice):
            revision = checkpoints.revision(entry.uid)
            before_snapshot = revision.before_snapshot
            after_snapshot = revision.after_snapshot
        else:
            assert before_by_uid is not None
            before_snapshot = before_by_uid[entry.uid]
            after_snapshot = checkpoint.get("snapshot")
        revision_items, result_count, reordered = context_item_changes(
            before_snapshot,
            after_snapshot,
        )
        command = checkpoint.get("command")
        action = command if isinstance(command, str) and command else "checkpoint"
        fragments: StyleAndTextTuples = [
            ("class:report-label", " CHECKPOINT  "),
            ("class:report-neutral", display_escape_text(entry.uid) + "\n"),
            ("class:report-label", " ACTION      "),
            (
                semantic_action_style(action, fallback="class:report-label"),
                display_escape_text(action) + "\n",
            ),
            ("class:report-label", " DESCRIPTION "),
            (
                "class:report-neutral",
                display_escape_text(entry.description or "(none)") + "\n\n",
            ),
            ("class:report-label", " REVISION DIFF"),
            (
                "class:report-neutral",
                f" · RESULT {_direct_item_count(result_count)}\n",
            ),
        ]
        counts = {
            treatment: sum(
                change.treatment == treatment
                for change in revision_items
            )
            for treatment in ("KEEP", "ADD", "EDIT", "REMOVE")
        }
        fragments.append(
            (
                "class:report-neutral",
                " SUMMARY · "
                f"{counts['KEEP']} kept · {counts['ADD']} added · "
                f"{counts['EDIT']} edited · {counts['REMOVE']} removed\n\n",
            )
        )
        unit_start_lines: list[int] = []
        if not revision_items:
            fragments.append(("class:report-neutral", " (empty direct Context)\n"))
        for change in revision_items:
            unit_start_lines.append(
                sum(text.count("\n") for _style, text in fragments)
            )
            fragments.extend(
                render_context_item_change(
                    change,
                    location=entry.uid,
                    verbose_uid=verbose_uids,
                )
            )
        if reordered:
            fragments.append(
                (
                    "class:report-neutral",
                    "\n ORDER · retained direct items changed position; result "
                    "rows remain authoritative.\n",
                )
            )
        return HistoryDetailView(
            content=fragments,
            unit_start_lines=tuple(unit_start_lines),
            unit_label="ITEM",
        )

    return render


def _encoded_lines(content: str) -> list[str]:
    encoded: list[str] = []
    for line in content.splitlines(keepends=True):
        if line.endswith("\r\n"):
            text = line[:-2]
            has_newline = True
        elif line.endswith(("\n", "\r")):
            text = line[:-1]
            has_newline = True
        else:
            text = line
            has_newline = False
        encoded.append(
            json.dumps([text, has_newline], ensure_ascii=False, separators=(",", ":"))
        )
    return encoded


def _raw_revision_lines(
    changes: Sequence[ContextItemChange],
    *,
    context_name: str,
) -> list[str]:
    lines: list[str] = []
    for change in changes:
        if change.treatment == "KEEP":
            continue
        before = context_item_text(change.before)
        after = context_item_text(change.after)
        label = f"{context_name}#{change.uid}"
        lines.append(f"diff --mem {label}")
        encoded = difflib.unified_diff(
            _encoded_lines(before or ""),
            _encoded_lines(after or ""),
            fromfile=f"a/{label}" if before is not None else "/dev/null",
            tofile=f"b/{label}" if after is not None else "/dev/null",
            lineterm="",
        )
        for line in encoded:
            if line.startswith(("--- ", "+++ ", "@@")) or not line:
                lines.append(line)
                continue
            marker = line[0]
            try:
                value = json.loads(line[1:])
            except json.JSONDecodeError:
                lines.append(line)
                continue
            if (
                isinstance(value, list)
                and len(value) == 2
                and isinstance(value[0], str)
                and isinstance(value[1], bool)
            ):
                lines.append(marker + value[0])
                if not value[1]:
                    lines.append("\\ No newline at end of file")
            else:
                lines.append(line)
    return lines


def render_checkpoint_revision_cli(
    checkpoints: Sequence[Mapping[str, Any]] | CheckpointHistorySlice,
    entry: HistoryPickerItem,
    *,
    context_name: str,
    stat: bool = False,
    raw: bool = False,
    verbose: bool = False,
) -> str:
    """Render one exact checkpoint revision without opening a terminal picker."""

    checkpoint, changes, result_count, _reordered = _revision_projection(
        checkpoints,
        entry,
    )
    counts = {
        treatment: sum(change.treatment == treatment for change in changes)
        for treatment in ("KEEP", "ADD", "EDIT", "REMOVE")
    }
    action = checkpoint.get("command")
    action = action if isinstance(action, str) and action else "checkpoint"
    header = [
        "UNIT        CHECKPOINT · THIS CHECKPOINT VS PREVIOUS",
        f"CHECKPOINT  {entry.uid}",
        f"CONTEXT     {context_name}",
        f"ACTION      {action}",
        f"DESCRIPTION {entry.description or '(none)'}",
        f"RESULT      {_direct_item_count(result_count)}",
        (
            "SUMMARY     "
            f"{counts['KEEP']} kept · {counts['ADD']} added · "
            f"{counts['EDIT']} edited · {counts['REMOVE']} removed"
        ),
    ]
    if stat:
        return "\n".join(header)
    if raw:
        body = _raw_revision_lines(changes, context_name=context_name)
        return "\n".join((*header, "", *body))
    return format_checkpoint_revision_report(
        checkpoints,
        entry,
        context_name=context_name,
        verbose=verbose,
    )


def checkpoint_diff_detail_renderer(
    checkpoints: Sequence[Mapping[str, Any]] | CheckpointHistorySlice,
):
    """Compatibility name for the shared complete revision renderer."""

    return checkpoint_revision_detail_renderer(checkpoints)


def checkpoint_restore_detail_renderer(
    current_snapshot: Mapping[str, Any],
    checkpoints: Sequence[Mapping[str, Any]] | CheckpointHistorySlice,
):
    """Compatibility adapter; Revert now reviews the checkpoint revision."""

    del current_snapshot
    return checkpoint_revision_detail_renderer(checkpoints)
