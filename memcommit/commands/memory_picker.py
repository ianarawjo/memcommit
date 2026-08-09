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
from memcommit.commands.tui_primitives import display_escape_text
from memcommit.commands.tui_text_layout import elide_terminal_text


MemoryPickerOperation = Literal["trace", "rationale"]


@runtime_checkable
class MemoryPickerItem(Protocol):
    """Minimal presentation projection supplied by provenance."""

    uid: str
    content: str
    status: Literal["CURRENT", "HISTORICAL"]


@dataclass(frozen=True)
class ScopedMemoryPickerItem:
    """Attach one selectable Memory projection to its public Context row."""

    context_name: str
    uid: str
    content: str
    status: Literal["CURRENT", "HISTORICAL"]
    catalog_context_names: tuple[str, ...] = ()


def _preview(value: str, limit: int = 100) -> str:
    escaped = display_escape_text(value)
    return elide_terminal_text(escaped, limit)


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
        fragments.append(
            (
                style,
                f"{pointer} {item.status:<10} "
                f"[{display_escape_text(item.uid[:8])}]  "
                f"{_preview(item.content)}",
            )
        )
        if index < len(options) - 1:
            fragments.append(("", "\n"))
    return fragments


def choose_memory(
    items: Sequence[MemoryPickerItem],
    *,
    context_name: str,
    operation: MemoryPickerOperation,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> str | None:
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
        return tuple(
            ContextMemoryRow(
                f"{item.status.casefold()} {item.uid[:8]}",
                item.content,
                selector=item.uid,
            )
            for item in items_by_context[name]
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
    )
    if selected is None:
        return None
    if not isinstance(selected, ContextMemorySelection):
        raise ValueError("Memory selection did not return an exact Memory.")
    return selected.selector
