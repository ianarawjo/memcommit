"""Shared read-only terminal picker for trace/rationale Memory selection."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.commands.context_picker import (
    ContextMemoryRow,
    ContextMemorySelection,
    choose_context,
)
from memcommit.context_targeting.tui.reach import ContextReachState
from memcommit.interfaces.console.text import display_escape_text
from memcommit.interfaces.tui.core.text_layout import elide_terminal_text


MemoryPickerOperation = Literal["trace", "rationale"]


@runtime_checkable
class MemoryPickerItem(Protocol):
    """Minimal presentation projection supplied by provenance."""

    uid: str
    content: str
    status: Literal["CURRENT", "HISTORICAL"]
    change_count: int | None


@dataclass(frozen=True)
class ScopedMemoryPickerItem:
    """Attach one selectable Memory projection to its public Context row."""

    context_name: str
    uid: str
    content: str
    status: Literal["CURRENT", "HISTORICAL"]
    catalog_context_names: tuple[str, ...] = ()
    change_count: int | None = None


@dataclass(frozen=True)
class MemoryReportTargetSelection:
    """Exact Memory plus the process-local Context range used to choose it."""

    root_context_name: str
    owner_context_name: str
    memory_uid: str
    include_descendants: bool


def _preview(value: str, limit: int = 100) -> str:
    escaped = display_escape_text(value)
    return elide_terminal_text(escaped, limit)


def _change_badge(value: int | None) -> str:
    if value is None:
        return "history unavailable"
    return f"r{value}"


def _memory_badges(item: MemoryPickerItem) -> tuple[str, ...]:
    """Project compact identity, exceptional lifecycle, and history badges."""

    identity = item.uid[:8]
    revision = _change_badge(item.change_count)
    if item.status == "HISTORICAL":
        return ("historical", identity, revision)
    return (identity, revision)


def _render_memory_options(
    options: Sequence[MemoryPickerItem],
    *,
    selected: int,
):
    """Render all rows and anchor prompt-toolkit at the selected Memory."""
    fragments: list[tuple[str, str]] = []
    for index, item in enumerate(options):
        is_selected = index == selected
        if is_selected:
            # The cursor marker lets Window scroll with the terminal height
            # without maintaining a second fixed-size viewport in this module.
            fragments.append(("[SetCursorPosition]", ""))
        style = "class:selected" if is_selected else ""
        pointer = "›" if is_selected else " "
        badges = "".join(
            f"[{display_escape_text(badge)}]" for badge in _memory_badges(item)
        )
        fragments.append(
            (
                style,
                f"{pointer} {badges} {_preview(item.content)}",
            )
        )
        if index < len(options) - 1:
            fragments.append(("", "\n"))
    return fragments


def _choose_memory_selection(
    items: Sequence[MemoryPickerItem],
    *,
    context_name: str,
    operation: MemoryPickerOperation,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
    initial_include_descendants: bool | None = None,
) -> tuple[ContextMemorySelection, bool] | None:
    """Select one Memory through the shared Context/Memory tree picker."""
    options = tuple(items)
    if operation not in {"trace", "rationale"}:
        raise ValueError("Memory picker operation must be trace or rationale.")
    if not isinstance(context_name, str) or not context_name:
        raise ValueError("Memory selection requires a Context name.")
    if not options:
        raise ValueError(
            "No current or retained historical direct Memories are available."
        )
    if any(
        not isinstance(item.uid, str)
        or not item.uid
        or not isinstance(item.content, str)
        or item.status not in {"CURRENT", "HISTORICAL"}
        or (
            item.change_count is not None
            and (
                isinstance(item.change_count, bool)
                or not isinstance(item.change_count, int)
                or item.change_count < 0
            )
        )
        for item in options
    ):
        raise ValueError("Memory selection received an invalid entry.")
    if len({item.uid for item in options}) != len(options):
        raise ValueError("Memory selection received duplicate UIDs.")
    if require_tty and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        raise ValueError(
            "Interactive Memory selection requires a terminal. "
            "Pass a Memory UID explicitly."
        )

    catalog_names = tuple(
        dict.fromkeys(
            name
            for item in options
            for name in getattr(item, "catalog_context_names", ())
        )
    )
    owner_names = tuple(
        dict.fromkeys(getattr(item, "context_name", context_name) for item in options)
    )
    # Rationale can select from a readable subtree whose current/root Context
    # has no direct Memory. Retain those empty structural rows so initial focus
    # still means the command's actual current location.
    names = tuple(dict.fromkeys((*catalog_names, *owner_names)))
    items_by_context = {
        name: tuple(
            item
            for item in options
            if getattr(item, "context_name", context_name) == name
        )
        for name in names
    }

    def memory_rows(name: str) -> tuple[ContextMemoryRow, ...]:
        rows: list[ContextMemoryRow] = []
        for item in items_by_context[name]:
            badges = _memory_badges(item)
            rows.append(
                ContextMemoryRow(
                    badges[0],
                    item.content,
                    selector=item.uid,
                    badges=badges[1:],
                )
            )
        return tuple(rows)

    reach_state = (
        ContextReachState.create(
            include_descendants=initial_include_descendants,
        )
        if initial_include_descendants is not None
        else None
    )

    selected = choose_context(
        names,
        current=context_name if context_name in names else names[0],
        title=(
            f"{operation.upper()} · SELECT A MEMORY · "
            f"{display_escape_text(context_name)}"
        ),
        accept_label=("open lineage" if operation == "trace" else "open rationale"),
        memory_loader=memory_rows,
        initially_expand_all=True,
        initially_show_memories=True,
        browse_only=True,
        selectable_memories=True,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
        memory_scope_root=(context_name if reach_state is not None else None),
        memory_reach_state=reach_state,
    )
    if selected is None:
        return None
    if not isinstance(selected, ContextMemorySelection):
        raise ValueError("Memory selection did not return an exact Memory.")
    return selected, (
        reach_state.include_descendants if reach_state is not None else False
    )


def choose_memory_report_target(
    items: Sequence[MemoryPickerItem],
    *,
    context_name: str,
    operation: MemoryPickerOperation,
    initial_include_descendants: bool = False,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> MemoryReportTargetSelection | None:
    """Choose the shared Context reach and one exact Memory for a report."""

    if type(initial_include_descendants) is not bool:
        raise TypeError("Initial Memory report reach must be a boolean.")
    selected = _choose_memory_selection(
        items,
        context_name=context_name,
        operation=operation,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
        initial_include_descendants=initial_include_descendants,
    )
    if selected is None:
        return None
    memory, include_descendants = selected
    return MemoryReportTargetSelection(
        root_context_name=context_name,
        owner_context_name=memory.context_name,
        memory_uid=memory.selector,
        include_descendants=include_descendants,
    )


def choose_memory(
    items: Sequence[MemoryPickerItem],
    *,
    context_name: str,
    operation: MemoryPickerOperation,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> str | None:
    """Compatibility picker without a range surface; return the exact UID."""

    selected = _choose_memory_selection(
        items,
        context_name=context_name,
        operation=operation,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    return selected[0].selector if selected is not None else None
