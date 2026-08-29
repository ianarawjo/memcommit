"""Prompt-toolkit view for the named Ground workbench."""

from __future__ import annotations

from importlib import import_module
from typing import Literal

from prompt_toolkit.application import Application
from prompt_toolkit.filters import Condition
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import DynamicContainer, FormattedTextControl, Layout, Window
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.output import Output

from memcommit.adapters.console.commands.ground.shell import (
    GROUND_CONTEXTS_FRAME_HEIGHT,
    GROUND_GOAL_FRAME_HEIGHT,
)
from memcommit.adapters.console.terminal.components.frame import (
    TuiRegion,
    bind_focused_frame_style,
    build_tui_frame,
)
from memcommit.adapters.console.terminal.components.in_frame_input import (
    InFrameInputManager,
    InFrameInputSection,
    INLINE_AGENT_COMMENT_TITLE,
)
from memcommit.adapters.console.terminal.components.scrollable_pane import (
    equal_pane_height,
)
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    MEMCOMMIT_TUI_STYLE,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.application.operations.ground.model import GroundSession

from memcommit.adapters.console.commands.ground.named_shell.presentation import (
    _aliased_items,
    render_named_ground_contexts_pane,
    render_named_ground_goal_pane,
    render_named_ground_header,
)
from memcommit.adapters.console.commands.ground.named_shell.proposal import (
    render_named_ground_proposal_blocks,
)
from memcommit.adapters.console.commands.ground.named_shell.runtime.state import (
    NamedGroundShellState,
)


