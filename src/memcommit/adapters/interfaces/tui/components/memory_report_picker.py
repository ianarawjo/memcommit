"""Shared read-only terminal picker for trace/rationale Memory selection."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.context_targeting.tui.reach import ContextReachState
from memcommit.context_targeting.tui.picker import (
    ContextMemoryBadge,
    ContextMemoryRow,
    ContextMemorySelection,
    ContextPickerActionReceipt,
    choose_context,
)
from memcommit.adapters.interfaces.console.text import (
    display_escape_text,
)
from memcommit.adapters.interfaces.tui.core.text_layout import (
    elide_terminal_text,
)


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


def _reject_context_target(_context_name: str) -> ContextPickerActionReceipt:
    """Explain the report picker's exact-Memory target boundary in place."""

    return ContextPickerActionReceipt(
        label="CONTEXT NOT SELECTABLE",
        detail="Select an exact Memory row; use Left/Right to browse Contexts.",
        label_style="class:memcommit.error",
    )


def _preview(value: str, limit: int = 100) -> str:
    escaped = display_escape_text(value)
    return elide_terminal_text(escaped, limit)


def _change_badge(value: int | None) -> str:
    if value is None:
        return "history unavailable"
    return f"r{value}"


def _memory_badges(item: MemoryPickerItem) -> tuple[ContextMemoryBadge, ...]:
    """Project compact identity, exceptional lifecycle, and history badges."""

    identity = item.uid[:8]
    revision = _change_badge(item.change_count)
    if item.status == "HISTORICAL":
        return (
            ContextMemoryBadge("historical", "historical-memory-badge"),
            ContextMemoryBadge(identity),
            ContextMemoryBadge(revision),
        )
    return (ContextMemoryBadge(identity), ContextMemoryBadge(revision))


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
        fragments.append((style, f"{pointer} "))
        for badge in _memory_badges(item):
            badge_style = (
                style if is_selected or badge.style is None else f"class:{badge.style}"
            )
            fragments.append((badge_style, f"[{display_escape_text(badge.text)}]"))
        fragments.append((style, f" {_preview(item.content)}"))
        if index < len(options) - 1:
            fragments.append(("", "\n"))
    return fragments


def _choose_memory_selection(
    items: Sequence[MemoryPickerItem],
    *,
    context_name: str,
    operation: MemoryPickerOperation,
    catalog_context_names: Sequence[str] | None = None,
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
    explicit_catalog = tuple(catalog_context_names or ())
    if not options and not explicit_catalog:
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

    item_catalog_names = tuple(
        dict.fromkeys(
            name
            for item in options
            for name in getattr(item, "catalog_context_names", ())
        )
    )
    owner_names = tuple(
        dict.fromkeys(getattr(item, "context_name", context_name) for item in options)
    )
    # A current-root report flow may deliberately open an empty Context. Keep
    # its frozen structural rows even when no Memory exists anywhere in that
    # range; candidate absence is presentation state, not permission to bypass
    # the exact/subtree control.
    names = tuple(dict.fromkeys((*explicit_catalog, *item_catalog_names, *owner_names)))
    if (
        any(not isinstance(name, str) or not name for name in names)
        or context_name not in names
        or any(owner not in names for owner in owner_names)
    ):
        raise ValueError("Memory selection received an invalid Context catalog.")
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
                    badges[0].text,
                    item.content,
                    label_style=badges[0].style,
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
        context_accept_handler=_reject_context_target,
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
    catalog_context_names: Sequence[str] | None = None,
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
        catalog_context_names=catalog_context_names,
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
    catalog_context_names: Sequence[str] | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> str | None:
    """Compatibility picker without a range surface; return the exact UID."""

    selected = _choose_memory_selection(
        items,
        context_name=context_name,
        operation=operation,
        catalog_context_names=catalog_context_names,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    return selected[0].selector if selected is not None else None
