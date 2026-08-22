"""Stacked interactive setup for one Source × Criteria Sever pass."""

from __future__ import annotations

import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import AbstractSet, Literal

from prompt_toolkit.application import Application, get_app
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, HSplit, Layout, Window
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles
from prompt_toolkit.widgets import Frame

from memcommit.context_targeting.tui.reach import (
    ContextReachState,
    render_context_reach,
)
from memcommit.context_naming import validate_portable_context_name
from memcommit.context_targeting.tui.range_selection import (
    project_checked_context_names,
)
from memcommit.context_targeting.tui.rendering import (
    ContextTreeRowDecoration,
    render_context_tree_rows,
)
from memcommit.context_targeting.tui.selection import ContextSelectionState
from memcommit.context_targeting.tui.tree import ContextTreeState, build_context_tree
from memcommit.selection.tui import tree_choice_marker, tree_choice_styles
from memcommit.context_targeting.tui.picker import (
    CONTEXT_PICKER_STYLE,
    ContextMemoryPreviewController,
    ContextMemoryRow,
    memory_visibility_key_hint,
)
from memcommit.source_projection.model import SourceDisplayFacts, SourceState
from memcommit.source_projection.presentation import (
    SourceDisplayValue,
    combine_source_display_tokens,
    normalize_source_display_tokens,
)
from memcommit.commands.tui_primitives import (
    ExactNameFieldControl,
    ExactNameFieldView,
)
from memcommit.interfaces.tui.core.theme import (
    MEMCOMMIT_TUI_STYLE,
)
from memcommit.interfaces.tui.core.keybindings import (
    bind_case_insensitive_key,
)
from memcommit.interfaces.tui.components.frame import (
    bind_focused_frame_style,
)
from memcommit.interfaces.tui.components.exact_command_review.rendering import (
    format_exact_command,
)
from memcommit.interactive_command_review import sever_start_command_review
from memcommit.interfaces.console.text import (
    display_escape_text,
)


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
    annotations: Mapping[str, SourceDisplayValue] | None = None,
    memory_loader: Callable[[str], Sequence[ContextMemoryRow]] | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> SeverSetupReceipt | None:
    """Select Source, one Criteria, and a save location in one full-screen TUI."""

    local = tuple(local_names)
    virtual = tuple(virtual_names)
    catalog = (*local, *virtual)
    if not local:
        raise ValueError("No local Contexts are available for Sever.")
    if any(not isinstance(name, str) or not name for name in catalog) or len(
        set(catalog)
    ) != len(catalog):
        raise ValueError("Sever setup received invalid Context names.")
    selectable_virtual = frozenset(selectable_virtual_names)
    if not selectable_virtual <= set(virtual):
        raise ValueError("Sever setup received invalid virtual Context permissions.")
    selectable = frozenset(local) | selectable_virtual
    labels = dict(annotations or {})
    if set(labels) - set(catalog):
        raise ValueError("Sever setup received invalid Context annotations.")
    try:
        for annotation in labels.values():
            if not normalize_source_display_tokens(annotation):
                raise ValueError("Context annotations must not be empty.")
    except (TypeError, ValueError) as error:
        raise ValueError(
            "Sever setup received invalid Context annotations."
        ) from error
    if require_tty and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        raise ValueError(
            "Interactive Sever setup requires a TTY. Pass SOURCE and CRITERIA "
            "outside a terminal; add RESULT only to save elsewhere."
        )

    tree = build_context_tree(catalog, materialized_names=selectable)
    initial_name = current if current in selectable else local[0]
    tree_state: dict[_Role, ContextTreeState] = {
        role: ContextTreeState.create(tree, selected=initial_name)
        for role in ("SOURCE", "CRITERIA")
    }
    # Both roles begin at the local current Context for orientation. Sever
    # still refuses to continue until the person makes them distinct.
    selections: dict[_Role, ContextSelectionState] = {
        role: ContextSelectionState.create(
            catalog,
            selected=(initial_name,),
            mode="SINGLE",
        )
        for role in ("SOURCE", "CRITERIA")
    }
    memory_previews = {
        role: ContextMemoryPreviewController(tree_state[role], memory_loader)
        for role in ("SOURCE", "CRITERIA")
        if memory_loader is not None
    }
    scope_choice: dict[_Role, ContextReachState] = {
        role: ContextReachState.create(include_descendants=True)
        for role in ("SOURCE", "CRITERIA")
    }
    scope_focused: dict[_Role, bool] = {
        "SOURCE": False,
        "CRITERIA": False,
    }
    default_output = _shared_local_output_name(
        selections["SOURCE"].selected_name,
        selections["CRITERIA"].selected_name,
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
        control = source_control if role == "SOURCE" else criteria_control
        preview = memory_previews.get(role)
        memory_focused = preview is not None and preview.memory_focused
        tree_focused = (
            app.layout.has_focus(control)
            and not scope_focused[role]
            and not memory_focused
        )
        wrap_width = max(1, get_app().output.get_size().columns - 1)
        checked_names = frozenset(
            project_checked_context_names(
                tree_state[role].tree,
                selections[role].selected_names,
                include_descendants=scope_choice[role].include_descendants,
                selectable_names=selectable,
            )
        )

        def decorate(row, cursor: bool) -> ContextTreeRowDecoration:
            available = row.name in selectable
            chosen = row.name in checked_names
            annotation: SourceDisplayValue | None = labels.get(row.name)
            if not available:
                annotation = combine_source_display_tokens(
                    annotation,
                    SourceDisplayFacts(states=(SourceState.UNAVAILABLE,)),
                )
            cursor_style, value_style = tree_choice_styles(
                cursor=cursor,
                selected=chosen,
                focused=tree_focused,
            )
            return ContextTreeRowDecoration(
                marker=tree_choice_marker(selected=chosen, available=available),
                active="*" if row.name == current else " ",
                annotation=annotation,
                cursor_style=cursor_style,
                value_style=value_style,
                branch=preview.branch_for(row) if preview is not None else None,
                nested_fragments=(
                    preview.render_nested(row, wrap_width=wrap_width)
                    if preview is not None
                    else ()
                ),
                anchor_cursor=not memory_focused,
            )

        return render_context_tree_rows(tree_state[role], decorate)

    source_control = FormattedTextControl(
        lambda: render_context("SOURCE"), focusable=True, show_cursor=False
    )
    criteria_control = FormattedTextControl(
        lambda: render_context("CRITERIA"), focusable=True, show_cursor=False
    )

    def context_frame(role: _Role, control: FormattedTextControl) -> Frame:
        def render_scope() -> list[tuple[str, str]]:
            return render_context_reach(
                scope_choice[role],
                title="SCOPE",
                focused=(scope_focused[role] and app.layout.has_focus(control)),
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

    def validate_output_name(candidate: str) -> None:
        validate_portable_context_name(candidate)
        if candidate == selections["SOURCE"].selected_name:
            if scope_choice["SOURCE"].include_descendants:
                raise ValueError(
                    "Self-save requires THIS CONTEXT ONLY for Source."
                )
            return
        if candidate in catalog:
            raise ValueError(
                "Other-save requires a new Context name; only Source may already exist."
            )

    output_field = ExactNameFieldControl.create(
        ExactNameFieldView(
            value=default_output,
            label="SAVE LOCATION · SOURCE OR NEW CONTEXT",
            state="SELF-SAVE OR OTHER-SAVE",
            validate=validate_output_name,
            value_label="Output Context name",
        ),
        input_name="sever-output-name",
    )
    output_editor = output_field.input
    output_frame = output_field.frame

    def current_receipt() -> SeverSetupReceipt:
        if selections["SOURCE"].selected_name == selections["CRITERIA"].selected_name:
            raise ValueError("Source and Criteria must be distinct.")
        return SeverSetupReceipt(
            source_name=selections["SOURCE"].selected_name,
            criteria_name=selections["CRITERIA"].selected_name,
            output_name=output_field.validate_candidate(),
            source_descendants=scope_choice["SOURCE"].include_descendants,
            criteria_descendants=scope_choice["CRITERIA"].include_descendants,
        )

    command_control: FormattedTextControl

    def render_command() -> list[tuple[str, str]]:
        focused = app.layout.has_focus(command_control)
        try:
            receipt = current_receipt()
            review = sever_start_command_review(
                source_name=receipt.source_name,
                criteria_name=receipt.criteria_name,
                output_name=receipt.output_name,
                source_descendants=receipt.source_descendants,
                criteria_descendants=receipt.criteria_descendants,
            )
        except (TypeError, ValueError) as error:
            return [
                ("class:error", " COMMAND · INVALID\n"),
                ("class:error", f" {display_escape_text(str(error))}"),
            ]
        return [
            (
                "class:focused-control" if focused else "class:report-label",
                " COMMAND · RUNNABLE · ENTER TO START\n",
            ),
            ("class:report-neutral", f" {format_exact_command(review)}"),
        ]

    command_control = FormattedTextControl(
        render_command,
        focusable=True,
        show_cursor=False,
    )
    command_frame = Frame(
        Window(command_control, wrap_lines=False),
        title="START COMMAND · SETUP ONLY",
        height=Dimension.exact(4),
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
        command_frame,
        is_focused=lambda: app.layout.has_focus(command_control),
    )
    def render_header() -> str:
        self_save = (
            output_editor.text.strip() == selections["SOURCE"].selected_name
        )
        return (
            " MEM SEVER · SETUP · "
            + ("SELF-SAVE" if self_save else "OTHER-SAVE")
            + "\n "
            f"SOURCE {display_escape_text(selections['SOURCE'].selected_name)} "
            f"({'SUBTREE' if scope_choice['SOURCE'].include_descendants else 'THIS ONLY'}) × "
            f"CRITERIA {display_escape_text(selections['CRITERIA'].selected_name)} "
            f"({'SUBTREE' if scope_choice['CRITERIA'].include_descendants else 'THIS ONLY'}) → "
            f"{'SELF-SAVE' if self_save else 'OTHER-SAVE'} "
            f"{display_escape_text(output_editor.text.strip())}"
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
                " OUTPUT: edit directly · Enter review command · Tab/Shift-Tab pane · "
                "Ctrl-C cancel"
            )
        if app.layout.has_focus(command_control):
            return " COMMAND: Enter start exact command · Shift-Tab back · Esc cancel"
        role = "SOURCE" if app.layout.has_focus(source_control) else "CRITERIA"
        if scope_focused[role]:
            return (
                f" {role} SCOPE: ← this Context only · → include descendants · "
                "↓ Context list · Tab/Shift-Tab pane · F continue · Q cancel"
            )
        expansion_action = (
            "A restore tree" if tree_state[role].all_expanded else "A expand all"
        )
        memory_hint = (
            memory_visibility_key_hint(memory_previews[role].tree) + " · "
            if role in memory_previews
            else ""
        )
        return (
            f" {role}: {memory_hint}"
            "↑/↓ move · ←/→ collapse/expand · Enter/Space choose · "
            f"top ↑ enters scope · {expansion_action} · " + "Tab/Shift-Tab pane · "
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
            command_frame,
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
        style=merge_styles([MEMCOMMIT_TUI_STYLE, CONTEXT_PICKER_STYLE]),
    )
    controls = (source_control, criteria_control, output_editor, command_control)

    def active_role() -> _Role:
        return "SOURCE" if app.layout.has_focus(source_control) else "CRITERIA"

    def move(delta: int) -> None:
        role = active_role()
        preview = memory_previews.get(role)
        if scope_focused[role]:
            if delta > 0:
                scope_focused[role] = False
            error_message["value"] = ""
            return
        if (
            delta < 0
            and selected_row_index(role) == 0
            and not (preview is not None and preview.memory_focused)
        ):
            scope_focused[role] = True
            error_message["value"] = ""
            return
        if preview is not None:
            preview.move(delta)
        else:
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
            preview = memory_previews.get(role)
            if preview is not None:
                preview.expand_selected()
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
            preview = memory_previews.get(role)
            if preview is not None:
                preview.collapse_selected()
            else:
                tree_state[role].collapse_selected()
        error_message["value"] = ""
        event.app.invalidate()

    @bindings.add("a", filter=tree_focus, eager=True)
    @bindings.add("A", filter=tree_focus, eager=True)
    def _toggle_expand_all(event) -> None:
        role = active_role()
        preview = memory_previews.get(role)
        if preview is not None:
            preview.toggle_expand_all()
        else:
            tree_state[role].toggle_expand_all()
        event.app.invalidate()

    @bindings.add("m", filter=tree_focus, eager=True)
    def _toggle_selected_memories(event) -> None:
        role = active_role()
        preview = memory_previews.get(role)
        if preview is not None and not scope_focused[role]:
            preview.toggle_selected_memories()
            error_message["value"] = ""
        event.app.invalidate()

    @bindings.add("M", filter=tree_focus, eager=True)
    def _toggle_all_memories(event) -> None:
        role = active_role()
        preview = memory_previews.get(role)
        if preview is not None and not scope_focused[role]:
            preview.toggle_all_memories()
            error_message["value"] = ""
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
        preview = memory_previews.get(role)
        if preview is not None and preview.memory_focused:
            # Preview rows remain read-only navigation stops; choosing one
            # cannot silently choose its owning Context.
            return
        name = tree_state[role].selected_name
        if name not in selectable:
            error_message["value"] = (
                "That row is query-only or a namespace and is unavailable to Sever."
            )
            return
        selections[role].choose(name)
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
        try:
            receipt = current_receipt()
            # Rebuild the public argv at approval while returning the typed
            # receipt. The shell is never recursively invoked from this TUI.
            sever_start_command_review(
                source_name=receipt.source_name,
                criteria_name=receipt.criteria_name,
                output_name=receipt.output_name,
                source_descendants=receipt.source_descendants,
                criteria_descendants=receipt.criteria_descendants,
            )
        except (TypeError, ValueError) as error:
            error_message["value"] = str(error)
            app.layout.focus(
                criteria_control
                if selections["SOURCE"].selected_name
                == selections["CRITERIA"].selected_name
                else output_editor
            )
            event.app.invalidate()
            return
        event.app.exit(result=receipt)

    def refresh_suggested_output() -> None:
        """Follow Source/Criteria until the person edits the proposed name."""

        previous = suggested_output["value"]
        suggested = _shared_local_output_name(
            selections["SOURCE"].selected_name,
            selections["CRITERIA"].selected_name,
            local_names=local,
            occupied_names=frozenset(catalog),
        )
        suggested_output["value"] = suggested
        if output_editor.text == previous:
            output_field.set_text(suggested)

    @bindings.add("f", filter=tree_focus, eager=True)
    @bindings.add("F", filter=tree_focus, eager=True)
    def _finish_from_tree(event) -> None:
        app.layout.focus(command_control)
        error_message["value"] = ""
        event.app.invalidate()

    @bindings.add("enter", filter=has_focus(output_editor), eager=True)
    def _finish_from_output(event) -> None:
        try:
            current_receipt()
        except (TypeError, ValueError) as error:
            error_message["value"] = str(error)
            event.app.invalidate()
            return
        app.layout.focus(command_control)
        error_message["value"] = ""
        event.app.invalidate()

    @bindings.add("enter", filter=has_focus(command_control), eager=True)
    def _finish_from_command(event) -> None:
        finish(event)

    @bind_case_insensitive_key(bindings, "q", filter=tree_focus, eager=True)
    @bindings.add("escape", eager=True)
    @bindings.add("c-c", eager=True)
    def _cancel(event) -> None:
        event.app.exit(result=None)

    try:
        return app.run()
    except (EOFError, KeyboardInterrupt):
        return None
