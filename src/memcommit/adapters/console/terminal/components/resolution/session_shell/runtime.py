"""Interactive runtime for the shared Resolution Session shell."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import (
    ConditionalContainer,
    DynamicContainer,
    FormattedTextControl,
    HSplit,
    Layout,
    Window,
)
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles
from prompt_toolkit.widgets import Frame

from memcommit.application.capabilities.review_policy import DecisionFreeBehavior
from memcommit.adapters.console.coordination.command_review.model import CommandReview
from memcommit.adapters.console.terminal.components.exact_name import (
    ExactNameFieldView,
    ExactNameInputControl,
)
from memcommit.adapters.console.terminal.components.multiline_input import (
    build_framed_multiline_input,
)
from memcommit.adapters.console.terminal.components.plain_text_clipboard import (
    copy_plain_text,
    plain_text_from_fragments,
)
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    MEMCOMMIT_TUI_STYLE,
    focused_control_style,
)
from memcommit.adapters.console.terminal.core.keybindings import (
    NavigationAccelerator,
    bind_case_insensitive_key,
)
from memcommit.adapters.console.terminal.components.frame import (
    TuiRegion,
    bind_focused_frame_style,
    build_tui_frame,
)
from memcommit.adapters.console.terminal.components.scrollable_pane import (
    WrappedScrollbarMargin,
)
from memcommit.adapters.console.terminal.core.capabilities import (
    require_interactive_terminal,
)
from memcommit.adapters.console.terminal.core.text import (
    safe_terminal_text,
)
from memcommit.adapters.console.terminal.components.save_location import (
    SaveLocationEditorState,
    save_location_row_fragments,
    save_location_tree_fragments,
)
from memcommit.adapters.console.terminal.components.session_help import bind_session_help
from memcommit.adapters.console.terminal.components.resolution.compact_shell import (
    run_compact_resolution_decisions,
)
from memcommit.adapters.console.terminal.components.semantic_viewer import (
    SemanticViewerController,
)
from memcommit.adapters.console.terminal.components.focus import (
    FocusSurface,
    SurfaceActionResult,
    SurfaceFocusController,
    SurfaceMoveResult,
    bind_surface_navigation,
)
from memcommit.adapters.console.terminal.components.impact import ImpactController
from memcommit.application.capabilities.resolution.workbench import (
    ResolutionNavigation,
    ResolutionWorkbenchAction,
    ResolutionWorkbenchError,
    ResolutionItem,
    ResolutionWorkbenchView,
)
from memcommit.adapters.console.terminal.components.responses.model import ResponseDraft, ResponseTarget
from memcommit.adapters.console.terminal.components.responses.resolution import (
    response_target_from_item,
)
from memcommit.persistence.command_ledger.study_actions import record_study_action
from memcommit.adapters.console.terminal.components.responses.state import ResponseFrameState
from memcommit.adapters.console.terminal.components.responses import response_frame_fragments
from memcommit.application.capabilities.reviewing.session_navigation import (
    SessionWorkbenchNavigation,
    WorkbenchSection,
    WorkbenchPane,
)


from memcommit.adapters.console.terminal.components.resolution.session_shell.presentation import (
    RESOLUTION_WORKBENCH_STYLE,
    ResolutionDestination,
    ResolutionGlobalStrategy,
    SessionTodoView,
    _current_impact,
    _impact_arrow_expansion,
    _impact_entry_item,
    _impact_entry_section_uid,
    _impact_repeats_results,
    _item_draft,
    _item_is_answered,
    _line,
    _memory_row_section_uid,
    _seeded_report_lines,
    _seeded_report_sections,
    _session_items_fragments,
    _source_memory_lines,
    _stable_sections,
    _stacked_horizontal_key_message,
    _viewer_focus_fragments,
    resolution_report_fragments,
    resolution_review_fragments,
    resolution_seeded_report_fragments,
    resolution_viewer_fragments,
    resolution_workbench_fragments,
    session_review_action_view,
    session_todo_view,
)


@dataclass(frozen=True)
class _FinalReviewOrigin:
    """Exact process-local focus state to restore after final review."""

    viewer_kind: str
    pane: WorkbenchPane
    row_index: int
    viewer_row_index: int
    section_uid: str | None


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
    if decision_free_behavior is None:
        # Keep legacy callers on their published final-review topology while
        # each operation adopts the ownership-aware policy explicitly.
        decision_free_behavior = (
            "FINAL_REVIEW"
            if start_final_review_when_no_required
            else "REPORT_FIRST"
        )
    elif start_final_review_when_no_required:
        raise ValueError(
            "Use either the legacy final-review flag or decision-free behavior."
        )
    if decision_free_behavior not in {
        "REPORT_FIRST",
        "FINAL_REVIEW",
        "AUTO_ACCEPT",
    }:
        raise ValueError("Unsupported decision-free application behavior.")
    current_navigation = navigation or ResolutionNavigation()
    supplier = (
        view_or_supplier if callable(view_or_supplier) else lambda: view_or_supplier
    )

    def current_view() -> ResolutionWorkbenchView:
        view = supplier()
        current_navigation.sync(view)
        return view

    def current_item_handoff() -> SessionTodoView | None:
        """Resolve operation-owned dynamic handoffs from current draft state."""

        return item_handoff() if callable(item_handoff) else item_handoff

    session_navigation = workbench_navigation or SessionWorkbenchNavigation()
    viewer_controller = SemanticViewerController(session_navigation)
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

    def report_sections() -> tuple[WorkbenchSection, ...]:
        active_view = current_view()
        if split_report_text is not None:
            lines = _seeded_report_lines(
                active_view,
                split_report_text,
                global_strategies,
                review_and_apply=review_and_apply,
                read_only=read_only,
                impact_controller=impact_controller,
                drafts=local_drafts,
            )
            entries = tuple(
                (
                    key.split(":", 1)[0],
                    f"SEEDED:{line_index}:{key}",
                    (
                        int(key.split(":", 1)[1]) + 1
                        if key.startswith("ITEM:")
                        else None
                        if key == "RESOLVE_ALL"
                        else 0
                    ),
                )
                for line_index, key in _seeded_report_sections(lines)
            )
            if not entries:
                # A read-only operation may seed a complete trusted report
                # without the common ITEM:/IMPACT markers. The report is still
                # one navigable Viewer surface; keeping an explicit fallback
                # section prevents focus/help projection from indexing an
                # empty semantic topology merely because no child stop exists.
                entries = (("REPORT", "SEEDED:REPORT", 0),)
            return _stable_sections(entries)
        entries: list[tuple[str, str, int | None]] = [
            (
                "OVERVIEW",
                f"REPORT:OVERVIEW:{section.uid}",
                0,
            )
            for section in active_view.semantic_overview_sections
        ]
        if active_view.report_items_summary is not None:
            entries.append(("REVIEW_ITEMS", "REPORT:REVIEW_ITEMS", 0))
        else:
            entries.extend(
                ("ITEM", f"ITEM:{item.uid}", index)
                for index, item in enumerate(active_view.items, start=1)
            )
        active_impact = _current_impact(impact_controller, active_view)
        impact_repeats_results = _impact_repeats_results(
            active_impact,
            active_view,
        )
        if active_view.show_results and not impact_repeats_results:
            entries.append(("RESULTS", "REPORT:RESULTS", 0))
        if active_impact is not None:
            entries.append(("IMPACT", "REPORT:IMPACT", 0))
            entries.extend(
                (
                    "IMPACT_ENTRY",
                    _impact_entry_section_uid(entry, index),
                    0,
                )
                for index, entry in enumerate(active_impact.entries, start=1)
            )
        if not read_only:
            entries.append(
                (
                    "REVIEW_AND_APPLY" if review_and_apply else "RESOLVE_ALL",
                    "REPORT:ACTION",
                    None,
                )
            )
        return _stable_sections(tuple(entries))

    def item_sections() -> tuple[WorkbenchSection, ...]:
        item = current_navigation.current_item(current_view())
        if item is None:
            return _stable_sections((("SUMMARY", "ITEM:SUMMARY", None),))
        entries: list[tuple[str, str, int | None]] = []

        def append_block_sections(blocks, *, start: int = 0) -> None:
            for block_index, block in enumerate(blocks, start=start):
                if block.memory_rows:
                    entries.extend(
                        (
                            "MEMORY_ROW",
                            _memory_row_section_uid(item.uid, block_index, row),
                            None,
                        )
                        for row in block.memory_rows
                    )
                else:
                    entries.append(
                        (
                            "BLOCK",
                            f"ITEM:{item.uid}:BLOCK:{block_index}:{block.heading}",
                            None,
                        )
                    )

        if item.issue_presentation is not None:
            for evidence_index, evidence in enumerate(item.issue_presentation.evidence):
                evidence_prefix = f"ITEM:{item.uid}:EVIDENCE:{evidence_index}"
                entries.append(
                    (
                        "EVIDENCE_CLASSIFICATION",
                        f"{evidence_prefix}:CLASSIFICATION",
                        None,
                    )
                )
                entries.extend(
                    (
                        "EVIDENCE_CRITERION",
                        f"{evidence_prefix}:CRITERION:{criterion_index}",
                        None,
                    )
                    for criterion_index, _criterion in enumerate(
                        evidence.criterion_blocks
                    )
                )
                for claim_index, claim in enumerate(evidence.source_groups):
                    for source in claim.sources:
                        entries.append(
                            (
                                "SOURCE_MEMORY",
                                (
                                    f"{evidence_prefix}:SOURCE:{claim_index}:"
                                    f"{source.memory_uid}"
                                ),
                                None,
                            )
                        )
                entries.append(
                    (
                        "EVIDENCE_REASON",
                        f"{evidence_prefix}:REASON",
                        None,
                    )
                )
            append_block_sections(item.blocks)
            return _stable_sections(tuple(entries))
        entries.append(("SUMMARY", f"ITEM:{item.uid}:SUMMARY", None))
        append_block_sections(item.blocks[: item.decision_block_index])
        append_block_sections(
            item.blocks[item.decision_block_index :],
            start=item.decision_block_index,
        )
        if item.evidence_refs:
            entries.append(("TRACE", f"ITEM:{item.uid}:TRACE", None))
        return _stable_sections(tuple(entries))

    def active_viewer_sections() -> tuple[WorkbenchSection, ...]:
        if viewer_content["kind"] == "REPORT":
            return report_sections()
        if viewer_content["kind"] == "REVIEW":
            entries: list[tuple[str, str, int | None]] = [
                ("SUMMARY", "REVIEW:SUMMARY", None)
            ]
            if review_action().kind in {
                "INCORPORATE RESPONSES",
                "INCORPORATE AND APPLY",
            }:
                entries.append(("POLICY", "REVIEW:POLICY", None))
            if final_command_review["value"] is not None:
                entries.append(("COMMAND", "REVIEW:COMMAND", None))
            entries.append(("ACTION", "REVIEW:ACTION", None))
            return _stable_sections(tuple(entries))
        return item_sections()

    def viewer_section_index() -> int:
        return viewer_controller.index(active_viewer_sections())

    def reset_viewer_section() -> None:
        viewer_controller.close_nested()
        sections = active_viewer_sections()
        session_navigation.section_uid = sections[0].uid if sections else None

    def focused_source_memory():
        """Resolve the exact typed Memory owned by the current Viewer stop."""

        section = viewer_controller.current(active_viewer_sections())
        item = current_navigation.current_item(current_view())
        if (
            section is None
            or section.kind != "SOURCE_MEMORY"
            or item is None
            or item.issue_presentation is None
        ):
            return None
        for evidence_index, evidence in enumerate(item.issue_presentation.evidence):
            for claim_index, claim in enumerate(evidence.source_groups):
                for source in claim.sources:
                    uid = (
                        f"ITEM:{item.uid}:EVIDENCE:{evidence_index}:SOURCE:"
                        f"{claim_index}:{source.memory_uid}"
                    )
                    if uid == section.uid:
                        return source
        return None

    def pane_content_width() -> int:
        """Track the live inner frame width, including terminal resizes."""
        try:
            columns = get_app().output.get_size().columns
        except (AttributeError, RuntimeError):
            return 76
        # Frame borders consume two cells and the scroll margin consumes one.
        return max(20, columns - 3)

    def split_kind() -> str:
        if session_navigation.pane == "save_location":
            return "SAVE_LOCATION"
        if session_navigation.pane == "responses":
            return "RESPONSES"
        if session_navigation.pane == "todo":
            return "TODO"
        if session_navigation.pane == "viewer" and viewer_content["kind"] == "REVIEW":
            return "RESOLVE_ALL"
        if session_navigation.row_index == 0:
            return "REPORT"
        if session_navigation.row_index <= len(current_view().items):
            return "ITEM"
        return "RESOLVE_ALL"

    def focused_impact_entry_uid() -> str | None:
        if not (
            split_viewer_items
            and session_navigation.pane == "viewer"
            and viewer_content["kind"] == "REPORT"
            and split_kind() == "REPORT"
        ):
            return None
        section = active_viewer_sections()[viewer_section_index()]
        if section.kind != "IMPACT_ENTRY":
            return None
        impact = _current_impact(impact_controller, current_view())
        if impact is None:
            return None
        for index, entry in enumerate(impact.entries, start=1):
            if _impact_entry_section_uid(entry, index) == section.uid and (
                entry.rules or entry.reason
            ):
                return section.uid
        return None

    def focused_impact_comment_item() -> ResolutionItem | None:
        if not (
            split_viewer_items
            and session_navigation.pane == "viewer"
            and viewer_content["kind"] == "REPORT"
            and split_kind() == "REPORT"
        ):
            return None
        section = active_viewer_sections()[viewer_section_index()]
        if section.kind != "IMPACT_ENTRY":
            return None
        active_view = current_view()
        impact = _current_impact(impact_controller, active_view)
        if impact is None:
            return None
        for index, entry in enumerate(impact.entries, start=1):
            if _impact_entry_section_uid(entry, index) != section.uid:
                continue
            item = _impact_entry_item(active_view, entry)
            return item if item is not None and item.commentable else None
        return None

    def review_action() -> SessionTodoView:
        if final_review_title["value"] == "RESOLVE ALL":
            if not global_strategies:
                return SessionTodoView(
                    "COMPLETE",
                    "No whole-set strategy available",
                    "Return and review an individual item.",
                )
            selected_strategy = global_strategies[strategy["index"]]
            return SessionTodoView(
                "RESOLVE ALL",
                selected_strategy.label,
                selected_strategy.comment
                or "Enter to run the selected whole-set strategy.",
            )
        return session_review_action_view(
            current_view(),
            local_drafts,
            whole_set_available=bool(global_strategies),
        )

    def displayed_todo() -> SessionTodoView:
        """Describe review entry before opening and confirmation after it."""

        active_view = current_view()
        if viewer_content["kind"] == "REVIEW":
            action = review_action()
            return SessionTodoView(
                final_review_title["value"],
                f"Confirm final {active_view.operation.title()} action",
                (f"{action.kind} is ready. Enter to {action.kind.lower()} now."),
            )
        return session_todo_view(
            active_view,
            local_drafts,
            review_and_apply=review_and_apply,
            read_only=read_only,
            whole_set_available=bool(global_strategies),
            read_only_handoff=read_only_handoff,
            item_handoff=current_item_handoff(),
        )

    def split_view_fragments():
        active_view = current_view()
        if viewer_content["kind"] == "REVIEW":
            return _viewer_focus_fragments(
                resolution_review_fragments(
                    active_view,
                    local_drafts,
                    global_strategies,
                    strategy["index"],
                    review_action(),
                    viewer_section_index(),
                    content_width=pane_content_width(),
                    review_title=final_review_title["value"],
                    command_review=final_command_review["value"],
                ),
                focused=session_navigation.pane == "viewer",
            )
        if viewer_content["kind"] == "REPORT":
            if split_report_text is not None:
                return _viewer_focus_fragments(
                    resolution_seeded_report_fragments(
                        active_view,
                        split_report_text,
                        report_fragments=split_report_fragments,
                        strategies=global_strategies,
                        drafts=local_drafts,
                        report_item_badges=split_report_item_badges,
                        report_conflicts_remaining=split_report_conflicts_remaining,
                        selected_strategy_index=strategy["index"],
                        focused_section=viewer_section_index(),
                        review_and_apply=review_and_apply,
                        read_only=read_only,
                        impact_controller=impact_controller,
                        content_width=pane_content_width(),
                    ),
                    focused=session_navigation.pane == "viewer",
                )
            return _viewer_focus_fragments(
                resolution_report_fragments(
                    active_view,
                    strategies=global_strategies,
                    drafts=local_drafts,
                    focused_section=viewer_section_index(),
                    review_and_apply=review_and_apply,
                    read_only=read_only,
                    impact_controller=impact_controller,
                    expanded_impact_section_uid=impact_reason_expanded["uid"],
                    content_width=pane_content_width(),
                ),
                focused=session_navigation.pane == "viewer",
            )
        return _viewer_focus_fragments(
            resolution_viewer_fragments(
                active_view,
                current_navigation,
                focused_section=viewer_section_index(),
                other_direction_editing=other_direction_editor["open"],
                expanded_memory_section_uid=expanded_memory_section_uid["uid"],
                nested_source_memory_uid=viewer_controller.nested_uid,
                nested_source_memory_line=viewer_controller.nested_index,
                include_response_sections=False,
                content_width=pane_content_width(),
            ),
            focused=session_navigation.pane == "viewer",
        )

    bindings = KeyBindings()
    status = {"value": ""}
    global_comment = {"value": False}
    strategy = {"index": 0}
    viewer_content = {"kind": "REPORT"}
    final_review_title = {"value": "APPLY CONFIRMATION"}
    final_review_origin: dict[str, _FinalReviewOrigin | None] = {"value": None}
    final_command_review: dict[str, CommandReview | None] = {"value": None}
    impact_reason_expanded: dict[str, str | None] = {"uid": None}
    navigation_accelerator = NavigationAccelerator()
    other_direction = {"focused": False}
    other_direction_editor = {"open": False}
    response_state = ResponseFrameState()
    global_response_draft = {"value": ResponseDraft()}
    expanded_memory_section_uid: dict[str, str | None] = {"uid": None}
    destination_editing = {"value": False}
    destination_editor_state = {
        "value": (
            SaveLocationEditorState.create(destination)
            if destination is not None
            else None
        )
    }
    input_heading = {"value": "COMMENT ON SELECTED ITEM"}
    local_drafts: dict[str, ResponseDraft] = {}

    def current_response_target() -> ResponseTarget | None:
        """Project only the response context currently visible to the person."""

        active_view = current_view()
        if global_comment["value"]:
            return ResponseTarget(
                item_uid="WHOLE_SET",
                item_label=f"Complete {active_view.operation.title()} proposal",
                obligation="NONE",
                state=(
                    "ANSWERED" if global_response_draft["value"].answered else "OPEN"
                ),
                mode="COMMENT",
                editable=(
                    not read_only
                    and not active_view.input_locked
                    and "SUBMIT_ALL" in active_view.capabilities
                ),
            )
        if viewer_content["kind"] != "ITEM" and not response_state.editing:
            return None
        item = current_navigation.current_item(active_view)
        if item is None:
            return None
        return response_target_from_item(
            active_view,
            item,
            read_only=read_only,
            stage_locally=review_and_apply or draft_saver is not None,
        )

    def current_response_draft(target: ResponseTarget) -> ResponseDraft:
        if target.item_uid == "WHOLE_SET":
            return global_response_draft["value"]
        item = current_navigation.current_item(current_view())
        if item is None or item.uid != target.item_uid:
            return ResponseDraft()
        return _item_draft(item, local_drafts)

    def sync_response_state() -> ResponseTarget | None:
        target = current_response_target()
        if target is None:
            return None
        response_state.sync(
            target,
            current_response_draft(target),
            frame_focused=session_navigation.pane == "responses",
        )
        return target

    def response_visible() -> bool:
        target = current_response_target()
        if not split_viewer_items or target is None:
            return False
        # Read-only review retains an answered choice/comment as evidence, but
        # an empty response target is not a semantic surface. Hiding that blank
        # frame also prevents inactive controls from suggesting that an
        # applied session can still be edited.
        return not read_only or current_response_draft(target).answered

    def set_viewer_content(kind: str) -> None:
        """Keep the outer frame label aligned with its semantic surface."""

        viewer_content["kind"] = kind
        # A final whole-set confirmation is a distinct surface, not
        # another report/detail Viewer. Removing the label also avoids two
        # competing headings such as VIEWER and APPLY CONFIRMATION.
        viewer_frame.title = "" if kind == "REVIEW" else "VIEWER"

    # To Do summarizes the whole session before any individual row is opened,
    # so seed it from the adapter's durable response projection or the
    # operation-owned loader instead of treating unvisited rows as unresolved.
    for item in current_view().items:
        if draft_loader is None:
            option_uid, comment = item.selected_option_uid, item.response_text
        else:
            option_uid, comment = draft_loader(item.uid)
        if option_uid is not None:
            item.option(option_uid)
        local_drafts[item.uid] = ResponseDraft(option_uid, comment)

    composer = build_framed_multiline_input(
        "RESPONSE",
        prompt="› ",
        buffer_name="resolution-message",
        height=Dimension(min=4, preferred=5, max=7),
        # The outer Responses frame may be focused while a choice row owns the
        # keyboard. Reset inherited focus styling until this inner box itself
        # becomes the active stop.
        frame_style="fg:#f4f5f7 nobold",
    )
    input_area = composer.text_area
    body_control = FormattedTextControl(
        lambda: (
            split_view_fragments()
            if split_viewer_items
            else resolution_workbench_fragments(
                current_view(),
                current_navigation,
                other_direction_focused=other_direction["focused"],
            )
        ),
        focusable=True,
        show_cursor=False,
    )
    body = Window(
        body_control,
        wrap_lines=True,
        # Resolution details contain long logical lines (source Memories,
        # evidence, and proposed children). Use the shared visual-row-aware
        # margin so the thumb and ^/v arrows follow what is actually visible.
        right_margins=[WrappedScrollbarMargin(display_arrows=True)],
    )

    def current_viewer_plain_text(*, whole_document: bool) -> str:
        """Project current rendered Viewer chrome to the shared y/Y contract."""

        fragments = (
            split_view_fragments()
            if split_viewer_items
            else resolution_workbench_fragments(
                current_view(),
                current_navigation,
                other_direction_focused=other_direction["focused"],
            )
        )
        return plain_text_from_fragments(
            fragments,
            whole_document=whole_document,
        )

    def responses_fragments() -> list[tuple[str, str]]:
        target = sync_response_state()
        if target is None:
            return [("", " No response target is open.\n")]
        return response_frame_fragments(
            target,
            current_response_draft(target),
            response_state,
            focused=session_navigation.pane == "responses",
            content_width=pane_content_width(),
        )

    responses_control = FormattedTextControl(
        responses_fragments,
        focusable=True,
        show_cursor=False,
    )
    responses_window = Window(
        responses_control,
        height=Dimension(min=4, preferred=9, max=13, weight=4),
        wrap_lines=True,
        right_margins=[WrappedScrollbarMargin(display_arrows=True)],
    )

    def item_fragments():
        active_view = current_view()
        return _session_items_fragments(
            active_view,
            selected_index=session_navigation.row_index,
            focused=session_navigation.pane == "items",
            content_width=pane_content_width(),
            report_label=f"Complete {active_view.operation.title()} report",
        )

    items_control = FormattedTextControl(
        item_fragments,
        focusable=True,
        show_cursor=False,
    )
    items_window = Window(
        items_control,
        height=Dimension(min=4, preferred=6, max=8, weight=3),
        wrap_lines=False,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )

    def todo_fragments() -> list[tuple[str, str]]:
        todo = displayed_todo()
        focused = session_navigation.pane == "todo"
        display_kind = (
            "APPLY CONFIRMATION"
            if todo.kind == "REVIEW AND APPLY"
            else todo.kind
        )
        return [
            ("[SetCursorPosition]", "") if focused else ("", ""),
            (
                focused_control_style(focused=focused),
                f"[ {safe_terminal_text(display_kind)} ]",
            ),
            (
                "",
                "  "
                + _line(
                    f"{safe_terminal_text(todo.label)} · "
                    f"{safe_terminal_text(todo.detail)}",
                    max(10, pane_content_width() - len(display_kind) - 8),
                ),
            ),
        ]

    todo_control = FormattedTextControl(
        todo_fragments,
        focusable=True,
        show_cursor=False,
    )
    todo_window = Window(
        todo_control,
        height=Dimension.exact(1),
        dont_extend_height=True,
        wrap_lines=False,
    )

    def destination_fragments() -> list[tuple[str, str]]:
        if destination is None:
            return []
        return save_location_row_fragments(
            destination,
            focused=session_navigation.pane == "save_location",
            content_width=pane_content_width(),
        )

    destination_control = FormattedTextControl(
        destination_fragments,
        focusable=True,
        show_cursor=False,
    )
    destination_window = Window(
        destination_control,
        height=Dimension.exact(1),
        dont_extend_height=True,
        wrap_lines=False,
    )
    destination_name_field = ExactNameInputControl.create(
        destination
        if destination is not None
        else ExactNameFieldView(value="", label="SAVE LOCATION"),
        input_name="resolution-save-location",
    )
    destination_input = destination_name_field.input

    def destination_tree_fragments() -> list[tuple[str, str]]:
        state = destination_editor_state["value"]
        if state is None:
            return []
        return save_location_tree_fragments(
            state,
            focused=get_app().layout.has_focus(destination_tree_control),
        )

    destination_tree_control = FormattedTextControl(
        destination_tree_fragments,
        focusable=True,
        show_cursor=False,
    )
    destination_tree_window = Window(
        destination_tree_control,
        height=Dimension(min=3, preferred=6, max=9, weight=1),
        wrap_lines=False,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )
    destination_editor_with_tree = HSplit(
        [
            Window(
                FormattedTextControl(
                    " PARENT CONTEXT · ↑/↓ MOVE · ←/→ EXPAND · ENTER USE"
                ),
                height=Dimension.exact(1),
                dont_extend_height=True,
            ),
            destination_tree_window,
            Window(
                FormattedTextControl(" EDIT DIRECTLY · ENTER SAVES EXACT NAME"),
                height=Dimension.exact(1),
                dont_extend_height=True,
            ),
            destination_input,
        ]
    )

    def destination_frame_content():
        if not destination_editing["value"]:
            return destination_window
        if destination_editor_state["value"] is None:
            return destination_input
        return destination_editor_with_tree

    destination_frame = Frame(
        DynamicContainer(destination_frame_content),
        title=(
            safe_terminal_text(destination.label)
            if destination is not None
            else "SAVE LOCATION"
        ),
    )
    writable_input_focused = has_focus(input_area) | has_focus(destination_input)

    def destination_tree_is_focused() -> bool:
        return (
            destination_editing["value"]
            and destination_editor_state["value"] is not None
            and get_app().layout.has_focus(destination_tree_control)
        )

    def load_draft() -> None:
        item = current_navigation.current_item(current_view())
        if item is None:
            current_navigation.selected_option_uid = None
            input_area.text = ""
            return
        if draft_loader is None:
            draft = _item_draft(item, local_drafts)
            selected_option_uid, comment = draft.selected_choice_uid, draft.text
        else:
            selected_option_uid, comment = draft_loader(item.uid)
            if selected_option_uid is not None:
                item.option(selected_option_uid)
        current_navigation.selected_option_uid = selected_option_uid
        if selected_option_uid is not None:
            # Reopening a durable draft must put the navigation cursor on the
            # same option that carries the visible checkmark. Otherwise Enter
            # silently changes a different row instead of toggling the staged
            # choice the person is looking at.
            current_navigation.option_cursor_uid = selected_option_uid
        input_area.text = comment
        input_area.buffer.cursor_position = len(comment)
        target = current_response_target()
        if target is not None:
            response_state.sync(target, ResponseDraft(selected_option_uid, comment))

    def save_draft() -> bool:
        item = current_navigation.current_item(current_view())
        if item is None:
            return True
        if response_validator is not None:
            try:
                response_validator(input_area.text)
            except (TypeError, ValueError) as error:
                set_status(str(error))
                return False
        draft = ResponseDraft(
            current_navigation.selected_option_uid,
            input_area.text,
        )
        local_drafts[item.uid] = draft
        target = current_response_target()
        if target is not None and target.item_uid == item.uid:
            response_state.sync(target, draft)
        if draft_saver is not None:
            draft_saver(item.uid, draft.selected_choice_uid, draft.text)
        return True

    def set_status(message: str) -> None:
        status["value"] = message

    def semantic_action(
        kind: str,
        *,
        item_uid: str | None = None,
        option_uid: str | None = None,
        comment: str = "",
    ) -> ResolutionWorkbenchAction | None:
        try:
            action = ResolutionWorkbenchAction(
                kind=kind,  # type: ignore[arg-type]
                item_uid=item_uid,
                option_uid=option_uid,
                comment=comment,
            )
            return current_view().validate_action(action)
        except ResolutionWorkbenchError as error:
            set_status(str(error))
            return None

    def incorporate_responses_action(
        active_view: ResolutionWorkbenchView,
        *,
        action_kind: str = "SUBMIT_ALL",
    ) -> ResolutionWorkbenchAction | None:
        """Build the one complete reviewed-response turn used by both surfaces."""

        if not global_strategies:
            set_status("No remaining-item policies are available.")
            return None
        selected_strategy = global_strategies[strategy["index"]]
        lines = ["Use these reviewed issue resolutions:"]
        unresolved_counts: dict[str, int] = {}
        unresolved_required: list[str] = []
        for item in active_view.items:
            obligation = item.effective_obligation
            draft = _item_draft(item, local_drafts)
            option_uid, comment = draft.selected_choice_uid, draft.text
            if obligation == "NONE" and not (item.commentable and comment.strip()):
                continue
            if option_uid is not None:
                option = item.option(option_uid)
                response = f"Choose this reading: {option.text}"
                if comment.strip():
                    response += f" Additional guidance: {comment.strip()}"
                lines.append(f"- {item.title}: {response}")
            elif comment.strip():
                lines.append(f"- {item.title}: Response: {comment.strip()}")
            elif item.response_state == "ANSWERED":
                lines.append(f"- {item.title}: Keep the saved response.")
            else:
                unresolved_counts[obligation] = unresolved_counts.get(obligation, 0) + 1
                if obligation == "REQUIRED":
                    unresolved_required.append(item.title)
        if unresolved_counts:
            counts = ", ".join(
                f"{priority} {count}"
                for priority, count in (
                    ("REQUIRED", unresolved_counts.get("REQUIRED", 0)),
                    ("OPTIONAL", unresolved_counts.get("OPTIONAL", 0)),
                )
                if count
            )
            lines.append(
                "For remaining items ("
                + counts
                + "), apply this policy: "
                + selected_strategy.comment
            )
        if unresolved_required:
            lines.append(
                "Still-required issue titles: " + "; ".join(unresolved_required)
            )
        return semantic_action(action_kind, comment="\n".join(lines))

    def destination_action(value: str) -> ResolutionWorkbenchAction | None:
        if destination is None:
            set_status("Save-location editing is unavailable here.")
            return None
        try:
            destination.validate_value(value)
            return ResolutionWorkbenchAction(
                kind="CHANGE_DESTINATION",
                destination=value,
            )
        except (OSError, TypeError, ValueError) as error:
            set_status(str(error))
            return None

    def project_previewed_items_row(active_view: ResolutionWorkbenchView) -> None:
        """Project the already-aligned shared Items row into operation state."""

        other_direction["focused"] = False
        other_direction_editor["open"] = False
        response_state.editing = False
        expanded_memory_section_uid["uid"] = None
        viewer_controller.close_nested()
        if session_navigation.row_index == 0:
            set_viewer_content("REPORT")
            current_navigation.close_detail()
            reset_viewer_section()
            return
        item = active_view.items[session_navigation.row_index - 1]
        set_viewer_content("ITEM")
        current_navigation.selected_item_uid = item.uid
        current_navigation.sync(active_view)
        current_navigation.close_detail()
        current_navigation.toggle_detail(active_view)
        reset_viewer_section()
        load_draft()
        sync_response_state()

    def preview_items_row(active_view: ResolutionWorkbenchView) -> None:
        """Align and project one explicitly selected Items row."""

        session_navigation.preview_selected_row()
        project_previewed_items_row(active_view)

    def move(delta: int) -> None:
        active_view = current_view()
        if split_viewer_items:
            if session_navigation.pane == "responses":
                target = sync_response_state()
                if target is None:
                    set_status("No response target is open.")
                    return
                response_state.move_focus(target, delta)
                set_status("")
                return
            if session_navigation.pane == "viewer":
                if viewer_controller.nested_uid is not None:
                    source = focused_source_memory()
                    if source is not None:
                        viewer_controller.move_nested(
                            len(
                                _source_memory_lines(
                                    source.content,
                                    pane_content_width(),
                                )
                            ),
                            delta,
                        )
                    set_status("")
                    return
                section = viewer_controller.move(active_viewer_sections(), delta)
                if viewer_content["kind"] == "REPORT" and section is not None:
                    session_navigation.row_index = section.row_index or 0
                    if section.kind == "ITEM" and section.row_index is not None:
                        item = active_view.items[section.row_index - 1]
                        current_navigation.selected_item_uid = item.uid
                set_status("")
                return
            if session_navigation.pane == "todo":
                set_status("")
                return
            if session_navigation.pane == "save_location":
                state = destination_editor_state["value"]
                if destination_tree_is_focused() and state is not None:
                    state.tree.move(delta)
                set_status("")
                return
            total_rows = len(active_view.items) + 1
            session_navigation.move_and_preview_row(total_rows, delta)
            project_previewed_items_row(active_view)
            set_status("")
            return
        item = current_navigation.current_item(active_view)
        if (
            item is not None
            and current_navigation.expanded_item_uid == item.uid
            and item.options
        ):
            current_navigation.move_option(active_view, delta)
        else:
            if not save_draft():
                return
            current_navigation.move_item(active_view, delta)
            load_draft()
        global_comment["value"] = False
        composer.frame.title = "RESPONSE" if split_viewer_items else "MESSAGE"
        set_status("")

    def open_item_input(*, title: str, clear: bool = False) -> None:
        destination_editing["value"] = False
        global_comment["value"] = False
        response_state.editing = True
        response_state.focus_response()
        composer.frame.title = title
        input_heading["value"] = title
        if clear:
            input_area.text = ""
        session_navigation.focus("composer")
        get_app().layout.focus(input_area)

    def open_global_input(*, clear: bool = False) -> None:
        destination_editing["value"] = False
        global_comment["value"] = True
        response_state.editing = True
        response_state.focus_response()
        other_direction_editor["open"] = False
        composer.frame.title = "WHOLE-SET COMMENT"
        input_heading["value"] = "WHOLE-SET GUIDANCE"
        if clear:
            global_response_draft["value"] = ResponseDraft()
        input_area.text = global_response_draft["value"].text
        input_area.buffer.cursor_position = len(input_area.text)
        sync_response_state()
        session_navigation.focus("composer")
        get_app().layout.focus(input_area)

    def open_destination_input() -> None:
        if destination is None or not destination_available:
            set_status("Save-location editing is unavailable here.")
            return
        destination_editing["value"] = True
        destination_editor_state["value"] = SaveLocationEditorState.create(destination)
        global_comment["value"] = False
        other_direction_editor["open"] = False
        response_state.editing = False
        destination_frame.title = safe_terminal_text(
            f"{destination.label} · CHOOSE PARENT OR EDIT DIRECTLY"
        )
        destination_name_field.set_text(destination.value)
        session_navigation.focus("save_location")
        get_app().layout.focus(destination_input)
        set_status("")

    def use_destination_parent() -> None:
        state = destination_editor_state["value"]
        if state is None:
            set_status("No parent Context catalog is available here.")
            return
        try:
            candidate = state.choose_cursor_as_parent(destination_input.text)
        except (TypeError, ValueError) as error:
            set_status(str(error))
            return
        destination_name_field.set_text(candidate)
        get_app().layout.focus(destination_input)
        set_status(
            f"Parent selected · {state.selected_parent} · edit the exact name or Enter."
        )

    def current_response_heading() -> str:
        item = current_navigation.current_item(current_view())
        if item is not None and item.issue_presentation is not None:
            return "RESPONSE"
        return "COMMENT ON SELECTED ITEM"

    def open_split_item(item_uid: str) -> None:
        """Open one selected item from Items or the state-derived To Do."""

        active_view = current_view()
        item_index = next(
            index
            for index, item in enumerate(active_view.items)
            if item.uid == item_uid
        )
        session_navigation.row_index = item_index + 1
        preview_items_row(active_view)
        session_navigation.open_selected(item_sections())
        event_app = get_app()
        event_app.layout.focus(body_control)
        set_status("")

    def close_final_review() -> None:
        """Return from final review to the exact process-local entry surface."""

        origin = final_review_origin["value"]
        final_review_origin["value"] = None
        final_command_review["value"] = None
        if origin is None:
            # Compatibility fallback for navigation state created before this
            # shell began tracking review entry. The report action is the
            # closest stable semantic parent of the confirmation surface.
            session_navigation.row_index = 0
            session_navigation.viewer_row_index = 0
            set_viewer_content("REPORT")
            sections = report_sections()
            action_section = next(
                (section for section in sections if section.uid == "REPORT:ACTION"),
                sections[0] if sections else None,
            )
            session_navigation.section_uid = (
                action_section.uid if action_section is not None else None
            )
            pane: WorkbenchPane = "viewer"
        else:
            session_navigation.row_index = origin.row_index
            session_navigation.viewer_row_index = origin.viewer_row_index
            set_viewer_content(origin.viewer_kind)
            session_navigation.section_uid = origin.section_uid
            viewer_controller.index(active_viewer_sections())
            pane = origin.pane

        if pane == "responses" and not response_visible():
            pane = "viewer"
        if pane == "save_location" and not destination_available:
            pane = "viewer"
        if pane == "composer":
            pane = "viewer"
        controls = {
            "viewer": body_control,
            "responses": responses_control,
            "items": items_control,
            "save_location": destination_control,
            "todo": todo_control,
        }
        _focus_surface_pane(pane)
        get_app().layout.focus(controls[pane])
        set_status("")

    def open_final_review() -> None:
        """Open the non-mutating review before a whole-set or apply action."""

        # A split report has no open response editor. Saving there would copy
        # the navigation sentinel (no selected option) over the first item's
        # already-staged durable choice after its detail was closed.
        if not split_viewer_items or response_visible():
            save_draft()
        active_view = current_view()
        todo = session_todo_view(
            active_view,
            local_drafts,
            review_and_apply=review_and_apply,
            read_only=read_only,
            whole_set_available=bool(global_strategies),
            read_only_handoff=read_only_handoff,
            item_handoff=current_item_handoff(),
        )
        if todo.kind not in {"REVIEW AND APPLY", "RESOLVE ALL"}:
            if todo.unresolved_item_uids:
                open_split_item(todo.unresolved_item_uids[0])
            else:
                set_status(todo.detail)
            return
        final_review_title["value"] = (
            "APPLY CONFIRMATION"
            if todo.kind == "REVIEW AND APPLY"
            else todo.kind
        )
        proposed_action = final_review_action(active_view, open_custom=False)
        final_command_review["value"] = (
            turn_command_review(proposed_action)
            if turn_command_review is not None and proposed_action is not None
            else None
        )
        if viewer_content["kind"] != "REVIEW":
            # This is a temporary confirmation layer. Preserve the exact
            # semantic stop and visible frame so both Enter on its summary and
            # the shared back keys can unwind without guessing a destination.
            final_review_origin["value"] = _FinalReviewOrigin(
                viewer_kind=viewer_content["kind"],
                pane=session_navigation.pane,
                row_index=session_navigation.row_index,
                viewer_row_index=session_navigation.viewer_row_index,
                section_uid=session_navigation.section_uid,
            )
        session_navigation.row_index = len(active_view.items) + 1
        session_navigation.viewer_row_index = session_navigation.row_index
        set_viewer_content("REVIEW")
        session_navigation.focus_section(
            active_viewer_sections(),
            kind="SUMMARY",
        )
        # Entering final review starts at its visible top, not at the To Do
        # handoff below the Viewer. This keeps the summary in view and makes
        # moving down to the exact Apply action an explicit review step.
        session_navigation.focus("viewer")
        get_app().layout.focus(body_control)
        set_status("")
        record_study_action(
            "APPROVAL_PRESENTED",
            surface="resolution",
            action=todo.kind,
        )

    def final_review_action(
        active_view: ResolutionWorkbenchView,
        *,
        open_custom: bool = True,
    ) -> ResolutionWorkbenchAction | None:
        final_action = review_action()
        if final_action.kind in {"APPLY", "APPLY AS IS"}:
            return semantic_action("ACCEPT")
        if final_action.kind == "INCORPORATE AND APPLY":
            return incorporate_responses_action(
                active_view,
                action_kind="INCORPORATE_AND_APPLY",
            )
        if final_action.kind == "INCORPORATE RESPONSES":
            return incorporate_responses_action(active_view)
        if final_action.kind == "RESOLVE ALL":
            selected_strategy = global_strategies[strategy["index"]]
            if selected_strategy.action_kind == "CUSTOM":
                if open_custom:
                    open_global_input(clear=True)
                return None
            return semantic_action(
                selected_strategy.action_kind,
                comment=selected_strategy.comment,
            )
        set_status("No final action is available.")
        return None

    def approved_final_review_action(
        active_view: ResolutionWorkbenchView,
    ) -> ResolutionWorkbenchAction | None:
        """Rebuild the final action and its command before returning either."""

        action = final_review_action(active_view)
        if action is None or turn_command_review is None:
            return action
        rebuilt = turn_command_review(action)
        if rebuilt != final_command_review["value"]:
            set_status(
                "The semantic turn changed after review. Reopen the final review."
            )
            return None
        return action

    def submit(event) -> None:
        active_view = current_view()
        comment = input_area.text.strip()
        if (review_and_apply or draft_saver is not None) and not global_comment[
            "value"
        ]:
            item = current_navigation.current_item(active_view)
            if not save_draft():
                event.app.invalidate()
                return
            other_direction_editor["open"] = False
            response_state.editing = False
            if split_viewer_items:
                session_navigation.focus("responses")
                event.app.layout.focus(responses_control)
            else:
                session_navigation.focus("viewer")
                event.app.layout.focus(body_control)
            if item is not None:
                draft = local_drafts.get(item.uid, ResponseDraft())
                option_uid, saved_comment = draft.selected_choice_uid, draft.text
                if option_uid is not None:
                    label = item.option(option_uid).label
                    set_status(f"Selected · {label}")
                elif saved_comment.strip():
                    set_status("Saved · Response")
            event.app.invalidate()
            return
        if global_comment["value"]:
            action = semantic_action("SUBMIT_ALL", comment=comment)
        else:
            item = current_navigation.current_item(active_view)
            action = semantic_action(
                "SUBMIT_ITEM",
                item_uid=item.uid if item is not None else None,
                option_uid=current_navigation.selected_option_uid,
                comment=comment,
            )
        if action is not None:
            event.app.exit(result=action)

    @bindings.add("pagedown", filter=~writable_input_focused)
    def _page_down(event) -> None:
        # Once results are independent sections, a page step advances several
        # short result blocks instead of trying to display one 234-result
        # monolith. Down still advances one block at a time.
        navigation_accelerator.reset()
        move(8)
        event.app.invalidate()

    @bindings.add("pageup", filter=~writable_input_focused)
    def _page_up(event) -> None:
        navigation_accelerator.reset()
        move(-8)
        event.app.invalidate()

    @bindings.add("end", filter=~writable_input_focused)
    def _end(event) -> None:
        navigation_accelerator.reset()
        move(1_000_000)
        event.app.invalidate()

    @bindings.add("home", filter=~writable_input_focused)
    def _home(event) -> None:
        navigation_accelerator.reset()
        move(-1_000_000)
        event.app.invalidate()

    def copy_current_viewer(event, *, whole_document: bool) -> None:
        copied = copy_plain_text(
            current_viewer_plain_text(whole_document=whole_document),
            success_message=(
                "complete current document"
                if whole_document
                else "focused semantic unit"
            ),
        )
        set_status(copied.message)
        event.app.invalidate()

    @bindings.add("y", filter=has_focus(body_control), eager=True)
    def _copy_focused_viewer(event) -> None:
        copy_current_viewer(event, whole_document=False)

    @bindings.add("Y", filter=has_focus(body_control), eager=True)
    def _copy_complete_viewer(event) -> None:
        copy_current_viewer(event, whole_document=True)

    def explain_unused_split_horizontal_key() -> None:
        """Make stacked-frame horizontal no-ops explicit instead of silent."""

        set_status(_stacked_horizontal_key_message(split_kind()))

    @bindings.add("right", filter=~writable_input_focused)
    def _right(event) -> None:
        state = destination_editor_state["value"]
        if destination_tree_is_focused() and state is not None:
            state.tree.expand_selected()
            set_status("")
            event.app.invalidate()
            return
        if split_viewer_items:
            impact_uid = focused_impact_entry_uid()
            if impact_uid is not None:
                impact_reason_expanded["uid"] = _impact_arrow_expansion(
                    impact_reason_expanded["uid"],
                    impact_uid,
                    expand=True,
                )
                set_status("Impact rationale shown.")
            elif split_kind() == "RESOLVE_ALL" and global_strategies:
                strategy["index"] = min(
                    strategy["index"] + 1,
                    len(global_strategies) - 1,
                )
            else:
                explain_unused_split_horizontal_key()
            event.app.invalidate()
            return
        save_draft()
        current_navigation.move_item(current_view(), 1)
        load_draft()
        event.app.invalidate()

    @bindings.add("left", filter=~writable_input_focused)
    def _left(event) -> None:
        state = destination_editor_state["value"]
        if destination_tree_is_focused() and state is not None:
            state.tree.collapse_selected()
            set_status("")
            event.app.invalidate()
            return
        if split_viewer_items:
            impact_uid = focused_impact_entry_uid()
            if impact_uid is not None:
                collapsed = _impact_arrow_expansion(
                    impact_reason_expanded["uid"],
                    impact_uid,
                    expand=False,
                )
                if collapsed != impact_reason_expanded["uid"]:
                    set_status("Impact rationale hidden.")
                impact_reason_expanded["uid"] = collapsed
            elif split_kind() == "RESOLVE_ALL" and global_strategies:
                strategy["index"] = max(strategy["index"] - 1, 0)
            else:
                explain_unused_split_horizontal_key()
            event.app.invalidate()
            return
        save_draft()
        current_navigation.move_item(current_view(), -1)
        load_draft()
        event.app.invalidate()

    def _open_or_choose(event) -> None:
        active_view = current_view()
        if split_viewer_items:
            kind = split_kind()
            if kind == "RESPONSES":
                target = sync_response_state()
                item = current_navigation.current_item(active_view)
                if target is not None and target.item_uid == "WHOLE_SET":
                    if not target.editable:
                        set_status("Whole-set guidance is read-only.")
                    else:
                        open_global_input()
                elif target is None or item is None or target.item_uid != item.uid:
                    set_status("No item response is available here.")
                elif response_state.option_navigation_active and not target.editable:
                    set_status("This response is read-only.")
                elif response_state.option_navigation_active:
                    draft = response_state.toggle_current_choice(target)
                    local_drafts[item.uid] = draft
                    current_navigation.selected_option_uid = draft.selected_choice_uid
                    if draft_saver is not None:
                        draft_saver(
                            item.uid,
                            draft.selected_choice_uid,
                            draft.text,
                        )
                    if draft.selected_choice_uid is None:
                        set_status("Selection cleared.")
                    else:
                        set_status(
                            "Selected · ✓ "
                            + target.choice(draft.selected_choice_uid).label
                        )
                elif response_state.section == "DECISION":
                    # A choice-bearing Decision is always directly focusable.
                    # This fallback is only reachable for a prompt-only target.
                    response_state.focus_response()
                    set_status("Move to Response and press Enter to answer.")
                elif not target.editable:
                    set_status("This response is read-only.")
                else:
                    open_item_input(title=current_response_heading())
                event.app.invalidate()
                return
            if kind == "REPORT":
                if (
                    session_navigation.pane == "viewer"
                    and viewer_content["kind"] == "REPORT"
                ):
                    sections = active_viewer_sections()
                    section = sections[viewer_section_index()]
                    if section.kind == "IMPACT_ENTRY":
                        impact_reason_expanded["uid"] = (
                            None
                            if impact_reason_expanded["uid"] == section.uid
                            else section.uid
                        )
                        set_status(
                            "Impact rationale hidden."
                            if impact_reason_expanded["uid"] is None
                            else "Impact rationale shown."
                        )
                        event.app.invalidate()
                        return
                    if section.kind in {"REVIEW_AND_APPLY", "RESOLVE_ALL"}:
                        open_final_review()
                        event.app.invalidate()
                        return
                other_direction_editor["open"] = False
                set_viewer_content("REPORT")
                reset_viewer_section()
                session_navigation.open_selected(report_sections())
                event.app.layout.focus(body_control)
                set_status("")
            elif kind == "SAVE_LOCATION":
                if destination_tree_is_focused():
                    use_destination_parent()
                else:
                    open_destination_input()
            elif kind == "ITEM":
                if (
                    session_navigation.pane != "viewer"
                    or viewer_content["kind"] != "ITEM"
                    or session_navigation.viewer_row_index
                    != session_navigation.row_index
                ):
                    item = active_view.items[session_navigation.row_index - 1]
                    open_split_item(item.uid)
                elif (
                    session_navigation.pane == "viewer"
                    and active_viewer_sections()[viewer_section_index()].kind
                    == "SOURCE_MEMORY"
                ):
                    section = active_viewer_sections()[viewer_section_index()]
                    if viewer_controller.nested_uid == section.uid:
                        viewer_controller.close_nested()
                        set_status("Memory reading closed.")
                    else:
                        viewer_controller.open_nested(section.uid)
                        set_status(
                            "Reading this Memory · ↑/↓ scroll · Enter/Escape back."
                        )
                    event.app.invalidate()
                    return
                elif read_only:
                    set_status("Applied Melds are read-only.")
                else:
                    section = active_viewer_sections()[viewer_section_index()]
                    item = current_navigation.current_item(active_view)
                    if section.kind == "MEMORY_ROW":
                        expanded_memory_section_uid["uid"] = (
                            None
                            if expanded_memory_section_uid["uid"] == section.uid
                            else section.uid
                        )
                        set_status(
                            "Evidence hidden."
                            if expanded_memory_section_uid["uid"] is None
                            else "Evidence shown."
                        )
                        event.app.invalidate()
                        return
                    set_status(
                        "This Viewer section is read-only; use the Responses frame "
                        "to answer."
                    )
            elif kind == "RESOLVE_ALL" and viewer_content["kind"] == "REVIEW":
                section = active_viewer_sections()[viewer_section_index()]
                if section.kind == "SUMMARY":
                    close_final_review()
                elif section.kind != "ACTION":
                    set_status("Move to the final action and press Enter.")
                else:
                    action = approved_final_review_action(active_view)
                    if action is not None:
                        record_study_action(
                            "APPROVAL_ACCEPTED",
                            surface="resolution",
                            action=action.kind,
                        )
                        event.app.exit(result=action)
                        return
            elif kind == "TODO" and viewer_content["kind"] == "REVIEW":
                action = approved_final_review_action(active_view)
                if action is not None:
                    record_study_action(
                        "APPROVAL_ACCEPTED",
                        surface="resolution",
                        action=action.kind,
                    )
                    event.app.exit(result=action)
                    return
            elif (
                kind == "TODO"
                and session_todo_view(
                    active_view,
                    local_drafts,
                    review_and_apply=review_and_apply,
                    read_only=read_only,
                    whole_set_available=bool(global_strategies),
                    read_only_handoff=read_only_handoff,
                    item_handoff=current_item_handoff(),
                ).unresolved_item_uids
            ):
                todo = session_todo_view(
                    active_view,
                    local_drafts,
                    review_and_apply=review_and_apply,
                    read_only=read_only,
                    whole_set_available=bool(global_strategies),
                    read_only_handoff=read_only_handoff,
                    item_handoff=current_item_handoff(),
                )
                open_split_item(todo.unresolved_item_uids[0])
            elif kind == "TODO" and current_item_handoff() is not None:
                item = current_navigation.current_item(active_view)
                if item is None:
                    set_status("There is no finding to hand off.")
                else:
                    # The operation receives the exact item identity and owns
                    # conversion, authority, provider use, and any Apply step.
                    event.app.exit(
                        result=ResolutionWorkbenchAction(
                            kind="HANDOFF",
                            item_uid=item.uid,
                        )
                    )
                    return
            elif kind == "TODO" and read_only:
                if read_only_handoff is None:
                    set_status("This saved session can only be inspected.")
                else:
                    # A standalone result remains immutable here. The handoff
                    # opens the owning operation, which must independently
                    # revalidate and obtain its normal Apply confirmation.
                    event.app.exit(result=ResolutionWorkbenchAction(kind="HANDOFF"))
                    return
            elif (
                kind == "TODO"
                and session_todo_view(
                    active_view,
                    local_drafts,
                    review_and_apply=review_and_apply,
                    read_only=read_only,
                    whole_set_available=bool(global_strategies),
                    read_only_handoff=read_only_handoff,
                    item_handoff=current_item_handoff(),
                ).kind
                == "COMPLETE"
            ):
                set_status(
                    "Required review is complete; close or revisit an optional review."
                )
            elif kind == "TODO" and review_and_apply:
                open_final_review()
            elif kind == "TODO" and not global_strategies:
                set_status("No whole-set strategies are available.")
            elif kind == "TODO":
                open_final_review()
            event.app.invalidate()
            return
        item = current_navigation.current_item(active_view)
        if item is None:
            set_status("There is no item to inspect.")
        elif current_navigation.expanded_item_uid != item.uid:
            current_navigation.toggle_detail(active_view)
            other_direction["focused"] = False
            set_status("")
        elif item.options:
            if item.issue_presentation is not None and other_direction["focused"]:
                current_navigation.selected_option_uid = None
                other_direction_editor["open"] = True
                open_item_input(
                    title=current_response_heading(),
                    clear=True,
                )
            else:
                current_navigation.toggle_option(active_view)
                if not save_draft():
                    event.app.invalidate()
                    return
                set_status("")
        else:
            current_navigation.toggle_detail(active_view)
            set_status("")
        event.app.invalidate()

    def _focus_surface_pane(pane: WorkbenchPane) -> None:
        """Keep semantic frame state aligned with prompt-toolkit focus."""

        if pane != "viewer":
            navigation_accelerator.reset()
            viewer_controller.close_nested()
        if pane == "items" and viewer_content["kind"] == "REVIEW":
            # Final review is not an Items row. Both Tab and vertical entry
            # expose the ordinary Report selection while leaving the reviewed
            # confirmation visible until the person moves or activates it.
            session_navigation.row_index = 0
        session_navigation.focus(pane)
        set_status("")

    def _move_viewer_surface(event, delta: int) -> SurfaceMoveResult:
        sections = active_viewer_sections()
        if viewer_controller.nested_uid is not None:
            # Nested Memory reading deliberately keeps its own Escape boundary;
            # reaching the last wrapped line must not silently leave the reader.
            navigation_accelerator.move(delta, app=event.app, move_one=move)
            return "CONSUMED"
        index = viewer_section_index()
        if (delta < 0 and index == 0) or (
            delta > 0 and index == len(sections) - 1
        ):
            navigation_accelerator.reset()
            return "BOUNDARY"
        navigation_accelerator.move(delta, app=event.app, move_one=move)
        return "MOVED"

    def _enter_viewer_surface(delta: int) -> None:
        sections = active_viewer_sections()
        if sections:
            session_navigation.section_uid = sections[0 if delta > 0 else -1].uid

    def _move_responses_surface(_event, delta: int) -> SurfaceMoveResult:
        target = sync_response_state()
        if target is None:
            return "BOUNDARY"
        before = (
            response_state.section,
            response_state.option_cursor_uid,
        )
        response_state.move_focus(target, delta)
        after = (
            response_state.section,
            response_state.option_cursor_uid,
        )
        set_status("")
        return "MOVED" if after != before else "BOUNDARY"

    def _enter_responses_surface(delta: int) -> None:
        target = sync_response_state()
        if target is None:
            return
        if delta < 0 or not target.choices:
            response_state.focus_response()
            return
        response_state.open_options(target)
        choices = response_state.choice_state
        if choices is not None:
            choices.cursor_uid = choices.options[0].uid

    def _move_items_surface(_event, delta: int) -> SurfaceMoveResult:
        active_view = current_view()
        total_rows = len(active_view.items) + 1
        before = session_navigation.row_index
        if (delta < 0 and before == 0) or (
            delta > 0 and before == total_rows - 1
        ):
            return "BOUNDARY"
        move(delta)
        return (
            "MOVED" if session_navigation.row_index != before else "BOUNDARY"
        )

    def _enter_items_surface(delta: int) -> None:
        # Entering a frame chooses its nearest edge without opening that row.
        # In particular, crossing out of final review must not close the review
        # until the person actually moves or activates an Items selection.
        session_navigation.row_index = (
            0 if delta > 0 else len(current_view().items)
        )

    def _single_row_surface_move(
        _event,
        _delta: int,
    ) -> SurfaceMoveResult:
        return "BOUNDARY"

    def _activate_surface(event) -> SurfaceActionResult:
        _open_or_choose(event)
        return "HANDLED"

    if split_viewer_items:

        def visible_focus_surfaces() -> tuple[FocusSurface, ...]:
            surfaces = [
                FocusSurface(
                    "viewer",
                    body_control,
                    move_vertical=_move_viewer_surface,
                    activate=_activate_surface,
                    on_focus=lambda: _focus_surface_pane("viewer"),
                    on_vertical_enter=_enter_viewer_surface,
                )
            ]
            if response_visible():
                surfaces.append(
                    FocusSurface(
                        "responses",
                        responses_control,
                        move_vertical=_move_responses_surface,
                        activate=_activate_surface,
                        on_focus=lambda: _focus_surface_pane("responses"),
                        on_vertical_enter=_enter_responses_surface,
                    )
                )
            surfaces.append(
                FocusSurface(
                    "items",
                    items_control,
                    move_vertical=_move_items_surface,
                    activate=_activate_surface,
                    on_focus=lambda: _focus_surface_pane("items"),
                    on_vertical_enter=_enter_items_surface,
                )
            )
            if destination_available:
                surfaces.append(
                    FocusSurface(
                        "save-location",
                        destination_control,
                        move_vertical=_single_row_surface_move,
                        activate=_activate_surface,
                        on_focus=lambda: _focus_surface_pane("save_location"),
                    )
                )
            surfaces.append(
                FocusSurface(
                    "todo",
                    todo_control,
                    move_vertical=_single_row_surface_move,
                    activate=_activate_surface,
                    on_focus=lambda: _focus_surface_pane("todo"),
                )
            )
            return tuple(surfaces)

        surface_focus = SurfaceFocusController(visible_focus_surfaces)
        bind_surface_navigation(bindings, surface_focus)
    else:

        @bindings.add("down", filter=~writable_input_focused)
        def _legacy_down(event) -> None:
            move(1)
            event.app.invalidate()

        @bindings.add("up", filter=~writable_input_focused)
        def _legacy_up(event) -> None:
            move(-1)
            event.app.invalidate()

        @bindings.add("enter", filter=~writable_input_focused)
        def _legacy_open_or_choose(event) -> None:
            _open_or_choose(event)

        @bindings.add("tab", filter=has_focus(body_control), eager=True)
        @bindings.add("s-tab", filter=has_focus(body_control), eager=True)
        def _legacy_focus_input(event) -> None:
            active_view = current_view()
            if active_view.input_locked:
                set_status("Resolution input is locked while analysis is pending.")
                event.app.invalidate()
                return
            if "SUBMIT_ITEM" not in active_view.capabilities:
                set_status("Item comments are unavailable here.")
                event.app.invalidate()
                return
            global_comment["value"] = False
            heading = current_response_heading()
            other_direction_editor["open"] = True
            composer.frame.title = heading
            input_heading["value"] = heading
            event.app.layout.focus(input_area)
            event.app.invalidate()

    editor_tab_focused = (
        has_focus(input_area)
        | has_focus(destination_input)
        | has_focus(destination_tree_control)
    )

    @bindings.add("tab", filter=editor_tab_focused, eager=True)
    @bindings.add("s-tab", filter=editor_tab_focused, eager=True)
    def _focus_input(event) -> None:
        if event.app.layout.has_focus(destination_input):
            if destination_editor_state["value"] is not None:
                event.app.layout.focus(destination_tree_control)
                set_status("Choose a parent Context with arrows, then press Enter.")
            else:
                set_status("Press Enter to save this location or Escape to cancel.")
            event.app.invalidate()
            return
        if destination_tree_is_focused():
            event.app.layout.focus(destination_input)
            set_status("Edit the exact Context name, then press Enter to save.")
            event.app.invalidate()
            return
        if event.app.layout.has_focus(input_area):
            if global_comment["value"]:
                if response_validator is not None:
                    try:
                        response_validator(input_area.text)
                    except (TypeError, ValueError) as error:
                        set_status(str(error))
                        event.app.invalidate()
                        return
                global_response_draft["value"] = ResponseDraft(None, input_area.text)
            else:
                if not save_draft():
                    event.app.invalidate()
                    return
            other_direction_editor["open"] = False
            response_state.editing = False
            if split_viewer_items:
                session_navigation.focus("responses")
                event.app.layout.focus(responses_control)
            else:
                event.app.layout.focus(body_control)
            event.app.invalidate()
            return
    @bindings.add("c", filter=~writable_input_focused)
    def _comment_item(event) -> None:
        if not split_viewer_items:
            return
        active_view = current_view()
        impact_item = focused_impact_comment_item()
        if impact_item is not None:
            if (
                active_view.input_locked
                or "SUBMIT_ITEM" not in active_view.capabilities
            ):
                set_status("Item comments are unavailable here.")
                event.app.invalidate()
                return
            current_navigation.selected_item_uid = impact_item.uid
            current_navigation.sync(active_view)
            open_split_item(impact_item.uid)
            open_item_input(title="COMMENT ON THIS CHANGE")
            event.app.invalidate()
            return
        if split_kind() == "RESOLVE_ALL":
            if active_view.input_locked or "SUBMIT_ALL" not in active_view.capabilities:
                set_status("Whole-set guidance is unavailable here.")
                event.app.invalidate()
                return
            open_global_input(clear=True)
            return
        if split_kind() != "ITEM":
            set_status("Choose one review item or RESOLVE ALL first.")
            event.app.invalidate()
            return
        if viewer_content["kind"] != "ITEM":
            set_status("Press Enter to open the selected review item first.")
            event.app.invalidate()
            return
        if active_view.input_locked or "SUBMIT_ITEM" not in active_view.capabilities:
            set_status("Item comments are unavailable here.")
            event.app.invalidate()
            return
        other_direction_editor["open"] = True
        open_item_input(title=current_response_heading())

    @bindings.add("g", filter=~writable_input_focused)
    def _global_comment(event) -> None:
        active_view = current_view()
        if "SUBMIT_ALL" not in active_view.capabilities:
            set_status("Whole-set comments are unavailable here.")
            event.app.invalidate()
            return
        if active_view.input_locked:
            set_status("Resolution input is locked while analysis is pending.")
            event.app.invalidate()
            return
        if split_viewer_items:
            open_global_input(clear=True)
        else:
            global_comment["value"] = True
            other_direction_editor["open"] = False
            composer.frame.title = "WHOLE-SET COMMENT"
            input_heading["value"] = "WHOLE-SET GUIDANCE"
            input_area.text = ""
            event.app.layout.focus(input_area)

    @bindings.add("enter", filter=has_focus(input_area), eager=True)
    @bindings.add("c-s", filter=has_focus(input_area), eager=True)
    @bindings.add("f2", filter=has_focus(input_area), eager=True)
    def _submit_input(event) -> None:
        submit(event)

    @bindings.add("c-j", filter=has_focus(input_area), eager=True)
    def _insert_newline(event) -> None:
        input_area.buffer.insert_text("\n")
        event.app.invalidate()

    @bindings.add("enter", filter=has_focus(destination_input), eager=True)
    def _submit_destination(event) -> None:
        action = destination_action(destination_input.text.strip())
        if action is not None:
            event.app.exit(result=action)
        else:
            event.app.invalidate()

    @bindings.add("up", filter=has_focus(destination_input), eager=True)
    def _browse_destination_parents(event) -> None:
        if destination_editor_state["value"] is None:
            set_status("No parent Context catalog is available here.")
        else:
            event.app.layout.focus(destination_tree_control)
            set_status("Choose a parent Context with arrows, then press Enter.")
        event.app.invalidate()

    @bindings.add("down", filter=has_focus(destination_tree_control), eager=True)
    @bindings.add("up", filter=has_focus(destination_tree_control), eager=True)
    def _move_destination_parent(event) -> None:
        state = destination_editor_state["value"]
        if state is not None:
            delta = -1 if event.key_sequence[0].key == Keys.Up else 1
            state.tree.move(delta)
            set_status("")
        event.app.invalidate()

    @bindings.add("enter", filter=has_focus(destination_tree_control), eager=True)
    def _use_destination_parent(event) -> None:
        use_destination_parent()
        event.app.invalidate()

    @bindings.add("c-j", filter=has_focus(destination_input), eager=True)
    def _reject_destination_newline(event) -> None:
        set_status("A Context name must stay on one line.")
        event.app.invalidate()

    def exit_simple(event, kind: str) -> None:
        action = semantic_action(kind)
        if action is not None:
            event.app.exit(result=action)
        else:
            event.app.invalidate()

    @bindings.add("p", filter=~writable_input_focused)
    def _preserve(event) -> None:
        exit_simple(event, "PRESERVE_ALL")

    @bindings.add("d", filter=~writable_input_focused)
    def _defer(event) -> None:
        exit_simple(event, "DEFER")

    @bindings.add("a", filter=~writable_input_focused)
    def _accept(event) -> None:
        if split_viewer_items and review_and_apply:
            open_final_review()
            event.app.invalidate()
            return
        exit_simple(event, "ACCEPT")

    @bindings.add("s", filter=~writable_input_focused)
    def _sort(event) -> None:
        if toggle_sort is None:
            set_status("Sorting is unavailable here.")
        else:
            save_draft()
            toggle_sort()
            current_navigation.sync(current_view())
            load_draft()
            set_status("")
        event.app.invalidate()

    def _collapse_detail(event) -> bool:
        if event.app.layout.has_focus(input_area):
            return False
        if (
            split_viewer_items
            and session_navigation.pane == "responses"
            and response_state.close_nested()
        ):
            set_status("")
            return True
        if viewer_controller.close_nested():
            set_status("")
            return True
        if expanded_memory_section_uid["uid"] is not None:
            expanded_memory_section_uid["uid"] = None
            set_status("")
            return True
        if current_navigation.expanded_item_uid is None:
            return False
        current_navigation.close_detail()
        return True

    def _close(event) -> None:
        if (
            save_draft_on_close
            and not event.app.layout.has_focus(input_area)
            and not save_draft()
        ):
            event.app.invalidate()
            return
        event.app.exit(result=ResolutionWorkbenchAction(kind="CLOSE"))

    @bindings.add("escape", filter=has_focus(destination_input), eager=True)
    def _cancel_destination_edit(event) -> None:
        destination_editing["value"] = False
        destination_editor_state["value"] = (
            SaveLocationEditorState.create(destination)
            if destination is not None
            else None
        )
        if destination is not None:
            destination_frame.title = safe_terminal_text(destination.label)
        session_navigation.focus("save_location")
        event.app.layout.focus(destination_control)
        set_status("")
        event.app.invalidate()

    @bindings.add("escape", filter=has_focus(input_area), eager=True)
    def _cancel_response_edit(event) -> None:
        if not split_viewer_items:
            _close(event)
            return
        if global_comment["value"]:
            input_area.text = global_response_draft["value"].text
        else:
            load_draft()
        response_state.editing = False
        other_direction_editor["open"] = False
        if split_viewer_items and response_visible():
            session_navigation.focus("responses")
            event.app.layout.focus(responses_control)
        else:
            session_navigation.focus("viewer")
            event.app.layout.focus(body_control)
        set_status("Response edit cancelled.")
        event.app.invalidate()

    @bindings.add("escape", filter=~writable_input_focused, eager=True)
    @bindings.add("backspace", filter=~writable_input_focused, eager=True)
    def _back_or_close(event) -> None:
        if destination_tree_is_focused():
            _cancel_destination_edit(event)
            return
        if (
            split_viewer_items
            and session_navigation.pane == "responses"
            and response_state.close_nested()
        ):
            set_status("")
            event.app.invalidate()
            return
        if viewer_controller.close_nested():
            set_status("")
            event.app.invalidate()
            return
        if expanded_memory_section_uid["uid"] is not None:
            expanded_memory_section_uid["uid"] = None
            set_status("")
            event.app.invalidate()
            return
        if split_viewer_items and viewer_content["kind"] == "REVIEW":
            close_final_review()
            event.app.invalidate()
            return
        if (
            split_viewer_items
            and not event.app.layout.has_focus(input_area)
            and session_navigation.row_index != 0
        ):
            session_navigation.row_index = 0
            set_viewer_content("REPORT")
            reset_viewer_section()
            current_navigation.close_detail()
            session_navigation.focus("items")
            event.app.layout.focus(items_control)
            event.app.invalidate()
            return
        # Keep the shared shell independent of operation-specific back
        # dispatchers: its only presentation layer is the expanded detail.
        if _collapse_detail(event):
            event.app.invalidate()
            return
        _close(event)

    @bind_case_insensitive_key(
        bindings, "q", filter=~writable_input_focused, eager=True
    )
    @bindings.add("c-c", eager=True)
    def _quit(event) -> None:
        _close(event)

    bind_session_help(
        bindings,
        filter=~writable_input_focused,
        app_input=app_input,
        app_output=app_output,
        study_surface="resolution",
    )

    def footer_text() -> str:
        if status["value"]:
            return f" {status['value']}"
        active_view = current_view()
        item = current_navigation.current_item(active_view)
        if get_app().layout.has_focus(destination_input):
            navigation_help = (
                " ↑/Tab browse parents  Enter save exact location  Esc cancel "
            )
        elif destination_tree_is_focused():
            navigation_help = (
                " ↑/↓ parent  ←/→ expand  Enter use  Tab edit directly  "
                "Esc/Backspace cancel "
            )
        elif split_viewer_items and split_kind() == "SAVE_LOCATION":
            navigation_help = " Enter change location  Tab switch  Q close "
        elif split_viewer_items and split_kind() == "RESPONSES":
            if read_only:
                navigation_help = (
                    " ↑/↓ saved response  Tab switch  Esc/Backspace report "
                )
            elif response_state.option_navigation_active:
                navigation_help = (
                    " ↑/↓ choice/Response  Enter select  "
                    "Esc/Backspace report  Tab switch "
                )
            else:
                navigation_help = (
                    " ↑/↓ choice/Response  Enter write response  Tab switch  "
                    "Esc/Backspace report "
                )
        elif split_viewer_items and split_kind() == "REPORT":
            if focused_impact_entry_uid() is not None:
                navigation_help = (
                    " ↑/↓ Memory  → show  ← hide  Enter toggle  "
                    "Tab switch  Esc/Backspace close "
                )
            else:
                navigation_help = (
                    " ↑/↓ block (hold accelerates)  PgUp/PgDn page  End last  Tab switch  "
                    "Enter inspect  Esc/Backspace close "
                    if read_only
                    else " ↑/↓ block (hold accelerates)  PgUp/PgDn page  End last  Tab switch  "
                    "Enter open  Esc/Backspace/Q close "
                )
        elif split_viewer_items and split_kind() == "TODO":
            todo = displayed_todo()
            if viewer_content["kind"] == "REVIEW":
                final_action = review_action()
                navigation_help = (
                    f" Enter {final_action.kind.lower()}  "
                    "Tab inspect review  Esc/Backspace return "
                )
            else:
                todo_hint = (
                    "apply confirmation"
                    if todo.kind == "REVIEW AND APPLY"
                    else todo.kind.lower()
                )
                navigation_help = (
                    " Tab switch  Q close "
                    if todo.kind == "COMPLETE"
                    else f" Enter {todo_hint}  Tab switch  Esc/Backspace back "
                )
        elif split_viewer_items and split_kind() == "RESOLVE_ALL":
            if viewer_content["kind"] == "REVIEW":
                final_action = review_action()
                review_section = active_viewer_sections()[viewer_section_index()]
                enter_hint = (
                    "Enter return"
                    if review_section.kind == "SUMMARY"
                    else f"Enter {final_action.kind.lower()}"
                    if review_section.kind == "ACTION"
                    else "←/→ policy"
                )
                navigation_help = (
                    f" ↑/↓ review  Tab switch  {enter_hint}  "
                    "Esc/Backspace return "
                )
            else:
                navigation_help = (
                    " ↑/↓ section/item  Tab switch  ←/→ strategy  "
                    "Enter open/run  C custom  Esc/Backspace report "
                )
        elif viewer_controller.nested_uid is not None:
            navigation_help = (
                " ↑/↓ scroll Memory  Enter/Esc/Backspace back  Tab switch "
            )
        elif (
            split_viewer_items
            and viewer_content["kind"] == "ITEM"
            and session_navigation.pane == "viewer"
            and active_viewer_sections()[viewer_section_index()].kind == "SOURCE_MEMORY"
        ):
            navigation_help = (
                " Enter read Memory  ↑/↓ section  Esc/Backspace back  Tab switch "
            )
        elif (
            split_viewer_items
            and viewer_content["kind"] == "ITEM"
            and session_navigation.pane == "viewer"
            and active_viewer_sections()[viewer_section_index()].kind == "MEMORY_ROW"
        ):
            navigation_help = (
                " Enter show/hide evidence  ↑/↓ Memory  Esc/Backspace back  Tab switch "
            )
        elif split_viewer_items and read_only:
            navigation_help = (
                " ↑/↓ section/item  Tab switch  Enter inspect  "
                "Esc/Backspace report "
            )
        elif split_viewer_items:
            navigation_help = (
                " ↑/↓ section  Tab Responses/Items  C response/comment  "
                "Esc/Backspace report "
            )
        elif (
            item is not None
            and current_navigation.expanded_item_uid == item.uid
            and item.options
        ):
            navigation_help = (
                " ↑/↓ option  Enter choose/clear  Esc/Backspace back  Tab comment "
            )
        elif current_navigation.expanded_item_uid is not None:
            navigation_help = " Enter close  Esc/Backspace back  Tab comment "
        else:
            navigation_help = (
                " ↑/↓ item  Enter detail  Shift-Tab switch  Tab/C comment "
                if split_viewer_items
                else " ↑/↓ item  Enter detail  Tab comment "
            )
        actions: list[str] = []
        if "SUBMIT_ALL" in active_view.capabilities:
            actions.append("G comment all")
        if "PRESERVE_ALL" in active_view.capabilities:
            actions.append("P preserve all")
        if "DEFER" in active_view.capabilities:
            actions.append("D defer")
        if "ACCEPT" in active_view.capabilities:
            actions.append("A review & apply" if review_and_apply else "A accept")
        if toggle_sort is not None:
            actions.append("S sort")
        if not (
            get_app().layout.has_focus(input_area)
            or get_app().layout.has_focus(destination_input)
        ):
            actions.append("H Help")
        if get_app().layout.has_focus(body_control):
            actions.append("y/Y copy")
        actions.append("Q close")
        state_label = (
            f" READ ONLY · {safe_terminal_text(active_view.status)} ·"
            if read_only
            else ""
        )
        return state_label + navigation_help + "  ".join(actions) + " "

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
    if split_viewer_items:
        viewer_frame = Frame(body, title="VIEWER")
        decision_container = ConditionalContainer(
            responses_window,
            filter=Condition(
                lambda: (
                    (target := current_response_target()) is not None
                    and target.has_decision
                )
            ),
        )
        responses_frame = Frame(
            HSplit([decision_container, composer.frame]),
            title="RESPONSES",
        )
        responses_container = ConditionalContainer(
            responses_frame,
            filter=Condition(response_visible),
        )
        items_frame = Frame(items_window, title="ITEMS")
        todo_frame = Frame(todo_window, title="TO DO")
        session_frames = [viewer_frame, responses_container, items_frame]
        if destination_available:
            session_frames.append(destination_frame)
        session_frames.extend([todo_frame, footer])
        # ``split_viewer_items`` separates semantic surfaces, not columns.
        # Compose those peer frames through the same one-column rule used by
        # Find and every other session workbench.
        root = build_tui_frame(*(TuiRegion(frame) for frame in session_frames))
        bind_focused_frame_style(
            viewer_frame,
            is_focused=lambda: session_navigation.pane == "viewer",
        )
        # Bind the nested box first. Its border glyphs become dynamic, so the
        # later outer-frame binding cannot accidentally make both surfaces
        # look focused at once.
        bind_focused_frame_style(
            composer.frame,
            is_focused=lambda: (
                session_navigation.pane == "composer"
                or (
                    session_navigation.pane == "responses"
                    and response_state.section == "RESPONSE"
                )
            ),
        )
        bind_focused_frame_style(
            responses_frame,
            is_focused=lambda: session_navigation.pane in {"responses", "composer"},
        )
        bind_focused_frame_style(
            items_frame,
            is_focused=lambda: session_navigation.pane == "items",
        )
        if destination_available:
            bind_focused_frame_style(
                destination_frame,
                is_focused=lambda: session_navigation.pane == "save_location",
            )
        bind_focused_frame_style(
            todo_frame,
            is_focused=lambda: session_navigation.pane == "todo",
        )
        focused_element = {
            "viewer": body_control,
            "responses": responses_control,
            "items": items_control,
            "save_location": destination_control,
            "todo": todo_control,
        }[session_navigation.pane]
    else:
        viewer_frame = Frame(HSplit([body, legacy_inline_input]), title="VIEWER")
        bind_focused_frame_style(
            viewer_frame,
            is_focused=lambda: True,
        )
        root = build_tui_frame(
            TuiRegion(viewer_frame),
            TuiRegion(footer),
        )
        focused_element = body_control
    application: Application[ResolutionWorkbenchAction] = Application(
        layout=Layout(root, focused_element=focused_element),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
        style=merge_styles(
            [
                MEMCOMMIT_TUI_STYLE,
                RESOLUTION_WORKBENCH_STYLE,
            ]
        ),
    )
    load_draft()

    def decision_free_apply_available() -> bool:
        if read_only or not review_and_apply:
            return False
        active_view = current_view()
        unresolved_required = any(
            item.effective_obligation == "REQUIRED"
            and not _item_is_answered(item, local_drafts)
            for item in active_view.items
        )
        if unresolved_required:
            return False
        todo = session_todo_view(
            active_view,
            local_drafts,
            review_and_apply=review_and_apply,
            read_only=read_only,
            whole_set_available=bool(global_strategies),
            read_only_handoff=read_only_handoff,
            item_handoff=current_item_handoff(),
        )
        if todo.kind != "REVIEW AND APPLY":
            return False
        review_action = session_review_action_view(
            active_view,
            local_drafts,
            whole_set_available=bool(global_strategies),
        )
        return review_action.kind in {"APPLY", "APPLY AS IS"}

    if (
        decision_free_behavior == "AUTO_ACCEPT"
        and decision_free_apply_available()
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
            and decision_free_apply_available()
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
