"""Operation-neutral exact Context-name editing controls."""

from __future__ import annotations

import sys
from dataclasses import dataclass

from prompt_toolkit import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.filters import has_focus
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import (
    Dimension,
    FormattedTextControl,
    HSplit,
    Layout,
    Window,
)
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.widgets import Frame, TextArea

from memcommit.adapters.console.terminal.components.exact_name import (
    ExactNameFieldControl,
    ExactNameFieldView,
)
from memcommit.adapters.console.terminal.components.report_card import boxed_lines
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    MEMCOMMIT_TUI_STYLE,
    focused_control_style,
)
from memcommit.adapters.console.terminal.components.frame import (
    build_focused_frame,
)
from memcommit.adapters.console.terminal.core.text import (
    display_escape_text,
    safe_terminal_text,
)
from memcommit.adapters.console.terminal.components.focus import (
    focus_in_order,
)
from memcommit.adapters.console.terminal.core.text_layout import (
    elide_terminal_text,
    single_line_terminal_text,
    terminal_cell_width,
)
from memcommit.core.context_targeting.tui.rendering import (
    ContextTreeRowDecoration,
    render_context_tree_rows,
)
from memcommit.core.context_targeting.tui.name_draft import (
    ContextNameDraftState,
    infer_context_parent,
)
from memcommit.core.context_targeting.tui.selection import ContextSelectionState
from memcommit.core.context_targeting.tui.tree import ContextTreeState, build_context_tree
from memcommit.adapters.console.terminal.components.selection import tree_choice_marker, tree_choice_styles


def suggest_fresh_context_name(
    stem: str,
    occupied_names: tuple[str, ...] | list[str],
) -> str:
    """Return an editable collision-free spelling without touching storage."""

    if not isinstance(stem, str) or not stem.strip():
        raise ValueError("Context-name suggestion stem must be nonempty text.")
    occupied = {
        name.casefold() for name in occupied_names if isinstance(name, str) and name
    }
    candidate = stem
    suffix = 2
    while candidate.casefold() in occupied:
        candidate = f"{stem}-{suffix}"
        suffix += 1
    return candidate


@dataclass(frozen=True)
class ContextNameView(ExactNameFieldView):
    """One exact Context name whose operation meaning is supplied by a caller."""

    label: str = "CONTEXT NAME"
    detail: str = "Enter to change this exact Context name."
    value_label: str = "Context name"
    context_names: tuple[str, ...] = ()
    current_context: str | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if not self.value.strip():
            raise ValueError("Context name must be nonempty text.")
        if not isinstance(self.context_names, tuple) or any(
            not isinstance(name, str)
            or not name
            or any(character in name for character in "\r\n")
            for name in self.context_names
        ):
            raise ValueError("Context-name catalog entries must be distinct lines.")
        if len(set(self.context_names)) != len(self.context_names):
            raise ValueError("Context-name catalog entries must be distinct lines.")
        if self.current_context is not None and (
            not isinstance(self.current_context, str)
            or not self.current_context
            or any(character in self.current_context for character in "\r\n")
        ):
            raise ValueError("Current Context must be one nonempty line.")


@dataclass
class ContextParentLocatorState:
    """Process-local destination-parent choice for one exact Context name."""

    tree: ContextTreeState
    selection: ContextSelectionState
    current_context: str | None = None

    @classmethod
    def create(cls, view: ContextNameView) -> "ContextParentLocatorState | None":
        """Create a parent browser when the caller supplies a frozen catalog."""

        if not view.context_names:
            return None
        selected = _initial_parent_context(view)
        tree = build_context_tree(view.context_names)
        return cls(
            tree=ContextTreeState.create(tree, selected=selected),
            selection=ContextSelectionState.create(
                view.context_names,
                selected=(selected,),
            ),
            current_context=view.current_context,
        )

    @property
    def selected_parent(self) -> str:
        return self.selection.selected_name

    def choose_cursor_as_parent(self, exact_value: str) -> str:
        """Reparent the exact final segment beneath the visible tree cursor."""

        parent = self.tree.selected_name
        draft = ContextNameDraftState(
            exact_name=exact_value,
            parent_name=self.selected_parent,
        )
        candidate = draft.choose_parent(parent)
        self.selection.choose(parent)
        return candidate


