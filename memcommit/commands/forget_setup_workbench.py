"""Flagless instruction and direct-Source setup for ``mem forget``."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.filters import has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import Dimension, FormattedTextControl, Layout, Window
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles
from prompt_toolkit.widgets import TextArea

from memcommit.commands.surface_focus import (
    FocusSurface,
    SurfaceActionResult,
    SurfaceFocusController,
    SurfaceMoveResult,
    bind_surface_navigation,
)
from memcommit.commands.tui_primitives import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
    TuiRegion,
    bind_case_insensitive_key,
    build_focused_frame,
    build_tui_frame,
    dispatch_tui_back,
    require_interactive_terminal,
    safe_terminal_text,
)
from memcommit.context_targeting.tui.selector import (
    ContextSelectorControl,
    ContextSelectorView,
)
from memcommit.source_projection.presentation import SourceDisplayValue


@dataclass(frozen=True)
class ForgetSetupReceipt:
    """One process-local instruction bound to one canonical direct Source."""

    context_name: str
    instruction: str

    def __post_init__(self) -> None:
        if not isinstance(self.context_name, str) or not self.context_name.strip():
            raise ValueError("Forget setup requires one Source Context.")
        if not isinstance(self.instruction, str) or not self.instruction.strip():
            raise ValueError("Forget setup requires a nonblank instruction.")


def choose_forget_setup(
    names: Sequence[str],
    *,
    current: str,
    annotations: Mapping[str, SourceDisplayValue] | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> ForgetSetupReceipt | None:
    """Compose a query-like instruction field with one shared Source selector."""

    catalog = tuple(names)
    if (
        not catalog
        or len(set(catalog)) != len(catalog)
        or any(not isinstance(name, str) or not name for name in catalog)
    ):
        raise ValueError("Forget setup requires a distinct readable catalog.")
    if current not in catalog:
        raise ValueError("Forget's current Context is outside the readable catalog.")
    if require_tty:
        require_interactive_terminal(
            "Interactive Forget setup",
            snapshot_hint='Pass an instruction, for example: mem forget "old details".',
        )

    selector = ContextSelectorControl(
        ContextSelectorView(
            names=catalog,
            selected=(current,),
            mode="SINGLE",
            label="SOURCE · ALL READABLE CONTEXTS · * CURRENT",
            current_context=current,
            annotations=tuple((annotations or {}).items()),
        ),
        height=min(9, max(3, len(catalog))),
    )
    bindings = KeyBindings()
    error_message = {"value": ""}
    instruction_area = TextArea(
        multiline=False,
        prompt="› ",
        wrap_lines=False,
        height=Dimension.exact(1),
        name="forget-instruction",
    )
    instruction_frame = build_focused_frame(
        instruction_area,
        title="INSTRUCTION · ENTER TO ANALYZE",
        is_focused=lambda: get_app().layout.has_focus(instruction_area),
        height=Dimension.exact(3),
    )

    def render_todo() -> list[tuple[str, str]]:
        focused = get_app().layout.has_focus(todo_control)
        pointer = "›" if focused else " "
        style = "class:memcommit.choice.active.focused" if focused else ""
        selected = safe_terminal_text(selector.selection.selected_name)
        ready = "READY" if instruction_area.text.strip() else "INSTRUCTION REQUIRED"
        cursor = [("[SetCursorPosition]", "")] if focused else []
        return [
            *cursor,
            (style, f"{pointer} ANALYZE AND REVIEW · {ready}\n"),
            ("", f"  SOURCE · {selected} · THIS CONTEXT ONLY\n"),
            (
                "",
                "  The complete direct Source and instruction run in one provider turn.",
            ),
        ]

    todo_control = FormattedTextControl(
        render_todo,
        focusable=True,
        show_cursor=False,
    )
    todo_frame = build_focused_frame(
        Window(todo_control, wrap_lines=True),
        title="TO DO · ENTER TO ANALYZE",
        is_focused=lambda: get_app().layout.has_focus(todo_control),
        height=Dimension.exact(5),
    )
    header = Window(
        FormattedTextControl(
            " MEM FORGET · SETUP\n"
            " ONE DIRECT CONTEXT · SOURCE CHANGES ONLY AFTER REVIEW AND APPLY"
        ),
        height=Dimension.exact(2),
        dont_extend_height=True,
    )

    def render_footer() -> str:
        if error_message["value"]:
            return f" {safe_terminal_text(error_message['value'])}"
        if get_app().layout.has_focus(instruction_area):
            return " Enter analyze · Tab/↓ Source · Esc cancel"
        if get_app().layout.has_focus(selector.control):
            expansion = (
                "A restore tree" if selector.tree.all_expanded else "A expand all"
            )
            return (
                " ↑/↓ move/cross · ←/→ collapse/expand · Enter/Space select · "
                f"{expansion} · / instruction · Esc back"
            )
        return " Enter analyze · ↑ Source · / instruction · Esc back"

    footer = Window(
        FormattedTextControl(render_footer),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    root = build_tui_frame(
        TuiRegion(header),
        TuiRegion(instruction_frame),
        TuiRegion(selector.frame),
        TuiRegion(todo_frame),
        TuiRegion(footer),
    )
    app: Application[ForgetSetupReceipt | None] = Application(
        layout=Layout(root, focused_element=instruction_area),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
    )

    def submit(event) -> SurfaceActionResult:
        instruction = instruction_area.text.strip()
        if not instruction:
            error_message["value"] = "Enter a Forget instruction before analysis."
            event.app.layout.focus(instruction_area)
            return "HANDLED"
        event.app.exit(
            result=ForgetSetupReceipt(
                context_name=selector.selection.selected_name,
                instruction=instruction,
            )
        )
        return "HANDLED"

    def move_instruction(_event, _delta: int) -> SurfaceMoveResult:
        return "BOUNDARY"

    def enter_instruction(_delta: int) -> None:
        instruction_area.buffer.cursor_position = len(instruction_area.text)

    def move_context(_event, delta: int) -> SurfaceMoveResult:
        before = selector.tree.selected_name
        selector.move(delta)
        return "MOVED" if selector.tree.selected_name != before else "BOUNDARY"

    def choose_context(_event) -> SurfaceActionResult:
        try:
            selector.choose_cursor()
        except ValueError as error:
            error_message["value"] = str(error)
        else:
            error_message["value"] = ""
        return "HANDLED"

    def enter_context(delta: int) -> None:
        rows = selector.tree.visible_rows()
        selector.tree.selected_name = rows[0 if delta > 0 else -1].name

    surfaces = SurfaceFocusController(
        (
            FocusSurface(
                "INSTRUCTION",
                instruction_area,
                move_vertical=move_instruction,
                activate=submit,
                on_vertical_enter=enter_instruction,
            ),
            FocusSurface(
                "SOURCE",
                selector.control,
                move_vertical=move_context,
                activate=choose_context,
                on_vertical_enter=enter_context,
            ),
            FocusSurface(
                "TO_DO",
                todo_control,
                move_vertical=lambda _event, _delta: "BOUNDARY",
                activate=submit,
            ),
        )
    )
    bind_surface_navigation(bindings, surfaces)

    @bindings.add("left", filter=has_focus(selector.control), eager=True)
    def _collapse(event) -> None:
        selector.collapse()
        error_message["value"] = ""
        event.app.invalidate()

    @bindings.add("right", filter=has_focus(selector.control), eager=True)
    def _expand(event) -> None:
        selector.expand()
        error_message["value"] = ""
        event.app.invalidate()

    @bindings.add(" ", filter=has_focus(selector.control), eager=True)
    def _choose(event) -> None:
        choose_context(event)
        event.app.invalidate()

    @bind_case_insensitive_key(bindings, "a", filter=has_focus(selector.control))
    def _toggle_expand_all(event) -> None:
        selector.toggle_expand_all()
        error_message["value"] = ""
        event.app.invalidate()

    read_only_focus = has_focus(selector.control) | has_focus(todo_control)

    def focus_instruction(event) -> None:
        event.app.layout.focus(instruction_area)
        instruction_area.buffer.cursor_position = len(instruction_area.text)

    @bindings.add("/", filter=read_only_focus, eager=True)
    def _instruction_shortcut(event) -> None:
        focus_instruction(event)
        event.app.invalidate()

    @bindings.add("backspace", filter=read_only_focus, eager=True)
    def _back_to_instruction(event) -> None:
        focus_instruction(event)
        event.app.invalidate()

    def close(event) -> None:
        event.app.exit(result=None)

    def return_to_instruction(event) -> bool:
        if event.app.layout.has_focus(instruction_area):
            return False
        focus_instruction(event)
        return True

    @bindings.add("escape", eager=True)
    def _escape(event) -> None:
        dispatch_tui_back(event, return_to_instruction, close=close)

    @bind_case_insensitive_key(bindings, "q", filter=read_only_focus, eager=True)
    def _cancel_read_only(event) -> None:
        close(event)

    @bindings.add("c-c", eager=True)
    @bindings.add(Keys.SIGINT, eager=True)
    @bindings.add("c-d", eager=True)
    def _cancel_anywhere(event) -> None:
        close(event)

    try:
        result = app.run()
    except (EOFError, KeyboardInterrupt):
        return None
    if result is not None and not isinstance(result, ForgetSetupReceipt):
        raise ValueError("Forget setup returned an invalid result.")
    return result
