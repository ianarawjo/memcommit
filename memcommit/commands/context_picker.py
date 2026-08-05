"""Small terminal tree picker for selecting one Context by name."""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import AbstractSet, Mapping

from prompt_toolkit.application import Application
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, HSplit, Layout, Window
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.styles import Style

from memcommit.commands.tui_primitives import (
    display_escape_text,
    navigable_tree_row_prefix,
)


_CONTEXT_NAVIGATION_HINT = " ↑↓ move  ←→ expand  "


@dataclass(frozen=True)
class ContextTreeRow:
    """One currently visible catalog Context."""

    name: str
    depth: int
    has_children: bool
    expanded: bool
    materialized: bool


@dataclass(frozen=True)
class ContextMemoryRow:
    """One read-only direct Memory projection below a Context row."""

    label: str
    content: str


@dataclass(frozen=True)
class ContextTree:
    """Read-only tree derived only from the picker catalog snapshot."""

    roots: tuple[str, ...]
    children_by_name: dict[str, tuple[str, ...]]
    parent_by_name: dict[str, str | None]
    materialized_names: frozenset[str]

    @property
    def expandable_names(self) -> frozenset[str]:
        return frozenset(
            name for name, children in self.children_by_name.items() if children
        )


def build_context_tree(
    options: Sequence[str],
    *,
    materialized_names: AbstractSet[str] | None = None,
) -> ContextTree:
    """Arrange only catalog Contexts below their nearest real catalog parent."""
    materialized = frozenset(
        options if materialized_names is None else materialized_names
    )
    if not materialized.issubset(options):
        raise ValueError("Materialized Context names must be in the picker catalog.")
    ordered_names = tuple(dict.fromkeys(options))
    option_set = frozenset(ordered_names)
    parent_by_name: dict[str, str | None] = {}
    children: dict[str | None, list[str]] = {None: []}
    for name in ordered_names:
        segments = name.split("/")
        parent = next(
            (
                "/".join(segments[:length])
                for length in range(len(segments) - 1, 0, -1)
                if "/".join(segments[:length]) in option_set
            ),
            None,
        )
        parent_by_name[name] = parent
        children.setdefault(parent, []).append(name)
        children.setdefault(name, [])
    # A missing prefix is not a Context and therefore receives no synthetic
    # navigation row. Callers that need a grouping parent must persist an
    # ordinary zero-Memory Context and include it in the frozen catalog.
    return ContextTree(
        roots=tuple(children[None]),
        children_by_name={name: tuple(children[name]) for name in ordered_names},
        parent_by_name=parent_by_name,
        materialized_names=materialized,
    )


def context_ancestors(tree: ContextTree, name: str) -> set[str]:
    """Return lexical tree ancestors from parent to root."""
    ancestors: set[str] = set()
    parent = tree.parent_by_name.get(name)
    while parent is not None:
        ancestors.add(parent)
        parent = tree.parent_by_name[parent]
    return ancestors


def expandable_context_subtree(tree: ContextTree, name: str) -> set[str]:
    """Return every expandable branch at or below one selected tree node."""

    expandable: set[str] = set()
    pending = [name]
    while pending:
        candidate = pending.pop()
        children = tree.children_by_name[candidate]
        if not children:
            continue
        expandable.add(candidate)
        pending.extend(children)
    return expandable


def visible_context_rows(
    tree: ContextTree,
    expanded: AbstractSet[str],
) -> tuple[ContextTreeRow, ...]:
    """Project process-local expansion state into depth-first visible rows."""
    rows: list[ContextTreeRow] = []
    pending = [(name, 0) for name in reversed(tree.roots)]
    while pending:
        name, depth = pending.pop()
        children = tree.children_by_name[name]
        is_expanded = bool(children) and name in expanded
        rows.append(
            ContextTreeRow(
                name=name,
                depth=depth,
                has_children=bool(children),
                expanded=is_expanded,
                materialized=name in tree.materialized_names,
            )
        )
        if is_expanded:
            pending.extend((child, depth + 1) for child in reversed(children))
    return tuple(rows)


