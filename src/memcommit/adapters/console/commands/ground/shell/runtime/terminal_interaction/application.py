"""Prompt-toolkit application composed from the blank-Ground runtime owners."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable, Sequence
from dataclasses import replace

from prompt_toolkit.application import Application, run_in_terminal
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import (
    DynamicContainer,
    FormattedTextControl,
    Layout,
    Window,
)
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.output import Output
from prompt_toolkit.widgets import Frame as _DefaultFrame

from memcommit.adapters.console.terminal.components.progress import (
    BUSY_FRAMES,
    BUSY_INTERVAL_SECONDS,
)
from memcommit.adapters.console.terminal.components.session_help import (
    bind_session_help,
)
from memcommit.adapters.console.terminal.core.capabilities import (
    require_interactive_terminal,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.adapters.console.terminal.components.exact_command_review import (
    bind_exact_command_approval,
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
    build_inline_direct_edit_input as _default_inline_direct_edit_input,
    classify_inline_edit_submission,
)
from memcommit.adapters.console.terminal.components.multiline_input import (
    build_framed_multiline_input as _default_framed_multiline_input,
)
from memcommit.adapters.console.terminal.components.scrollable_pane import (
    build_scrollable_text_pane as _default_scrollable_text_pane,
    equal_pane_height,
    scroll_wrapped_page,
)
from memcommit.adapters.console.terminal.components.table import (
    SelectedTableCellProcessor,
    clamp_table_position,
)
from memcommit.adapters.console.terminal.core.keybindings import (
    bind_case_insensitive_key,
    dispatch_tui_back,
)
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    MEMCOMMIT_TUI_STYLE,
)
from memcommit.application.operations.ground.model import (
    GroundError,
    validate_ground_goal,
)
from memcommit.core.context_targeting.naming import validate_portable_context_name
from memcommit.core.context_targeting.tui.picker import choose_context

from memcommit.adapters.console.commands.ground.shell.presentation import (
    _BLANK_MEMORY_TABLE_COLUMNS,
    _agent_block,
    _render_ground_memory_table,
    _render_proposal_command_block,
    _render_proposal_effects_block,
    render_ground_contexts_pane as _default_render_ground_contexts_pane,
    render_ground_goal_pane,
    render_ground_location_pane,
    render_ground_memories_pane,
    render_ground_rules_pane,
    render_ground_workspace_pane,
)
from memcommit.adapters.console.commands.ground.shell.proposal import (
    GroundApplier,
    GroundInterpreter,
    GroundShellProposal,
    GroundShellResult,
)
from memcommit.adapters.console.commands.ground.shell.runtime.context_selection import (
    GroundContextCandidateRow,
    candidate_row_at,
    initial_candidate_index,
    ordered_context_rows as build_ordered_context_rows,
    toggle_selected_context,
)
from memcommit.adapters.console.commands.ground.shell.runtime.grounding_drafting import (
    freeze_grounding_response,
    interpret_from_background_thread,
)
from memcommit.adapters.console.commands.ground.shell.runtime.session import (
    GroundPane,
    GroundShellState,
    prepare_ground_shell_start,
)
from memcommit.adapters.console.commands.ground.shell.runtime.terminal_interaction.activity import (
    pane_activity_text as project_pane_activity,
    pane_thinking_verb,
    pane_turn_label,
)
from memcommit.adapters.console.commands.ground.shell.runtime.terminal_interaction.focus import (
    cycle_focus as cycle_terminal_focus,
)


INITIAL_QUESTION = "What are you trying to understand, decide, or make together?"
GROUND_GOAL_FRAME_HEIGHT = Dimension(min=3, preferred=5, max=5)
# CONTEXTS is the first-turn orientation and selection surface. Its preferred
# outer height leaves five body rows, while the shared three-row minimum lets
# prompt-toolkit compress it to one body row on a conventional 24-row terminal.
GROUND_CONTEXTS_FRAME_HEIGHT = Dimension(min=3, preferred=7, max=10)
GROUND_LOCATION_FRAME_HEIGHT = Dimension.exact(3)
# Compatibility aliases remain patchable by focused shell tests while Ground
# shares the same liveness vocabulary and cadence as blocking commands.
_THINKING_SUFFIXES = BUSY_FRAMES
_THINKING_INTERVAL_SECONDS = BUSY_INTERVAL_SECONDS


def run_ground_shell(
    *,
    interpret: GroundInterpreter,
    apply: GroundApplier,
    ground_name: str | None = None,
    initial_request: str = "",
    initial_proposal: GroundShellProposal | None = None,
    initial_submitted_turns: Sequence[str] = (),
    current_context_name: str | None = None,
    context_catalog_count: int = 0,
    context_catalog_names: Sequence[str] = (),
    validate_new_context: Callable[[str], str] = validate_portable_context_name,
    choose_save_location: Callable[[str | None], str | None] | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
    background_interpretation: bool = True,
) -> GroundShellResult:
    """Run the blank-Ground dialogue until one command is applied or cancelled."""
    # Keep the historical runtime-module monkeypatch seams even though runtime
    # is now a package. Focused interaction tests and downstream adapters may
    # replace these factories before constructing one Application.
    runtime_facade = sys.modules[__package__.rsplit(".", 1)[0]]
    Frame = getattr(runtime_facade, "Frame", _DefaultFrame)
    build_scrollable_text_pane = getattr(
        runtime_facade,
        "build_scrollable_text_pane",
        _default_scrollable_text_pane,
    )
    build_framed_multiline_input = getattr(
        runtime_facade,
        "build_framed_multiline_input",
        _default_framed_multiline_input,
    )
    build_inline_direct_edit_input = getattr(
        runtime_facade,
        "build_inline_direct_edit_input",
        _default_inline_direct_edit_input,
    )
    render_ground_contexts_pane = getattr(
        runtime_facade,
        "render_ground_contexts_pane",
        _default_render_ground_contexts_pane,
    )
    thinking_interval_seconds = getattr(
        runtime_facade,
        "_THINKING_INTERVAL_SECONDS",
        _THINKING_INTERVAL_SECONDS,
    )
    if require_tty:
        require_interactive_terminal(
            "Interactive Ground",
            snapshot_hint=("Run 'mem ground' in a terminal or use a snapshot mode."),
        )

    start = prepare_ground_shell_start(
        ground_name=ground_name,
        initial_request=initial_request,
        initial_proposal=initial_proposal,
        initial_submitted_turns=initial_submitted_turns,
        context_catalog_count=context_catalog_count,
        context_catalog_names=context_catalog_names,
    )
    fixed_ground_name = start.fixed_ground_name
    frozen_initial_proposal = start.frozen_initial_proposal
    frozen_initial_turns = start.frozen_initial_turns
    working_goal = start.working_goal
    state = GroundShellState.create(
        fixed_ground_name=fixed_ground_name,
        initial_proposal=frozen_initial_proposal,
        initial_turns=frozen_initial_turns,
        working_goal=working_goal,
        context_catalog_count=context_catalog_count,
        initial_question=INITIAL_QUESTION,
    )
    # Liveness begins only when ``begin_interpretation`` records the owning
    # pane. Rendering it earlier would briefly revive the legacy assumption
    # that every initial Goal turn belongs to Context discovery.
    # A badge means that this process received a new result for a pane after
    # the person's last explicit visit. It deliberately does not mean that a
    # Ground layer is complete or agreed: Ground has no implicit completion
    # criterion, and focus chosen by the program must not dismiss a result.
    mark_pane_updates = state.mark_pane_updates
    acknowledge_pane = state.acknowledge_pane

    bindings = KeyBindings()
    # Goal is an orientation statement, not a document surface. Three body
    # rows are enough for the 40-word authoring contract; longer legacy or
    # provisional text remains inspectable through this pane's scrollbar.
    # Rules, Memories, and Chat absorb the remaining reading space after
    # the compact Goal and bounded Contexts panel. Their independent
    # scrollbars still bound content growth, while leaving max unset avoids a
    # dead band below ACTION on taller terminals.
    pane_height = equal_pane_height(
        minimum=3,
        preferred=4,
    )
    message_height = Dimension(min=3, preferred=4, max=5)
    embedded_field_height = Dimension(min=1, preferred=2, max=3)
    conversation_pane_height = Dimension(min=5, preferred=7)
    direct_edit_pane_height = Dimension(min=7, preferred=9)
    approval_action_height = Dimension.exact(4)
    compact_action_height = Dimension.exact(3)

    def current_thinking_suffix() -> str:
        return _THINKING_SUFFIXES[state.thinking_phase]

    def pane_activity_text(target: GroundPane, base: str) -> str:
        return project_pane_activity(
            target,
            base,
            state.pane_activities[target],
        )

    def ordered_context_rows() -> tuple[GroundContextCandidateRow, ...]:
        return build_ordered_context_rows(
            fixed_ground_name=fixed_ground_name,
            suggestions=state.context_suggestions,
            new_suggestions=state.new_context_suggestions,
            current_context_name=current_context_name,
            discovery_complete=state.context_discovery_complete,
            direct_context_names=context_catalog_names,
        )

    def reset_context_candidate_cursor() -> None:
        state.context_candidate_index = initial_candidate_index(ordered_context_rows())

    def context_cursor_row() -> GroundContextCandidateRow | None:
        state.context_candidate_index, row = candidate_row_at(
            ordered_context_rows(),
            state.context_candidate_index,
        )
        return row

    def candidate_cursor_name() -> str | None:
        row = context_cursor_row()
        return row.context_name if row is not None else None

    location_pane = build_scrollable_text_pane(
        "LOCATION",
        render_ground_location_pane(
            state.planned_ground_name,
            source=state.location_source,
        ),
        buffer_name="ground-new-location",
        height=GROUND_LOCATION_FRAME_HEIGHT,
        notification=lambda: state.pane_notifications["LOCATION"],
    )
    goal_pane = build_scrollable_text_pane(
        "GOAL",
        pane_activity_text(
            "GOAL",
            render_ground_goal_pane(
                frozen_initial_proposal,
                working_goal=state.editable_goal,
            ),
        ),
        buffer_name="ground-new-goal",
        height=GROUND_GOAL_FRAME_HEIGHT,
        notification=lambda: state.pane_notifications["GOAL"],
    )
    contexts_pane = build_scrollable_text_pane(
        "CONTEXTS",
        (
            render_ground_contexts_pane(
                current_context_name=current_context_name,
                catalog_count=context_catalog_count,
                discovery_in_progress=state.context_discovery_in_progress,
                thinking_suffix=current_thinking_suffix(),
            )
            if context_catalog_count
            else render_ground_workspace_pane(state.planned_ground_name)
        ),
        buffer_name="ground-new-contexts",
        height=GROUND_CONTEXTS_FRAME_HEIGHT,
        notification=lambda: state.pane_notifications["CONTEXTS"],
    )
    rules_pane = build_scrollable_text_pane(
        "RULES",
        render_ground_rules_pane(state.rule_drafts),
        buffer_name="ground-new-rules",
        height=pane_height,
        notification=lambda: state.pane_notifications["RULES"],
    )
    cases_pane = build_scrollable_text_pane(
        "MEMORIES",
        render_ground_memories_pane(state.memory_drafts),
        buffer_name="ground-new-cases",
        height=pane_height,
        notification=lambda: state.pane_notifications["MEMORIES"],
    )
    # LIST preserves wrapped cards. TABLE uses logical rows and lets the
    # selected-cell cursor drive horizontal scrolling like a spreadsheet.
    cases_pane.text_area.window.wrap_lines = Condition(
        lambda: state.memory_view == "LIST"
    )
    cases_pane.text_area.control.input_processors.append(
        SelectedTableCellProcessor(
            lambda: (
                state.memory_table_render.selected_span
                if state.memory_view == "TABLE"
                and state.memory_table_render is not None
                else None
            )
        )
    )

    def conversation_text() -> str:
        blocks = list(state.conversation)
        proposal = state.pending
        if proposal is not None:
            if state.review_view == "EFFECTS":
                blocks.append(
                    _render_proposal_effects_block(
                        proposal,
                        has_local_new_context=bool(state.local_new_context_name),
                    )
                )
            else:
                blocks.append(
                    _render_proposal_command_block(proposal),
                )
        if state.error_message and state.active_turn_target == "CHAT":
            blocks.append(
                "INTERPRETATION FAILED · NOTHING APPLIED\n"
                f"  {safe_terminal_text(state.error_message)}"
            )
        return "\n\n".join(blocks)

    dialogue_pane = build_scrollable_text_pane(
        "CHAT",
        conversation_text(),
        buffer_name="ground-new-dialogue",
        height=pane_height,
        notification=lambda: state.pane_notifications["CHAT"],
    )
    composer = build_framed_multiline_input(
        "MESSAGE",
        prompt="› ",
        buffer_name="ground-new-message",
        height=message_height,
    )
    input_area = composer.text_area
    direct_editor = build_inline_direct_edit_input(
        buffer_name="ground-new-direct-edit",
    )
    direct_edit_area = direct_editor.text_area

    header = Window(
        FormattedTextControl(" MEM GROUND · DRAFT"),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    approval_panel = Frame(
        Window(
            FormattedTextControl(
                "CHAT: ←/↑ cmd · →/↓ fx\nEnter apply · A also · E/B/Q"
            ),
            wrap_lines=True,
        ),
        title="ACTION",
        height=approval_action_height,
    )
    error_panel = Frame(
        Window(
            FormattedTextControl("R retry · E refine · B/Q"),
            wrap_lines=True,
        ),
        title="ACTION",
        height=compact_action_height,
    )
    apply_error_panel = Frame(
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

    def footer_text() -> str:
        active_mode = state.mode
        if state.panel_comment_target is not None:
            target = state.panel_comment_target
            return (
                f" Enter · send {pane_turn_label(target).lower()}    "
                "Ctrl-J · newline    "
                "Esc · collapse"
            )
        if state.inline_context_open:
            if application.layout.has_focus(direct_edit_area):
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
        contexts_focused = application.layout.has_focus(contexts_pane.text_area)
        memories_focused = application.layout.has_focus(cases_pane.text_area)
        location_focused = application.layout.has_focus(location_pane.text_area)
        input_focused = application.layout.has_focus(input_area)
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
            and bool(ordered_context_rows())
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
            if active_mode == "INPUT" and application.layout.has_focus(
                goal_pane.text_area
            ):
                return (
                    " Enter · talk here    E · edit Goal    L · location    "
                    "B · Grounds    Q · quit"
                )
            return (
                " Enter · talk here    C · same action    L · location    "
                "B · Grounds    Q · quit"
            )
        if active_mode == "APPROVAL":
            row = context_cursor_row()
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

    footer = Window(
        FormattedTextControl(footer_text),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )

    normal_root = build_tui_frame(
        TuiRegion(header),
        TuiRegion(location_pane.container),
        TuiRegion(goal_pane.container),
        TuiRegion(contexts_pane.container),
        TuiRegion(rules_pane.container),
        TuiRegion(cases_pane.container),
        TuiRegion(dialogue_pane.container),
        TuiRegion(action_panel),
        TuiRegion(footer),
    )
    # The same Message buffer is embedded in whichever semantic pane owns the
    # current exchange. This preserves one continuous conversational surface
    # without introducing a detached sixth panel or duplicating input state.
    input_manager = InFrameInputManager(
        goal_pane,
        contexts_pane,
        rules_pane,
        cases_pane,
        dialogue_pane,
    )

    def pane_for_layer(layer: GroundPane):
        return {
            "LOCATION": location_pane,
            "GOAL": goal_pane,
            "CONTEXTS": contexts_pane,
            "RULES": rules_pane,
            "MEMORIES": cases_pane,
            "CHAT": dialogue_pane,
        }.get(layer, dialogue_pane)

    def sync_pane_titles() -> None:
        base_titles: dict[GroundPane, str] = {
            "LOCATION": "LOCATION",
            "GOAL": "GOAL",
            "CONTEXTS": "CONTEXTS",
            "RULES": "RULES",
            "MEMORIES": "MEMORIES",
            "CHAT": "CHAT",
        }
        for target, title in base_titles.items():
            activity = state.pane_activities[target]
            pane_for_layer(target).frame.title = (
                f"{title} · THINKING{current_thinking_suffix()} · "
                f"{pane_thinking_verb(target)}"
                if activity.phase == "THINKING"
                else title
            )

    def sync_input_host() -> None:
        input_manager.clear()
        if state.inline_goal_open:
            input_manager.show(
                goal_pane,
                InFrameInputSection(
                    "EDIT (DIRECTLY)",
                    direct_edit_area,
                    height=embedded_field_height,
                ),
                InFrameInputSection(
                    INLINE_AGENT_COMMENT_TITLE,
                    input_area,
                    height=embedded_field_height,
                ),
                height=direct_edit_pane_height,
            )
            return
        if state.inline_context_open:
            input_manager.show(
                contexts_pane,
                InFrameInputSection(
                    "EDIT (DIRECTLY)",
                    direct_edit_area,
                    height=embedded_field_height,
                ),
                InFrameInputSection(
                    INLINE_AGENT_COMMENT_TITLE,
                    input_area,
                    height=embedded_field_height,
                ),
                height=direct_edit_pane_height,
            )
            return
        if state.panel_comment_target is not None:
            target = state.panel_comment_target
            input_manager.show(
                pane_for_layer(target),
                InFrameInputSection(
                    pane_turn_label(target),
                    input_area,
                    height=embedded_field_height,
                ),
                height=conversation_pane_height,
            )
            return
        if state.mode in {"INPUT", "CONTEXT_SELECTION"}:
            input_manager.show(
                dialogue_pane,
                InFrameInputSection(
                    "MESSAGE",
                    input_area,
                    height=embedded_field_height,
                ),
                height=conversation_pane_height,
            )

    sync_input_host()
    application: Application[GroundShellResult] = Application(
        layout=Layout(
            normal_root,
            # Ground is Goal-first. The general Message composer remains one
            # explicit Tab stop, but opening the workbench must not visually
            # or semantically make Chat the primary entry surface.
            focused_element=goal_pane.text_area,
        ),
        key_bindings=bindings,
        full_screen=True,
        # Make the reading contract explicit instead of relying on
        # prompt-toolkit deriving page navigation from full_screen mode.
        enable_page_navigation_bindings=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
        style=MEMCOMMIT_TUI_STYLE,
    )
    # Ground does not bind Alt-prefixed actions, so a short escape-sequence
    # timeout improves the dedicated cancel key without creating ambiguity.
    application.ttimeoutlen = 0.05

    for pane in (
        location_pane,
        goal_pane,
        contexts_pane,
        rules_pane,
        cases_pane,
        dialogue_pane,
    ):
        bind_focused_frame_style(
            pane.frame,
            is_focused=lambda pane=pane: application.layout.has_focus(pane.frame),
        )

    def sync_contexts_pane(*, align_candidate: bool = False) -> None:
        if (
            not context_catalog_count
            and not state.context_suggestions
            and not state.new_context_suggestions
        ):
            contexts_pane.set_text(
                pane_activity_text(
                    "CONTEXTS",
                    render_ground_workspace_pane(state.planned_ground_name),
                ),
                anchor="preserve",
            )
            return
        cursor_row = context_cursor_row()
        cursor_name = cursor_row.context_name if cursor_row is not None else None
        rendered = render_ground_contexts_pane(
            state.context_suggestions,
            new_context_suggestions=state.new_context_suggestions,
            current_context_name=current_context_name,
            catalog_count=context_catalog_count,
            discovery_complete=state.context_discovery_complete,
            # The active pane's title owns the liveness cue. Keeping the old
            # Context-body spinner as well would duplicate THINKING and make a
            # Goal-owned turn look like Context discovery.
            discovery_in_progress=False,
            thinking_suffix=current_thinking_suffix(),
            candidate_cursor_name=cursor_name,
            candidate_cursor_kind=(cursor_row.kind if cursor_row is not None else None),
            selected_context_names=state.selected_context_names,
            local_new_context_name=state.local_new_context_name,
            selection_finished=state.context_selection_finished,
            direct_context_names=context_catalog_names,
        )
        projected = pane_activity_text("CONTEXTS", rendered)
        contexts_pane.set_text(projected, anchor="preserve")
        if align_candidate and cursor_name is not None:
            marker = projected.find("› ")
            if marker >= 0:
                # The TextArea stays read-only; moving its cursor only asks
                # prompt-toolkit to keep the highlighted logical row visible.
                contexts_pane.text_area.buffer.cursor_position = marker

    def sync_memories_pane(*, align_selection: bool = False) -> None:
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
            projected = pane_activity_text("MEMORIES", rendered.text)
            cases_pane.set_text(
                projected,
                anchor="preserve",
            )
            if align_selection and rendered.selected_span is not None:
                cases_pane.text_area.buffer.cursor_position = (
                    len(projected) - len(rendered.text) + rendered.cursor_position
                )
            return
        state.memory_table_render = None
        rendered_text = render_ground_memories_pane(state.memory_drafts)
        projected = pane_activity_text("MEMORIES", rendered_text)
        cases_pane.set_text(
            projected,
            anchor="preserve",
        )
        if align_selection and state.memory_drafts:
            marker = projected.find(f"c{row + 1} ")
            if marker >= 0:
                cases_pane.text_area.buffer.cursor_position = marker

    def sync_panes(*, dialogue_anchor: str = "end") -> None:
        sync_pane_titles()
        location_pane.set_text(
            render_ground_location_pane(
                state.planned_ground_name,
                source=state.location_source,
            ),
            anchor="preserve",
        )
        goal_pane.set_text(
            pane_activity_text(
                "GOAL",
                render_ground_goal_pane(
                    state.pending,
                    working_goal=state.editable_goal,
                ),
            ),
            anchor="preserve",
        )
        sync_contexts_pane()
        rules_pane.set_text(
            pane_activity_text(
                "RULES",
                render_ground_rules_pane(state.rule_drafts),
            ),
            anchor="preserve",
        )
        sync_memories_pane(align_selection=state.memory_view == "TABLE")
        dialogue_pane.set_text(
            conversation_text(),
            anchor=dialogue_anchor,
        )

    def focus_conversation() -> None:
        application.layout.focus(dialogue_pane.text_area)

    def focus_contexts() -> None:
        application.layout.focus(contexts_pane.text_area)

    def focus_turn_target(target: GroundPane) -> None:
        application.layout.focus(pane_for_layer(target).text_area)
        acknowledge_pane(target)

    def focus_input(*, restore: bool) -> None:
        state.mode = "INPUT"
        state.pending = None
        state.suspended_context_proposal = None
        state.review_view = "COMMAND"
        state.error_message = ""
        state.status_message = ""
        if restore:
            input_area.text = state.last_submission
            input_area.buffer.cursor_position = len(input_area.text)
        else:
            input_area.text = ""
        sync_input_host()
        sync_panes(dialogue_anchor="end")
        application.layout.focus(input_area)
        application.invalidate()

    def dialogue_payload() -> str:
        return (
            state.submitted_turns[0]
            if len(state.submitted_turns) == 1
            else "\n\n".join(
                f"USER TURN {index}\n{turn}"
                for index, turn in enumerate(
                    state.submitted_turns,
                    start=1,
                )
            )
        )

    def finish_interpretation(
        response: object,
        *,
        append_user: bool,
        initial: bool,
        turn_target: GroundPane,
    ) -> None:
        drafted = freeze_grounding_response(
            response,
            planned_ground_name=state.planned_ground_name,
            context_catalog_count=context_catalog_count,
        )
        kind = drafted.kind
        understanding = drafted.understanding
        question = drafted.question
        frozen_contexts = drafted.context_suggestions
        frozen_new_contexts = drafted.new_context_suggestions
        frozen_rule_drafts = drafted.rule_drafts
        frozen_memory_drafts = drafted.memory_drafts
        state.context_suggestions = frozen_contexts
        state.new_context_suggestions = frozen_new_contexts
        state.rule_drafts = frozen_rule_drafts
        state.memory_drafts = frozen_memory_drafts
        # A focused turn belongs to its originating pane. Other panes receive
        # badges only when the response actually changed their semantic data;
        # the same request is never duplicated into Chat as presentation.
        mark_pane_updates(turn_target)
        if fixed_ground_name is None:
            mark_pane_updates("CONTEXTS")
        if frozen_rule_drafts:
            mark_pane_updates("RULES")
        if frozen_memory_drafts:
            mark_pane_updates("MEMORIES")
        if kind != "ASK":
            mark_pane_updates("GOAL")
        state.selected_memory_index = 0
        state.selected_memory_column = 0
        reset_context_candidate_cursor()
        state.selected_context_names = ()
        state.context_selection_finished = False
        state.context_discovery_in_progress = False
        state.context_discovery_complete = True
        activity = state.pane_activities[turn_target]
        activity.phase = "NEEDS_CLARIFICATION" if kind == "ASK" else "PROPOSED"
        activity.detail = question if kind == "ASK" else ""
        if turn_target == "CHAT" and (append_user or initial):
            state.conversation.append(
                _agent_block(
                    understanding=understanding,
                    question=question,
                )
            )
        elif turn_target == "CHAT":
            state.conversation.append(
                "\n".join(
                    [
                        "AGENT RETRY",
                        f"  {safe_terminal_text(understanding)}",
                        "",
                        "AGENT QUESTION",
                        f"  {safe_terminal_text(question)}",
                    ]
                )
            )
        state.error_message = ""
        state.status_message = ""
        if kind == "ASK":
            focus_input(restore=False)
            if frozen_contexts or frozen_new_contexts:
                sync_contexts_pane(align_candidate=True)
                focus_contexts()
                application.invalidate()
            elif turn_target != "CHAT":
                state.status_message = (
                    f"{turn_target.title()} revision needs clarification · "
                    "Enter to continue in this pane."
                )
                sync_panes(dialogue_anchor="preserve")
                focus_turn_target(turn_target)
                application.invalidate()
            return
        frozen = drafted.proposal
        if frozen is None:
            raise AssertionError("A PROPOSE turn must freeze one Ground proposal.")
        if state.planned_ground_name is None:
            # The provider may suggest a portable initial location, but the
            # persistent LOCATION pane keeps it visibly unapproved and lets
            # the person replace it through the shared Context tree.
            state.planned_ground_name = frozen.ground_name
            state.location_source = "SUGGESTED"
            mark_pane_updates("LOCATION", "CONTEXTS")
        else:
            # A person-owned local location plan outranks later provider
            # naming. The exact command is always rebuilt from this value.
            frozen = replace(
                frozen,
                ground_name=state.planned_ground_name,
            )
        exact_goal = state.required_direct_goal
        if exact_goal is not None and frozen.goal != exact_goal:
            raise ValueError(
                "The provider rewrote the directly edited Goal; no command "
                "was prepared."
            )
        if exact_goal is None:
            state.pending_inline_goal = None
        state.editable_goal = frozen.goal
        state.pending = frozen
        state.review_view = "COMMAND"
        state.mode = (
            "CONTEXT_SELECTION"
            if frozen_contexts or frozen_new_contexts
            else "APPROVAL"
        )
        input_area.text = ""
        sync_input_host()
        sync_panes(dialogue_anchor="end")
        if frozen_contexts or frozen_new_contexts:
            sync_contexts_pane(align_candidate=True)
            focus_contexts()
        elif turn_target != "CHAT":
            state.status_message = (
                f"{turn_target.title()} revision proposed · inspect this pane; "
                "Tab to CHAT for the exact command review."
            )
            focus_turn_target(turn_target)
        else:
            focus_conversation()
        application.invalidate()

    def fail_interpretation(error: Exception, *, turn_target: GroundPane) -> None:
        state.pending = None
        state.suspended_context_proposal = None
        state.context_suggestions = ()
        state.new_context_suggestions = ()
        state.rule_drafts = ()
        state.memory_drafts = ()
        state.selected_memory_index = 0
        state.selected_memory_column = 0
        state.memory_table_render = None
        state.context_candidate_index = 0
        state.selected_context_names = ()
        state.local_new_context_name = ""
        state.context_selection_finished = False
        state.context_discovery_in_progress = False
        state.context_discovery_complete = False
        state.error_message = f"{type(error).__name__}: {error}"
        activity = state.pane_activities[turn_target]
        activity.phase = "FAILED"
        activity.detail = state.error_message
        state.status_message = ""
        mark_pane_updates(turn_target)
        if fixed_ground_name is None:
            mark_pane_updates("CONTEXTS")
        state.mode = "ERROR"
        sync_input_host()
        sync_panes(dialogue_anchor="end")
        focus_turn_target(turn_target)
        application.invalidate()

    async def interpret_in_background(
        text: str,
        *,
        append_user: bool,
        initial: bool,
        turn_target: GroundPane,
    ) -> None:
        try:
            response = await interpret_from_background_thread(
                interpret,
                text,
            )
            if state.shell_closed:
                return
            finish_interpretation(
                response,
                append_user=append_user,
                initial=initial,
                turn_target=turn_target,
            )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            if not state.shell_closed:
                fail_interpretation(error, turn_target=turn_target)

    async def animate_thinking(generation: int) -> None:
        """Animate the title of the pane that owns the active semantic turn."""
        while (
            not state.shell_closed
            and state.context_discovery_in_progress
            and state.interpretation_generation == generation
        ):
            await asyncio.sleep(thinking_interval_seconds)
            if (
                state.shell_closed
                or not state.context_discovery_in_progress
                or state.interpretation_generation != generation
            ):
                return
            state.thinking_phase = (state.thinking_phase + 1) % len(_THINKING_SUFFIXES)
            # Title-only liveness preserves every pane's independent viewport
            # and keeps the cue above, rather than below, the owned request.
            sync_pane_titles()
            application.invalidate()

    def begin_interpretation(
        text: str,
        *,
        append_user: bool,
        initial: bool = False,
        preserve_local_new_context: bool = False,
        turn_target: GroundPane = "CHAT",
        turn_display: str | None = None,
    ) -> None:
        if append_user:
            state.submitted_turns.append(text)
            if turn_target == "CHAT":
                state.conversation.append(
                    f"YOU\n  {safe_terminal_text(turn_display or text)}"
                )
        state.active_turn_target = turn_target
        activity = state.pane_activities[turn_target]
        activity.phase = "THINKING"
        activity.request = (turn_display or text).strip()
        activity.detail = ""
        payload = dialogue_payload()
        state.pending = None
        state.suspended_context_proposal = None
        state.context_suggestions = ()
        state.new_context_suggestions = ()
        state.rule_drafts = ()
        state.memory_drafts = ()
        state.selected_memory_index = 0
        state.selected_memory_column = 0
        state.memory_table_render = None
        state.context_candidate_index = 0
        state.selected_context_names = ()
        if not preserve_local_new_context:
            state.local_new_context_name = ""
        state.context_selection_finished = False
        state.context_discovery_complete = False
        state.context_discovery_in_progress = True
        state.thinking_phase = 0
        state.interpretation_generation += 1
        generation = state.interpretation_generation
        state.error_message = ""
        state.status_message = ""
        state.mode = "INTERPRETING"
        sync_input_host()
        sync_panes(dialogue_anchor="end")
        focus_turn_target(turn_target)
        application.invalidate()
        if background_interpretation:
            application.create_background_task(animate_thinking(generation))
            application.create_background_task(
                interpret_in_background(
                    payload,
                    append_user=append_user,
                    initial=initial,
                    turn_target=turn_target,
                )
            )
            return
        try:
            finish_interpretation(
                interpret(payload),
                append_user=append_user,
                initial=initial,
                turn_target=turn_target,
            )
        except Exception as error:
            fail_interpretation(error, turn_target=turn_target)

    def collapse_inline_goal(
        event: object | None = None,
        *,
        focus_goal: bool = True,
    ) -> bool:
        if not state.inline_goal_open:
            return False
        state.inline_goal_open = False
        state.inline_goal_original = ""
        direct_edit_area.text = ""
        composer.frame.title = "MESSAGE"
        input_area.text = state.suspended_message
        state.suspended_message = ""
        sync_input_host()
        if focus_goal:
            application.layout.focus(goal_pane.text_area)
        if event is not None:
            getattr(event, "app").invalidate()
        else:
            application.invalidate()
        return True

    def collapse_inline_context(
        event: object | None = None,
        *,
        focus_contexts_after: bool = True,
    ) -> bool:
        if not state.inline_context_open:
            return False
        state.inline_context_open = False
        state.inline_context_original = ""
        direct_edit_area.text = ""
        composer.frame.title = "MESSAGE"
        input_area.text = state.suspended_message
        state.suspended_message = ""
        sync_input_host()
        if focus_contexts_after:
            focus_contexts()
        if event is not None:
            getattr(event, "app").invalidate()
        else:
            application.invalidate()
        return True

    def panel_comment_owner_area():
        return {
            "GOAL": goal_pane.text_area,
            "CONTEXTS": contexts_pane.text_area,
            "RULES": rules_pane.text_area,
            "MEMORIES": cases_pane.text_area,
            "CHAT": dialogue_pane.text_area,
        }.get(state.panel_comment_target, dialogue_pane.text_area)

    def collapse_panel_comment(
        event: object | None = None,
        *,
        focus_owner: bool = True,
    ) -> bool:
        if state.panel_comment_target is None:
            return False
        owner = panel_comment_owner_area()
        state.panel_comment_target = None
        state.panel_comment_focus = ""
        composer.frame.title = "MESSAGE"
        input_area.text = state.suspended_message
        state.suspended_message = ""
        sync_input_host()
        if focus_owner:
            application.layout.focus(owner)
        if event is not None:
            getattr(event, "app").invalidate()
        else:
            application.invalidate()
        return True

    def open_panel_comment(
        *,
        target: GroundPane,
        focus: str,
    ) -> None:
        if state.mode not in {"INPUT", "CONTEXT_SELECTION"}:
            return
        acknowledge_pane(target)
        if target == "CHAT":
            # Chat already contains the ordinary Message field. Entering it
            # changes focus only and adds no synthetic FOCUS marker.
            application.layout.focus(input_area)
            application.invalidate()
            return
        state.suspended_message = input_area.text
        input_area.text = ""
        state.panel_comment_target = target
        state.panel_comment_focus = focus
        composer.frame.title = pane_turn_label(target)
        state.status_message = ""
        sync_input_host()
        application.layout.focus(input_area)
        application.invalidate()

    def finish_panel_comment() -> None:
        target = state.panel_comment_target
        if target is None:
            return
        comment = input_area.text.strip()
        if not comment:
            state.status_message = "Enter a nonblank agent comment first."
            application.invalidate()
            return
        focus = state.panel_comment_focus or target
        # Only the panel label and raw comment cross the blank-Ground boundary.
        # Provider-authored preview text is deliberately excluded so it cannot
        # be mistaken for USER_EXACT evidence on this follow-up turn.
        payload = "\n".join(
            [
                f"FOCUS · {focus}",
                INLINE_AGENT_COMMENT_TITLE,
                comment,
            ]
        )
        state.suspended_message = ""
        collapse_panel_comment(focus_owner=False)
        state.last_submission = payload
        state.last_submission_target = target
        state.last_submission_display = comment
        begin_interpretation(
            payload,
            append_user=True,
            turn_target=target,
            turn_display=comment,
        )

    def restore_suspended_context_approval(
        event: object | None = None,
    ) -> bool:
        proposal = state.suspended_context_proposal
        if (
            proposal is None
            or state.inline_context_open
            or state.mode != "CONTEXT_SELECTION"
        ):
            return False
        state.pending = proposal
        state.suspended_context_proposal = None
        state.mode = "APPROVAL"
        sync_input_host()
        state.status_message = (
            "Local Context edit cancelled; exact Ground approval restored."
        )
        sync_panes(dialogue_anchor="end")
        focus_contexts()
        if event is not None:
            getattr(event, "app").invalidate()
        else:
            application.invalidate()
        return True

    def complete_context_plan(*, allow_empty: bool = False) -> bool:
        selected = state.selected_context_names
        new_name = state.local_new_context_name
        if not selected and not new_name and not allow_empty:
            state.status_message = (
                "Select an existing Context with Space or enter a new "
                "Context name first."
            )
            application.invalidate()
            return False
        state.context_selection_finished = True
        sync_contexts_pane()
        parts = []
        if selected:
            parts.append(f"{len(selected)} existing")
        if new_name:
            parts.append("1 new local name")
        summary = " + ".join(parts) or "No Context plan"
        suspended = state.suspended_context_proposal
        if suspended is not None:
            state.pending = suspended
            state.suspended_context_proposal = None
            state.mode = "APPROVAL"
            sync_input_host()
            state.status_message = (
                f"{summary}. The Ground command is ready for a fresh Enter."
            )
            sync_panes(dialogue_anchor="end")
            focus_conversation()
            application.invalidate()
            return True
        if state.mode == "CONTEXT_SELECTION" and state.pending is not None:
            # Context planning never expands the frozen creation command. A
            # future Context init and frame bind remain separate approvals.
            state.mode = "APPROVAL"
            sync_input_host()
            state.status_message = (
                f"{summary}. Enter approves only the Ground name and Goal."
            )
            focus_conversation()
        else:
            state.status_message = f"{summary}. Continue in Message."
            application.layout.focus(input_area)
        application.invalidate()
        return True

    def open_inline_context(*, prefill: str) -> None:
        if state.mode not in {"INPUT", "CONTEXT_SELECTION"}:
            return
        acknowledge_pane("CONTEXTS")
        state.inline_context_original = prefill
        state.suspended_message = input_area.text
        input_area.text = ""
        direct_edit_area.text = prefill
        direct_edit_area.buffer.cursor_position = len(prefill)
        composer.frame.title = INLINE_AGENT_COMMENT_TITLE
        state.inline_context_open = True
        state.status_message = ""
        sync_input_host()
        application.layout.focus(direct_edit_area)
        application.invalidate()

    def finish_inline_context() -> None:
        original = state.inline_context_original
        edited = direct_edit_area.text
        comment = input_area.text.strip()
        submission_kind = classify_inline_edit_submission(
            original=original,
            edited=edited,
            comment=comment,
        )
        if submission_kind == "NOOP" and original:
            # Opening NEW? with N and submitting it unchanged is an explicit
            # acceptance
            # of that proposed exact name, even though no byte changed.
            submission_kind = "DIRECT"
        if submission_kind == "NOOP":
            collapse_inline_context(focus_contexts_after=True)
            state.status_message = "No Context name or agent comment was submitted."
            application.invalidate()
            return
        if submission_kind in {"DIRECT", "BOTH"}:
            try:
                exact_name = validate_new_context(edited)
            except (OSError, ValueError) as error:
                state.status_message = safe_terminal_text(str(error))
                application.invalidate()
                return
            if not isinstance(exact_name, str) or not exact_name:
                state.status_message = (
                    "The new Context validator returned no exact name."
                )
                application.invalidate()
                return
            state.local_new_context_name = exact_name
            state.conversation.append(
                "\n".join(
                    [
                        "YOU · NEW CONTEXT NAME (DIRECTLY)",
                        f"  {safe_terminal_text(exact_name)}",
                        "  PLANNED CONTEXT · NOT CREATED",
                    ]
                )
            )
        else:
            exact_name = ""

        state.suspended_message = ""
        collapse_inline_context(focus_contexts_after=False)
        if comment:
            # The agent receives the comment, never the catalog suggestion or
            # exact local name. Those remain process-local orientation and do
            # not become hidden provider evidence on a follow-up turn.
            blocks = [
                "FOCUS · NEW CONTEXT PLANNING",
                INLINE_AGENT_COMMENT_TITLE,
                comment,
            ]
            payload = "\n".join(blocks)
            state.last_submission = payload
            state.last_submission_target = "CONTEXTS"
            state.last_submission_display = comment
            begin_interpretation(
                payload,
                append_user=True,
                preserve_local_new_context=bool(exact_name),
                turn_target="CONTEXTS",
                turn_display=comment,
            )
            return
        sync_panes(dialogue_anchor="end")
        complete_context_plan()

    def open_inline_goal() -> None:
        if state.mode != "INPUT":
            return
        acknowledge_pane("GOAL")
        original = state.editable_goal
        state.inline_goal_original = original
        state.suspended_message = input_area.text
        input_area.text = ""
        direct_edit_area.text = original
        direct_edit_area.buffer.cursor_position = len(original)
        composer.frame.title = INLINE_AGENT_COMMENT_TITLE
        state.inline_goal_open = True
        state.status_message = ""
        sync_input_host()
        application.layout.focus(direct_edit_area)
        application.invalidate()

    def finish_inline_goal() -> None:
        original = state.inline_goal_original
        edited = direct_edit_area.text
        comment = input_area.text.strip()
        submission_kind = classify_inline_edit_submission(
            original=original,
            edited=edited,
            comment=comment,
        )
        if submission_kind == "NOOP":
            collapse_inline_goal(focus_goal=True)
            state.status_message = "No edit or agent comment was submitted."
            application.invalidate()
            return
        if submission_kind in {"DIRECT", "BOTH"}:
            try:
                exact_goal = validate_ground_goal(
                    edited,
                    label="directly edited Ground goal",
                )
            except GroundError as error:
                state.status_message = safe_terminal_text(str(error))
                application.invalidate()
                return
            state.editable_goal = exact_goal
            state.required_direct_goal = exact_goal
            state.pending_inline_goal = (
                original,
                exact_goal,
                comment,
            )
            blocks = [
                "FOCUS · GOAL",
                "EDIT (DIRECTLY) · PRESERVE EXACTLY",
                exact_goal,
            ]
            if comment:
                blocks.extend(
                    [
                        "",
                        INLINE_AGENT_COMMENT_TITLE,
                        comment,
                    ]
                )
            payload = "\n".join(blocks)
            turn_display = (
                f"DIRECT GOAL\n{exact_goal}\n\n{comment}"
                if comment
                else f"DIRECT GOAL\n{exact_goal}"
            )
        else:
            state.pending_inline_goal = None
            blocks = ["FOCUS · GOAL"]
            if state.editable_goal:
                blocks.extend(
                    [
                        "CURRENT GOAL · DRAFT",
                        state.editable_goal,
                    ]
                )
            blocks.extend([INLINE_AGENT_COMMENT_TITLE, comment])
            payload = "\n".join(blocks)
            turn_display = comment
        state.suspended_message = ""
        collapse_inline_goal(focus_goal=False)
        state.last_submission = payload
        state.last_submission_target = "GOAL"
        state.last_submission_display = turn_display
        begin_interpretation(
            payload,
            append_user=True,
            turn_target="GOAL",
            turn_display=turn_display,
        )

    input_mode = Condition(lambda: state.mode == "INPUT")
    context_selection_mode = Condition(lambda: state.mode == "CONTEXT_SELECTION")
    inline_goal_mode = Condition(
        lambda: state.mode == "INPUT" and state.inline_goal_open
    )
    inline_context_mode = Condition(
        lambda: state.mode in {"INPUT", "CONTEXT_SELECTION"}
        and state.inline_context_open
    )
    inline_edit_mode = inline_goal_mode | inline_context_mode
    panel_comment_mode = Condition(
        lambda: state.mode in {"INPUT", "CONTEXT_SELECTION"}
        and state.panel_comment_target is not None
    )
    normal_input_mode = input_mode & ~inline_edit_mode & ~panel_comment_mode
    navigation_mode = (
        (normal_input_mode | context_selection_mode)
        & ~inline_edit_mode
        & ~panel_comment_mode
    )
    approval_mode = Condition(lambda: state.mode == "APPROVAL")
    approval_dialogue_focus = approval_mode & has_focus(dialogue_pane.text_area)
    error_mode = Condition(lambda: state.mode == "ERROR")
    action_mode = Condition(lambda: state.mode in {"APPROVAL", "ERROR", "APPLY_ERROR"})
    read_panes = (
        location_pane.text_area,
        goal_pane.text_area,
        contexts_pane.text_area,
        rules_pane.text_area,
        cases_pane.text_area,
        dialogue_pane.text_area,
    )
    read_pane_focus = (
        has_focus(location_pane.text_area)
        | has_focus(goal_pane.text_area)
        | has_focus(contexts_pane.text_area)
        | has_focus(rules_pane.text_area)
        | has_focus(cases_pane.text_area)
        | has_focus(dialogue_pane.text_area)
    )
    memory_pane_focus = (
        has_focus(cases_pane.text_area)
        & ~inline_edit_mode
        & Condition(lambda: bool(state.memory_drafts))
    )
    memory_table_focus = memory_pane_focus & Condition(
        lambda: state.memory_view == "TABLE"
    )
    inline_field_focus = inline_edit_mode & (
        has_focus(direct_edit_area) | has_focus(input_area)
    )
    # Preserve visual top-to-bottom order. Starting at Goal makes Shift-Tab
    # reach Location immediately, while ordinary Tab proceeds through the
    # semantic workbench and eventually wraps through Message and Location.
    focus_order = (*read_panes, input_area)
    focus_layers = {
        id(input_area): "CHAT",
        id(location_pane.text_area): "LOCATION",
        id(goal_pane.text_area): "GOAL",
        id(contexts_pane.text_area): "CONTEXTS",
        id(rules_pane.text_area): "RULES",
        id(cases_pane.text_area): "MEMORIES",
        id(dialogue_pane.text_area): "CHAT",
    }

    def acknowledge_focused_read_pane() -> None:
        for pane in read_panes:
            if application.layout.has_focus(pane):
                acknowledge_pane(focus_layers[id(pane)])
                return

    context_candidate_focus = (
        navigation_mode
        & has_focus(contexts_pane.text_area)
        & Condition(lambda: bool(ordered_context_rows()))
        & Condition(lambda: not state.context_selection_finished)
    )
    finished_context_focus = (
        (input_mode | approval_mode)
        & has_focus(contexts_pane.text_area)
        & Condition(
            lambda: bool(ordered_context_rows()) or bool(state.local_new_context_name)
        )
        & Condition(lambda: state.context_selection_finished)
    )
    approval_context_add_focus = (
        approval_mode
        & has_focus(contexts_pane.text_area)
        & Condition(lambda: not state.context_selection_finished)
        & Condition(
            lambda: (
                context_cursor_row() is not None
                and context_cursor_row().kind == "ADD_NEW"
            )
        )
    )
    location_focus = has_focus(location_pane.text_area)
    location_edit_available = (
        (input_mode | approval_mode)
        & read_pane_focus
        & ~inline_edit_mode
        & ~panel_comment_mode
    )

    def choose_or_change_save_location(event) -> None:
        """Expand the focused compact Location into the shared tree editor."""

        acknowledge_pane("LOCATION")
        if choose_save_location is None:
            state.status_message = (
                "Save Location editing is unavailable in this adapter."
            )
            event.app.invalidate()
            return

        async def choose() -> None:
            result = await run_in_terminal(
                lambda: choose_save_location(state.planned_ground_name),
                in_executor=True,
            )
            if result is None:
                state.status_message = "Save Location change cancelled."
                application.invalidate()
                return
            exact_name = validate_portable_context_name(result)
            state.planned_ground_name = exact_name
            state.location_source = "SELECTED"
            if state.pending is not None:
                state.pending = replace(
                    state.pending,
                    ground_name=exact_name,
                )
            if state.suspended_context_proposal is not None:
                state.suspended_context_proposal = replace(
                    state.suspended_context_proposal,
                    ground_name=exact_name,
                )
            mark_pane_updates("LOCATION", "CONTEXTS", "CHAT")
            state.status_message = (
                f"Save Location selected · {safe_terminal_text(exact_name)} "
                "· NOT CREATED."
            )
            sync_panes(dialogue_anchor="end")
            application.invalidate()

        event.app.create_background_task(choose())

    @bindings.add("l", filter=location_edit_available, eager=True)
    @bindings.add("L", filter=location_edit_available, eager=True)
    def _choose_or_change_save_location(event) -> None:
        choose_or_change_save_location(event)

    @bindings.add(
        "enter",
        filter=location_edit_available & location_focus,
        eager=True,
    )
    def _expand_focused_save_location(event) -> None:
        choose_or_change_save_location(event)

    def cycle_focus(step: int) -> None:
        cycle_terminal_focus(
            application,
            elements=focus_order,
            layers=focus_layers,
            acknowledge=acknowledge_pane,
            step=step,
        )

    def cycle_read_focus(step: int) -> None:
        cycle_terminal_focus(
            application,
            elements=read_panes,
            layers=focus_layers,
            acknowledge=acknowledge_pane,
            step=step,
            default_index=len(read_panes) - 1,
        )

    @bindings.add("tab", filter=navigation_mode, eager=True)
    def _focus_next(_event) -> None:
        cycle_focus(1)

    @bindings.add(Keys.BackTab, filter=navigation_mode, eager=True)
    def _focus_previous(_event) -> None:
        cycle_focus(-1)

    @bindings.add("tab", filter=inline_edit_mode, eager=True)
    @bindings.add(Keys.BackTab, filter=inline_edit_mode, eager=True)
    def _cycle_inline_edit_fields(event) -> None:
        target = (
            input_area
            if event.app.layout.has_focus(direct_edit_area)
            else direct_edit_area
        )
        event.app.layout.focus(target)
        event.app.invalidate()

    @bindings.add(
        "tab",
        filter=~navigation_mode & ~inline_edit_mode & ~panel_comment_mode,
        eager=True,
    )
    def _focus_next_modal_pane(_event) -> None:
        # The composer is replaced by ACTION in modal states, but browsing a
        # read-only pane cannot edit or implicitly approve the frozen command.
        cycle_read_focus(1)

    @bindings.add(
        Keys.BackTab,
        filter=~navigation_mode & ~inline_edit_mode & ~panel_comment_mode,
        eager=True,
    )
    def _focus_previous_modal_pane(_event) -> None:
        cycle_read_focus(-1)

    @bindings.add(Keys.PageDown, filter=read_pane_focus, eager=True)
    def _page_down(event) -> None:
        acknowledge_focused_read_pane()
        scroll_wrapped_page(event, direction=1)

    @bindings.add(Keys.PageUp, filter=read_pane_focus, eager=True)
    def _page_up(event) -> None:
        acknowledge_focused_read_pane()
        scroll_wrapped_page(event, direction=-1)

    def focused_comment_target() -> tuple[str, str] | None:
        if application.layout.has_focus(goal_pane.text_area):
            return "GOAL", "GOAL"
        if application.layout.has_focus(contexts_pane.text_area):
            return "CONTEXTS", "CONTEXTS"
        if application.layout.has_focus(rules_pane.text_area):
            return "RULES", "RULES"
        if application.layout.has_focus(cases_pane.text_area):
            return "MEMORIES", "MEMORIES"
        if application.layout.has_focus(dialogue_pane.text_area):
            return "CHAT", "CHAT"
        return None

    @bindings.add(
        "c",
        filter=navigation_mode & read_pane_focus,
        eager=True,
    )
    def _open_focused_comment(_event) -> None:
        selected = focused_comment_target()
        if selected is None:
            return
        target, focus = selected
        open_panel_comment(target=target, focus=focus)

    def toggle_memory_view() -> None:
        if not state.memory_drafts:
            return
        acknowledge_pane("MEMORIES")
        if state.memory_view == "LIST":
            state.selected_memory_index = (
                cases_pane.text_area.buffer.document.cursor_position_row
            )
            state.memory_view = "TABLE"
        else:
            state.memory_view = "LIST"
        sync_memories_pane(align_selection=True)
        application.invalidate()

    def move_memory_table_cell(*, row_step: int = 0, column_step: int = 0) -> None:
        acknowledge_pane("MEMORIES")
        row, column = clamp_table_position(
            row_count=len(state.memory_drafts),
            column_count=len(_BLANK_MEMORY_TABLE_COLUMNS),
            row=state.selected_memory_index + row_step,
            column=state.selected_memory_column + column_step,
        )
        state.selected_memory_index = row
        state.selected_memory_column = column
        sync_memories_pane(align_selection=True)
        application.invalidate()

    @bindings.add("v", filter=memory_pane_focus, eager=True)
    def _toggle_memory_view(_event) -> None:
        toggle_memory_view()

    @bindings.add("down", filter=memory_table_focus, eager=True)
    def _next_memory_table_row(_event) -> None:
        move_memory_table_cell(row_step=1)

    @bindings.add("up", filter=memory_table_focus, eager=True)
    def _previous_memory_table_row(_event) -> None:
        move_memory_table_cell(row_step=-1)

    @bindings.add("right", filter=memory_table_focus, eager=True)
    def _next_memory_table_column(_event) -> None:
        move_memory_table_cell(column_step=1)

    @bindings.add("left", filter=memory_table_focus, eager=True)
    def _previous_memory_table_column(_event) -> None:
        move_memory_table_cell(column_step=-1)

    def move_context_candidate(step: int) -> None:
        candidates = ordered_context_rows()
        if not candidates:
            return
        acknowledge_pane("CONTEXTS")
        state.context_candidate_index = max(
            0,
            min(
                state.context_candidate_index + step,
                len(candidates) - 1,
            ),
        )
        sync_contexts_pane(align_candidate=True)
        application.invalidate()

    @bindings.add("down", filter=context_candidate_focus, eager=True)
    def _next_context_candidate(_event) -> None:
        move_context_candidate(1)

    @bindings.add("up", filter=context_candidate_focus, eager=True)
    def _previous_context_candidate(_event) -> None:
        move_context_candidate(-1)

    @bindings.add(" ", filter=context_candidate_focus, eager=True)
    def _toggle_context_candidate(event) -> None:
        acknowledge_pane("CONTEXTS")
        row = context_cursor_row()
        if row is None:
            return
        if row.kind != "EXISTING":
            state.status_message = (
                "Press F to continue without a Context plan."
                if row.kind == "CONTINUE_EMPTY"
                else (
                    "Press P to open the direct ordinary Context tree."
                    if row.kind == "DIRECT_PICK"
                    else (
                        "Press N to edit this new Context name; Space "
                        "selects existing Contexts only."
                    )
                )
            )
            event.app.invalidate()
            return
        selected_name = row.context_name
        # Selection order is meaningful only inside this view: the first
        # checked name is the local Main and later names are additional hints.
        # Actual frame roles still require a separate binding.
        state.selected_context_names = toggle_selected_context(
            state.selected_context_names,
            selected_name,
        )
        sync_contexts_pane(align_candidate=True)
        state.status_message = (
            f"{len(state.selected_context_names)} Context(s) selected for this draft."
        )
        event.app.invalidate()

    @bindings.add("p", filter=context_candidate_focus, eager=True)
    @bindings.add("P", filter=context_candidate_focus, eager=True)
    def _direct_context_picker(event) -> None:
        if not context_catalog_names:
            state.status_message = "No ordinary Context names are available."
            event.app.invalidate()
            return

        async def choose() -> None:
            selected = state.selected_context_names
            result = await run_in_terminal(
                lambda: choose_context(
                    tuple(context_catalog_names),
                    current=(
                        selected[-1]
                        if selected and selected[-1] in context_catalog_names
                        else current_context_name
                    ),
                    app_input=app_input,
                    app_output=app_output,
                    require_tty=require_tty,
                ),
                # The nested picker owns a synchronous prompt-toolkit
                # Application. Run it off the outer Ground event loop so its
                # internal asyncio.run() remains valid.
                in_executor=True,
            )
            if result is None:
                state.status_message = "Direct Context selection cancelled."
            else:
                names = list(state.selected_context_names)
                if result not in names:
                    names.append(result)
                state.selected_context_names = tuple(names)
                state.status_message = (
                    f"{len(names)} Context(s) selected for this draft."
                )
                sync_contexts_pane(align_candidate=True)
            application.invalidate()

        event.app.create_background_task(choose())

    @bindings.add("n", filter=context_candidate_focus, eager=True)
    def _edit_context_name_plan(event) -> None:
        row = context_cursor_row()
        if row is None:
            return
        if row.kind == "NEW_SUGGESTION":
            open_inline_context(prefill=row.context_name)
            return
        if row.kind == "ADD_NEW":
            open_inline_context(prefill=state.local_new_context_name)
            return
        state.status_message = (
            "N edits NEW? or ADD NEW CONTEXT; Space selects existing Contexts."
        )
        event.app.invalidate()

    @bindings.add("f", filter=context_candidate_focus, eager=True)
    def _finish_context_selection(_event) -> None:
        acknowledge_pane("CONTEXTS")
        row = context_cursor_row()
        if row is not None and row.kind == "CONTINUE_EMPTY":
            state.local_new_context_name = ""
            complete_context_plan(allow_empty=True)
            return
        complete_context_plan()

    @bindings.add(
        "f",
        filter=finished_context_focus,
        eager=True,
    )
    def _reopen_context_selection(event) -> None:
        # Reopening changes only process-local checkmarks. The frozen Ground
        # creation argv remains pending and cannot run until a later Enter.
        state.context_selection_finished = False
        state.mode = "CONTEXT_SELECTION"
        sync_input_host()
        state.status_message = (
            "Context plan reopened · Space selects existing · F finishes · "
            "N edits a new name."
        )
        sync_contexts_pane(align_candidate=True)
        focus_contexts()
        event.app.invalidate()

    @bindings.add(
        "n",
        filter=approval_context_add_focus,
        eager=True,
    )
    def _open_add_context_from_approval(event) -> None:
        proposal = state.pending
        if proposal is None:
            return
        # N explicitly leaves the exact-approval layer before opening an
        # editor. The unchanged receipt is restored only after the local name
        # passes validation, so no pane editor coexists with approval mode.
        state.suspended_context_proposal = proposal
        state.pending = None
        state.mode = "CONTEXT_SELECTION"
        state.review_view = "COMMAND"
        state.status_message = (
            "Ground approval suspended while editing a local Context name."
        )
        sync_panes(dialogue_anchor="end")
        open_inline_context(prefill=state.local_new_context_name)
        event.app.invalidate()

    @bindings.add(
        "enter",
        filter=(
            navigation_mode & read_pane_focus & ~has_focus(location_pane.text_area)
        ),
        eager=True,
    )
    def _talk_in_focused_pane(_event) -> None:
        selected = focused_comment_target()
        if selected is None:
            return
        target, focus = selected
        open_panel_comment(target=target, focus=focus)

    @bindings.add(
        "e",
        filter=normal_input_mode & has_focus(goal_pane.text_area),
        eager=True,
    )
    def _open_goal_editor(_event) -> None:
        open_inline_goal()

    @bindings.add("enter", filter=inline_field_focus, eager=True)
    def _submit_inline_edit(_event) -> None:
        if state.inline_context_open:
            finish_inline_context()
        else:
            finish_inline_goal()

    @bindings.add(
        "enter",
        filter=panel_comment_mode & has_focus(input_area),
        eager=True,
    )
    def _submit_panel_comment(_event) -> None:
        finish_panel_comment()

    @bindings.add(
        "enter",
        filter=(has_focus(input_area) & ~inline_edit_mode & ~panel_comment_mode),
        eager=True,
    )
    def _submit(event) -> None:
        text = input_area.text.strip()
        if not text:
            state.status_message = "Enter a nonblank description first."
            event.app.invalidate()
            return
        state.status_message = ""
        acknowledge_pane("CHAT")
        state.last_submission = text
        state.last_submission_target = "CHAT"
        state.last_submission_display = text
        input_area.text = ""
        begin_interpretation(
            text,
            append_user=True,
            turn_target="CHAT",
            turn_display=text,
        )

    @bindings.add(
        "c-j",
        filter=(
            (has_focus(input_area) & ~inline_edit_mode)
            | (inline_goal_mode & inline_field_focus)
            | (inline_context_mode & has_focus(input_area))
        ),
        eager=True,
    )
    def _insert_newline(event) -> None:
        event.app.current_buffer.insert_text("\n")
        event.app.invalidate()

    @bindings.add(
        "c-j",
        filter=inline_context_mode & has_focus(direct_edit_area),
        eager=True,
    )
    def _reject_newline_in_context_name(event) -> None:
        state.status_message = (
            "Context names are one line; press Tab to add a multiline comment."
        )
        event.app.invalidate()

    @bind_exact_command_approval(
        bindings,
        filter=approval_dialogue_focus,
        legacy_a_filter=approval_mode,
        eager=True,
    )
    def _approve(event) -> None:
        if state.mode != "APPROVAL" or state.pending is None:
            return
        # Freeze the reference before calling out.  Repeated keypresses cannot
        # approve another command because a successful call exits this app.
        proposal = state.pending
        state.mode = "APPLYING"
        event.app.invalidate()
        try:
            actual_output = apply(proposal)
        except Exception as error:
            state.conversation.append(
                "\n".join(
                    [
                        "APPLY FAILED",
                        f"  {safe_terminal_text(type(error).__name__)}: "
                        f"{safe_terminal_text(str(error))}",
                        "",
                        "The same approval will not be retried automatically.",
                    ]
                )
            )
            state.error_message = ""
            mark_pane_updates("CHAT")
            state.mode = "APPLY_ERROR"
            sync_panes(dialogue_anchor="end")
            focus_conversation()
            event.app.invalidate()
            return
        event.app.exit(
            result=state.result(
                "APPLIED",
                proposal=proposal,
                actual_output=actual_output,
            )
        )

    @bindings.add("up", filter=approval_dialogue_focus, eager=True)
    @bindings.add("left", filter=approval_dialogue_focus, eager=True)
    def _show_command(event) -> None:
        if state.mode != "APPROVAL":
            return
        acknowledge_pane("CHAT")
        state.review_view = "COMMAND"
        sync_panes(dialogue_anchor="end")
        event.app.invalidate()

    @bindings.add("down", filter=approval_dialogue_focus, eager=True)
    @bindings.add("right", filter=approval_dialogue_focus, eager=True)
    def _show_effects(event) -> None:
        if state.mode != "APPROVAL":
            return
        acknowledge_pane("CHAT")
        state.review_view = "EFFECTS"
        sync_panes(dialogue_anchor="end")
        event.app.invalidate()

    @bindings.add("e", filter=action_mode, eager=True)
    def _refine(event) -> None:
        if state.mode not in {
            "CONTEXT_SELECTION",
            "APPROVAL",
            "ERROR",
            "APPLY_ERROR",
        }:
            return
        previous_mode = state.mode
        inline_draft = state.pending_inline_goal
        if state.pending is not None:
            # Refinement explicitly discards the frozen creation receipt, but
            # retains its reviewed Goal as the next editable unsaved draft.
            state.editable_goal = state.pending.goal
        state.conversation.append(
            "REFINEMENT\n  Previous proposal or interpretation returned for revision."
        )
        if inline_draft is not None and previous_mode in {
            "CONTEXT_SELECTION",
            "APPROVAL",
            "ERROR",
        }:
            original, edited, comment = inline_draft
            focus_input(restore=False)
            open_inline_goal()
            # Reopen the same authority-bearing fields.  Treating the
            # host-framed exact edit as an ordinary Message would silently
            # downgrade it into provider-authored wording on resubmission.
            state.inline_goal_original = original
            direct_edit_area.text = edited
            direct_edit_area.buffer.cursor_position = len(edited)
            input_area.text = comment
            input_area.buffer.cursor_position = len(comment)
            event.app.invalidate()
            return
        if inline_draft is not None and previous_mode == "APPLY_ERROR":
            # The external command may have reached its mutation boundary
            # even though the shell did not receive confirmation.  Never
            # recreate the same direct proposal from an uncertain result.
            state.pending_inline_goal = None
            state.required_direct_goal = None
            focus_input(restore=False)
            state.status_message = (
                "The direct Goal edit was discarded after an unconfirmed "
                "apply; reopen Goal before proposing it again."
            )
            event.app.invalidate()
            return
        focus_input(restore=True)

    @bindings.add("r", filter=error_mode, eager=True)
    def _retry(event) -> None:
        if state.mode != "ERROR":
            return
        state.error_message = ""
        begin_interpretation(
            state.last_submission,
            append_user=False,
            turn_target=state.last_submission_target,
            turn_display=state.last_submission_display,
        )

    def cancel(event) -> None:
        # Executor-backed provider work may finish after Escape. The closed
        # flag makes its result observationally inert: no proposal, apply, or
        # state mutation can occur after this shell has left the screen.
        state.shell_closed = True
        event.app.exit(result=state.result("CANCELLED"))

    @bindings.add("b", filter=read_pane_focus, eager=True)
    def _back_to_picker(event) -> None:
        # Returning to the launcher never applies the pending creation
        # receipt. It does carry the exact validated proposal so the caller
        # can publish a separately typed NOT CREATED resume receipt first.
        state.shell_closed = True
        event.app.exit(result=state.result("BACK_TO_PICKER"))

    @bind_case_insensitive_key(bindings, "q", filter=read_pane_focus, eager=True)
    def _quit_ground(event) -> None:
        cancel(event)

    bind_session_help(
        bindings,
        filter=read_pane_focus,
        app_input=app_input,
        app_output=app_output,
        study_surface="ground",
    )

    @bindings.add("escape", eager=True)
    def _cancel_on_escape(event) -> None:
        dispatch_tui_back(
            event,
            collapse_panel_comment,
            collapse_inline_context,
            collapse_inline_goal,
            restore_suspended_context_approval,
            close=cancel,
        )

    @bindings.add("c-c", eager=True)
    @bindings.add(Keys.SIGINT, eager=True)
    def _cancel_anywhere(event) -> None:
        cancel(event)

    def start_initial_turn() -> None:
        # The positional request is already USER TURN 1. Scheduling provider
        # work only after the event loop starts makes target-owned THINKING
        # visible, while keeping Escape responsive during the read-only call.
        begin_interpretation(
            working_goal,
            append_user=False,
            initial=True,
            turn_target="GOAL",
            turn_display=working_goal,
        )

    try:
        if initial_request.strip():
            state.submitted_turns.append(working_goal)
            if background_interpretation:
                return application.run(pre_run=start_initial_turn)
            start_initial_turn()
        return application.run()
    except (EOFError, KeyboardInterrupt):
        return state.result("CANCELLED")
    finally:
        state.shell_closed = True
