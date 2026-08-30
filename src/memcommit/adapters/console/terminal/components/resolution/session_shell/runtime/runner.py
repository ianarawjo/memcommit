"""Lifecycle runner for the shared Resolution Session shell."""

from __future__ import annotations

from collections.abc import Callable

from prompt_toolkit.filters import has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import (
    ConditionalContainer,
    FormattedTextControl,
    HSplit,
    Window,
)
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.output import Output
from prompt_toolkit.widgets import Frame

from memcommit.application.capabilities.review_policy import DecisionFreeBehavior
from memcommit.adapters.console.terminal.components.command_editor.model import CommandReview
from memcommit.adapters.console.terminal.components.multiline_input import (
    build_framed_multiline_input,
)
from memcommit.adapters.console.terminal.core.keybindings import (
    NavigationAccelerator,
)
from memcommit.adapters.console.terminal.core.capabilities import (
    require_interactive_terminal,
)
from memcommit.adapters.console.terminal.components.resolution.compact_shell import (
    run_compact_resolution_decisions,
)
from memcommit.adapters.console.terminal.components.semantic_viewer import (
    SemanticViewerController,
)
from memcommit.adapters.console.terminal.components.impact import ImpactController
from memcommit.application.capabilities.resolution.workbench import (
    ResolutionNavigation,
    ResolutionWorkbenchAction,
    ResolutionWorkbenchView,
)
from memcommit.adapters.console.terminal.components.responses.model import ResponseDraft
from memcommit.persistence.command_ledger.study_actions import record_study_action
from memcommit.application.capabilities.reviewing.session_navigation import (
    SessionWorkbenchNavigation,
)

from memcommit.adapters.console.terminal.components.resolution.session_shell.controller import (
    ResolutionSessionController,
    normalize_decision_free_behavior,
)
from memcommit.adapters.console.terminal.components.resolution.session_shell.runtime.layout import (
    ResolutionShellWidgets,
    build_resolution_shell_layout,
)
from memcommit.adapters.console.terminal.components.resolution.session_shell.runtime.controls import (
    ResolutionControlConfig,
    ResolutionShellControls,
)
from memcommit.adapters.console.terminal.components.resolution.session_shell.runtime.editors import (
    ResolutionEditors,
)
from memcommit.adapters.console.terminal.components.resolution.session_shell.runtime.review_flow import (
    ResolutionReviewFlow,
)
from memcommit.adapters.console.terminal.components.resolution.session_shell.runtime.keymap import (
    ResolutionKeyboardHintState,
    ResolutionKeymapOptions,
    bind_resolution_keymap,
    resolution_keyboard_hint_text,
)


from memcommit.adapters.console.terminal.components.resolution.session_shell.presentation import (
    ResolutionDestination,
    ResolutionGlobalStrategy,
    SessionTodoView,
    _item_draft,
    session_todo_view,
)


