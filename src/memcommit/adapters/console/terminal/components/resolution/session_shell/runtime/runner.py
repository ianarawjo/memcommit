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
from memcommit.adapters.console.terminal.components.command_editor.model import (
    CommandReview,
)
from memcommit.adapters.console.terminal.components.multiline_input import (
    build_framed_multiline_input,
)
from memcommit.adapters.console.terminal.core.keybindings import (
    NavigationAccelerator,
)
from memcommit.adapters.console.terminal.core.capabilities import (
    require_interactive_terminal,
)
from memcommit.adapters.console.terminal.components.semantic_viewer import (
    SemanticViewerController,
)
from memcommit.adapters.console.terminal.components.resolution.effect_preview import (
    EffectPreviewSource,
    EffectReportPresentation,
)
from memcommit.application.capabilities.resolution.workbench import (
    ResolutionNavigation,
    ResolutionWorkbenchAction,
    ResolutionWorkbenchView,
)
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
    report_apply: bool = False,
    start_final_review_when_no_required: bool = False,
    decision_free_behavior: DecisionFreeBehavior | None = None,
    read_only: bool = False,
    read_only_handoff: SessionTodoView | None = None,
    item_handoff: SessionTodoView | None = None,
    impact_controller: EffectPreviewSource | None = None,
    effect_report: EffectReportPresentation | None = None,
    destination: ResolutionDestination | None = None,
    turn_command_review: (
        Callable[[ResolutionWorkbenchAction], CommandReview | None] | None
    ) = None,
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
    if effect_report is not None and (
        not (report_apply or read_only)
        or not split_viewer_items
        or review_and_apply
        or global_strategies
        or item_handoff is not None
        or impact_controller is None
        or split_report_text is not None
        or destination is not None
        or draft_loader is not None
        or draft_saver is not None
        or decision_free_behavior is not None
        or start_final_review_when_no_required
    ):
        raise ValueError("An effect report requires an exact preview and explicit Apply or read-only inspection.")
    if report_apply and (
        not split_viewer_items
        or review_and_apply
        or read_only
        or global_strategies
    ):
        raise ValueError(
            "Report Apply requires the full writable report without a "
            "separate review or resolution strategy."
        )
    decision_free_behavior = normalize_decision_free_behavior(
        decision_free_behavior,
        start_final_review_when_no_required=start_final_review_when_no_required,
    )
    current_navigation = navigation or ResolutionNavigation()
    supplier = (
        view_or_supplier if callable(view_or_supplier) else lambda: view_or_supplier
    )
    session_navigation = workbench_navigation or SessionWorkbenchNavigation()
    if effect_report is not None:
        session_navigation.focus("viewer")
        session_navigation.row_index = 0
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
        report_apply=report_apply,
        report_apply_label=effect_report.apply_label if effect_report else "APPLY",
        read_only=read_only,
        read_only_handoff=read_only_handoff,
        item_handoff=item_handoff,
        destination=destination,
        draft_saver_available=draft_saver is not None,
    )
    current_view = controller.current_view
    if report_apply and "ACCEPT" not in current_view().capabilities:
        raise ValueError("Report Apply requires the ACCEPT capability.")
    if effect_report is not None and (
        current_view().items
        or current_view().capabilities != (frozenset() if read_only else frozenset({"ACCEPT"}))
    ):
        raise ValueError("An effect report cannot hide actionable review items.")
    current_response_target = controller.current_response_target

    def response_visible() -> bool:
        return controller.response_visible(split_viewer_items=split_viewer_items)

    semantic_action = controller.semantic_action
    response_state = controller.response_state
    input_heading = controller.input_heading

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
            report_apply=report_apply,
            read_only=read_only,
            impact_controller=impact_controller,
            effect_report=effect_report,
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

    def footer_text() -> str:
        if controller.status["value"]:
            return f" {controller.status['value']}"
        if effect_report is not None:
            if read_only:
                if session_navigation.pane == "todo":
                    return " Enter open Apply workflow · Tab viewer · Esc close"
                return (
                    " ↑/↓ move · Enter expand/collapse · ←/→ hide/show"
                    + (" · Tab Apply workflow" if read_only_handoff is not None else "")
                    + " · Esc close"
                )
            return (
                " ↑/↓ move · Enter apply · Tab viewer · Esc cancel"
                if session_navigation.pane == "todo"
                else " ↑/↓ move · Enter expand/collapse · ←/→ hide/show · Tab Apply · Esc cancel"
            )
        return resolution_keyboard_hint_text(keyboard_hint_state)

    footer = Window(
        FormattedTextControl(footer_text),
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
            todo_title="APPLY" if report_apply else "TO DO",
            footer=footer,
        ),
        frame_factory=Frame,
        bindings=bindings,
        session_navigation=session_navigation,
        response_state=response_state,
        current_response_target=current_response_target,
        response_visible=response_visible,
        split_viewer_items=split_viewer_items,
        items_available=effect_report is None,
        todo_available=(effect_report is None or report_apply or read_only_handoff is not None),
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
