"""Formatted terminal rendering for Context and direct-item picker rows."""

from __future__ import annotations

from collections.abc import Sequence
from typing import AbstractSet, Mapping

from prompt_toolkit.styles import Style, merge_styles
from prompt_toolkit.utils import get_cwidth

from memcommit.adapters.console.terminal.components.selection import tree_choice_marker
from memcommit.adapters.console.terminal.components.tree_row import (
    navigable_tree_row_prefix,
)
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.core.context_targeting.model import DirectMemoryTarget
from memcommit.adapters.console.terminal.components.operation_context_scope_editor.state.tree import (
    ContextTree,
    ContextTreeRow,
    ContextTreeState,
)
from memcommit.source_projection.model import SourceDisplayFacts, SourceState
from memcommit.source_projection.presentation import (
    SourceDisplayValue,
    SourceTokenRole,
    normalize_source_display_tokens,
    source_annotation_tokens,
    source_object_label,
)
from memcommit.source_projection.tui import render_source_display_tokens
from memcommit.adapters.console.terminal.components.context_picker.model import (
    ContextMemoryRow,
)


_CONTEXT_NAVIGATION_HINT = " ↑↓ move  ←→ expand  "
_CONTEXT_PICKER_STYLE = merge_styles(
    [
        MEMCOMMIT_TUI_STYLE,
        SEMANTIC_VIEWER_STYLE,
        Style.from_dict(
            {
                # Context and read-only Memory navigation share one moving
                # focus bar without sharing selection semantics.
                "selected": "reverse bold",
                "focused": "reverse bold",
            }
        ),
    ]
)
# Embedded browse-only surfaces share the picker's focus grammar without
# reaching through its complete selection application.
CONTEXT_PICKER_STYLE = _CONTEXT_PICKER_STYLE


def memory_visibility_key_hint(state: ContextTreeState) -> str:
    """Name the lowercase local and uppercase global preview scopes.

    The case difference is easy to miss in a dense terminal footer.  Keep the
    key spelling, current action, and affected Context range together so every
    tree-based caller exposes the same presentation contract.
    """

    local_action = "hide" if state.memories_visible_for(state.selected_name) else "show"
    global_action = "hide" if state.show_memories else "show"
    return (
        f"m THIS Context: {local_action} items · M EVERY Context: {global_action} items"
    )


def render_context_options(
    rows: Sequence[ContextTreeRow],
    *,
    selected: str,
    current: str | None,
    annotations: Mapping[str, SourceDisplayValue] | None = None,
    memories_by_context: Mapping[str, Sequence[ContextMemoryRow]] | None = None,
    show_memories: bool = False,
    visible_memory_contexts: AbstractSet[str] | None = None,
    display_names: Mapping[str, str] | None = None,
    wrap_width: int | None = None,
    memory_anchor: tuple[str, int] | None = None,
    selectable_memories: bool = False,
) -> list[tuple[str, str]]:
    """Render visible tree rows and anchor prompt-toolkit at the selection."""
    fragments: list[tuple[str, str]] = []
    for index, row in enumerate(rows):
        is_selected = row.name == selected
        context_is_focused = is_selected and memory_anchor is None
        if context_is_focused:
            # A real cursor anchor lets Window own terminal-height-dependent
            # scrolling while expansion controls which tree rows exist.
            fragments.append(("[SetCursorPosition]", ""))
        is_current = row.name == current
        style = "class:selected" if context_is_focused else ""
        memory_is_visible = (
            row.name in visible_memory_contexts
            if visible_memory_contexts is not None
            else show_memories
        )
        # Branch nodes use the marker for Context descendants. A materialized
        # leaf uses the same marker for its direct-Memory presentation layer;
        # without this distinction an open leaf misleadingly remains a dot.
        leaf_has_memory_layer = (
            not row.has_children
            and row.materialized
            and memories_by_context is not None
        )
        branch = (
            "▾"
            if row.expanded or (leaf_has_memory_layer and memory_is_visible)
            else "▸"
            if row.has_children or leaf_has_memory_layer
            else "·"
        )
        annotation = (annotations or {}).get(row.name)
        if annotation is None and not row.materialized:
            annotation = SourceDisplayFacts(states=(SourceState.UNAVAILABLE,))
        display_tokens = normalize_source_display_tokens(annotation)
        ownership_tokens = tuple(
            token for token in display_tokens if token.role is SourceTokenRole.OWNERSHIP
        )
        annotation_tokens = tuple(
            token
            for token in display_tokens
            if token.role is not SourceTokenRole.OWNERSHIP
        )
        display_name = (display_names or {}).get(row.name, row.name)
        # Keep raw names in the tree for identity and return only an escaped
        # label to prompt-toolkit; selection never returns presentation text.
        prefix = navigable_tree_row_prefix(
            selected=is_selected,
            current=is_current,
            depth=row.depth,
            branch=branch,
        )
        if ownership_tokens:
            fragments.append((style, prefix))
            fragments.extend(
                render_source_display_tokens(
                    ownership_tokens,
                    override_style=style,
                )
            )
            fragments.append((style, " "))
            fragments.append(
                (
                    # The shared focus bar must remain the only active color.
                    style or "class:report-neutral",
                    display_escape_text(display_name),
                )
            )
        else:
            fragments.append((style, prefix + display_escape_text(display_name)))
        if annotation_tokens:
            fragments.append((style, "  "))
            fragments.extend(
                render_source_display_tokens(
                    annotation_tokens,
                    override_style=style,
                )
            )
        if memory_is_visible and row.materialized:
            fragments.extend(
                render_context_memory_previews(
                    row,
                    (memories_by_context or {}).get(row.name, ()),
                    wrap_width=wrap_width,
                    memory_anchor=memory_anchor,
                    selectable_memories=selectable_memories,
                )
            )
        if index < len(rows) - 1:
            fragments.append(("", "\n"))
    return fragments