def run_resolution_workbench_shell(
    view_or_supplier: (ResolutionWorkbenchView | Callable[[], ResolutionWorkbenchView]),
    *,
    navigation: ResolutionNavigation | None = None,
    workbench_navigation: SessionWorkbenchNavigation | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
    terminal_label: str = "Interactive resolution workbench",
    snapshot_hint: str = (
        "Run the same command outside a TTY to render its saved snapshot."
    ),
    draft_loader: (Callable[[str], tuple[str | None, str]] | None) = None,
    draft_saver: (Callable[[str, str | None, str], None] | None) = None,
    response_validator: Callable[[str], None] | None = None,
    save_draft_on_close: bool = False,
    toggle_sort: Callable[[], None] | None = None,
    split_viewer_items: bool = False,
    global_strategies: tuple[ResolutionGlobalStrategy, ...] = (),
    split_report_text: str | None = None,
    split_report_fragments: tuple[tuple[str, str], ...] | None = None,
    split_report_item_badges: tuple[str, ...] = (),
    split_report_conflicts_remaining: int | None = None,
    review_and_apply: bool = False,
    start_final_review_when_no_required: bool = False,
    decision_free_behavior: DecisionFreeBehavior | None = None,
    read_only: bool = False,
    read_only_handoff: SessionTodoView | None = None,
    item_handoff: SessionTodoView | None = None,
    impact_controller: ImpactController | None = None,
    destination: ResolutionDestination | None = None,
    turn_command_review: (
        Callable[[ResolutionWorkbenchAction], CommandReview | None] | None
    ) = None,
    compact_decisions: bool = False,
) -> ResolutionWorkbenchAction:
    """Collect one UID-bound semantic or close action; never call a provider.

    A workflow may begin at its exact final approval, or return its exact
    Accept action without rendering, when no unanswered REQUIRED decision
    remains. The operation chooses that behavior from its mutation authority
    and recovery boundary.
    """
    if require_tty:
        require_interactive_terminal(
            terminal_label,
            snapshot_hint=snapshot_hint,
        )
    if split_report_fragments is not None and split_report_text is None:
        raise ValueError("Styled split reports require matching plain report text.")
    decision_free_behavior = normalize_decision_free_behavior(
        decision_free_behavior,
        start_final_review_when_no_required=start_final_review_when_no_required,
    )
    current_navigation = navigation or ResolutionNavigation()
    supplier = (
        view_or_supplier if callable(view_or_supplier) else lambda: view_or_supplier
    )
    session_navigation = workbench_navigation or SessionWorkbenchNavigation()
    destination_available = (
        split_viewer_items and destination is not None and not read_only
    )
    if destination is not None and not split_viewer_items:
        raise ValueError("Editable save locations require the split session workbench.")
    if split_viewer_items:
        # A caller may reuse process-local navigation, but a composer cannot be
        # the initial target before the shell has opened an input surface.
        if session_navigation.pane in {"composer", "responses"} or (
            session_navigation.pane == "save_location" and not destination_available
        ):
            session_navigation.focus("viewer")
    else:
        session_navigation.focus("viewer")

    controller = ResolutionSessionController(
        supplier=supplier,
        navigation=current_navigation,
        session_navigation=session_navigation,
        global_strategies=global_strategies,
        review_and_apply=review_and_apply,
        read_only=read_only,
        read_only_handoff=read_only_handoff,
        item_handoff=item_handoff,
        destination=destination,
        draft_saver_available=draft_saver is not None,
    )
    current_view = controller.current_view
    current_item_handoff = controller.current_item_handoff
    current_response_target = controller.current_response_target

    def response_visible() -> bool:
        return controller.response_visible(split_viewer_items=split_viewer_items)

    semantic_action = controller.semantic_action
    response_state = controller.response_state
    input_heading = controller.input_heading
    local_drafts = controller.local_drafts

    viewer_controller = SemanticViewerController(session_navigation)

    controller.seed_drafts(draft_loader)
    shell_controls = ResolutionShellControls(
        controller,
        viewer_controller,
        ResolutionControlConfig(
            split_viewer_items=split_viewer_items,
            global_strategies=global_strategies,
            split_report_text=split_report_text,
            split_report_fragments=split_report_fragments,
            split_report_item_badges=split_report_item_badges,
            split_report_conflicts_remaining=split_report_conflicts_remaining,
            review_and_apply=review_and_apply,
            read_only=read_only,
            impact_controller=impact_controller,
            destination=destination,
            destination_available=destination_available,
        ),
        multiline_input_factory=build_framed_multiline_input,
        frame_factory=Frame,
    )
    bindings = KeyBindings()
    navigation_accelerator = NavigationAccelerator()

    active_viewer_sections = shell_controls.active_viewer_sections
    viewer_section_index = shell_controls.viewer_section_index
    split_kind = shell_controls.split_kind
    focused_impact_entry_uid = shell_controls.focused_impact_entry_uid
    destination_tree_is_focused = shell_controls.destination_tree_is_focused

    composer = shell_controls.composer
    input_area = shell_controls.input_area
    body_control = shell_controls.body_control
    body = shell_controls.body
    responses_control = shell_controls.responses_control
    responses_window = shell_controls.responses_window
    items_control = shell_controls.items_control
    items_window = shell_controls.items_window
    todo_control = shell_controls.todo_control
    todo_window = shell_controls.todo_window
    destination_control = shell_controls.destination_control
    destination_input = shell_controls.destination_input
    destination_frame = shell_controls.destination_frame

    editors = ResolutionEditors(
        controller,
        shell_controls,
        draft_loader=draft_loader,
        draft_saver=draft_saver,
        response_validator=response_validator,
        split_viewer_items=split_viewer_items,
        destination=destination,
        destination_available=destination_available,
    )
    load_draft = editors.load_draft

    review_flow = ResolutionReviewFlow(
        controller,
        shell_controls,
        editors,
        viewer_controller,
        navigation_accelerator,
        split_viewer_items=split_viewer_items,
        global_strategies=global_strategies,
        review_and_apply=review_and_apply,
        read_only=read_only,
        read_only_handoff=read_only_handoff,
        destination_available=destination_available,
        draft_saver_available=draft_saver is not None,
        turn_command_review=turn_command_review,
    )
    open_final_review = review_flow.open_final_review
    final_review_action = review_flow.final_review_action

    bind_resolution_keymap(
        bindings,
        controller,
        shell_controls,
        editors,
        review_flow,
        viewer_controller,
        navigation_accelerator,
        ResolutionKeymapOptions(
            split_viewer_items=split_viewer_items,
            global_strategies=global_strategies,
            review_and_apply=review_and_apply,
            read_only=read_only,
            read_only_handoff=read_only_handoff,
            destination=destination,
            destination_available=destination_available,
            draft_saver=draft_saver,
            response_validator=response_validator,
            save_draft_on_close=save_draft_on_close,
            toggle_sort=toggle_sort,
            app_input=app_input,
            app_output=app_output,
        ),
    )

    keyboard_hint_state = ResolutionKeyboardHintState(
        controller=controller,
        split_viewer_items=split_viewer_items,
        read_only=read_only,
        review_and_apply=review_and_apply,
        toggle_sort_available=toggle_sort is not None,
        split_kind=split_kind,
        destination_tree_is_focused=destination_tree_is_focused,
        focused_impact_entry_uid=focused_impact_entry_uid,
        active_viewer_sections=active_viewer_sections,
        viewer_section_index=viewer_section_index,
        viewer_controller=viewer_controller,
        input_area=input_area,
        destination_input=destination_input,
        body_control=body_control,
    )
    footer = Window(
        FormattedTextControl(
            lambda: (
                f" {controller.status['value']}"
                if controller.status["value"]
                else resolution_keyboard_hint_text(keyboard_hint_state)
            )
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    legacy_inline_input = ConditionalContainer(
        HSplit(
            [
                Window(
                    FormattedTextControl(lambda: input_heading["value"]),
                    height=Dimension.exact(1),
                    char="─",
                ),
                input_area,
            ],
            height=Dimension.exact(5),
        ),
        filter=has_focus(input_area),
    )
    shell_layout = build_resolution_shell_layout(
        ResolutionShellWidgets(
            body=body,
            body_control=body_control,
            legacy_inline_input=legacy_inline_input,
            responses_window=responses_window,
            responses_control=responses_control,
            composer_frame=composer.frame,
            items_window=items_window,
            items_control=items_control,
            destination_frame=destination_frame,
            destination_control=destination_control,
            todo_window=todo_window,
            todo_control=todo_control,
            footer=footer,
        ),
        frame_factory=Frame,
        bindings=bindings,
        session_navigation=session_navigation,
        response_state=response_state,
        current_response_target=current_response_target,
        response_visible=response_visible,
        split_viewer_items=split_viewer_items,
        destination_available=destination_available,
        app_input=app_input,
        app_output=app_output,
    )
    application = shell_layout.application
    viewer_frame = shell_layout.viewer_frame
    shell_controls.attach_viewer_frame(viewer_frame)
    load_draft()

    if (
        decision_free_behavior == "AUTO_ACCEPT"
        and controller.decision_free_apply_available()
    ):
        automatic = semantic_action("ACCEPT")
        if automatic is not None:
            record_study_action(
                "DECISION_FREE_AUTO_ACCEPT",
                surface="resolution",
                action=automatic.kind,
            )
            record_study_action(
                "TUI_ACTION",
                surface="resolution",
                action=automatic.kind,
            )
            return automatic

    if compact_decisions:
        compact_response_changes: set[str] = set()

        def selected_compact_option(item_uid: str) -> str | None:
            item = current_view().item(item_uid)
            return _item_draft(item, local_drafts).selected_choice_uid

        def stage_compact_option(item_uid: str, option_uid: str) -> None:
            item = current_view().item(item_uid)
            item.option(option_uid)
            existing = _item_draft(item, local_drafts)
            draft = ResponseDraft(option_uid, existing.text)
            # A compact choice is process-local until Apply/Continue consumes
            # it. Closing this surface must not manufacture a durable draft.
            local_drafts[item_uid] = draft

        def compact_response_text(item_uid: str) -> str:
            item = current_view().item(item_uid)
            return _item_draft(item, local_drafts).text

        def stage_compact_response(item_uid: str, text: str) -> None:
            item = current_view().item(item_uid)
            existing = _item_draft(item, local_drafts)
            # Response text follows the same process-local boundary as compact
            # choices. Continue consumes it; opening or closing this surface
            # must not manufacture a durable draft.
            local_drafts[item_uid] = ResponseDraft(
                existing.selected_choice_uid,
                text,
            )
            compact_response_changes.add(item_uid)

        def compact_continue_action(
            focused_item_uid: str | None,
        ) -> ResolutionWorkbenchAction | None:
            active_view = current_view()
            changed_responses = tuple(
                item
                for item in active_view.items
                if item.uid in compact_response_changes
            )
            if changed_responses and global_strategies:
                action = final_review_action(active_view, open_custom=False)
                if action is not None:
                    return action
            if changed_responses:
                item = next(
                    (
                        candidate
                        for candidate in changed_responses
                        if candidate.uid == focused_item_uid
                    ),
                    changed_responses[0],
                )
                draft = _item_draft(item, local_drafts)
                if draft.selected_choice_uid is None and not draft.text.strip():
                    return None
                return semantic_action(
                    "SUBMIT_ITEM",
                    item_uid=item.uid,
                    option_uid=draft.selected_choice_uid,
                    comment=draft.text,
                )
            action = final_review_action(active_view, open_custom=False)
            if action is not None:
                return action
            if focused_item_uid is None:
                return None
            draft = _item_draft(active_view.item(focused_item_uid), local_drafts)
            if draft.selected_choice_uid is None and not draft.text.strip():
                return None
            return semantic_action(
                "SUBMIT_ITEM",
                item_uid=focused_item_uid,
                option_uid=draft.selected_choice_uid,
                comment=draft.text,
            )

        def compact_continue_label() -> str:
            todo = session_todo_view(
                current_view(),
                local_drafts,
                review_and_apply=review_and_apply,
                read_only=read_only,
                whole_set_available=bool(global_strategies),
                read_only_handoff=read_only_handoff,
                item_handoff=current_item_handoff(),
            )
            return {
                "REVIEW AND APPLY": "Apply",
                "RESOLVE ALL": "Continue",
                "COMPLETE": "Close",
            }.get(todo.kind, "Submit selected")

        return run_compact_resolution_decisions(
            current_view,
            selected_option=selected_compact_option,
            stage_option=stage_compact_option,
            response_text=compact_response_text,
            stage_response=stage_compact_response,
            response_validator=response_validator,
            build_continue_action=compact_continue_action,
            continue_label=compact_continue_label,
            destination=destination,
            app_input=app_input,
            app_output=app_output,
        )

    def open_initial_final_review() -> None:
        if (
            decision_free_behavior == "FINAL_REVIEW"
            and controller.decision_free_apply_available()
        ):
            open_final_review()

    try:
        result = application.run(pre_run=open_initial_final_review)
    except (EOFError, KeyboardInterrupt):
        result = ResolutionWorkbenchAction(kind="CLOSE")
    record_study_action(
        "TUI_ACTION",
        surface="resolution",
        action=result.kind,
    )
    return result