@dataclass
class ContextTreeState:
    """Embeddable process-local navigation over one frozen Context catalog.

    The state performs no terminal I/O and returns no semantic receipt. A
    standalone picker or a larger operation TUI may render it and decide what
    accepting the selected name means.
    """

    tree: ContextTree
    selected_name: str
    expanded: set[str] = field(default_factory=set)
    all_expanded: bool = False
    show_memories: bool = False
    memory_visibility_overrides: dict[str, bool] = field(default_factory=dict)
    _before_expand_all: set[str] = field(default_factory=set, repr=False)

    @classmethod
    def create(cls, tree: ContextTree, *, selected: str) -> "ContextTreeState":
        if selected not in tree.parent_by_name:
            raise ValueError("Selected Context is not in the picker catalog.")
        expanded = context_ancestors(tree, selected)
        return cls(
            tree=tree,
            selected_name=selected,
            expanded=expanded,
            _before_expand_all=set(expanded),
        )

    def visible_rows(self) -> tuple[ContextTreeRow, ...]:
        return visible_context_rows(self.tree, self.expanded)

    def selected_row_index(self) -> int:
        return next(
            index
            for index, row in enumerate(self.visible_rows())
            if row.name == self.selected_name
        )

    def move(self, delta: int) -> None:
        rows = self.visible_rows()
        index = self.selected_row_index()
        next_index = max(0, min(index + delta, len(rows) - 1))
        self.selected_name = rows[next_index].name

    def _enter_manual_expansion(self) -> None:
        if self.all_expanded:
            self.all_expanded = False
            self._before_expand_all = set(self.expanded)

    def _expandable_levels(self, root: str) -> dict[int, set[str]]:
        """Group expandable nodes by depth below one selected anchor."""

        levels: dict[int, set[str]] = {}
        pending = [(root, 0)]
        while pending:
            name, depth = pending.pop()
            children = self.tree.children_by_name[name]
            if not children:
                continue
            levels.setdefault(depth, set()).add(name)
            pending.extend((child, depth + 1) for child in children)
        return levels

    def expand_selected(self) -> None:
        """Reveal one more complete descendant depth below the cursor."""

        name = self.selected_name
        children = self.tree.children_by_name[name]
        levels = self._expandable_levels(name)
        collapsed_by_depth = {
            depth: names - self.expanded
            for depth, names in levels.items()
            if names - self.expanded
        }
        if collapsed_by_depth:
            self._enter_manual_expansion()
            self.expanded.update(
                collapsed_by_depth[min(collapsed_by_depth)]
            )
        elif children:
            self.selected_name = children[0]

    def collapse_selected(self) -> None:
        """Hide the deepest expanded descendant depth below the cursor."""

        name = self.selected_name
        expanded_by_depth = {
            depth: names & self.expanded
            for depth, names in self._expandable_levels(name).items()
            if names & self.expanded
        }
        if expanded_by_depth:
            self._enter_manual_expansion()
            self.expanded.difference_update(
                expanded_by_depth[max(expanded_by_depth)]
            )
            return
        parent = self.tree.parent_by_name[name]
        if parent is not None:
            self.selected_name = parent

    def toggle_expand_all(self) -> None:
        if self.all_expanded:
            restored = set(self._before_expand_all)
            # A row first reached while fully expanded must remain visible.
            restored.update(context_ancestors(self.tree, self.selected_name))
            self.expanded.clear()
            self.expanded.update(restored)
            self.all_expanded = False
            return
        self._before_expand_all = set(self.expanded)
        self.expanded.update(self.tree.expandable_names)
        self.all_expanded = True

    def toggle_memories(self) -> None:
        """Show or hide every Memory projection as one fresh global state."""

        self.show_memories = not self.show_memories
        self.memory_visibility_overrides.clear()

    def memories_visible_for(self, name: str) -> bool:
        """Return effective Memory visibility for one Context node."""

        return self.memory_visibility_overrides.get(name, self.show_memories)

    def toggle_selected_memories(self) -> None:
        """Toggle only the selected Context against the current global state."""

        name = self.selected_name
        self.memory_visibility_overrides[name] = not self.memories_visible_for(name)


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
) -> list[tuple[str, str]]:
    """Render visible tree rows and anchor prompt-toolkit at the selection."""
    fragments: list[tuple[str, str]] = []
    for index, row in enumerate(rows):
        is_selected = row.name == selected
        if is_selected:
            # A real cursor anchor lets Window own terminal-height-dependent
            # scrolling while expansion controls which tree rows exist.
            fragments.append(("[SetCursorPosition]", ""))
        is_current = row.name == current
        style = "class:selected" if is_selected else ""
        branch = "▾" if row.expanded else "▸" if row.has_children else "·"
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
        memory_is_visible = (
            row.name in visible_memory_contexts
            if visible_memory_contexts is not None
            else show_memories
        )
        if memory_is_visible and row.materialized:
            memories = (memories_by_context or {}).get(row.name, ())
            for memory in memories:
                fragments.append(("", "\n"))
                fragments.append(
                    (
                        "class:memory",
                        "  " * (row.depth + 1)
                        + f"· [{display_escape_text(memory.label)}] "
                        + display_escape_text(memory.content),
                    )
                )
        if index < len(rows) - 1:
            fragments.append(("", "\n"))
    return fragments


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
) -> str | None:
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

    catalog = (*options, *virtual)
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
            or tree.materialized_names
            != frozenset(options) | selectable_virtual
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
        )

    control = FormattedTextControl(
        text=render_options,
        focusable=True,
        show_cursor=False,
    )

    @bindings.add("down")
    def _next_context(event) -> None:
        state.move(1)
        event.app.invalidate()

    @bindings.add("up")
    def _previous_context(event) -> None:
        state.move(-1)
        event.app.invalidate()

    @bindings.add("right")
    def _expand_or_enter_context(event) -> None:
        state.expand_selected()
        load_visible_memories()
        event.app.invalidate()

    @bindings.add("left")
    def _collapse_or_leave_context(event) -> None:
        state.collapse_selected()
        event.app.invalidate()

    @bindings.add("a")
    @bindings.add("A")
    def _toggle_expand_all(event) -> None:
        state.toggle_expand_all()
        load_visible_memories()
        event.app.invalidate()

    @bindings.add("M")
    def _toggle_memories(event) -> None:
        if memory_loader is not None:
            state.toggle_memories()
            load_visible_memories()
        event.app.invalidate()

    @bindings.add("m")
    def _toggle_selected_memories(event) -> None:
        if memory_loader is not None:
            state.toggle_selected_memories()
            load_visible_memories()
        event.app.invalidate()

    @bindings.add("enter")
    def _accept_context(event) -> None:
        name = state.selected_name
        if browse_only:
            if name in state.expanded:
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
        wrap_lines=False,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )

    def render_footer() -> str:
        rows = state.visible_rows()
        expansion_action = "A restore tree" if state.all_expanded else "A expand all"
        name = state.selected_name
        if name in tree.materialized_names:
            enter_action = (
                "Enter open/collapse"
                if browse_only
                else f"Enter {display_escape_text(accept_label)}"
            )
        elif name in annotations:
            enter_action = "Enter unavailable"
        elif name in state.expanded:
            enter_action = "Enter collapse"
        else:
            enter_action = "Enter open"
        memory_action = ""
        if memory_loader is not None:
            local_action = (
                "m hide here"
                if state.memories_visible_for(state.selected_name)
                else "m show here"
            )
            global_action = (
                "M hide all" if state.show_memories else "M show all"
            )
            memory_action = f"{local_action}  {global_action}  "
        close_action = "q close" if browse_only else "q cancel"
        return (
            _CONTEXT_NAVIGATION_HINT
            + f"{expansion_action}  {memory_action}{enter_action}  {close_action}"
            f" · {state.selected_row_index() + 1}/{len(rows)}"
            f" · {len(tree.materialized_names)} selectable"
        )

    footer = Window(
        FormattedTextControl(render_footer),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    app: Application[str | None] = Application(
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
        style=Style.from_dict(
            {
                "selected": "reverse bold",
                "memory": "fg:#a6adc8",
            }
        ),
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