# Compatibility for Save Location and early Context-name callers. New code
# names the control by the parent-locator role instead of its first composition.
ContextNameEditorState = ContextParentLocatorState


def _initial_parent_context(view: ContextNameView) -> str:
    """Prefer the nearest materialized ancestor without inventing tree rows."""

    return infer_context_parent(
        view.value,
        view.context_names,
        fallback=view.current_context,
    )


def context_name_tree_fragments(
    state: ContextParentLocatorState,
    *,
    focused: bool,
) -> list[tuple[str, str]]:
    """Render the parent locator through the common Context-tree grammar."""

    def decorate(row, cursor: bool) -> ContextTreeRowDecoration:
        selected = row.name == state.selected_parent
        cursor_style, value_style = tree_choice_styles(
            cursor=cursor,
            selected=selected,
            focused=focused,
        )
        return ContextTreeRowDecoration(
            marker=tree_choice_marker(selected=selected),
            active="*" if row.name == state.current_context else " ",
            cursor_style=cursor_style,
            value_style=value_style,
        )

    return render_context_tree_rows(state.tree, decorate)


def context_name_row_fragments(
    view: ContextNameView,
    *,
    focused: bool,
    content_width: int,
) -> list[tuple[str, str]]:
    """Render one compact exact-name row for an embedding workbench."""

    action = "Enter to change"
    state = (
        f" · {single_line_terminal_text(safe_terminal_text(view.state))}"
        if view.state.strip()
        else ""
    )
    action_suffix = f"    {action}"
    full_suffix = f"{state}{action_suffix}"
    suffix = (
        full_suffix
        if content_width - terminal_cell_width(full_suffix) >= 4
        else action_suffix
    )
    safe_value = single_line_terminal_text(safe_terminal_text(view.value))
    available = content_width - terminal_cell_width(suffix)
    if available <= 0:
        row = elide_terminal_text(action, max(1, content_width))
        fragments: list[tuple[str, str]] = []
        if focused:
            fragments.append(("[SetCursorPosition]", ""))
        fragments.append((focused_control_style(focused=focused), row))
        return fragments
    value = elide_terminal_text(safe_value, available, position="middle")
    row = f"{value}{suffix}"
    fragments: list[tuple[str, str]] = []
    if focused:
        fragments.append(("[SetCursorPosition]", ""))
    fragments.append((focused_control_style(focused=focused), row))
    return fragments


def context_name_card_lines(
    view: ContextNameView,
    *,
    width: int = 72,
) -> list[str]:
    """Render the exact-name contract in a non-full-screen review card."""

    state = f" · {view.state}" if view.state.strip() else ""
    return boxed_lines(
        view.label,
        f"{display_escape_text(view.value)}{state}\n{view.detail}",
        width=width,
    )


@dataclass
class ContextParentLocatorControl:
    """Embeddable existing-Context parent browser independent of name input."""

    state: ContextParentLocatorState
    control: FormattedTextControl
    frame: Frame

    @classmethod
    def create(
        cls,
        state: ContextParentLocatorState,
        *,
        height: int = 5,
        label: str = "PARENT CONTEXT · ENTER SELECTS LOCATION",
    ) -> "ContextParentLocatorControl":
        if height < 1:
            raise ValueError("Context parent-locator height must be positive.")
        if not isinstance(label, str) or not label.strip():
            raise ValueError("Context parent-locator label must be nonempty text.")

        control: FormattedTextControl

        def render_tree() -> list[tuple[str, str]]:
            return context_name_tree_fragments(
                state,
                focused=get_app().layout.has_focus(control),
            )

        control = FormattedTextControl(
            render_tree,
            focusable=True,
            show_cursor=False,
        )
        frame = build_focused_frame(
            Window(
                control,
                wrap_lines=False,
                right_margins=[ScrollbarMargin(display_arrows=True)],
            ),
            title=safe_terminal_text(label),
            is_focused=lambda: get_app().layout.has_focus(control),
            height=Dimension.exact(height + 2),
        )
        return cls(state=state, control=control, frame=frame)

    def move(self, delta: int) -> None:
        self.state.tree.move(delta)

    def expand(self) -> None:
        self.state.tree.expand_selected()

    def collapse(self) -> None:
        self.state.tree.collapse_selected()

    def choose_parent(self, exact_value: str) -> str:
        return self.state.choose_cursor_as_parent(exact_value)


