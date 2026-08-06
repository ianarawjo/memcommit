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
    ContextTreeState,
    build_context_tree,
)
from memcommit.commands.horizontal_choice import (
    HorizontalChoiceOption,
    HorizontalChoiceState,
    render_horizontal_choice,
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


def _shared_local_output_name(
    source_name: str,
    criteria_name: str,
    *,
    local_names: Sequence[str],
    occupied_names: AbstractSet[str],
) -> str:
    """Choose a fresh result under the deepest shared ordinary ancestor."""

    source_parts = source_name.split("/")
    criteria_parts = criteria_name.split("/")
    shared_parts: list[str] = []
    for source_part, criteria_part in zip(source_parts, criteria_parts):
        if source_part != criteria_part:
            break
        shared_parts.append(source_part)
    local = frozenset(local_names)
    output_base = next(
        (
            "/".join(shared_parts[:depth])
            for depth in range(len(shared_parts), 0, -1)
            if "/".join(shared_parts[:depth]) in local
        ),
        None,
    )
    output_stem = f"{output_base}/severed" if output_base else "severed"
    default_output = output_stem
    suffix = 2
    while default_output in occupied_names:
        default_output = f"{output_stem}-{suffix}"
        suffix += 1
    return default_output


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

    tree = build_context_tree(catalog, materialized_names=selectable)
    initial_name = current if current in selectable else local[0]
    tree_state: dict[_Role, ContextTreeState] = {
        role: ContextTreeState.create(tree, selected=initial_name)
        for role in ("SOURCE", "CRITERIA")
    }
    # Both roles begin at the local current Context for orientation. Sever
    # still refuses to continue until the person makes them distinct.
    selected: dict[_Role, str] = {
        "SOURCE": initial_name,
        "CRITERIA": initial_name,
    }
    scope_choice: dict[_Role, HorizontalChoiceState] = {
        role: HorizontalChoiceState(
            (
                HorizontalChoiceOption("EXACT", "THIS CONTEXT ONLY"),
                HorizontalChoiceOption("SUBTREE", "INCLUDE DESCENDANTS"),
            ),
            selected_uid="SUBTREE",
        )
        for role in ("SOURCE", "CRITERIA")
    }
    scope_focused: dict[_Role, bool] = {
        "SOURCE": False,
        "CRITERIA": False,
    }
    default_output = _shared_local_output_name(
        selected["SOURCE"],
        selected["CRITERIA"],
        local_names=local,
        occupied_names=frozenset(catalog),
    )
    suggested_output = {"value": default_output}

    error_message = {"value": ""}
    bindings = KeyBindings()

    def visible_rows(role: _Role):
        return tree_state[role].visible_rows()

    def selected_row_index(role: _Role) -> int:
        return tree_state[role].selected_row_index()

    def render_context(role: _Role) -> list[tuple[str, str]]:
        fragments: list[tuple[str, str]] = []
        rows = visible_rows(role)
        for index, row in enumerate(rows):
            focused = tree_state[role].selected_name == row.name
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
            return render_horizontal_choice(
                scope_choice[role],
                title="SCOPE",
                focused=scope_focused[role],
            )

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
            " MEM SEVER · SETUP · SOURCE UNCHANGED\n "
            f"SOURCE {display_escape_text(selected['SOURCE'])} "
            f"({'SUBTREE' if scope_choice['SOURCE'].selected_uid == 'SUBTREE' else 'THIS ONLY'}) × "
            f"CRITERIA {display_escape_text(selected['CRITERIA'])} "
            f"({'SUBTREE' if scope_choice['CRITERIA'].selected_uid == 'SUBTREE' else 'THIS ONLY'}) → "
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
        expansion_action = (
            "A restore tree" if tree_state[role].all_expanded else "A expand all"
        )
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
        if scope_focused[role]:
            if delta > 0:
                scope_focused[role] = False
            error_message["value"] = ""
            return
        if delta < 0 and selected_row_index(role) == 0:
            scope_focused[role] = True
            error_message["value"] = ""
            return
        tree_state[role].move(delta)
        error_message["value"] = ""

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
            scope_choice[role].move(1)
        else:
            tree_state[role].expand_selected()
        error_message["value"] = ""
        event.app.invalidate()

    @bindings.add("left", filter=tree_focus, eager=True)
    def _left(event) -> None:
        role = active_role()
        if scope_focused[role]:
            scope_choice[role].move(-1)
        else:
            tree_state[role].collapse_selected()
        error_message["value"] = ""
        event.app.invalidate()

    @bindings.add("a", filter=tree_focus, eager=True)
    @bindings.add("A", filter=tree_focus, eager=True)
    def _toggle_expand_all(event) -> None:
        role = active_role()
        tree_state[role].toggle_expand_all()
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
        name = tree_state[role].selected_name
        if name not in selectable:
            error_message["value"] = (
                "That row is query-only or a namespace and is unavailable to Sever."
            )
            return
        selected[role] = name
        refresh_suggested_output()
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
                source_descendants=(
                    scope_choice["SOURCE"].selected_uid == "SUBTREE"
                ),
                criteria_descendants=(
                    scope_choice["CRITERIA"].selected_uid == "SUBTREE"
                ),
            )
        )

    def refresh_suggested_output() -> None:
        """Follow Source/Criteria until the person edits the proposed name."""

        previous = suggested_output["value"]
        suggested = _shared_local_output_name(
            selected["SOURCE"],
            selected["CRITERIA"],
            local_names=local,
            occupied_names=frozenset(catalog),
        )
        suggested_output["value"] = suggested
        if output_editor.text == previous:
            output_editor.text = suggested
            output_editor.buffer.cursor_position = len(suggested)

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
