"""Small terminal tree picker for selecting one Context by name."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import dataclass
from typing import AbstractSet, Mapping

from prompt_toolkit.application import Application
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, HSplit, Layout, Window
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.styles import Style

from memcommit.commands.tui_primitives import display_escape_text


_CONTEXT_NAVIGATION_HINT = " ↑↓ move  ←→ expand  "


@dataclass(frozen=True)
class _ContextTreeRow:
    """One currently visible Context or grouping namespace."""

    name: str
    depth: int
    has_children: bool
    expanded: bool
    materialized: bool


@dataclass(frozen=True)
class _ContextTree:
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


def _build_context_tree(
    options: Sequence[str],
    *,
    materialized_names: AbstractSet[str] | None = None,
) -> _ContextTree:
    """Arrange catalog names under lexical prefixes without inventing targets."""
    materialized = frozenset(
        options if materialized_names is None else materialized_names
    )
    if not materialized.issubset(options):
        raise ValueError("Materialized Context names must be in the picker catalog.")
    parent_by_name: dict[str, str | None] = {}
    children: dict[str | None, list[str]] = {None: []}
    ordered_names: list[str] = []
    for materialized_name in options:
        segments = materialized_name.split("/")
        for length in range(1, len(segments) + 1):
            name = "/".join(segments[:length])
            if name in parent_by_name:
                continue
            parent = "/".join(segments[: length - 1]) or None
            parent_by_name[name] = parent
            children.setdefault(parent, []).append(name)
            children.setdefault(name, [])
            ordered_names.append(name)
    # Missing prefixes are navigation-only rows. They keep legacy/orphaned
    # descendants collapsible but can never be returned as switch targets.
    return _ContextTree(
        roots=tuple(children[None]),
        children_by_name={name: tuple(children[name]) for name in ordered_names},
        parent_by_name=parent_by_name,
        materialized_names=materialized,
    )


def _context_ancestors(tree: _ContextTree, name: str) -> set[str]:
    """Return lexical tree ancestors from parent to root."""
    ancestors: set[str] = set()
    parent = tree.parent_by_name.get(name)
    while parent is not None:
        ancestors.add(parent)
        parent = tree.parent_by_name[parent]
    return ancestors


def _expandable_context_subtree(tree: _ContextTree, name: str) -> set[str]:
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


def _visible_context_rows(
    tree: _ContextTree,
    expanded: AbstractSet[str],
) -> tuple[_ContextTreeRow, ...]:
    """Project process-local expansion state into depth-first visible rows."""
    rows: list[_ContextTreeRow] = []
    pending = [(name, 0) for name in reversed(tree.roots)]
    while pending:
        name, depth = pending.pop()
        children = tree.children_by_name[name]
        is_expanded = bool(children) and name in expanded
        rows.append(
            _ContextTreeRow(
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


def _render_context_options(
    rows: Sequence[_ContextTreeRow],
    *,
    selected: str,
    current: str | None,
    annotations: Mapping[str, str] | None = None,
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
        pointer = "›" if is_selected else " "
        active = "*" if is_current else " "
        branch = "▾" if row.expanded else "▸" if row.has_children else "·"
        annotation = (annotations or {}).get(row.name)
        suffix = (
            "  " + annotation
            if annotation is not None
            else "  [namespace only]"
            if not row.materialized
            else ""
        )
        # Keep raw names in the tree for identity and return only an escaped
        # label to prompt-toolkit; selection never returns presentation text.
        fragments.append(
            (
                style,
                f"{pointer} {active} {'  ' * row.depth}{branch} "
                f"{display_escape_text(row.name)}{suffix}",
            )
        )
        if index < len(rows) - 1:
            fragments.append(("", "\n"))
    return fragments


def _render_context_roots(tree: _ContextTree) -> str:
    """Render a pinned, read-only root ribbon for namespace orientation."""
    return " Roots · " + " · ".join(display_escape_text(name) for name in tree.roots)


def choose_context(
    names: Sequence[str],
    *,
    current: str | None,
    virtual_names: Sequence[str] = (),
    selectable_virtual_names: AbstractSet[str] = frozenset(),
    virtual_annotations: Mapping[str, str] | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
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
    annotations = dict(virtual_annotations or {})
    selectable_virtual = frozenset(selectable_virtual_names)
    if not selectable_virtual <= set(virtual):
        raise ValueError("Selectable virtual Contexts are invalid.")
    if set(annotations) - set(virtual) or any(
        not isinstance(label, str) or not label for label in annotations.values()
    ):
        raise ValueError("Virtual Context annotations are invalid.")
    if require_tty and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        raise ValueError(
            "Interactive context selection requires a terminal. "
            "Pass a Context name explicitly."
        )

    catalog = (*options, *virtual)
    tree = _build_context_tree(
        catalog,
        materialized_names=frozenset(options) | selectable_virtual,
    )
    selected = {
        "name": current if current in catalog else options[0],
    }
    # Expansion is deliberately process-local. Opening the picker must never
    # turn a navigation preference into Context, Profile, or current-state data.
    expanded = _context_ancestors(tree, selected["name"])
    expansion_mode = {
        "all": False,
        "before_all": set(expanded),
    }
    bindings = KeyBindings()

    def visible_rows() -> tuple[_ContextTreeRow, ...]:
        return _visible_context_rows(tree, expanded)

    def selected_row_index() -> int:
        return next(
            index
            for index, row in enumerate(visible_rows())
            if row.name == selected["name"]
        )

    def render_options():
        return _render_context_options(
            visible_rows(),
            selected=selected["name"],
            current=current,
            annotations=annotations,
        )

    control = FormattedTextControl(
        text=render_options,
        focusable=True,
        show_cursor=False,
    )

    def move(delta: int) -> None:
        rows = visible_rows()
        index = selected_row_index()
        next_index = max(0, min(index + delta, len(rows) - 1))
        selected["name"] = rows[next_index].name

    def enter_manual_expansion_mode() -> None:
        if expansion_mode["all"]:
            expansion_mode["all"] = False
            expansion_mode["before_all"] = set(expanded)

    def expand_subtree(name: str) -> None:
        enter_manual_expansion_mode()
        expanded.update(_expandable_context_subtree(tree, name))

    def collapse_subtree(name: str) -> None:
        enter_manual_expansion_mode()
        expanded.difference_update(_expandable_context_subtree(tree, name))

    @bindings.add("down")
    def _next_context(event) -> None:
        move(1)
        event.app.invalidate()

    @bindings.add("up")
    def _previous_context(event) -> None:
        move(-1)
        event.app.invalidate()

    @bindings.add("right")
    def _expand_or_enter_context(event) -> None:
        name = selected["name"]
        children = tree.children_by_name[name]
        if children and name not in expanded:
            expand_subtree(name)
        elif children:
            selected["name"] = children[0]
        event.app.invalidate()

    @bindings.add("left")
    def _collapse_or_leave_context(event) -> None:
        name = selected["name"]
        if tree.children_by_name[name] and name in expanded:
            collapse_subtree(name)
        else:
            parent = tree.parent_by_name[name]
            if parent is not None:
                selected["name"] = parent
        event.app.invalidate()

    @bindings.add("a")
    @bindings.add("A")
    def _toggle_expand_all(event) -> None:
        if expansion_mode["all"]:
            restored = set(expansion_mode["before_all"])
            # The chosen row must remain visible when returning to the compact
            # tree, even if it was first reached in expand-all mode.
            restored.update(_context_ancestors(tree, selected["name"]))
            expanded.clear()
            expanded.update(restored)
            expansion_mode["all"] = False
        else:
            expansion_mode["before_all"] = set(expanded)
            expanded.update(tree.expandable_names)
            expansion_mode["all"] = True
        event.app.invalidate()

    @bindings.add("enter")
    def _accept_context(event) -> None:
        name = selected["name"]
        if name in tree.materialized_names:
            event.app.exit(result=name)
            return
        if name in expanded:
            collapse_subtree(name)
        else:
            expand_subtree(name)
        event.app.invalidate()

    @bindings.add("q", eager=True)
    @bindings.add("escape")
    @bindings.add("c-c", eager=True)
    def _cancel(event) -> None:
        event.app.exit(result=None)

    header = Window(
        FormattedTextControl(" Select a Context\n" + _render_context_roots(tree)),
        height=Dimension.exact(2),
        dont_extend_height=True,
    )
    options_window = Window(
        control,
        wrap_lines=False,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )

    def render_footer() -> str:
        rows = visible_rows()
        expansion_action = "A restore tree" if expansion_mode["all"] else "A expand all"
        name = selected["name"]
        if name in tree.materialized_names:
            enter_action = "Enter switch"
        elif name in annotations:
            enter_action = "Enter unavailable"
        elif name in expanded:
            enter_action = "Enter collapse"
        else:
            enter_action = "Enter open"
        return (
            _CONTEXT_NAVIGATION_HINT + f"{expansion_action}  {enter_action}  q cancel"
            f" · {selected_row_index() + 1}/{len(rows)}"
            f" · {len(options)} total"
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
            }
        ),
    )
    try:
        return app.run()
    except (EOFError, KeyboardInterrupt):
        return None