@dataclass
class ContextNameControl:
    """Embeddable direct input plus optional Context-parent locator."""

    view: ContextNameView
    field: ExactNameFieldControl
    parent_locator: ContextParentLocatorControl | None
    container: object
    draft_state: ContextNameDraftState
    _updating_input: bool = False

    @classmethod
    def create(
        cls,
        view: ContextNameView,
        *,
        input_name: str = "context-name",
        parent_height: int = 5,
    ) -> "ContextNameControl":
        if parent_height < 1:
            raise ValueError("Context-name parent height must be positive.")
        field = ExactNameFieldControl.create(view, input_name=input_name)
        editor_state = ContextParentLocatorState.create(view)
        parent_locator = (
            ContextParentLocatorControl.create(
                editor_state,
                height=parent_height,
            )
            if editor_state is not None
            else None
        )
        parts = (
            [field.frame]
            if parent_locator is None
            else [parent_locator.frame, field.frame]
        )
        container = HSplit(parts)
        control = cls(
            view=view,
            field=field,
            parent_locator=parent_locator,
            container=container,
            draft_state=ContextNameDraftState(
                exact_name=view.value,
                parent_name=(
                    editor_state.selected_parent
                    if editor_state is not None
                    else None
                ),
            ),
        )

        def record_direct_edit(_buffer) -> None:
            if not control._updating_input:
                control.draft_state.record_direct_edit(control.field.text)

        control.input.buffer.on_text_changed += record_direct_edit
        return control

    @property
    def editor_state(self) -> ContextParentLocatorState | None:
        return self.parent_locator.state if self.parent_locator is not None else None

    @property
    def input(self) -> TextArea:
        return self.field.input

    @property
    def tree_control(self) -> FormattedTextControl | None:
        return self.parent_locator.control if self.parent_locator is not None else None

    @property
    def name_frame(self) -> Frame:
        return self.field.frame

    @property
    def tree_frame(self) -> Frame | None:
        return self.parent_locator.frame if self.parent_locator is not None else None

    @property
    def text(self) -> str:
        return self.field.text

    def set_text(self, value: str) -> None:
        self.draft_state.replace_programmatically(value)
        self._updating_input = True
        try:
            self.field.set_text(value)
        finally:
            self._updating_input = False

    def validate_candidate(self) -> str:
        return self.field.validate_candidate()

    def choose_cursor_as_parent(self) -> str:
        if self.parent_locator is None:
            raise ValueError("No parent Context catalog is available.")
        parent = self.parent_locator.state.tree.selected_name
        candidate = self.draft_state.choose_parent(parent)
        self.parent_locator.state.selection.choose(parent)
        self.set_text(candidate)
        return candidate

    @property
    def direct_edit_started(self) -> bool:
        return self.draft_state.edited

    @property
    def focusables(self) -> tuple[object, ...]:
        if self.tree_control is None:
            return (self.input,)
        return (self.tree_control, self.input)


