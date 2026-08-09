"""Small terminal tree picker for selecting one Context by name."""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import AbstractSet, Literal, Mapping

from prompt_toolkit.application import Application, get_app
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, HSplit, Layout, Window
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.output import Output
from prompt_toolkit.styles import Style, merge_styles
from prompt_toolkit.utils import get_cwidth

from memcommit.commands.tui_primitives import (
    NavigationAccelerator,
    SEMANTIC_VIEWER_STYLE,
    WrappedScrollbarMargin,
    display_escape_text,
    navigable_tree_row_prefix,
)
from memcommit.context_targeting.tui.tree import (
    ContextTree,
    ContextTreeRow,
    ContextTreeState,
    build_context_tree,
    context_ancestors,
    expandable_context_subtree,
    visible_context_rows,
)


_CONTEXT_NAVIGATION_HINT = " ↑↓ move  ←→ expand  "
_CONTEXT_PICKER_STYLE = merge_styles(
    [
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


@dataclass(frozen=True)
class ContextMemoryRow:
    """One read-only projection below a Context row."""

    label: str
    content: str
    style: Literal["memory-object", "report-neutral"] = "memory-object"
    selector: str | None = None


@dataclass(frozen=True)
class ContextMemorySelection:
    """Exact selectable direct-item receipt returned by an operation picker."""

    context_name: str
    selector: str


@dataclass(frozen=True)
class ContextPickerNavigationUnit:
    """One viewport stop; only Context units are semantically selectable."""

    kind: Literal["CONTEXT", "MEMORY"]
    context_name: str
    memory_index: int | None = None


@dataclass(frozen=True)
class ContextSubtreeSelection:
    """Explicit alternate receipt for a selected Context's descendants."""

    name: str


def render_context_options(
    rows: Sequence[ContextTreeRow],
    *,
    selected: str,
    current: str | None,
    annotations: Mapping[str, str] | None = None,
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
        display_name = (display_names or {}).get(row.name, row.name)
        suffix = (
            "  " + annotation
            if annotation is not None
            else "  [unavailable]"
            if not row.materialized
            else ""
        )
        # Keep raw names in the tree for identity and return only an escaped
        # label to prompt-toolkit; selection never returns presentation text.
        fragments.append(
            (
                style,
                navigable_tree_row_prefix(
                    selected=is_selected,
                    current=is_current,
                    depth=row.depth,
                    branch=branch,
                )
                + f"{display_escape_text(display_name)}{suffix}",
            )
        )
        if memory_is_visible and row.materialized:
            memories = (memories_by_context or {}).get(row.name, ())
            for memory_index, memory in enumerate(memories):
                fragments.append(("", "\n"))
                memory_is_focused = memory_anchor == (row.name, memory_index)
                if memory_is_focused:
                    # Memory previews can anchor viewport motion without
                    # becoming selectable Context-tree rows.
                    fragments.append(("[SetCursorPosition]", ""))
                memory_style = (
                    "class:focused" if memory_is_focused else f"class:{memory.style}"
                )
                memory_pointer = (
                    "›" if selectable_memories and memory_is_focused else "·"
                )
                leading = (
                    "  " * (row.depth + 1)
                    + f"{memory_pointer} [{display_escape_text(memory.label)}] "
                )
                content_lines = _wrap_memory_preview(
                    display_escape_text(memory.content),
                    available_width=(
                        None
                        if wrap_width is None
                        else max(1, wrap_width - get_cwidth(leading))
                    ),
                )
                fragments.append(
                    (
                        memory_style,
                        leading + content_lines[0],
                    )
                )
                for continuation in content_lines[1:]:
                    fragments.append(("", "\n"))
                    fragments.append(
                        (
                            memory_style,
                            " " * get_cwidth(leading) + continuation,
                        )
                    )
        if index < len(rows) - 1:
            fragments.append(("", "\n"))
    return fragments


def context_picker_navigation_units(
    rows: Sequence[ContextTreeRow],
    *,
    memories_by_context: Mapping[str, Sequence[ContextMemoryRow]] | None = None,
    show_memories: bool = False,
    visible_memory_contexts: AbstractSet[str] | None = None,
) -> tuple[ContextPickerNavigationUnit, ...]:
    """Interleave Context selection rows with read-only Memory viewport stops."""

    units: list[ContextPickerNavigationUnit] = []
    for row in rows:
        units.append(ContextPickerNavigationUnit("CONTEXT", row.name))
        memory_is_visible = (
            row.name in visible_memory_contexts
            if visible_memory_contexts is not None
            else show_memories
        )
        if not memory_is_visible or not row.materialized:
            continue
        units.extend(
            ContextPickerNavigationUnit("MEMORY", row.name, memory_index)
            for memory_index, _memory in enumerate(
                (memories_by_context or {}).get(row.name, ())
            )
        )
    return tuple(units)


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


def choose_context(
    names: Sequence[str],
    *,
    current: str | None,
    local_annotations: Mapping[str, str] | None = None,
    virtual_names: Sequence[str] = (),
    selectable_virtual_names: AbstractSet[str] = frozenset(),
    virtual_annotations: Mapping[str, str] | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
    title: str = "Select a Context",
    accept_label: str = "select",
    memory_loader: Callable[[str], Sequence[ContextMemoryRow]] | None = None,
    browse_only: bool = False,
    initially_expand_selected: bool = False,
    initially_expand_all: bool = False,
    initially_show_memories: bool = False,
    tree_override: ContextTree | None = None,
    display_names: Mapping[str, str] | None = None,
    descendant_scope_names: AbstractSet[str] = frozenset(),
    selectable_memories: bool = False,
) -> str | ContextSubtreeSelection | ContextMemorySelection | None:
    """Return the selected Context name, or ``None`` when cancelled."""
    options = tuple(names)
    virtual = tuple(virtual_names)
    if not options:
        raise ValueError("No contexts are available to select.")
    if any(not isinstance(name, str) or not name for name in options) or len(
        set(options)
    ) != len(options):
        raise ValueError("Context selection received invalid names.")
    if (
        any(not isinstance(name, str) or not name for name in virtual)
        or len(set(virtual)) != len(virtual)
        or set(options).intersection(virtual)
    ):
        raise ValueError("Virtual Context selection received invalid names.")
    local_labels = dict(local_annotations or {})
    annotations = {**local_labels, **dict(virtual_annotations or {})}
    selectable_virtual = frozenset(selectable_virtual_names)
    if not selectable_virtual <= set(virtual):
        raise ValueError("Selectable virtual Contexts are invalid.")
    if set(local_labels) - set(options):
        raise ValueError("Local Context annotations are invalid.")
    if set(virtual_annotations or {}) - set(virtual) or any(
        not isinstance(label, str) or not label for label in annotations.values()
    ):
        raise ValueError("Virtual Context annotations are invalid.")
    if require_tty and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        raise ValueError(
            "Interactive context selection requires a terminal. "
            "Pass a Context name explicitly."
        )
    if selectable_memories and memory_loader is None:
        raise ValueError("Selectable Memories require a Memory loader.")

    catalog = (*options, *virtual)
    subtree_names = frozenset(descendant_scope_names)
    if not subtree_names <= set(catalog):
        raise ValueError("Descendant-scope Contexts are outside the catalog.")
    labels = dict(display_names or {})
    if set(labels) - set(catalog) or any(
        not isinstance(label, str) or not label for label in labels.values()
    ):
        raise ValueError("Context display names are invalid.")
    if (
        not isinstance(title, str)
        or not title.strip()
        or any(character in title for character in "\r\n")
        or not isinstance(accept_label, str)
        or not accept_label.strip()
        or any(character in accept_label for character in "\r\n")
    ):
        raise ValueError("Context selection labels must be nonempty single lines.")

    if tree_override is None:
        tree = build_context_tree(
            catalog,
            materialized_names=frozenset(options) | selectable_virtual,
        )
    else:
        tree = tree_override
        if (
            set(tree.parent_by_name) != set(catalog)
            or tree.materialized_names != frozenset(options) | selectable_virtual
        ):
            raise ValueError("Context tree override does not match its catalog.")
    state = ContextTreeState.create(
        tree,
        selected=current if current in catalog else options[0],
    )
    if initially_expand_selected and state.selected_name in tree.expandable_names:
        state.expanded.add(state.selected_name)
    if initially_expand_all:
        state.expanded.update(tree.expandable_names)
        state.all_expanded = True
        state._before_expand_all = set()
    state.show_memories = initially_show_memories and memory_loader is not None
    memory_cache: dict[str, tuple[ContextMemoryRow, ...]] = {}
    memory_anchor: tuple[str, int] | None = None
    navigation_accelerator = NavigationAccelerator()

    def load_visible_memories() -> None:
        if memory_loader is None:
            return
        for row in state.visible_rows():
            if (
                not row.materialized
                or not state.memories_visible_for(row.name)
                or row.name in memory_cache
            ):
                continue
            try:
                memory_cache[row.name] = tuple(memory_loader(row.name))
            except (OSError, RuntimeError, ValueError):
                # Navigation is a read-only aid. A concurrent disappearance
                # must not turn it into an authority or persistence boundary.
                memory_cache[row.name] = (
                    ContextMemoryRow("unavailable", "Memory preview changed"),
                )

    load_visible_memories()
    # Expansion is deliberately process-local. Opening the picker must never
    # turn a navigation preference into Context, Profile, or current-state data.
    bindings = KeyBindings()

    def render_options():
        wrap_width = max(1, get_app().output.get_size().columns - 1)
        return render_context_options(
            state.visible_rows(),
            selected=state.selected_name,
            current=current,
            annotations=annotations,
            memories_by_context=memory_cache,
            visible_memory_contexts=frozenset(
                row.name
                for row in state.visible_rows()
                if state.memories_visible_for(row.name)
            ),
            display_names=labels,
            wrap_width=wrap_width,
            memory_anchor=memory_anchor,
            selectable_memories=selectable_memories,
        )

    def navigation_units() -> tuple[ContextPickerNavigationUnit, ...]:
        return context_picker_navigation_units(
            state.visible_rows(),
            memories_by_context=memory_cache,
            visible_memory_contexts=frozenset(
                row.name
                for row in state.visible_rows()
                if state.memories_visible_for(row.name)
            ),
        )

    def current_navigation_unit() -> ContextPickerNavigationUnit:
        units = navigation_units()
        if memory_anchor is not None:
            candidate = ContextPickerNavigationUnit(
                "MEMORY",
                memory_anchor[0],
                memory_anchor[1],
            )
            if candidate in units:
                return candidate
        return ContextPickerNavigationUnit("CONTEXT", state.selected_name)

    def move_navigation_unit(direction: int) -> None:
        nonlocal memory_anchor
        units = navigation_units()
        current = current_navigation_unit()
        index = units.index(current)
        target = units[max(0, min(index + direction, len(units) - 1))]
        state.selected_name = target.context_name
        memory_anchor = (
            (target.context_name, target.memory_index)
            if target.kind == "MEMORY" and target.memory_index is not None
            else None
        )

    def continuation_prefix(line_number: int, wrap_count: int):
        if wrap_count == 0:
            return ""
        wrap_width = max(1, get_app().output.get_size().columns - 1)
        prefixes = context_option_continuation_prefixes(
            state.visible_rows(),
            memories_by_context=memory_cache,
            visible_memory_contexts=frozenset(
                row.name
                for row in state.visible_rows()
                if state.memories_visible_for(row.name)
            ),
            wrap_width=wrap_width,
        )
        return prefixes[line_number] if line_number < len(prefixes) else ""

    control = FormattedTextControl(
        text=render_options,
        focusable=True,
        show_cursor=False,
    )

    @bindings.add("down")
    def _next_context(event) -> None:
        navigation_accelerator.move(
            1,
            app=event.app,
            move_one=move_navigation_unit,
        )

    @bindings.add("up")
    def _previous_context(event) -> None:
        navigation_accelerator.move(
            -1,
            app=event.app,
            move_one=move_navigation_unit,
        )

    @bindings.add("right")
    def _expand_or_enter_context(event) -> None:
        nonlocal memory_anchor
        navigation_accelerator.reset()
        if memory_anchor is not None:
            return
        state.expand_selected(include_leaf_memories=memory_loader is not None)
        load_visible_memories()
        event.app.invalidate()

    @bindings.add("left")
    def _collapse_or_leave_context(event) -> None:
        nonlocal memory_anchor
        navigation_accelerator.reset()
        if memory_anchor is not None:
            memory_anchor = None
            event.app.invalidate()
            return
        state.collapse_selected(include_leaf_memories=memory_loader is not None)
        event.app.invalidate()

    @bindings.add("a")
    @bindings.add("A")
    def _toggle_expand_all(event) -> None:
        nonlocal memory_anchor
        navigation_accelerator.reset()
        memory_anchor = None
        state.toggle_expand_all()
        load_visible_memories()
        event.app.invalidate()

    @bindings.add("M")
    def _toggle_memories(event) -> None:
        nonlocal memory_anchor
        navigation_accelerator.reset()
        if memory_loader is not None:
            state.toggle_memories()
            load_visible_memories()
            if not state.memories_visible_for(state.selected_name):
                memory_anchor = None
        event.app.invalidate()

    @bindings.add("m")
    def _toggle_selected_memories(event) -> None:
        nonlocal memory_anchor
        navigation_accelerator.reset()
        if memory_loader is not None:
            state.toggle_selected_memories()
            load_visible_memories()
            if not state.memories_visible_for(state.selected_name):
                memory_anchor = None
        event.app.invalidate()

    @bindings.add("enter")
    def _accept_context(event) -> None:
        navigation_accelerator.reset()
        if memory_anchor is not None:
            if selectable_memories:
                context_name, memory_index = memory_anchor
                memory = memory_cache[context_name][memory_index]
                if memory.selector is not None:
                    event.app.exit(
                        result=ContextMemorySelection(
                            context_name=context_name,
                            selector=memory.selector,
                        )
                    )
                    return
            # By default a Memory remains a viewport stop only. Enter never
            # changes selection or turns its parent into an implicit receipt.
            event.app.invalidate()
            return
        name = state.selected_name
        if name in subtree_names and name not in tree.materialized_names:
            # A catalog-only parent has no exact history of its own. Enter can
            # therefore open the frozen changed descendants without competing
            # with an exact-Context action; arrows retain tree expansion.
            event.app.exit(result=ContextSubtreeSelection(name))
            return
        if browse_only:
            if not tree.children_by_name[name] and memory_loader is not None:
                state.toggle_selected_memories()
                load_visible_memories()
            elif name in state.expanded:
                state.collapse_selected()
            else:
                state.expand_selected()
                load_visible_memories()
            event.app.invalidate()
            return
        if name in tree.materialized_names:
            event.app.exit(result=name)
            return
        if name in state.expanded:
            state.collapse_selected()
        else:
            state.expand_selected()
        event.app.invalidate()

    @bindings.add("q", eager=True)
    @bindings.add("escape")
    @bindings.add("c-c", eager=True)
    def _cancel(event) -> None:
        event.app.exit(result=None)

    header = Window(
        FormattedTextControl(
            f" {display_escape_text(title)}\n"
            + render_context_roots(tree, display_names=labels)
        ),
        height=Dimension.exact(2),
        dont_extend_height=True,
    )
    options_window = Window(
        control,
        wrap_lines=True,
        get_line_prefix=continuation_prefix,
        right_margins=[WrappedScrollbarMargin(display_arrows=True)],
    )

    def render_footer() -> str:
        units = navigation_units()
        navigation_index = units.index(current_navigation_unit())
        expansion_action = "A restore tree" if state.all_expanded else "A expand all"
        name = state.selected_name
        if memory_anchor is not None:
            memory = memory_cache[memory_anchor[0]][memory_anchor[1]]
            enter_action = (
                f"Enter {display_escape_text(accept_label)}"
                if selectable_memories and memory.selector is not None
                else "Enter preview only"
            )
        elif name in tree.materialized_names:
            enter_action = (
                "Enter open/collapse"
                if browse_only
                else f"Enter {display_escape_text(accept_label)}"
            )
        elif name in subtree_names:
            enter_action = "Enter open changed descendants"
        elif name in annotations:
            enter_action = "Enter unavailable"
        elif name in state.expanded:
            enter_action = "Enter collapse"
        else:
            enter_action = "Enter open"
        memory_action = ""
        if memory_loader is not None:
            local_action = (
                "m hide Memories here"
                if state.memories_visible_for(state.selected_name)
                else "m show Memories here"
            )
            global_action = (
                "M hide all Memories" if state.show_memories else "M show all Memories"
            )
            memory_action = f"{local_action}  {global_action}  "
        close_action = "q close" if browse_only else "q cancel"
        return (
            _CONTEXT_NAVIGATION_HINT
            + f"{expansion_action}  {memory_action}{enter_action}  {close_action}"
            f" · {navigation_index + 1}/{len(units)}"
            f" · {len(tree.materialized_names)} selectable"
        )

    footer = Window(
        FormattedTextControl(render_footer),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    app: Application[str | ContextSubtreeSelection | ContextMemorySelection | None] = (
        Application(
            layout=Layout(
                HSplit(
                    [
                        header,
                        Window(height=1, char="─"),
                        options_window,
                        Window(height=1, char="─"),
                        footer,
                    ]
                ),
                focused_element=control,
            ),
            key_bindings=bindings,
            full_screen=True,
            erase_when_done=True,
            input=app_input,
            output=app_output,
            style=_CONTEXT_PICKER_STYLE,
        )
    )
    try:
        return app.run()
    except (EOFError, KeyboardInterrupt):
        return None


# Compatibility aliases preserve the existing focused unit-test and prototype
# imports while new embedders use the public component names above.
_ContextTreeRow = ContextTreeRow
_ContextTree = ContextTree
_build_context_tree = build_context_tree
_context_ancestors = context_ancestors
_expandable_context_subtree = expandable_context_subtree
_visible_context_rows = visible_context_rows
_render_context_options = render_context_options
_render_context_roots = render_context_roots