def render_context_memory_previews(
    row: ContextTreeRow,
    memories: Sequence[ContextMemoryRow],
    *,
    wrap_width: int | None,
    memory_anchor: tuple[str, int] | None,
    selectable_memories: bool = False,
    selected_memory: DirectMemoryTarget | None = None,
    selected_memories: AbstractSet[DirectMemoryTarget] | None = None,
    show_selection_marker: bool = False,
) -> list[tuple[str, str]]:
    """Render direct Memory rows nested beneath one shared Context-tree row."""

    fragments: list[tuple[str, str]] = []
    for memory_index, memory in enumerate(memories):
        if memory.section_label is not None:
            fragments.append(("", "\n"))
            fragments.append(
                (
                    "class:report-label",
                    "  " * (row.depth + 1) + display_escape_text(memory.section_label),
                )
            )
        fragments.append(("", "\n"))
        memory_is_focused = memory_anchor == (row.name, memory_index)
        if memory_is_focused:
            # Hover anchors viewport motion; retained selection is independent.
            fragments.append(("[SetCursorPosition]", ""))
        memory_style = "class:focused" if memory_is_focused else f"class:{memory.style}"
        memory_target = (
            DirectMemoryTarget(row.name, memory.selector)
            if memory.selector is not None
            else None
        )
        memory_is_selected = memory_target is not None and (
            memory_target in (selected_memories or frozenset())
            or memory_target == selected_memory
        )
        if show_selection_marker:
            memory_pointer = "›" if memory_is_focused else " "
            memory_prefix = (
                f"{memory_pointer} "
                + tree_choice_marker(
                    selected=memory_is_selected,
                    available=memory.selector is not None,
                )
                + " "
            )
        else:
            memory_pointer = "›" if selectable_memories and memory_is_focused else "·"
            memory_prefix = f"{memory_pointer} "
        object_label = memory.object_label_override or (
            source_object_label(memory.source) if memory.source is not None else ""
        )
        display_label = (f"{object_label} " if object_label else "") + memory.label
        memory_annotations = (
            *(
                source_annotation_tokens(memory.source)
                if memory.source is not None
                else ()
            ),
            *memory.supplemental_annotations,
        )
        label_style = (
            memory_style
            if memory_is_focused or memory.label_style is None
            else f"class:{memory.label_style}"
        )
        styled_leading_fragments = [
            (
                memory_style,
                "  " * (row.depth + 1) + memory_prefix,
            ),
            (label_style, f"[{display_escape_text(display_label)}]"),
        ]
        for badge in memory.badges:
            styled_leading_fragments.append((memory_style, " "))
            badge_style = (
                memory_style
                if memory_is_focused or badge.style is None
                else f"class:{badge.style}"
            )
            styled_leading_fragments.append(
                (badge_style, f"[{display_escape_text(badge.text)}]")
            )
        styled_leading_fragments.append((memory_style, " "))
        leading = "".join(text for _style, text in styled_leading_fragments)
        has_custom_badge_style = not memory_is_focused and (
            memory.annotation_style is not None
            or memory.label_style is not None
            or any(badge.style is not None for badge in memory.badges)
        )
        annotation_width = get_cwidth(
            " · ".join(token.text for token in memory_annotations)
            + (" · " if memory_annotations else "")
        )
        content_lines = _wrap_memory_preview(
            display_escape_text(memory.content),
            available_width=(
                None
                if wrap_width is None
                else max(
                    1,
                    wrap_width - get_cwidth(leading) - annotation_width,
                )
            ),
        )
        if not memory_annotations:
            if has_custom_badge_style:
                fragments.extend(styled_leading_fragments)
                fragments.append((memory_style, content_lines[0]))
            else:
                fragments.append((memory_style, leading + content_lines[0]))
        else:
            if has_custom_badge_style:
                fragments.extend(styled_leading_fragments)
            else:
                fragments.append((memory_style, leading))
            fragments.extend(
                render_source_display_tokens(
                    memory_annotations,
                    override_style=(
                        memory_style
                        if memory_is_focused
                        else (
                            f"class:{memory.annotation_style}"
                            if memory.annotation_style is not None
                            else ""
                        )
                    ),
                )
            )
            fragments.append((memory_style, " · "))
            fragments.append((memory_style, content_lines[0]))
        for continuation in content_lines[1:]:
            fragments.append(("", "\n"))
            fragments.append(
                (
                    memory_style,
                    " " * (get_cwidth(leading) + annotation_width) + continuation,
                )
            )
    return fragments