def choose_context_name(
    view: ContextNameView,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> str | None:
    """Edit one exact Context name in a compact reusable terminal control."""

    if require_tty and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        raise ValueError(
            "Interactive Context naming requires a terminal. Pass a name explicitly."
        )
    control = ContextNameControl.create(view)
    status = {"value": ""}
    bindings = KeyBindings()

    def set_status(value: object = "") -> None:
        status["value"] = display_escape_text(str(value)) if value else ""

    @bindings.add("enter", filter=has_focus(control.input), eager=True)
    def _submit(event) -> None:
        try:
            candidate = control.validate_candidate()
        except (OSError, TypeError, ValueError) as error:
            set_status(error)
            event.app.invalidate()
            return
        event.app.exit(result=candidate)

    if control.tree_control is not None:
        tree_focus = has_focus(control.tree_control)

        @bindings.add("up", filter=tree_focus, eager=True)
        def _tree_up(event) -> None:
            assert control.editor_state is not None
            control.editor_state.tree.move(-1)
            set_status()
            event.app.invalidate()

        @bindings.add("down", filter=tree_focus, eager=True)
        def _tree_down(event) -> None:
            assert control.editor_state is not None
            control.editor_state.tree.move(1)
            set_status()
            event.app.invalidate()

        @bindings.add("left", filter=tree_focus, eager=True)
        def _tree_left(event) -> None:
            assert control.editor_state is not None
            control.editor_state.tree.collapse_selected()
            event.app.invalidate()

        @bindings.add("right", filter=tree_focus, eager=True)
        def _tree_right(event) -> None:
            assert control.editor_state is not None
            control.editor_state.tree.expand_selected()
            event.app.invalidate()

        @bindings.add("enter", filter=tree_focus, eager=True)
        def _choose_parent(event) -> None:
            edited = control.direct_edit_started
            try:
                candidate = control.choose_cursor_as_parent()
            except (TypeError, ValueError) as error:
                set_status(error)
                event.app.invalidate()
                return
            event.app.layout.focus(control.input)
            set_status(
                "Parent selected · edited exact name preserved."
                if edited
                else f"Parent selected · edit {candidate} or press Enter."
            )
            event.app.invalidate()

        @bindings.add("escape", filter=tree_focus, eager=True)
        @bindings.add("backspace", filter=tree_focus, eager=True)
        def _leave_parent(event) -> None:
            event.app.layout.focus(control.input)
            set_status()
            event.app.invalidate()

        @bindings.add("up", filter=has_focus(control.input), eager=True)
        def _open_parent(event) -> None:
            assert control.tree_control is not None
            event.app.layout.focus(control.tree_control)
            set_status("Choose a parent Context, then press Enter.")
            event.app.invalidate()

    @bindings.add("tab")
    @bindings.add("s-tab")
    def _cycle(event) -> None:
        delta = -1 if event.key_sequence[0].key == Keys.BackTab else 1
        focus_in_order(event.app, control.focusables, delta, wrap=True)
        set_status()
        event.app.invalidate()

    @bindings.add("c-j", filter=has_focus(control.input), eager=True)
    def _reject_newline(event) -> None:
        set_status("Context names stay on one line.")
        event.app.invalidate()

    @bindings.add("escape", filter=has_focus(control.input), eager=True)
    @bindings.add("c-c", eager=True)
    def _cancel(event) -> None:
        event.app.exit(result=None)

    def footer_fragments() -> FormattedText:
        if status["value"]:
            return FormattedText([("class:error", f" {status['value']}")])
        parent_hint = " · Up/Tab parent" if control.tree_control is not None else ""
        return FormattedText(
            [
                (
                    "",
                    f" Edit directly · Ctrl-U clear{parent_hint} · Enter continue · Esc cancel",
                )
            ]
        )

    parent_rows = 7 if control.tree_control is not None else 0
    root = HSplit(
        [
            Window(
                FormattedTextControl(
                    FormattedText([("class:heading", f" {view.label}")])
                ),
                height=Dimension.exact(1),
                dont_extend_height=True,
            ),
            control.container,
            Window(
                FormattedTextControl(footer_fragments),
                height=Dimension.exact(1),
                dont_extend_height=True,
            ),
        ],
        height=Dimension.exact(5 + parent_rows),
    )
    app: Application[str | None] = Application(
        layout=Layout(root, focused_element=control.input),
        key_bindings=bindings,
        full_screen=False,
        mouse_support=False,
        style=MEMCOMMIT_TUI_STYLE,
        input=app_input,
        output=app_output,
    )
    try:
        return app.run()
    except (EOFError, KeyboardInterrupt):
        return None
