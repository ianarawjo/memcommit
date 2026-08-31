"""Prompt-toolkit view for the blank Ground workbench."""

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

from memcommit.adapters.console.commands.ground_workbench.ground.shell.presentation import (
    _BLANK_MEMORY_TABLE_COLUMNS,
    _render_ground_memory_table,
    _render_proposal_command_block,
    _render_proposal_effects_block,
    render_ground_goal_pane,
    render_ground_location_pane,
    render_ground_memories_pane,
    render_ground_rules_pane,
    render_ground_workspace_pane,
)
from memcommit.adapters.console.commands.ground_workbench.ground.shell.proposal import (
    GroundShellProposal,
    GroundShellResult,
)
from memcommit.adapters.console.commands.ground_workbench.ground.shell.runtime.context_selection import (
    GroundContextCandidateRow,
    candidate_row_at,
    initial_candidate_index,
    ordered_context_rows as build_ordered_context_rows,
)
from memcommit.adapters.console.commands.ground_workbench.ground.shell.runtime.session import (
    GroundPane,
    GroundShellState,
)
from memcommit.adapters.console.commands.ground_workbench.ground.shell.runtime.terminal_interaction.activity import (
    pane_activity_text as project_pane_activity,
    pane_thinking_verb,
    pane_turn_label,
)
from memcommit.adapters.console.commands.ground_workbench.ground.shell.runtime.terminal_interaction.focus import (
    cycle_focus as cycle_terminal_focus,
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
from memcommit.adapters.console.terminal.components.table import (
    SelectedTableCellProcessor,
    clamp_table_position,
)
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    MEMCOMMIT_TUI_STYLE,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text


INITIAL_QUESTION = "What are you trying to understand, decide, or make together?"
GROUND_GOAL_FRAME_HEIGHT = Dimension(min=3, preferred=5, max=5)
# CONTEXTS is the first-turn orientation and selection surface. Its preferred
# outer height leaves five body rows, while the shared three-row minimum lets
# prompt-toolkit compress it to one body row on a conventional 24-row terminal.
GROUND_CONTEXTS_FRAME_HEIGHT = Dimension(min=3, preferred=7, max=10)
GROUND_LOCATION_FRAME_HEIGHT = Dimension.exact(3)


class BlankGroundWorkbenchView:
    """Build and synchronize the blank Ground terminal projection."""

    def __init__(
        self,
        state: GroundShellState,
        *,
        fixed_ground_name: str | None,
        frozen_initial_proposal: GroundShellProposal | None,
        working_goal: str,
        current_context_name: str | None,
        context_catalog_count: int,
        context_catalog_names: tuple[str, ...],
        thinking_suffixes: tuple[str, ...],
    ) -> None:
        self.state = state
        self.fixed_ground_name = fixed_ground_name
        self.current_context_name = current_context_name
        self.context_catalog_count = context_catalog_count
        self.context_catalog_names = context_catalog_names
        self.thinking_suffixes = thinking_suffixes
        self.application: Application[GroundShellResult] | None = None

        runtime_api = import_module(
            "memcommit.adapters.console.commands.ground_workbench.ground.shell.runtime"
        )
        # Resolve the historical runtime facade at construction time. Focused
        # shell tests and capture adapters patch these factories before one
        # Application is built, so moving the implementation must not freeze
        # their defaults at import time.
        self._Frame = runtime_api.Frame
        self._build_scrollable_text_pane = runtime_api.build_scrollable_text_pane
        self._build_framed_multiline_input = runtime_api.build_framed_multiline_input
        self._build_inline_direct_edit_input = (
            runtime_api.build_inline_direct_edit_input
        )
        self._render_ground_contexts_pane = runtime_api.render_ground_contexts_pane

        # Goal is an orientation statement, not a document surface. Rules,
        # Memories, and Chat absorb the remaining reading space.
        pane_height = equal_pane_height(minimum=3, preferred=4)
        message_height = Dimension(min=3, preferred=4, max=5)
        self.embedded_field_height = Dimension(min=1, preferred=2, max=3)
        self.conversation_pane_height = Dimension(min=5, preferred=7)
        self.direct_edit_pane_height = Dimension(min=7, preferred=9)
        approval_action_height = Dimension.exact(4)
        compact_action_height = Dimension.exact(3)

        self.location_pane = self._build_scrollable_text_pane(
            "LOCATION",
            render_ground_location_pane(
                state.planned_ground_name,
                source=state.location_source,
            ),
            buffer_name="ground-new-location",
            height=GROUND_LOCATION_FRAME_HEIGHT,
            notification=lambda: state.pane_notifications["LOCATION"],
        )
        self.goal_pane = self._build_scrollable_text_pane(
            "GOAL",
            self.pane_activity_text(
                "GOAL",
                render_ground_goal_pane(
                    frozen_initial_proposal,
                    working_goal=working_goal,
                ),
            ),
            buffer_name="ground-new-goal",
            height=GROUND_GOAL_FRAME_HEIGHT,
            notification=lambda: state.pane_notifications["GOAL"],
        )
        self.contexts_pane = self._build_scrollable_text_pane(
            "CONTEXTS",
            (
                self._render_ground_contexts_pane(
                    current_context_name=current_context_name,
                    catalog_count=context_catalog_count,
                    discovery_in_progress=state.context_discovery_in_progress,
                    thinking_suffix=self.current_thinking_suffix(),
                )
                if context_catalog_count
                else render_ground_workspace_pane(state.planned_ground_name)
            ),
            buffer_name="ground-new-contexts",
            height=GROUND_CONTEXTS_FRAME_HEIGHT,
            notification=lambda: state.pane_notifications["CONTEXTS"],
        )
        self.rules_pane = self._build_scrollable_text_pane(
            "RULES",
            render_ground_rules_pane(state.rule_drafts),
            buffer_name="ground-new-rules",
            height=pane_height,
            notification=lambda: state.pane_notifications["RULES"],
        )
        self.cases_pane = self._build_scrollable_text_pane(
            "MEMORIES",
            render_ground_memories_pane(state.memory_drafts),
            buffer_name="ground-new-cases",
            height=pane_height,
            notification=lambda: state.pane_notifications["MEMORIES"],
        )
        # LIST preserves wrapped cards. TABLE uses logical rows and lets the
        # selected-cell cursor drive horizontal scrolling like a spreadsheet.
        self.cases_pane.text_area.window.wrap_lines = Condition(
            lambda: state.memory_view == "LIST"
        )
        self.cases_pane.text_area.control.input_processors.append(
            SelectedTableCellProcessor(
                lambda: (
                    state.memory_table_render.selected_span
                    if state.memory_view == "TABLE"
                    and state.memory_table_render is not None
                    else None
                )
            )
        )
        self.dialogue_pane = self._build_scrollable_text_pane(
            "CHAT",
            self.conversation_text(),
            buffer_name="ground-new-dialogue",
            height=pane_height,
            notification=lambda: state.pane_notifications["CHAT"],
        )
        self.composer = self._build_framed_multiline_input(
            "MESSAGE",
            prompt="› ",
            buffer_name="ground-new-message",
            height=message_height,
        )
        self.input_area = self.composer.text_area
        self.direct_editor = self._build_inline_direct_edit_input(
            buffer_name="ground-new-direct-edit",
        )
        self.direct_edit_area = self.direct_editor.text_area

        header = Window(
            FormattedTextControl(" MEM GROUND · DRAFT"),
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
            TuiRegion(self.location_pane.container),
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
            self.location_pane.text_area,
            self.goal_pane.text_area,
            self.contexts_pane.text_area,
            self.rules_pane.text_area,
            self.cases_pane.text_area,
            self.dialogue_pane.text_area,
        )
        # Starting at Goal makes Shift-Tab reach Location immediately while
        # ordinary Tab follows the visible top-to-bottom workbench order.
        self.focus_order = (*self.read_panes, self.input_area)
        self.focus_layers: dict[int, GroundPane] = {
            id(self.input_area): "CHAT",
            id(self.location_pane.text_area): "LOCATION",
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
    ) -> Application[GroundShellResult]:
        application: Application[GroundShellResult] = Application(
            layout=Layout(self.root, focused_element=self.goal_pane.text_area),
            key_bindings=bindings,
            full_screen=True,
            enable_page_navigation_bindings=True,
            erase_when_done=True,
            input=app_input,
            output=app_output,
            mouse_support=False,
            style=MEMCOMMIT_TUI_STYLE,
        )
        application.ttimeoutlen = 0.05
        self.application = application
        for pane in (
            self.location_pane,
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

    def require_application(self) -> Application[GroundShellResult]:
        if self.application is None:
            raise RuntimeError("Blank Ground workbench Application is not attached.")
        return self.application

    def has_focus(self, element: object) -> bool:
        return self.application is not None and self.application.layout.has_focus(
            element
        )

    def invalidate(self) -> None:
        self.require_application().invalidate()

    def current_thinking_suffix(self) -> str:
        return self.thinking_suffixes[self.state.thinking_phase]

    def pane_activity_text(self, target: GroundPane, base: str) -> str:
        return project_pane_activity(
            target,
            base,
            self.state.pane_activities[target],
        )

    def ordered_context_rows(self) -> tuple[GroundContextCandidateRow, ...]:
        return build_ordered_context_rows(
            fixed_ground_name=self.fixed_ground_name,
            suggestions=self.state.context_suggestions,
            new_suggestions=self.state.new_context_suggestions,
            current_context_name=self.current_context_name,
            discovery_complete=self.state.context_discovery_complete,
            direct_context_names=self.context_catalog_names,
        )

    def reset_context_candidate_cursor(self) -> None:
        self.state.context_candidate_index = initial_candidate_index(
            self.ordered_context_rows()
        )

    def context_cursor_row(self) -> GroundContextCandidateRow | None:
        self.state.context_candidate_index, row = candidate_row_at(
            self.ordered_context_rows(),
            self.state.context_candidate_index,
        )
        return row

    def conversation_text(self) -> str:
        state = self.state
        blocks = list(state.conversation)
        proposal = state.pending
        if proposal is not None:
            blocks.append(
                _render_proposal_effects_block(
                    proposal,
                    has_local_new_context=bool(state.local_new_context_name),
                )
                if state.review_view == "EFFECTS"
                else _render_proposal_command_block(proposal)
            )
        if state.error_message and state.active_turn_target == "CHAT":
            blocks.append(
                "INTERPRETATION FAILED · NOTHING APPLIED\n"
                f"  {safe_terminal_text(state.error_message)}"
            )
        return "\n\n".join(blocks)

    def footer_text(self) -> str:
        state = self.state
        active_mode = state.mode
        if state.panel_comment_target is not None:
            target = state.panel_comment_target
            return (
                f" Enter · send {pane_turn_label(target).lower()}    "
                "Ctrl-J · newline    Esc · collapse"
            )
        if state.inline_context_open:
            if self.has_focus(self.direct_edit_area):
                return (
                    " Enter · use exact one-line name    "
                    "Tab · comment    Esc · collapse"
                )
            return (
                " Enter · send comment    Ctrl-J · newline    "
                "Tab · exact name    Esc · collapse"
            )
        if state.inline_goal_open:
            return (
                " Enter · review edit/comment    Ctrl-J · newline    "
                "Tab/Shift-Tab · field    Esc · collapse"
            )
        contexts_focused = self.has_focus(self.contexts_pane.text_area)
        memories_focused = self.has_focus(self.cases_pane.text_area)
        location_focused = self.has_focus(self.location_pane.text_area)
        input_focused = self.has_focus(self.input_area)
        if location_focused and active_mode in {"INPUT", "APPROVAL"}:
            return (
                " LOCATION: Enter/L · choose or change    "
                "Tab/Shift-Tab · move    B · Grounds    Q · quit"
            )
        if (
            state.context_selection_finished
            and contexts_focused
            and active_mode in {"INPUT", "APPROVAL"}
        ):
            return (
                " CONTEXTS: Enter talk here    F edit selection    "
                "B · Grounds    Q · quit"
            )
        if state.status_message:
            return f" {state.status_message}"
        if memories_focused and state.memory_drafts:
            tail = (
                "Enter · exact approval"
                if active_mode == "APPROVAL"
                else "Enter · talk here"
            )
            if state.memory_view == "TABLE":
                return (
                    " MEMORIES · TABLE: ↑/↓ row · ←/→ column · "
                    f"V · list    {tail}    B · Grounds    Q · quit"
                )
            return (
                " MEMORIES · LIST: ↑/↓ scroll · V · table    "
                f"{tail}    B · Grounds    Q · quit"
            )
        if active_mode == "INTERPRETING":
            return f" Waiting in {state.active_turn_target}    B · Grounds    Q · quit"
        if (
            active_mode in {"INPUT", "CONTEXT_SELECTION"}
            and contexts_focused
            and not state.context_selection_finished
            and bool(self.ordered_context_rows())
        ):
            return (
                " CONTEXTS: ↑/↓ move · Space select · F finish · "
                "P direct tree · N exact name · B Grounds · Q quit"
            )
        if active_mode in {"INPUT", "CONTEXT_SELECTION"}:
            if input_focused:
                return (
                    " Enter · send    Ctrl-J · newline    "
                    "Tab · panes (B Grounds · Q quit)"
                )
            if active_mode == "INPUT" and self.has_focus(self.goal_pane.text_area):
                return (
                    " Enter · talk here    E · edit Goal    L · location    "
                    "B · Grounds    Q · quit"
                )
            return (
                " Enter · talk here    C · same action    L · location    "
                "B · Grounds    Q · quit"
            )
        if active_mode == "APPROVAL":
            row = self.context_cursor_row()
            if (
                contexts_focused
                and not state.context_selection_finished
                and row is not None
                and row.kind == "ADD_NEW"
            ):
                return (
                    " CONTEXTS: N · plan a new Context name    "
                    "Enter approve · B Grounds · Q quit"
                )
            return (
                " No command runs without Enter · exact approval    "
                "L · location    B · Grounds    Q · quit"
            )
        if active_mode == "APPLY_ERROR":
            return " The exact command will not be applied again"
        return " The failed interpretation cannot change Ground state"

    def pane_for_layer(self, layer: GroundPane):
        return {
            "LOCATION": self.location_pane,
            "GOAL": self.goal_pane,
            "CONTEXTS": self.contexts_pane,
            "RULES": self.rules_pane,
            "MEMORIES": self.cases_pane,
            "CHAT": self.dialogue_pane,
        }.get(layer, self.dialogue_pane)

    def sync_pane_titles(self) -> None:
        base_titles: dict[GroundPane, str] = {
            "LOCATION": "LOCATION",
            "GOAL": "GOAL",
            "CONTEXTS": "CONTEXTS",
            "RULES": "RULES",
            "MEMORIES": "MEMORIES",
            "CHAT": "CHAT",
        }
        for target, title in base_titles.items():
            activity = self.state.pane_activities[target]
            self.pane_for_layer(target).frame.title = (
                f"{title} · THINKING{self.current_thinking_suffix()} · "
                f"{pane_thinking_verb(target)}"
                if activity.phase == "THINKING"
                else title
            )

    def sync_input_host(self) -> None:
        state = self.state
        self.input_manager.clear()
        if state.inline_goal_open:
            self.input_manager.show(
                self.goal_pane,
                InFrameInputSection(
                    "EDIT (DIRECTLY)",
                    self.direct_edit_area,
                    height=self.embedded_field_height,
                ),
                InFrameInputSection(
                    INLINE_AGENT_COMMENT_TITLE,
                    self.input_area,
                    height=self.embedded_field_height,
                ),
                height=self.direct_edit_pane_height,
            )
            return
        if state.inline_context_open:
            self.input_manager.show(
                self.contexts_pane,
                InFrameInputSection(
                    "EDIT (DIRECTLY)",
                    self.direct_edit_area,
                    height=self.embedded_field_height,
                ),
                InFrameInputSection(
                    INLINE_AGENT_COMMENT_TITLE,
                    self.input_area,
                    height=self.embedded_field_height,
                ),
                height=self.direct_edit_pane_height,
            )
            return
        if state.panel_comment_target is not None:
            target = state.panel_comment_target
            self.input_manager.show(
                self.pane_for_layer(target),
                InFrameInputSection(
                    pane_turn_label(target),
                    self.input_area,
                    height=self.embedded_field_height,
                ),
                height=self.conversation_pane_height,
            )
            return
        if state.mode in {"INPUT", "CONTEXT_SELECTION"}:
            self.input_manager.show(
                self.dialogue_pane,
                InFrameInputSection(
                    "MESSAGE",
                    self.input_area,
                    height=self.embedded_field_height,
                ),
                height=self.conversation_pane_height,
            )

    def sync_contexts_pane(self, *, align_candidate: bool = False) -> None:
        state = self.state
        if (
            not self.context_catalog_count
            and not state.context_suggestions
            and not state.new_context_suggestions
        ):
            self.contexts_pane.set_text(
                self.pane_activity_text(
                    "CONTEXTS",
                    render_ground_workspace_pane(state.planned_ground_name),
                ),
                anchor="preserve",
            )
            return
        cursor_row = self.context_cursor_row()
        cursor_name = cursor_row.context_name if cursor_row is not None else None
        rendered = self._render_ground_contexts_pane(
            state.context_suggestions,
            new_context_suggestions=state.new_context_suggestions,
            current_context_name=self.current_context_name,
            catalog_count=self.context_catalog_count,
            discovery_complete=state.context_discovery_complete,
            discovery_in_progress=False,
            thinking_suffix=self.current_thinking_suffix(),
            candidate_cursor_name=cursor_name,
            candidate_cursor_kind=(cursor_row.kind if cursor_row is not None else None),
            selected_context_names=state.selected_context_names,
            local_new_context_name=state.local_new_context_name,
            selection_finished=state.context_selection_finished,
            direct_context_names=self.context_catalog_names,
        )
        projected = self.pane_activity_text("CONTEXTS", rendered)
        self.contexts_pane.set_text(projected, anchor="preserve")
        if align_candidate and cursor_name is not None:
            marker = projected.find("› ")
            if marker >= 0:
                self.contexts_pane.text_area.buffer.cursor_position = marker

    def sync_memories_pane(self, *, align_selection: bool = False) -> None:
        state = self.state
        row, column = clamp_table_position(
            row_count=len(state.memory_drafts),
            column_count=len(_BLANK_MEMORY_TABLE_COLUMNS),
            row=state.selected_memory_index,
            column=state.selected_memory_column,
        )
        state.selected_memory_index = row
        state.selected_memory_column = column
        if state.memory_view == "TABLE":
            rendered = _render_ground_memory_table(
                state.memory_drafts,
                selected_memory_index=row,
                selected_memory_column=column,
            )
            state.memory_table_render = rendered
            projected = self.pane_activity_text("MEMORIES", rendered.text)
            self.cases_pane.set_text(projected, anchor="preserve")
            if align_selection and rendered.selected_span is not None:
                self.cases_pane.text_area.buffer.cursor_position = (
                    len(projected) - len(rendered.text) + rendered.cursor_position
                )
            return
        state.memory_table_render = None
        rendered_text = render_ground_memories_pane(state.memory_drafts)
        projected = self.pane_activity_text("MEMORIES", rendered_text)
        self.cases_pane.set_text(projected, anchor="preserve")
        if align_selection and state.memory_drafts:
            marker = projected.find(f"c{row + 1} ")
            if marker >= 0:
                self.cases_pane.text_area.buffer.cursor_position = marker

    def sync_panes(
        self, *, dialogue_anchor: Literal["end", "preserve"] = "end"
    ) -> None:
        state = self.state
        self.sync_pane_titles()
        self.location_pane.set_text(
            render_ground_location_pane(
                state.planned_ground_name,
                source=state.location_source,
            ),
            anchor="preserve",
        )
        self.goal_pane.set_text(
            self.pane_activity_text(
                "GOAL",
                render_ground_goal_pane(
                    state.pending,
                    working_goal=state.editable_goal,
                ),
            ),
            anchor="preserve",
        )
        self.sync_contexts_pane()
        self.rules_pane.set_text(
            self.pane_activity_text(
                "RULES",
                render_ground_rules_pane(state.rule_drafts),
            ),
            anchor="preserve",
        )
        self.sync_memories_pane(align_selection=state.memory_view == "TABLE")
        self.dialogue_pane.set_text(
            self.conversation_text(),
            anchor=dialogue_anchor,
        )

    def focus_conversation(self) -> None:
        self.require_application().layout.focus(self.dialogue_pane.text_area)

    def focus_contexts(self) -> None:
        self.require_application().layout.focus(self.contexts_pane.text_area)

    def focus_message(self) -> None:
        self.require_application().layout.focus(self.input_area)

    def focus_turn_target(self, target: GroundPane) -> None:
        self.require_application().layout.focus(self.pane_for_layer(target).text_area)
        self.state.acknowledge_pane(target)

    def panel_comment_owner_area(self):
        return {
            "GOAL": self.goal_pane.text_area,
            "CONTEXTS": self.contexts_pane.text_area,
            "RULES": self.rules_pane.text_area,
            "MEMORIES": self.cases_pane.text_area,
            "CHAT": self.dialogue_pane.text_area,
        }.get(self.state.panel_comment_target, self.dialogue_pane.text_area)

    def focused_comment_target(self) -> tuple[GroundPane, str] | None:
        if self.has_focus(self.goal_pane.text_area):
            return "GOAL", "GOAL"
        if self.has_focus(self.contexts_pane.text_area):
            return "CONTEXTS", "CONTEXTS"
        if self.has_focus(self.rules_pane.text_area):
            return "RULES", "RULES"
        if self.has_focus(self.cases_pane.text_area):
            return "MEMORIES", "MEMORIES"
        if self.has_focus(self.dialogue_pane.text_area):
            return "CHAT", "CHAT"
        return None

    def acknowledge_focused_read_pane(self) -> None:
        for pane in self.read_panes:
            if self.has_focus(pane):
                self.state.acknowledge_pane(self.focus_layers[id(pane)])
                return

    def cycle_focus(self, step: int) -> None:
        cycle_terminal_focus(
            self.require_application(),
            elements=self.focus_order,
            layers=self.focus_layers,
            acknowledge=self.state.acknowledge_pane,
            step=step,
        )

    def cycle_read_focus(self, step: int) -> None:
        cycle_terminal_focus(
            self.require_application(),
            elements=self.read_panes,
            layers=self.focus_layers,
            acknowledge=self.state.acknowledge_pane,
            step=step,
            default_index=len(self.read_panes) - 1,
        )

    def toggle_memory_view(self) -> None:
        state = self.state
        if not state.memory_drafts:
            return
        state.acknowledge_pane("MEMORIES")
        if state.memory_view == "LIST":
            state.selected_memory_index = (
                self.cases_pane.text_area.buffer.document.cursor_position_row
            )
            state.memory_view = "TABLE"
        else:
            state.memory_view = "LIST"
        self.sync_memories_pane(align_selection=True)
        self.invalidate()

    def move_memory_table_cell(
        self,
        *,
        row_step: int = 0,
        column_step: int = 0,
    ) -> None:
        state = self.state
        state.acknowledge_pane("MEMORIES")
        row, column = clamp_table_position(
            row_count=len(state.memory_drafts),
            column_count=len(_BLANK_MEMORY_TABLE_COLUMNS),
            row=state.selected_memory_index + row_step,
            column=state.selected_memory_column + column_step,
        )
        state.selected_memory_index = row
        state.selected_memory_column = column
        self.sync_memories_pane(align_selection=True)
        self.invalidate()

    def move_context_candidate(self, step: int) -> None:
        candidates = self.ordered_context_rows()
        if not candidates:
            return
        self.state.acknowledge_pane("CONTEXTS")
        self.state.context_candidate_index = max(
            0,
            min(
                self.state.context_candidate_index + step,
                len(candidates) - 1,
            ),
        )
        self.sync_contexts_pane(align_candidate=True)
        self.invalidate()