class NamedGroundWorkbenchView:
    """Build and synchronize the five-pane named Ground terminal view."""

    def __init__(
        self,
        state: NamedGroundShellState,
        *,
        context_hints: tuple[str, ...],
        new_context_hint: str | None,
    ) -> None:
        self.state = state
        self.context_hints = context_hints
        self.new_context_hint = new_context_hint
        self.application: Application | None = None
        runtime_api = import_module(
            "memcommit.adapters.console.commands.ground.named_shell.runtime"
        )
        # These names were patchable on the former single-module runtime. Keep
        # resolving them at workbench construction so structural extraction
        # does not invalidate terminal capture and rendering test seams.
        self._Frame = runtime_api.Frame
        self._build_framed_multiline_input = runtime_api.build_framed_multiline_input
        self._build_inline_direct_edit_input = (
            runtime_api.build_inline_direct_edit_input
        )
        self._build_scrollable_text_pane = runtime_api.build_scrollable_text_pane
        self._render_named_ground_memories_pane = (
            runtime_api.render_named_ground_memories_pane
        )
        self._render_named_ground_memory_detail = (
            runtime_api.render_named_ground_memory_detail
        )
        self._render_named_ground_rules_pane = (
            runtime_api.render_named_ground_rules_pane
        )

        # Goal stays compact because new/revised Goals are limited to 40 words.
        # Rules, Memories, and Chat absorb the remaining reading space.
        pane_height = equal_pane_height(minimum=3, preferred=4)
        message_height = Dimension(min=3, preferred=4, max=5)
        self.embedded_field_height = Dimension(min=1, preferred=2, max=3)
        self.conversation_pane_height = Dimension(min=5, preferred=7)
        self.direct_edit_pane_height = Dimension(min=7, preferred=9)
        approval_action_height = Dimension.exact(4)
        compact_action_height = Dimension.exact(3)

        self.goal_pane = self._build_scrollable_text_pane(
            "GOAL",
            render_named_ground_goal_pane(
                state.current,
                fit_receipt=state.fit_receipt,
            ),
            buffer_name="ground-named-goal",
            height=GROUND_GOAL_FRAME_HEIGHT,
            notification=lambda: state.pane_notifications["GOAL"],
        )
        self.contexts_pane = self._build_scrollable_text_pane(
            "CONTEXTS",
            self.rendered_contexts(state.current),
            buffer_name="ground-named-contexts",
            height=GROUND_CONTEXTS_FRAME_HEIGHT,
            notification=lambda: state.pane_notifications["CONTEXTS"],
        )
        self.rules_pane = self._build_scrollable_text_pane(
            "RULES",
            self._render_named_ground_rules_pane(
                state.current,
                selected_rule_index=0,
                placement_hint=state.placement_choice["RULES"],
                fit_receipt=state.fit_receipt,
            ),
            buffer_name="ground-named-rules",
            height=pane_height,
            notification=lambda: state.pane_notifications["RULES"],
        )
        self.cases_pane = self._build_scrollable_text_pane(
            "MEMORIES",
            self._render_named_ground_memories_pane(
                state.current,
                selected_memory_index=0,
                placement_hint=state.placement_choice["MEMORIES"],
                fit_receipt=state.fit_receipt,
            ),
            buffer_name="ground-named-cases",
            height=pane_height,
            notification=lambda: state.pane_notifications["MEMORIES"],
        )
        # Saved Memories remain one physical row in List. Their Enter detail
        # may wrap because it is a reading surface rather than a scanner.
        self.cases_pane.text_area.window.wrap_lines = Condition(
            lambda: state.memory_detail_open
        )
        self.dialogue_pane = self._build_scrollable_text_pane(
            "CHAT",
            self.conversation_text(),
            buffer_name="ground-named-dialogue",
            height=pane_height,
            notification=lambda: state.pane_notifications["CHAT"],
        )
        self.composer = self._build_framed_multiline_input(
            "MESSAGE",
            prompt="› ",
            buffer_name="ground-named-message",
            height=message_height,
        )
        self.input_area = self.composer.text_area
        self.direct_editor = self._build_inline_direct_edit_input(
            buffer_name="ground-named-direct-edit",
        )
        self.direct_edit_area = self.direct_editor.text_area
        self.direct_edit_area.buffer.read_only = Condition(
            lambda: state.inline_direct_locked
        )

        header = Window(
            FormattedTextControl(
                lambda: render_named_ground_header(state.current)
                + (" · AUTO-FIT ON" if state.auto_fit_enabled else "")
            ),
            height=Dimension.exact(1),
            dont_extend_height=True,
        )
        approval_panel = self._Frame(
            Window(
                FormattedTextControl(
                    "CHAT: ←/↑ cmd · →/↓ fx\nEnter apply · A also · E/B/Q"
                ),
                wrap_lines=True,
            ),
            title="ACTION",
            height=approval_action_height,
        )
        error_panel = self._Frame(
            Window(
                FormattedTextControl("R retry · E refine · B/Q"),
                wrap_lines=True,
            ),
            title="ACTION",
            height=compact_action_height,
        )
        apply_error_panel = self._Frame(
            Window(
                FormattedTextControl("E refine · B/Q"),
                wrap_lines=True,
            ),
            title="ACTION",
            height=compact_action_height,
        )
        empty_action_panel = Window(height=Dimension.exact(0))
        action_panel = DynamicContainer(
            lambda: (
                approval_panel
                if state.mode == "APPROVAL"
                else apply_error_panel
                if state.mode == "APPLY_ERROR"
                else error_panel
                if state.mode == "ERROR"
                else empty_action_panel
            )
        )
        footer = Window(
            FormattedTextControl(self.footer_text),
            height=Dimension.exact(1),
            dont_extend_height=True,
        )
        self.root = build_tui_frame(
            TuiRegion(header),
            TuiRegion(self.goal_pane.container),
            TuiRegion(self.contexts_pane.container),
            TuiRegion(self.rules_pane.container),
            TuiRegion(self.cases_pane.container),
            TuiRegion(self.dialogue_pane.container),
            TuiRegion(action_panel),
            TuiRegion(footer),
        )
        self.input_manager = InFrameInputManager(
            self.goal_pane,
            self.contexts_pane,
            self.rules_pane,
            self.cases_pane,
            self.dialogue_pane,
        )
        self.sync_input_host()

        self.read_panes = (
            self.goal_pane.text_area,
            self.contexts_pane.text_area,
            self.rules_pane.text_area,
            self.cases_pane.text_area,
            self.dialogue_pane.text_area,
        )
        self.focus_order = (self.input_area, *self.read_panes)
        self.focus_layers = {
            id(self.input_area): "CHAT",
            id(self.goal_pane.text_area): "GOAL",
            id(self.contexts_pane.text_area): "CONTEXTS",
            id(self.rules_pane.text_area): "RULES",
            id(self.cases_pane.text_area): "MEMORIES",
            id(self.dialogue_pane.text_area): "CHAT",
        }

    def build_application(
        self,
        bindings: KeyBindings,
        *,
        app_input: Input | None,
        app_output: Output | None,
    ) -> Application:
        application: Application = Application(
            layout=Layout(
                self.root,
                focused_element=(
                    self.input_area
                    if self.input_manager.active_pane is not None
                    else self.dialogue_pane.text_area
                ),
            ),
            key_bindings=bindings,
            full_screen=True,
            enable_page_navigation_bindings=True,
            erase_when_done=True,
            input=app_input,
            output=app_output,
            mouse_support=False,
            style=MEMCOMMIT_TUI_STYLE,
        )
        # Ground has no Alt-prefixed actions. A short timeout lets a literal
        # Escape collapse the pane editor before the next navigation key.
        application.ttimeoutlen = 0.05
        self.application = application
        for pane in (
            self.goal_pane,
            self.contexts_pane,
            self.rules_pane,
            self.cases_pane,
            self.dialogue_pane,
        ):
            bind_focused_frame_style(
                pane.frame,
                is_focused=lambda pane=pane: application.layout.has_focus(pane.frame),
            )
        return application

    def rendered_contexts(self, active: GroundSession) -> str:
        state = self.state
        base = render_named_ground_contexts_pane(
            active,
            context_hints=self.context_hints,
            new_context_hint=self.new_context_hint,
            fit_receipt=state.fit_receipt,
        )
        if not state.placement_choice["CONTEXTS"]:
            return base
        return (
            base
            + "\n\nPLACEMENT TARGET · DIRECT SELECTION\n"
            + safe_terminal_text(state.placement_choice["CONTEXTS"])
            + " · P to choose from the Context tree"
        )

    def conversation_text(self) -> str:
        state = self.state
        blocks = list(state.conversation)
        if state.pending is not None:
            command_block, effects_block = render_named_ground_proposal_blocks(
                state.current,
                state.pending,
            )
            blocks.append(
                effects_block if state.review_view == "EFFECTS" else command_block
            )
        if state.error_message:
            blocks.append(
                "TURN FAILED · NOTHING NEW APPLIED\n"
                f"  {safe_terminal_text(state.error_message)}"
            )
        return "\n\n".join(blocks)

    def footer_text(self) -> str:
        state = self.state
        if state.panel_comment_target is not None:
            return " Enter · send focused comment    Ctrl-J · newline    Esc · collapse"
        if state.inline_target is not None:
            if state.inline_direct_locked:
                return (
                    " Unbound saved Goal · comment only    "
                    "bind before direct edit    Esc · collapse"
                )
            return (
                " Enter · review edit/comment    Ctrl-J · newline    "
                "Tab/Shift-Tab · field    Esc · collapse"
            )
        if state.fit_turn.busy:
            activity = "." * ((state.fit_turn.frame % 3) + 1)
            close_state = (
                "CLOSE REQUESTED · waiting for receipt boundary"
                if state.fit_turn.close_requested
                else "Esc/Q closes after the receipt boundary"
            )
            return (
                f" FIT RUNNING{activity} · Ground and Contexts unchanged · "
                + close_state
            )
        if state.status_message:
            return f" {state.status_message}"
        active_mode = state.mode
        if (
            active_mode in {"INPUT", "APPROVAL"}
            and self.has_focus(self.cases_pane.text_area)
            and _aliased_items(state.current, "CASE")
        ):
            tail = (
                "E · edit selected" if active_mode == "INPUT" else "A · exact approval"
            )
            if state.memory_detail_open:
                return (
                    " MEMORY DETAIL: Esc/Backspace · list    "
                    f"Space · toggle USE    F · run Fit    P · placement    "
                    f"C · comment    {tail}    B · Grounds    Q · quit"
                )
            return (
                " MEMORIES: ↑/↓ Example · Space · toggle USE    "
                "Enter · details    F · run Fit    "
                f"P · placement    C · comment    {tail}    "
                "B · Grounds    Q · quit"
            )
        if active_mode == "INPUT" and self.has_focus(self.rules_pane.text_area):
            if state.draft_queue:
                if state.draft_queue_stale:
                    return (
                        " Enter · talk here    R · reclassify drafts    "
                        "B · Grounds    Q · quit"
                    )
                return (
                    " ↑/↓ · draft    Enter · talk here    "
                    "P · placement    R · review READY Rule    B · Grounds    Q · quit"
                )
        if active_mode == "INPUT" and self.has_focus(self.goal_pane.text_area):
            return (
                " Enter · talk here    F · Fit    E · edit Goal    "
                "B · Grounds    Q · quit"
            )
        if active_mode == "INPUT":
            if self.has_focus(self.contexts_pane.text_area):
                return (
                    " F · Fit    P · placement Context tree    "
                    "Enter · talk here    B · Grounds    Q · quit"
                )
            if self.has_focus(self.input_area):
                return (
                    " Enter · send    Ctrl-J · newline    "
                    "Tab · panes (B Grounds · Q quit)"
                )
            return (
                " Enter · talk in this pane    C · same action    "
                "B · Grounds    Q · quit"
            )
        if active_mode == "APPROVAL":
            return (
                " One approval applies one exact command · "
                "B returns to Grounds · Q quits without approval"
            )
        if active_mode == "APPLY_ERROR":
            return " An unconfirmed command is never retried automatically"
        return " No Ground state changed from the failed turn"

    def pane_for_layer(self, layer: str):
        return {
            "GOAL": self.goal_pane,
            "CONTEXTS": self.contexts_pane,
            "RULE": self.rules_pane,
            "RULES": self.rules_pane,
            "MEMORY": self.cases_pane,
            "MEMORIES": self.cases_pane,
            "CHAT": self.dialogue_pane,
        }.get(layer, self.dialogue_pane)

    def sync_input_host(self) -> None:
        state = self.state
        self.input_manager.clear()
        if state.inline_target is not None:
            sections = [
                InFrameInputSection(
                    "EDIT (DIRECTLY)",
                    self.direct_edit_area,
                    height=self.embedded_field_height,
                    allow_read_only=state.inline_direct_locked,
                ),
                InFrameInputSection(
                    INLINE_AGENT_COMMENT_TITLE,
                    self.input_area,
                    height=self.embedded_field_height,
                ),
            ]
            self.input_manager.show(
                self.pane_for_layer(state.inline_target),
                *sections,
                height=self.direct_edit_pane_height,
            )
            return
        if state.panel_comment_target is not None:
            self.input_manager.show(
                self.pane_for_layer(state.panel_comment_target),
                InFrameInputSection(
                    INLINE_AGENT_COMMENT_TITLE,
                    self.input_area,
                    height=self.embedded_field_height,
                ),
                height=self.conversation_pane_height,
            )
            return
        if state.mode == "INPUT":
            self.input_manager.show(
                self.dialogue_pane,
                InFrameInputSection(
                    "MESSAGE",
                    self.input_area,
                    height=self.embedded_field_height,
                ),
                height=self.conversation_pane_height,
            )

    def sync_rules_pane(
        self,
        *,
        align_draft: bool = False,
        align_saved: bool = False,
    ) -> None:
        state = self.state
        rendered = self._render_named_ground_rules_pane(
            state.current,
            drafts=state.draft_queue,
            selected_draft_index=state.draft_index,
            drafts_stale=state.draft_queue_stale,
            selected_rule_index=(
                None if state.draft_queue else state.selected_rule_index
            ),
            placement_hint=state.placement_choice["RULES"],
            fit_receipt=state.fit_receipt,
        )
        self.rules_pane.set_text(rendered, anchor="preserve")
        if align_draft and state.draft_queue:
            marker = rendered.find(f"› d{state.draft_index + 1} ")
            if marker >= 0:
                self.rules_pane.text_area.buffer.cursor_position = marker
        elif align_saved and not state.draft_queue:
            marker = rendered.find(f"› r{state.selected_rule_index + 1} ")
            if marker >= 0:
                self.rules_pane.text_area.buffer.cursor_position = marker

    def sync_memories_pane(self, *, align_selection: bool = False) -> None:
        state = self.state
        cases = _aliased_items(state.current, "CASE")
        row = max(0, min(state.selected_memory_index, max(0, len(cases) - 1)))
        state.selected_memory_index = row
        if not cases:
            state.memory_detail_open = False
        if state.memory_detail_open:
            rendered = self._render_named_ground_memory_detail(
                state.current,
                selected_memory_index=row,
                fit_receipt=state.fit_receipt,
            )
            if state.placement_choice["MEMORIES"]:
                rendered += (
                    "\n\nPLACEMENT TARGET · DIRECT SELECTION\n"
                    + safe_terminal_text(state.placement_choice["MEMORIES"])
                )
            self.cases_pane.set_text(rendered, anchor="preserve")
            if align_selection:
                self.cases_pane.text_area.buffer.cursor_position = 0
            return
        rendered = self._render_named_ground_memories_pane(
            state.current,
            selected_memory_index=row,
            placement_hint=state.placement_choice["MEMORIES"],
            fit_receipt=state.fit_receipt,
        )
        self.cases_pane.set_text(rendered, anchor="preserve")
        if align_selection and cases:
            marker = rendered.find("› ")
            if marker >= 0:
                self.cases_pane.text_area.buffer.cursor_position = marker

    def sync_panes(self, *, dialogue_anchor: str = "end") -> None:
        state = self.state
        self.goal_pane.set_text(
            render_named_ground_goal_pane(
                state.current,
                fit_receipt=state.fit_receipt,
            ),
            anchor="preserve",
        )
        self.contexts_pane.set_text(
            self.rendered_contexts(state.current),
            anchor="preserve",
        )
        self.sync_rules_pane()
        self.sync_memories_pane()
        self.dialogue_pane.set_text(
            self.conversation_text(),
            anchor=dialogue_anchor,
        )

    def require_application(self) -> Application:
        if self.application is None:
            raise RuntimeError("Named Ground workbench Application is not attached.")
        return self.application

    def has_focus(self, element) -> bool:
        return self.application is not None and self.application.layout.has_focus(
            element
        )

    def invalidate(self) -> None:
        self.require_application().invalidate()

    def focus_conversation(self) -> None:
        self.require_application().layout.focus(self.dialogue_pane.text_area)

    def focus_message(self) -> None:
        self.require_application().layout.focus(self.input_area)

    def inline_owner_area(self):
        return {
            "GOAL": self.goal_pane.text_area,
            "RULE": self.rules_pane.text_area,
            "MEMORY": self.cases_pane.text_area,
        }.get(self.state.inline_target, self.goal_pane.text_area)

    def panel_comment_owner_area(self):
        return {
            "GOAL": self.goal_pane.text_area,
            "CONTEXTS": self.contexts_pane.text_area,
            "RULES": self.rules_pane.text_area,
            "MEMORIES": self.cases_pane.text_area,
            "CHAT": self.dialogue_pane.text_area,
        }.get(self.state.panel_comment_target, self.dialogue_pane.text_area)

    def focused_placement_layer(self) -> str | None:
        if self.has_focus(self.contexts_pane.text_area):
            return "CONTEXTS"
        if self.has_focus(self.rules_pane.text_area):
            return "RULES"
        if self.has_focus(self.cases_pane.text_area):
            return "MEMORIES"
        return None

    def acknowledge_focused_read_pane(self) -> None:
        for pane in self.read_panes:
            if self.has_focus(pane):
                self.state.acknowledge_pane(self.focus_layers[id(pane)])
                return

    def cycle_focus(self, step: int) -> None:
        application = self.require_application()
        current_index = next(
            (
                index
                for index, element in enumerate(self.focus_order)
                if application.layout.has_focus(element)
            ),
            0,
        )
        target = self.focus_order[(current_index + step) % len(self.focus_order)]
        application.layout.focus(target)
        self.state.acknowledge_pane(self.focus_layers[id(target)])
        application.invalidate()

    def cycle_read_focus(self, step: int) -> None:
        application = self.require_application()
        current_index = next(
            (
                index
                for index, element in enumerate(self.read_panes)
                if application.layout.has_focus(element)
            ),
            len(self.read_panes) - 1,
        )
        target = self.read_panes[(current_index + step) % len(self.read_panes)]
        application.layout.focus(target)
        self.state.acknowledge_pane(self.focus_layers[id(target)])
        application.invalidate()

    def focused_comment_target(self) -> tuple[str, str] | None:
        state = self.state
        if self.has_focus(self.goal_pane.text_area):
            return "GOAL", "GOAL"
        if self.has_focus(self.contexts_pane.text_area):
            return "CONTEXTS", "CONTEXTS"
        if self.has_focus(self.rules_pane.text_area):
            if not state.draft_queue:
                selected = state.selected_saved_item("RULE", state.selected_rule_index)
                if selected is not None:
                    return "RULES", f"RULE {selected[0]}"
            return "RULES", "RULES"
        if self.has_focus(self.cases_pane.text_area):
            selected = state.selected_saved_item("CASE", state.selected_memory_index)
            if selected is not None:
                return "MEMORIES", f"MEMORY {selected[0]}"
            return "MEMORIES", "MEMORIES"
        if self.has_focus(self.dialogue_pane.text_area):
            return "CHAT", "CHAT"
        return None

    def open_memory_detail(self) -> None:
        if not _aliased_items(self.state.current, "CASE"):
            return
        self.state.acknowledge_pane("MEMORIES")
        self.state.memory_detail_open = True
        self.sync_memories_pane(align_selection=True)
        self.invalidate()

    def collapse_memory_detail(self, _event: object | None = None) -> bool:
        if not self.state.memory_detail_open:
            return False
        self.state.memory_detail_open = False
        self.sync_memories_pane(align_selection=True)
        return True

    def move_saved_item(
        self,
        *,
        kind: Literal["RULE", "CASE"],
        step: int,
    ) -> None:
        state = self.state
        items = _aliased_items(state.current, kind)
        if not items:
            return
        state.acknowledge_pane("RULES" if kind == "RULE" else "MEMORIES")
        current_index = (
            state.selected_rule_index if kind == "RULE" else state.selected_memory_index
        )
        next_index = max(0, min(current_index + step, len(items) - 1))
        if kind == "RULE":
            state.selected_rule_index = next_index
            self.sync_rules_pane(align_saved=True)
        else:
            state.selected_memory_index = next_index
            self.sync_memories_pane(align_selection=True)
        self.invalidate()

    def move_rule_draft(self, step: int) -> None:
        state = self.state
        if not state.draft_queue:
            return
        state.acknowledge_pane("RULES")
        state.draft_index = max(
            0,
            min(state.draft_index + step, len(state.draft_queue) - 1),
        )
        state.status_message = ""
        self.sync_rules_pane(align_draft=True)
        self.invalidate()
