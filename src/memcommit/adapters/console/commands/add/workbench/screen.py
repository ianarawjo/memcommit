"""Context, scrollable Memory viewer, and repeatable compact Add input."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.filters import has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import Dimension, FormattedTextControl, Layout, Window
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles

from memcommit.application.operations.add.application import (
    AddedMemory,
    AddRequest,
    AddResult,
)
from memcommit.adapters.console.commands.add.workbench.model import AddWorkbenchSetup
from memcommit.adapters.console.terminal.components.focus import (
    FocusSurface,
    SurfaceActionResult,
    SurfaceFocusController,
    SurfaceMoveResult,
    bind_surface_navigation,
)
from memcommit.adapters.console.terminal.components.frame import (
    TuiRegion,
    bind_focused_frame_style,
    build_tui_frame,
)
from memcommit.adapters.console.terminal.components.operation_context_scope_editor.compact_context_selector import (
    CompactContextSelectorControl,
)
from memcommit.adapters.console.terminal.components.operation_context_scope_editor.existing_context_selector import (
    ContextSelectorControl,
    ContextSelectorView,
)
from memcommit.adapters.console.terminal.components.primitives import (
    ExactNameFieldControl,
    ExactNameFieldView,
)
from memcommit.adapters.console.terminal.components.scrollable_pane import (
    build_scrollable_formatted_text_pane,
    move_wrapped_read_cursor,
    scroll_wrapped_page,
)
from memcommit.adapters.console.terminal.core.capabilities import (
    require_interactive_terminal,
)
from memcommit.adapters.console.terminal.core.keybindings import (
    bind_case_insensitive_key,
    bind_tui_interrupt,
    dispatch_tui_back,
)
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text


def _build_context_selector(setup: AddWorkbenchSetup) -> ContextSelectorControl:
    return ContextSelectorControl(
        ContextSelectorView(
            names=setup.names,
            selected=(setup.selected_context,),
            mode="SINGLE",
            label="CONTEXT",
            current_context=setup.current_context,
            selectable_names=setup.selectable_names,
            annotations=setup.annotations,
        ),
        height=min(8, max(3, len(setup.names))),
    )


def memory_fragments(memories: tuple[AddedMemory, ...]) -> list[tuple[str, str]]:
    if not memories:
        return [("", " (no direct Memories)")]
    fragments: list[tuple[str, str]] = []
    for index, memory in enumerate(memories):
        if index:
            fragments.append(("", "\n"))
        fragments.append(("", f" [{safe_terminal_text(memory.uid[:8])}] "))
        fragments.append(("class:memory-object", safe_terminal_text(memory.content)))
    return fragments


class _AddWorkbench:
    """Keep each successful Enter receipt while composing the next Memory."""

    def __init__(
        self,
        *,
        setup: AddWorkbenchSetup,
        execute: Callable[[AddRequest], AddResult],
        load_memories: Callable[[str], tuple[AddedMemory, ...]],
        app_input: Input | None,
        app_output: Output | None,
    ) -> None:
        self.execute = execute
        self.load_memories = load_memories
        self.results: list[AddResult] = []
        self.status = ""
        self.selector = _build_context_selector(setup)
        self.context = CompactContextSelectorControl(self.selector)
        self.viewer = build_scrollable_formatted_text_pane(
            "VIEWER", height=Dimension.exact(12), buffer_name="add-viewer"
        )
        bind_focused_frame_style(
            self.viewer.frame,
            is_focused=lambda: get_app().layout.has_focus(self.viewer.text_area),
        )
        memory_field = ExactNameFieldControl.create(
            ExactNameFieldView(
                value="",
                label="ADD",
                value_label="Memory",
                strip_candidate=False,
            ),
            input_name="add-memory-input",
        )
        self.memory_input = memory_field.input
        self.bindings = KeyBindings()
        self.surfaces = SurfaceFocusController(self._surfaces)
        bind_surface_navigation(self.bindings, self.surfaces)
        self._bind_keys()
        root = build_tui_frame(
            TuiRegion(Window(FormattedTextControl(" MEM ADD"), height=1)),
            TuiRegion(self.context.container),
            TuiRegion(self.viewer.container),
            TuiRegion(memory_field.frame),
            TuiRegion(Window(FormattedTextControl(self._render_footer), height=1)),
        )
        self.app: Application[tuple[AddResult, ...]] = Application(
            layout=Layout(root, focused_element=self.memory_input),
            key_bindings=self.bindings,
            full_screen=False,
            erase_when_done=True,
            input=app_input,
            output=app_output,
            mouse_support=False,
            style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
        )
        self._refresh_viewer()

    def _surfaces(self) -> tuple[FocusSurface, ...]:
        return (
            FocusSurface(
                "CONTEXT",
                self.context.control,
                move_vertical=self._move_context,
                activate=self._choose_context,
            ),
            FocusSurface(
                "VIEWER",
                self.viewer.text_area,
                move_vertical=self._move_viewer,
                on_focus=self.context.close,
            ),
            FocusSurface(
                "ADD",
                self.memory_input,
                activate=self._submit,
                on_focus=self.context.close,
            ),
        )

    def run(self) -> tuple[AddResult, ...]:
        return self.app.run()

    def _render_footer(self) -> str:
        if get_app().layout.has_focus(self.memory_input):
            hint = "Enter add · Tab Context · Esc close"
        elif get_app().layout.has_focus(self.viewer.text_area):
            hint = "↑/↓ scroll · Tab Add · Esc close"
        elif self.context.is_open:
            hint = "↑/↓ move · ←/→ tree · Enter select · Tab Viewer · Esc back"
        else:
            hint = "Enter change Context · Tab Viewer · Esc close"
        return (
            " "
            + (safe_terminal_text(self.status) + " · " if self.status else "")
            + hint
        )

    def _refresh_viewer(self, *, added: bool = False) -> None:
        try:
            memories = self.load_memories(self.selector.selection.selected_name)
        except (OSError, RuntimeError, TypeError, ValueError):
            # Never keep the previous Context's content after a failed read or
            # treat a failed Viewer refresh as a failed, retryable Add.
            self.viewer.set_formatted_text(
                [
                    (
                        "",
                        " Memories unavailable · Context could not be read.",
                    )
                ],
                anchor="start",
            )
        else:
            self.viewer.set_formatted_text(
                memory_fragments(memories), anchor="end" if added else "start"
            )

    def _move_context(self, _event, delta: int) -> SurfaceMoveResult:
        if not self.context.is_open:
            return "BOUNDARY"
        before = self.selector.tree.selected_name
        self.selector.move(delta)
        return "MOVED" if self.selector.tree.selected_name != before else "BOUNDARY"

    def _move_viewer(self, event, delta: int) -> SurfaceMoveResult:
        return (
            "MOVED" if move_wrapped_read_cursor(event, direction=delta) else "BOUNDARY"
        )

    def _choose_context(self, event) -> SurfaceActionResult:
        if not self.context.is_open:
            self.context.open()
        else:
            try:
                self.selector.choose_cursor()
            except ValueError as error:
                self.status = str(error)
                return "HANDLED"
            self.context.close()
            self.status = ""
            self._refresh_viewer()
        event.app.layout.focus(self.context.control)
        return "HANDLED"

    def _submit(self, event) -> SurfaceActionResult:
        content = self.memory_input.text
        if not content.strip():
            self.status = "A Memory must contain nonblank text."
            return "HANDLED"
        request = AddRequest(
            context_locator=self.selector.selection.selected_name, contents=(content,)
        )
        try:
            completed = self.execute(request)
            if not isinstance(completed, AddResult):
                raise TypeError("Add application returned an invalid result.")
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            self.status = f"Add failed · {error}"
            self._refresh_viewer()
        else:
            self.results.append(completed)
            self.memory_input.text = ""
            self.status = (
                f"Added [{completed.memories[0].uid[:8]}] to {completed.context_name}"
            )
            self._refresh_viewer(added=True)
        return "HANDLED"

    def _paste(self, event) -> None:
        if "\n" in event.data or "\r" in event.data:
            self.status = "Paste one Memory on a single line."
        else:
            self.memory_input.buffer.insert_text(event.data)
        event.app.invalidate()

    def _close(self, event) -> None:
        event.app.exit(result=tuple(self.results))

    def _close_context(self, event) -> bool:
        if not self.context.is_open:
            return False
        was_focused = event.app.layout.has_focus(self.context.control)
        self.context.close()
        if was_focused:
            event.app.layout.focus(self.context.control)
        return True

    def _back(self, event) -> None:
        dispatch_tui_back(event, self._close_context, close=self._close)

    def _collapse(self, event) -> None:
        self.selector.collapse()
        event.app.invalidate()

    def _expand(self, event) -> None:
        self.selector.expand()
        event.app.invalidate()

    def _expand_all(self, event) -> None:
        self.selector.toggle_expand_all()
        event.app.invalidate()

    def _bind_keys(self) -> None:
        selector_focus = has_focus(self.selector.control)
        viewer_focus = has_focus(self.viewer.text_area)
        memory_focus = has_focus(self.memory_input)
        self.bindings.add("left", filter=selector_focus, eager=True)(self._collapse)
        self.bindings.add("right", filter=selector_focus, eager=True)(self._expand)
        bind_case_insensitive_key(self.bindings, "a", filter=selector_focus)(
            self._expand_all
        )
        self.bindings.add("pageup", filter=viewer_focus)(
            partial(scroll_wrapped_page, direction=-1)
        )
        self.bindings.add("pagedown", filter=viewer_focus)(
            partial(scroll_wrapped_page, direction=1)
        )
        self.bindings.add(Keys.BracketedPaste, filter=memory_focus)(self._paste)
        self.bindings.add("escape", eager=True)(self._back)
        self.bindings.add("backspace", filter=~memory_focus, eager=True)(self._back)
        bind_case_insensitive_key(self.bindings, "q", filter=~memory_focus)(self._back)
        bind_tui_interrupt(self.bindings, self._close)


def run_add_workbench(
    *,
    setup: AddWorkbenchSetup,
    execute: Callable[[AddRequest], AddResult],
    load_memories: Callable[[str], tuple[AddedMemory, ...]],
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> tuple[AddResult, ...]:
    """Browse one Context and immediately append each submitted Memory."""

    if require_tty:
        require_interactive_terminal(
            "Interactive Add",
            snapshot_hint="Pass positional MEMORY values or --paste outside a terminal.",
        )
    if not isinstance(setup, AddWorkbenchSetup):
        raise TypeError("Add workbench requires an AddWorkbenchSetup.")
    return _AddWorkbench(
        setup=setup,
        execute=execute,
        load_memories=load_memories,
        app_input=app_input,
        app_output=app_output,
    ).run()
