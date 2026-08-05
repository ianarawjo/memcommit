"""Stacked interactive setup for one Source × Criteria Sever pass."""

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import AbstractSet, Literal

from prompt_toolkit.application import Application
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, HSplit, Layout, Window
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.widgets import Frame, TextArea

from memcommit.commands.context_picker import (
    _build_context_tree,
    _context_ancestors,
    _expandable_context_subtree,
    _visible_context_rows,
)
from memcommit.commands.tui_primitives import (
    MEMCOMMIT_TUI_STYLE,
    bind_focused_frame_style,
    display_escape_text,
)
from memcommit.store import validate_context_name


_Role = Literal["SOURCE", "CRITERIA"]


@dataclass(frozen=True)
class SeverSetupReceipt:
    """The names and recursive scopes selected in one process-local setup view."""

    source_name: str
    criteria_name: str
    output_name: str
    source_descendants: bool = True
    criteria_descendants: bool = True


def choose_sever_setup(
    local_names: Sequence[str],
    *,
    current: str | None,
    virtual_names: Sequence[str] = (),
    selectable_virtual_names: AbstractSet[str] = frozenset(),
    annotations: Mapping[str, str] | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> SeverSetupReceipt | None:
    """Select Source, one Criteria, and a fresh Output in one full-screen TUI."""

    local = tuple(local_names)
    virtual = tuple(virtual_names)
    catalog = (*local, *virtual)
    if not local:
        raise ValueError("No local Contexts are available for Sever.")
    if (
        any(not isinstance(name, str) or not name for name in catalog)
        or len(set(catalog)) != len(catalog)
    ):
        raise ValueError("Sever setup received invalid Context names.")
    selectable_virtual = frozenset(selectable_virtual_names)
    if not selectable_virtual <= set(virtual):
        raise ValueError("Sever setup received invalid virtual Context permissions.")
    selectable = frozenset(local) | selectable_virtual
    labels = dict(annotations or {})
    if set(labels) - set(catalog) or any(
        not isinstance(label, str) or not label for label in labels.values()
    ):
        raise ValueError("Sever setup received invalid Context annotations.")
    if require_tty and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        raise ValueError(
            "Interactive Sever setup requires a TTY. Pass --source, --criteria, "
            "and --save-as outside a terminal."
        )

    tree = _build_context_tree(catalog, materialized_names=selectable)
    initial_name = current if current in selectable else local[0]
    cursor: dict[_Role, str] = {
        "SOURCE": initial_name,
        "CRITERIA": initial_name,
    }
    # Both roles begin at the local current Context for orientation. Sever
    # still refuses to continue until the person makes them distinct.
    selected: dict[_Role, str] = {
        "SOURCE": initial_name,
        "CRITERIA": initial_name,
    }
    expanded: dict[_Role, set[str]] = {
        role: _context_ancestors(tree, initial_name)
        for role in ("SOURCE", "CRITERIA")
    }
    expand_all: dict[_Role, bool] = {"SOURCE": False, "CRITERIA": False}
    include_descendants: dict[_Role, bool] = {
        "SOURCE": True,
        "CRITERIA": True,
    }
    scope_focused: dict[_Role, bool] = {
        "SOURCE": False,
        "CRITERIA": False,
    }
    before_expand_all: dict[_Role, set[str]] = {
        role: set(expanded[role]) for role in ("SOURCE", "CRITERIA")
    }
    output_base = current if current in local else local[0]
    output_stem = f"{output_base}/severed"
    default_output = output_stem
    suffix = 2
    while default_output in catalog:
        default_output = f"{output_stem}-{suffix}"
        suffix += 1

    error_message = {"value": ""}
    bindings = KeyBindings()

    def visible_rows(role: _Role):
        return _visible_context_rows(tree, expanded[role])

    def selected_row_index(role: _Role) -> int:
        return next(
            index
            for index, row in enumerate(visible_rows(role))
            if row.name == cursor[role]
        )

    def render_context(role: _Role) -> list[tuple[str, str]]:
        fragments: list[tuple[str, str]] = []
        rows = visible_rows(role)
        for index, row in enumerate(rows):
            focused = cursor[role] == row.name
            if focused:
                fragments.append(("[SetCursorPosition]", ""))
            available = row.name in selectable
            chosen = selected[role] == row.name
            pointer = "›" if focused else " "
            marker = "✓" if chosen else "·" if available else "×"
            active = "*" if row.name == current else " "
            branch = "▾" if row.expanded else "▸" if row.has_children else "·"
            annotation = labels.get(row.name, "")
            if not available:
                annotation = (annotation + " · " if annotation else "") + (
                    "UNAVAILABLE"
                )
            suffix_text = (
                f"  {display_escape_text(annotation)}" if annotation else ""
            )
            style = "class:memcommit.table.selected" if focused else ""
            fragments.append(
                (
                    style,
                    f"{pointer} {marker} {active} {'  ' * row.depth}{branch} "
                    f"{display_escape_text(row.name)}{suffix_text}",
                )
            )
            if index < len(rows) - 1:
                fragments.append(("", "\n"))
        return fragments

    source_control = FormattedTextControl(
        lambda: render_context("SOURCE"), focusable=True, show_cursor=False
    )
    criteria_control = FormattedTextControl(
        lambda: render_context("CRITERIA"), focusable=True, show_cursor=False
    )

    def context_frame(role: _Role, control: FormattedTextControl) -> Frame:
        def render_scope() -> list[tuple[str, str]]:
            style = (
                "class:memcommit.table.selected" if scope_focused[role] else ""
            )
            pointer = "›" if scope_focused[role] else " "
            text = (
                "( ) THIS CONTEXT ONLY · (●) INCLUDE DESCENDANTS"
                if include_descendants[role]
                else "(●) THIS CONTEXT ONLY · ( ) INCLUDE DESCENDANTS"
            )
            return [(style, f"{pointer} SCOPE · {text} · ←/→ SELECT")]

        scope = Window(
            FormattedTextControl(render_scope),
            height=Dimension.exact(1),
            dont_extend_height=True,
        )
        options = Window(
            control,
            wrap_lines=False,
            right_margins=[ScrollbarMargin(display_arrows=True)],
        )
        title = (
            "SOURCE · ORDINARY CONTEXT"
            if role == "SOURCE"
            else "CRITERIA · ONE ORDINARY CONTEXT ROOT"
        )
        return Frame(
            HSplit([scope, Window(height=1, char="─"), options]),
            title=title,
            height=Dimension(min=4, weight=1),
        )

    source_frame = context_frame("SOURCE", source_control)
    criteria_frame = context_frame("CRITERIA", criteria_control)
    output_editor = TextArea(
        text=default_output,
        multiline=False,
        prompt="› ",
        focusable=True,
        wrap_lines=False,
        height=Dimension.exact(1),
        name="sever-output-name",
    )
    output_editor.buffer.cursor_position = len(default_output)
    output_frame = Frame(
        output_editor,
        title="OUTPUT CONTEXT NAME · EDIT DIRECTLY · NOT CREATED",
        height=Dimension.exact(3),
    )

    bind_focused_frame_style(
        source_frame,
        is_focused=lambda: app.layout.has_focus(source_control),
    )
    bind_focused_frame_style(
        criteria_frame,
        is_focused=lambda: app.layout.has_focus(criteria_control),
    )
    bind_focused_frame_style(
        output_frame,
        is_focused=lambda: app.layout.has_focus(output_editor),
    )

    def render_header() -> str:
        return (
            " MEM SEVER · SETUP · NOT SENT\n "
            f"SOURCE {display_escape_text(selected['SOURCE'])} "
            f"({'SUBTREE' if include_descendants['SOURCE'] else 'THIS ONLY'}) × "
            f"CRITERIA {display_escape_text(selected['CRITERIA'])} "
            f"({'SUBTREE' if include_descendants['CRITERIA'] else 'THIS ONLY'}) → "
            f"OUTPUT {display_escape_text(output_editor.text.strip())}"
        )

    tree_focus = Condition(
        lambda: app.layout.has_focus(source_control)
        or app.layout.has_focus(criteria_control)
    )

    def render_footer() -> str:
        if error_message["value"]:
            return f" {display_escape_text(error_message['value'])}"
        if app.layout.has_focus(output_editor):
            return (
                " OUTPUT: edit directly · Enter continue · Tab/Shift-Tab pane · "
                "Ctrl-C cancel"
            )
        role = "SOURCE" if app.layout.has_focus(source_control) else "CRITERIA"
        if scope_focused[role]:
            return (
                f" {role} SCOPE: ← this Context only · → include descendants · "
                "↓ Context list · Tab/Shift-Tab pane · F continue · Q cancel"
            )
        expansion_action = "A restore tree" if expand_all[role] else "A expand all"
        return (
            f" {role}: ↑/↓ move · ←/→ collapse/expand · Enter/Space choose · "
            f"top ↑ enters scope · {expansion_action} · Tab/Shift-Tab pane · "
            "F continue · Q cancel"
        )

    header = Window(
        FormattedTextControl(render_header),
        height=Dimension.exact(2),
        dont_extend_height=True,
    )
    footer = Window(
        FormattedTextControl(render_footer),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    root = HSplit(
        [
            header,
            Window(height=1, char="─"),
            source_frame,
            criteria_frame,
            output_frame,
            footer,
        ]
    )
    app: Application[SeverSetupReceipt | None] = Application(
        layout=Layout(root, focused_element=source_control),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        style=MEMCOMMIT_TUI_STYLE,
    )
    controls = (source_control, criteria_control, output_editor)

    def active_role() -> _Role:
        return "SOURCE" if app.layout.has_focus(source_control) else "CRITERIA"

    def move(delta: int) -> None:
        role = active_role()
        rows = visible_rows(role)
        index = selected_row_index(role)
        if scope_focused[role]:
            if delta > 0:
                scope_focused[role] = False
            error_message["value"] = ""
            return
        if delta < 0 and index == 0:
            scope_focused[role] = True
            error_message["value"] = ""
            return
        cursor[role] = rows[max(0, min(index + delta, len(rows) - 1))].name
        error_message["value"] = ""

    def enter_manual_expansion(role: _Role) -> None:
        if expand_all[role]:
            expand_all[role] = False
            before_expand_all[role] = set(expanded[role])

    def expand_right(role: _Role) -> None:
        name = cursor[role]
        children = tree.children_by_name[name]
        if children and name not in expanded[role]:
            enter_manual_expansion(role)
            expanded[role].update(_expandable_context_subtree(tree, name))
        elif children:
            cursor[role] = children[0]

    def collapse_left(role: _Role) -> None:
        name = cursor[role]
        if tree.children_by_name[name] and name in expanded[role]:
            enter_manual_expansion(role)
            expanded[role].difference_update(
                _expandable_context_subtree(tree, name)
            )
        else:
            parent = tree.parent_by_name[name]
            if parent is not None:
                cursor[role] = parent

    @bindings.add("down", filter=tree_focus, eager=True)
    def _down(event) -> None:
        move(1)
        event.app.invalidate()

    @bindings.add("up", filter=tree_focus, eager=True)
    def _up(event) -> None:
        move(-1)
        event.app.invalidate()

    @bindings.add("right", filter=tree_focus, eager=True)
    def _right(event) -> None:
        role = active_role()
        if scope_focused[role]:
            include_descendants[role] = True
        else:
            expand_right(role)
        error_message["value"] = ""
        event.app.invalidate()

    @bindings.add("left", filter=tree_focus, eager=True)
    def _left(event) -> None:
        role = active_role()
        if scope_focused[role]:
            include_descendants[role] = False
        else:
            collapse_left(role)
        error_message["value"] = ""
        event.app.invalidate()

    @bindings.add("a", filter=tree_focus, eager=True)
    @bindings.add("A", filter=tree_focus, eager=True)
    def _toggle_expand_all(event) -> None:
        role = active_role()
        if expand_all[role]:
            restored = set(before_expand_all[role])
            restored.update(_context_ancestors(tree, cursor[role]))
            expanded[role] = restored
            expand_all[role] = False
        else:
            before_expand_all[role] = set(expanded[role])
            expanded[role].update(tree.expandable_names)
            expand_all[role] = True
        event.app.invalidate()

    @bindings.add("tab")
    def _next_pane(event) -> None:
        index = next(
            index
            for index, control in enumerate(controls)
            if app.layout.has_focus(control)
        )
        app.layout.focus(controls[(index + 1) % len(controls)])
        error_message["value"] = ""
        event.app.invalidate()

    @bindings.add("s-tab")
    def _previous_pane(event) -> None:
        index = next(
            index
            for index, control in enumerate(controls)
            if app.layout.has_focus(control)
        )
        app.layout.focus(controls[(index - 1) % len(controls)])
        error_message["value"] = ""
        event.app.invalidate()

    def choose_active() -> None:
        role = active_role()
        if scope_focused[role]:
            error_message["value"] = (
                "Use Left/Right to choose this Context only or include descendants."
            )
            return
        name = cursor[role]
        if name not in selectable:
            error_message["value"] = (
                "That row is query-only or a namespace and is unavailable to Sever."
            )
            return
        selected[role] = name
        error_message["value"] = ""
        if role == "SOURCE":
            app.layout.focus(criteria_control)
        else:
            output_editor.buffer.cursor_position = len(output_editor.text)
            app.layout.focus(output_editor)

    @bindings.add("enter", filter=tree_focus, eager=True)
    @bindings.add(" ", filter=tree_focus, eager=True)
    def _choose(event) -> None:
        choose_active()
        event.app.invalidate()

    def finish(event) -> None:
        if selected["SOURCE"] == selected["CRITERIA"]:
            error_message["value"] = "Source and Criteria must be distinct."
            app.layout.focus(criteria_control)
            event.app.invalidate()
            return
        candidate = output_editor.text.strip()
        try:
            validate_context_name(candidate)
            if candidate in catalog:
                raise ValueError("Output must be a new Context name.")
        except ValueError as error:
            error_message["value"] = str(error)
            app.layout.focus(output_editor)
            event.app.invalidate()
            return
        event.app.exit(
            result=SeverSetupReceipt(
                source_name=selected["SOURCE"],
                criteria_name=selected["CRITERIA"],
                output_name=candidate,
                source_descendants=include_descendants["SOURCE"],
                criteria_descendants=include_descendants["CRITERIA"],
            )
        )

    @bindings.add("f", filter=tree_focus, eager=True)
    @bindings.add("F", filter=tree_focus, eager=True)
    def _finish_from_tree(event) -> None:
        finish(event)

    @bindings.add("enter", filter=has_focus(output_editor), eager=True)
    def _finish_from_output(event) -> None:
        finish(event)

    @bindings.add("q", filter=tree_focus, eager=True)
    @bindings.add("escape", eager=True)
    @bindings.add("c-c", eager=True)
    def _cancel(event) -> None:
        event.app.exit(result=None)

    try:
        return app.run()
    except (EOFError, KeyboardInterrupt):
        return None
