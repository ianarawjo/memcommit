"""Bidirectional compact setup for flagless ``mem forget``."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from prompt_toolkit.application import Application, get_app
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.formatted_text.base import StyleAndTextTuples
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import (
    ConditionalContainer,
    Dimension,
    Float,
    FloatContainer,
    FormattedTextControl,
    HSplit,
    Layout,
    VSplit,
    Window,
)
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles
from prompt_toolkit.widgets import TextArea

from memcommit.adapters.console.commands.forget.command_codec import (
    FORGET_COMMAND_FORM,
    build_forget_review,
    parse_forget_command_argv,
)
from memcommit.adapters.console.terminal.components.command_editor import (
    CommandDraft,
    CommandEditorControl,
    resolve_displayed_command_value,
)
from memcommit.adapters.console.terminal.components.exact_name import (
    ExactNameFieldView,
    ExactNameInputControl,
)
from memcommit.adapters.console.terminal.components.focus import (
    FocusSurface,
    SurfaceActionResult,
    SurfaceFocusController,
    SurfaceMoveResult,
    bind_surface_navigation,
)
from memcommit.adapters.console.terminal.components.frame import build_focused_frame
from memcommit.adapters.console.terminal.components.operation_context_scope_editor.existing_context_selector import (
    ContextSelectorControl,
    ContextSelectorView,
)
from memcommit.adapters.console.terminal.core.capabilities import (
    require_interactive_terminal,
)
from memcommit.adapters.console.terminal.core.keybindings import (
    bind_case_insensitive_key,
)
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
    focused_control_style,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.source_projection.presentation import (
    SourceDisplayValue,
    source_display_text,
)


@dataclass(frozen=True)
class ForgetSetupResult:
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
) -> ForgetSetupResult | None:
    """Collect Source and instruction through one bidirectional command form."""

    catalog = tuple(names)
    if (
        not catalog
        or len(set(catalog)) != len(catalog)
        or any(not isinstance(name, str) or not name for name in catalog)
    ):
        raise ValueError("Forget setup requires a distinct readable catalog.")
    if current not in catalog:
        raise ValueError("Forget's current Context is outside the readable catalog.")
    annotation_map = dict(annotations or {})
    if set(annotation_map) - set(catalog):
        raise ValueError("Forget setup annotations are outside its catalog.")
    if require_tty:
        require_interactive_terminal(
            "Interactive Forget setup",
            snapshot_hint='Pass an instruction, for example: mem forget "old details".',
        )

    status = {"value": ""}
    browser_open = {"value": False}
    programmatic_update = {"value": False}

    def completion_metadata() -> dict[str, str]:
        result: dict[str, str] = {}
        for name in catalog:
            values: list[str] = []
            if name == current:
                values.append("CURRENT")
            annotation = source_display_text(annotation_map.get(name))
            if annotation:
                values.append(annotation)
            result[name] = " · ".join(values)
        return result

    def resolve_source(value: str) -> str:
        return resolve_displayed_command_value(
            value.strip(),
            catalog,
            label="Forget Source",
        )

    source_name = ExactNameInputControl.create(
        ExactNameFieldView(
            value=current,
            label="FROM",
            detail="Use one exact readable direct Source Context.",
            validate=resolve_source,
            value_label="Forget Source",
        ),
        input_name="forget-source",
        prompt="› ",
        completer=WordCompleter(
            catalog,
            meta_dict=completion_metadata(),
            sentence=True,
            match_middle=True,
        ),
        complete_while_typing=True,
        width=Dimension(min=18, preferred=54, max=72),
        dont_extend_width=True,
    )
    instruction_input = TextArea(
        multiline=False,
        prompt="› ",
        wrap_lines=False,
        height=Dimension.exact(1),
        name="forget-instruction",
    )
    selector = ContextSelectorControl(
        ContextSelectorView(
            names=catalog,
            selected=(current,),
            mode="SINGLE",
            label="FROM · ALL READABLE CONTEXTS · * CURRENT",
            current_context=current,
            annotations=tuple(annotation_map.items()),
        ),
        height=min(8, max(3, len(catalog))),
    )
    # Browse promises the complete frozen readable namespace, so opening it
    # must not hide an eligible child behind another expansion gesture.
    selector.toggle_expand_all()

    def current_result() -> ForgetSetupResult:
        instruction = instruction_input.text.strip()
        if not instruction:
            raise ValueError("Forget requires one nonblank instruction.")
        return ForgetSetupResult(resolve_source(source_name.text), instruction)

    def apply_command_argv(argv: tuple[str, ...]) -> None:
        displayed_source, instruction = parse_forget_command_argv(argv)
        # Resolve and validate every value before moving either upper field.
        # Invalid command edits therefore never leave a partially changed form.
        result = ForgetSetupResult(resolve_source(displayed_source), instruction)
        programmatic_update["value"] = True
        try:
            source_name.set_text(result.context_name)
            instruction_input.text = result.instruction
            instruction_input.buffer.cursor_position = len(result.instruction)
            selector.select_name(result.context_name)
        finally:
            programmatic_update["value"] = False
        status["value"] = ""

    def review_current():
        result = current_result()
        return build_forget_review(
            source_name=result.context_name,
            instruction=result.instruction,
        )

    command_control = CommandEditorControl.create(
        CommandDraft(
            review=review_current,
            apply_argv=apply_command_argv,
            form=FORGET_COMMAND_FORM,
        ),
        action_label="RUN EXACT FORGET COMMAND",
        incomplete_action="FIX THE COMMAND BEFORE RUNNING",
        input_name="forget-proposed-command",
    )

    def upper_value_changed(_buffer) -> None:
        if programmatic_update["value"]:
            return
        status["value"] = ""
        try:
            get_app().invalidate()
        except RuntimeError:
            pass

    source_name.input.buffer.on_text_changed += upper_value_changed
    instruction_input.buffer.on_text_changed += upper_value_changed

    browse_control: FormattedTextControl

    def render_browse() -> StyleAndTextTuples:
        focused = get_app().layout.has_focus(browse_control)
        return [
            (
                focused_control_style(
                    focused=focused,
                    selected=browser_open["value"],
                ),
                "[ BROWSE ]",
            )
        ]

    browse_control = FormattedTextControl(
        render_browse,
        focusable=True,
        show_cursor=False,
    )

    def source_row_focused() -> bool:
        return get_app().layout.has_focus(
            source_name.input
        ) or get_app().layout.has_focus(browse_control)

    source_label = FormattedTextControl(
        lambda: [
            (
                focused_control_style(focused=source_row_focused()),
                f"{'›' if source_row_focused() else ' '} FROM",
            )
        ],
        show_cursor=False,
    )
    instruction_label = FormattedTextControl(
        lambda: [
            (
                focused_control_style(
                    focused=get_app().layout.has_focus(instruction_input)
                ),
                (
                    "› INSTRUCTION"
                    if get_app().layout.has_focus(instruction_input)
                    else "  INSTRUCTION"
                ),
            )
        ],
        show_cursor=False,
    )

    def render_source_state() -> StyleAndTextTuples:
        try:
            candidate = resolve_source(source_name.text)
        except ValueError:
            return [("class:source-state", "UNAVAILABLE · THIS CONTEXT ONLY")]
        values = ["CURRENT"] if candidate == current else []
        annotation = source_display_text(annotation_map.get(candidate))
        if annotation:
            values.append(annotation)
        values.append("THIS CONTEXT ONLY")
        return [("class:source-access", " · ".join(values))]

    label_width = Dimension.exact(15)
    source_row = VSplit(
        [
            Window(source_label, width=label_width, dont_extend_height=True),
            source_name.input,
            Window(
                browse_control,
                width=Dimension.exact(11),
                dont_extend_height=True,
            ),
            Window(
                FormattedTextControl(render_source_state),
                width=Dimension(min=20, preferred=42, weight=1),
                dont_extend_height=True,
            ),
        ],
        height=Dimension.exact(1),
    )
    instruction_row = VSplit(
        [
            Window(instruction_label, width=label_width, dont_extend_height=True),
            instruction_input,
        ],
        height=Dimension.exact(1),
    )
    command_frame = build_focused_frame(
        command_control.body,
        title="COMMAND",
        is_focused=command_control.is_focused,
        height=Dimension(min=3, preferred=3, max=4),
    )
    command_frame.container.style = command_control.frame_style

    catalog_detail = ConditionalContainer(
        HSplit(
            [
                Window(
                    FormattedTextControl(
                        "  FROM · ALL READABLE CONTEXTS · ENTER USES ONE DIRECT SOURCE"
                    ),
                    height=Dimension.exact(1),
                    dont_extend_height=True,
                ),
                Window(
                    selector.control,
                    wrap_lines=False,
                    right_margins=[ScrollbarMargin(display_arrows=True)],
                    height=Dimension.exact(min(8, len(catalog))),
                    dont_extend_height=True,
                ),
            ]
        ),
        filter=Condition(lambda: browser_open["value"]),
    )
    header = Window(
        FormattedTextControl(" NEW FORGET · CHOOSE SOURCE AND INSTRUCTION"),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    footer_control = FormattedTextControl()
    footer = Window(
        footer_control,
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    root = FloatContainer(
        content=HSplit(
            [
                header,
                source_row,
                instruction_row,
                command_frame,
                catalog_detail,
                footer,
            ]
        ),
        floats=[
            Float(
                xcursor=True,
                ycursor=True,
                content=CompletionsMenu(
                    max_height=8,
                    scroll_offset=1,
                    display_arrows=True,
                ),
            )
        ],
    )

    bindings = KeyBindings()

    def focus_instruction(event) -> None:
        event.app.layout.focus(instruction_input)
        instruction_input.buffer.cursor_position = len(instruction_input.text)

    def focus_command(event) -> None:
        command_control.sync_if_review_changed()
        event.app.layout.focus(command_control.active_control)
        command_control.input.buffer.cursor_position = len(command_control.input.text)

    def move_source(event, delta: int) -> SurfaceMoveResult:
        buffer = source_name.input.buffer
        if buffer.complete_state is not None:
            if delta > 0:
                buffer.complete_next()
            else:
                buffer.complete_previous()
            return "CONSUMED"
        if delta > 0:
            focus_instruction(event)
            return "CONSUMED"
        return "BOUNDARY"

    def confirm_source(event) -> SurfaceActionResult:
        buffer = source_name.input.buffer
        if (
            buffer.complete_state is not None
            and buffer.complete_state.current_completion is not None
        ):
            buffer.apply_completion(buffer.complete_state.current_completion)
        try:
            canonical = resolve_source(source_name.text)
        except ValueError as error:
            status["value"] = str(error)
            return "HANDLED"
        source_name.set_text(canonical)
        selector.select_name(canonical)
        status["value"] = ""
        focus_instruction(event)
        return "HANDLED"

    def open_browser(event) -> SurfaceActionResult:
        buffer = source_name.input.buffer
        if buffer.complete_state is not None:
            buffer.cancel_completion()
        try:
            selected = resolve_source(source_name.text)
        except ValueError:
            selected = current
        selector.select_name(selected)
        browser_open["value"] = True
        status["value"] = ""
        event.app.layout.focus(selector.control)
        return "HANDLED"

    def move_browse_row(event, delta: int) -> SurfaceMoveResult:
        if delta > 0:
            focus_instruction(event)
            return "CONSUMED"
        return "BOUNDARY"

    def move_instruction(event, delta: int) -> SurfaceMoveResult:
        if delta < 0:
            event.app.layout.focus(source_name.input)
            source_name.input.buffer.cursor_position = len(source_name.text)
        else:
            focus_command(event)
        return "CONSUMED"

    def confirm_instruction(event) -> SurfaceActionResult:
        if not instruction_input.text.strip():
            status["value"] = "Forget requires one nonblank instruction."
            return "HANDLED"
        status["value"] = ""
        focus_command(event)
        return "HANDLED"

    def move_command(event, delta: int) -> SurfaceMoveResult:
        if delta < 0:
            focus_instruction(event)
            return "CONSUMED"
        return "BOUNDARY"

    def finish(event) -> SurfaceActionResult:
        if not command_control.validate_current(event.app):
            status["value"] = command_control.draft.error
            return "HANDLED"
        try:
            result = current_result()
        except ValueError as error:
            status["value"] = str(error)
            return "HANDLED"
        event.app.exit(result=result)
        return "HANDLED"

    def _move_selector(delta: int) -> SurfaceMoveResult:
        before = selector.tree.selected_name
        selector.move(delta)
        return "MOVED" if selector.tree.selected_name != before else "BOUNDARY"

    def choose_browser(event) -> SurfaceActionResult:
        try:
            selector.choose_cursor()
            selected = selector.tree.selected_name
            source_name.set_text(selected)
        except ValueError as error:
            status["value"] = str(error)
            return "HANDLED"
        browser_open["value"] = False
        status["value"] = ""
        event.app.layout.focus(browse_control)
        return "HANDLED"

    def visible_surfaces() -> tuple[FocusSurface, ...]:
        if browser_open["value"]:
            return (
                FocusSurface(
                    "FROM_BROWSER",
                    selector.control,
                    move_vertical=lambda _event, delta: _move_selector(delta),
                    activate=choose_browser,
                ),
            )
        return (
            FocusSurface(
                "FROM",
                source_name.input,
                move_vertical=move_source,
                activate=confirm_source,
            ),
            FocusSurface(
                "FROM_BROWSE",
                browse_control,
                move_vertical=move_browse_row,
                activate=open_browser,
            ),
            FocusSurface(
                "INSTRUCTION",
                instruction_input,
                move_vertical=move_instruction,
                activate=confirm_instruction,
            ),
            FocusSurface(
                "COMMAND",
                command_control.active_control,
                move_vertical=move_command,
                activate=finish,
                on_focus=command_control.sync_if_review_changed,
            ),
        )

    def close_browser(event) -> bool:
        if not browser_open["value"]:
            return False
        browser_open["value"] = False
        status["value"] = ""
        event.app.layout.focus(browse_control)
        return True

    surfaces = SurfaceFocusController(visible_surfaces)
    bind_surface_navigation(bindings, surfaces)

    @bindings.add("right", filter=has_focus(source_name.input), eager=True)
    def _source_right(event) -> None:
        buffer = source_name.input.buffer
        if buffer.cursor_position < len(buffer.text):
            buffer.cursor_position += 1
        else:
            event.app.layout.focus(browse_control)
        event.app.invalidate()

    @bindings.add("left", filter=has_focus(browse_control), eager=True)
    def _browse_left(event) -> None:
        event.app.layout.focus(source_name.input)
        source_name.input.buffer.cursor_position = len(source_name.text)
        event.app.invalidate()

    @bindings.add("right", filter=has_focus(browse_control), eager=True)
    def _browse_right(event) -> None:
        focus_instruction(event)
        event.app.invalidate()

    @bindings.add("left", filter=has_focus(selector.control), eager=True)
    def _collapse(event) -> None:
        selector.collapse()
        event.app.invalidate()

    @bindings.add("right", filter=has_focus(selector.control), eager=True)
    def _expand(event) -> None:
        selector.expand()
        event.app.invalidate()

    @bindings.add(" ", filter=has_focus(selector.control), eager=True)
    def _choose_with_space(event) -> None:
        choose_browser(event)
        event.app.invalidate()

    @bind_case_insensitive_key(
        bindings,
        "a",
        filter=has_focus(selector.control),
        eager=True,
    )
    def _toggle_expand_all(event) -> None:
        selector.toggle_expand_all()
        event.app.invalidate()

    writable_focus = (
        has_focus(source_name.input)
        | has_focus(instruction_input)
        | has_focus(command_control.active_control)
    )

    @bindings.add("escape", eager=True)
    def _escape(event) -> None:
        if close_browser(event):
            event.app.invalidate()
            return
        if get_app().layout.has_focus(source_name.input):
            buffer = source_name.input.buffer
            if buffer.complete_state is not None:
                buffer.cancel_completion()
                event.app.invalidate()
                return
        event.app.exit(result=None)

    @bindings.add("backspace", filter=has_focus(selector.control), eager=True)
    def _browser_back(event) -> None:
        close_browser(event)
        event.app.invalidate()

    @bind_case_insensitive_key(
        bindings,
        "q",
        filter=~writable_focus,
        eager=True,
    )
    @bindings.add("c-c", eager=True)
    @bindings.add(Keys.SIGINT, eager=True)
    @bindings.add("c-d", eager=True)
    def _cancel(event) -> None:
        event.app.exit(result=None)

    def render_footer() -> str:
        if status["value"]:
            return " " + safe_terminal_text(status["value"])
        if browser_open["value"]:
            return " ↑/↓ Context · Enter use · ←/→ collapse/expand · Esc close"
        if get_app().layout.has_focus(source_name.input):
            return " Type exact Context · → at end Browse · ↓ Instruction · Esc cancel"
        if get_app().layout.has_focus(browse_control):
            return " Enter browse · ← Source · ↓ Instruction · Esc cancel"
        if get_app().layout.has_focus(instruction_input):
            return (
                " Type instruction · Enter command · ↑ Source · ↓ Command · Esc cancel"
            )
        if command_control.is_focused():
            return (
                " Enter run exact Forget command · ↑ Instruction · Esc cancel"
                if command_control.valid
                else " Fix the command before running · ↑ Instruction · Esc cancel"
            )
        return " Tab next control · Esc cancel"

    footer_control.text = render_footer
    app: Application[ForgetSetupResult | None] = Application(
        layout=Layout(root, focused_element=instruction_input),
        key_bindings=bindings,
        full_screen=False,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
        before_render=lambda _app: command_control.sync_if_review_changed(),
    )
    try:
        result = app.run()
    except (EOFError, KeyboardInterrupt):
        return None
    if result is not None and not isinstance(result, ForgetSetupResult):
        raise ValueError("Forget setup returned an invalid result.")
    return result


__all__ = ["ForgetSetupResult", "choose_forget_setup"]