def render_context_memory_detail(
    memory: ContextMemoryRow | None,
) -> list[tuple[str, str]]:
    """Render the exact typed fields attached to one focused nested row."""

    if memory is None or not memory.details:
        return []
    title = memory.detail_title or memory.label
    label_width = max(len(detail.label) for detail in memory.details)
    fragments: list[tuple[str, str]] = [
        ("class:report-label", f" SELECTED COMMAND · {display_escape_text(title)}")
    ]
    for detail in memory.details:
        fragments.append(("", "\n"))
        fragments.append(
            (
                "class:report-neutral",
                f" {display_escape_text(detail.label):<{label_width}}  ",
            )
        )
        fragments.append(
            (
                f"class:{detail.style}"
                if detail.style is not None
                else "class:report-neutral",
                display_escape_text(detail.value),
            )
        )
    return fragments


def _wrap_memory_preview(
    content: str,
    *,
    available_width: int | None,
) -> tuple[str, ...]:
    """Soft-wrap escaped preview text at whitespace boundaries."""

    if available_width is None or get_cwidth(content) <= available_width:
        return (content,)
    lines: list[str] = []
    remaining = content
    while get_cwidth(remaining) > available_width:
        used = 0
        fit = 0
        for index, character in enumerate(remaining):
            width = get_cwidth(character)
            if used + width > available_width:
                break
            used += width
            fit = index + 1
        if fit == 0:
            fit = 1
        boundary = max(
            (
                index
                for index, character in enumerate(remaining[:fit], start=1)
                if character.isspace()
            ),
            default=0,
        )
        split_at = boundary if boundary else fit
        line = remaining[:split_at].rstrip()
        if not line:
            line = remaining[:fit]
            split_at = fit
        lines.append(line)
        remaining = remaining[split_at:].lstrip()
    lines.append(remaining)
    return tuple(lines)


def context_option_continuation_prefixes(
    rows: Sequence[ContextTreeRow],
    *,
    memories_by_context: Mapping[str, Sequence[ContextMemoryRow]] | None = None,
    show_memories: bool = False,
    visible_memory_contexts: AbstractSet[str] | None = None,
    wrap_width: int | None = None,
) -> tuple[str, ...]:
    """Return one hanging indent for every logical picker body line.

    Prompt-toolkit wraps a formatted-text Window after the row fragments have
    been built. Keeping the continuation prefix separate lets a resized
    terminal reflow long previews without inserting durable newlines into
    Memory content. Context continuations align with their displayed name;
    Memory continuations align after the selector so the selector is not
    repeated on every visual line.
    """

    prefixes: list[str] = []
    for row in rows:
        # Pointer, current marker, tree indentation, branch glyph, and space.
        prefixes.append(" " * (6 + 2 * row.depth))
        memory_is_visible = (
            row.name in visible_memory_contexts
            if visible_memory_contexts is not None
            else show_memories
        )
        if not memory_is_visible or not row.materialized:
            continue
        for memory in (memories_by_context or {}).get(row.name, ()):
            if memory.section_label is not None:
                prefixes.append(" " * (2 * (row.depth + 1)))
            leading = (
                "  " * (row.depth + 1) + f"· [{display_escape_text(memory.label)}] "
            )
            wrapped_lines = _wrap_memory_preview(
                display_escape_text(memory.content),
                available_width=(
                    None
                    if wrap_width is None
                    else max(1, wrap_width - get_cwidth(leading))
                ),
            )
            prefixes.extend(" " * get_cwidth(leading) for _ in wrapped_lines)
    return tuple(prefixes)


def render_context_roots(
    tree: ContextTree,
    *,
    display_names: Mapping[str, str] | None = None,
) -> str:
    """Render a pinned, read-only root ribbon for namespace orientation."""
    return " Roots · " + " · ".join(
        display_escape_text((display_names or {}).get(name, name))
        for name in tree.roots
    )
