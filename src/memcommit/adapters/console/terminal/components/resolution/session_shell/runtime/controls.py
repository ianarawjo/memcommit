"""Live prompt-toolkit controls for the Resolution Session runtime."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from prompt_toolkit.application.current import get_app
from prompt_toolkit.filters import has_focus
from prompt_toolkit.layout import (
    DynamicContainer,
    FormattedTextControl,
    HSplit,
    Window,
)
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.widgets import Frame

from memcommit.adapters.console.coordination.command_review.model import CommandReview
from memcommit.adapters.console.terminal.components.exact_name import (
    ExactNameFieldView,
    ExactNameInputControl,
)
from memcommit.adapters.console.terminal.components.impact import ImpactController
from memcommit.adapters.console.terminal.components.multiline_input import (
    build_framed_multiline_input,
)
from memcommit.adapters.console.terminal.components.plain_text_clipboard import (
    plain_text_from_fragments,
)
from memcommit.adapters.console.terminal.components.responses import (
    response_frame_fragments,
)
from memcommit.adapters.console.terminal.components.responses.model import ResponseDraft
from memcommit.adapters.console.terminal.components.save_location import (
    save_location_row_fragments,
    save_location_tree_fragments,
)
from memcommit.adapters.console.terminal.components.scrollable_pane import (
    WrappedScrollbarMargin,
)
from memcommit.adapters.console.terminal.components.semantic_viewer import (
    SemanticViewerController,
)
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    focused_control_style,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.application.capabilities.resolution.workbench import (
    ResolutionItem,
    ResolutionWorkbenchView,
)
from memcommit.application.capabilities.reviewing.session_navigation import (
    WorkbenchSection,
)

from memcommit.adapters.console.terminal.components.resolution.session_shell.controller import (
    ResolutionSessionController,
)
from memcommit.adapters.console.terminal.components.resolution.session_shell.presentation import (
    ResolutionDestination,
    ResolutionGlobalStrategy,
    SessionTodoView,
    _current_impact,
    _impact_entry_item,
    _impact_entry_section_uid,
    _impact_repeats_results,
    _line,
    _memory_row_section_uid,
    _seeded_report_lines,
    _seeded_report_sections,
    _session_items_fragments,
    _stable_sections,
    _viewer_focus_fragments,
    resolution_report_fragments,
    resolution_review_fragments,
    resolution_seeded_report_fragments,
    resolution_viewer_fragments,
    resolution_workbench_fragments,
)


def report_sections(
    view: ResolutionWorkbenchView,
    *,
    split_report_text: str | None,
    global_strategies: tuple[ResolutionGlobalStrategy, ...],
    review_and_apply: bool,
    read_only: bool,
    impact_controller: ImpactController | None,
    drafts: dict[str, ResponseDraft],
) -> tuple[WorkbenchSection, ...]:
    """Project a report into stable semantic navigation stops."""

    if split_report_text is not None:
        lines = _seeded_report_lines(
            view,
            split_report_text,
            global_strategies,
            review_and_apply=review_and_apply,
            read_only=read_only,
            impact_controller=impact_controller,
            drafts=drafts,
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
            # A trusted read-only report is still one navigable surface even
            # when it does not expose the common ITEM:/IMPACT child markers.
            entries = (("REPORT", "SEEDED:REPORT", 0),)
        return _stable_sections(entries)

    entries: list[tuple[str, str, int | None]] = [
        ("OVERVIEW", f"REPORT:OVERVIEW:{section.uid}", 0)
        for section in view.semantic_overview_sections
    ]
    if view.report_items_summary is not None:
        entries.append(("REVIEW_ITEMS", "REPORT:REVIEW_ITEMS", 0))
    else:
        entries.extend(
            ("ITEM", f"ITEM:{item.uid}", index)
            for index, item in enumerate(view.items, start=1)
        )
    active_impact = _current_impact(impact_controller, view)
    impact_repeats_results = _impact_repeats_results(active_impact, view)
    if view.show_results and not impact_repeats_results:
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


def item_sections(item: ResolutionItem | None) -> tuple[WorkbenchSection, ...]:
    """Project one opened item into its stable evidence/detail stops."""

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
                for criterion_index, _criterion in enumerate(evidence.criterion_blocks)
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


def review_sections(
    action: SessionTodoView,
    command_review: CommandReview | None,
) -> tuple[WorkbenchSection, ...]:
    """Project final review into summary, policy, command, and action stops."""

    entries: list[tuple[str, str, int | None]] = [("SUMMARY", "REVIEW:SUMMARY", None)]
    if action.kind in {"INCORPORATE RESPONSES", "INCORPORATE AND APPLY"}:
        entries.append(("POLICY", "REVIEW:POLICY", None))
    if command_review is not None:
        entries.append(("COMMAND", "REVIEW:COMMAND", None))
    entries.append(("ACTION", "REVIEW:ACTION", None))
    return _stable_sections(tuple(entries))


@dataclass(frozen=True)
class ResolutionControlConfig:
    """Frozen rendering and availability inputs for one live control set."""

    split_viewer_items: bool
    global_strategies: tuple[ResolutionGlobalStrategy, ...]
    split_report_text: str | None
    split_report_fragments: tuple[tuple[str, str], ...] | None
    split_report_item_badges: tuple[str, ...]
    split_report_conflicts_remaining: int | None
    review_and_apply: bool
    read_only: bool
    impact_controller: ImpactController | None
    destination: ResolutionDestination | None
    destination_available: bool


class ResolutionShellControls:
    """Create and own every live control used by the full session shell."""

    def __init__(
        self,
        controller: ResolutionSessionController,
        viewer_controller: SemanticViewerController,
        config: ResolutionControlConfig,
        *,
        multiline_input_factory: Callable[..., Any] = build_framed_multiline_input,
        frame_factory: Callable[..., Frame] = Frame,
    ) -> None:
        self.controller = controller
        self.viewer_controller = viewer_controller
        self.config = config
        self.viewer_frame: Frame | None = None

        self.composer = multiline_input_factory(
            "RESPONSE",
            prompt="› ",
            buffer_name="resolution-message",
            height=Dimension(min=4, preferred=5, max=7),
            # The outer Responses frame may be focused while a choice row owns
            # the keyboard, so the nested box starts neutral.
            frame_style="fg:#f4f5f7 nobold",
        )
        self.input_area = self.composer.text_area
        self.body_control = FormattedTextControl(
            lambda: (
                self.split_view_fragments()
                if config.split_viewer_items
                else resolution_workbench_fragments(
                    controller.current_view(),
                    controller.navigation,
                    other_direction_focused=controller.other_direction["focused"],
                )
            ),
            focusable=True,
            show_cursor=False,
        )
        self.body = Window(
            self.body_control,
            wrap_lines=True,
            right_margins=[WrappedScrollbarMargin(display_arrows=True)],
        )

        self.responses_control = FormattedTextControl(
            self.responses_fragments,
            focusable=True,
            show_cursor=False,
        )
        self.responses_window = Window(
            self.responses_control,
            height=Dimension(min=4, preferred=9, max=13, weight=4),
            wrap_lines=True,
            right_margins=[WrappedScrollbarMargin(display_arrows=True)],
        )
        self.items_control = FormattedTextControl(
            self.item_fragments,
            focusable=True,
            show_cursor=False,
        )
        self.items_window = Window(
            self.items_control,
            height=Dimension(min=4, preferred=6, max=8, weight=3),
            wrap_lines=False,
            right_margins=[ScrollbarMargin(display_arrows=True)],
        )
        self.todo_control = FormattedTextControl(
            self.todo_fragments,
            focusable=True,
            show_cursor=False,
        )
        self.todo_window = Window(
            self.todo_control,
            height=Dimension.exact(1),
            dont_extend_height=True,
            wrap_lines=False,
        )
        self.destination_control = FormattedTextControl(
            self.destination_fragments,
            focusable=True,
            show_cursor=False,
        )
        self.destination_window = Window(
            self.destination_control,
            height=Dimension.exact(1),
            dont_extend_height=True,
            wrap_lines=False,
        )
        self.destination_name_field = ExactNameInputControl.create(
            config.destination
            if config.destination is not None
            else ExactNameFieldView(value="", label="SAVE LOCATION"),
            input_name="resolution-save-location",
        )
        self.destination_input = self.destination_name_field.input
        self.destination_tree_control = FormattedTextControl(
            self.destination_tree_fragments,
            focusable=True,
            show_cursor=False,
        )
        destination_tree_window = Window(
            self.destination_tree_control,
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
                self.destination_input,
            ]
        )
        self._destination_editor_with_tree = destination_editor_with_tree
        self.destination_frame = frame_factory(
            DynamicContainer(self.destination_frame_content),
            title=(
                safe_terminal_text(config.destination.label)
                if config.destination is not None
                else "SAVE LOCATION"
            ),
        )
        self.writable_input_focused = has_focus(self.input_area) | has_focus(
            self.destination_input
        )

    @property
    def current_view(self) -> ResolutionWorkbenchView:
        return self.controller.current_view()

    def attach_viewer_frame(self, frame: Frame) -> None:
        """Attach the frame created by layout before any review transition."""

        self.viewer_frame = frame

    def response_visible(self) -> bool:
        return self.controller.response_visible(
            split_viewer_items=self.config.split_viewer_items
        )

    def report_sections(self) -> tuple[WorkbenchSection, ...]:
        return report_sections(
            self.controller.current_view(),
            split_report_text=self.config.split_report_text,
            global_strategies=self.config.global_strategies,
            review_and_apply=self.config.review_and_apply,
            read_only=self.config.read_only,
            impact_controller=self.config.impact_controller,
            drafts=self.controller.local_drafts,
        )

    def item_sections(self) -> tuple[WorkbenchSection, ...]:
        return item_sections(
            self.controller.navigation.current_item(self.controller.current_view())
        )

    def active_viewer_sections(self) -> tuple[WorkbenchSection, ...]:
        if self.controller.viewer_content["kind"] == "REPORT":
            return self.report_sections()
        if self.controller.viewer_content["kind"] == "REVIEW":
            return review_sections(
                self.controller.review_action(),
                self.controller.final_command_review["value"],
            )
        return self.item_sections()

    def viewer_section_index(self) -> int:
        return self.viewer_controller.index(self.active_viewer_sections())

    def reset_viewer_section(self) -> None:
        self.viewer_controller.close_nested()
        sections = self.active_viewer_sections()
        self.controller.session_navigation.section_uid = (
            sections[0].uid if sections else None
        )

    def focused_source_memory(self):
        """Resolve the exact typed Memory owned by the current Viewer stop."""

        section = self.viewer_controller.current(self.active_viewer_sections())
        item = self.controller.navigation.current_item(self.controller.current_view())
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

    @staticmethod
    def pane_content_width() -> int:
        """Track the live inner frame width, including terminal resizes."""

        try:
            columns = get_app().output.get_size().columns
        except (AttributeError, RuntimeError):
            return 76
        return max(20, columns - 3)

    def split_kind(self) -> str:
        navigation = self.controller.session_navigation
        if navigation.pane == "save_location":
            return "SAVE_LOCATION"
        if navigation.pane == "responses":
            return "RESPONSES"
        if navigation.pane == "todo":
            return "TODO"
        if (
            navigation.pane == "viewer"
            and self.controller.viewer_content["kind"] == "REVIEW"
        ):
            return "RESOLVE_ALL"
        if navigation.row_index == 0:
            return "REPORT"
        if navigation.row_index <= len(self.controller.current_view().items):
            return "ITEM"
        return "RESOLVE_ALL"

    def focused_impact_entry_uid(self) -> str | None:
        navigation = self.controller.session_navigation
        if not (
            self.config.split_viewer_items
            and navigation.pane == "viewer"
            and self.controller.viewer_content["kind"] == "REPORT"
            and self.split_kind() == "REPORT"
        ):
            return None
        section = self.active_viewer_sections()[self.viewer_section_index()]
        if section.kind != "IMPACT_ENTRY":
            return None
        impact = _current_impact(
            self.config.impact_controller,
            self.controller.current_view(),
        )
        if impact is None:
            return None
        for index, entry in enumerate(impact.entries, start=1):
            if _impact_entry_section_uid(entry, index) == section.uid and (
                entry.rules or entry.reason
            ):
                return section.uid
        return None

    def focused_impact_comment_item(self) -> ResolutionItem | None:
        navigation = self.controller.session_navigation
        if not (
            self.config.split_viewer_items
            and navigation.pane == "viewer"
            and self.controller.viewer_content["kind"] == "REPORT"
            and self.split_kind() == "REPORT"
        ):
            return None
        section = self.active_viewer_sections()[self.viewer_section_index()]
        if section.kind != "IMPACT_ENTRY":
            return None
        active_view = self.controller.current_view()
        impact = _current_impact(self.config.impact_controller, active_view)
        if impact is None:
            return None
        for index, entry in enumerate(impact.entries, start=1):
            if _impact_entry_section_uid(entry, index) != section.uid:
                continue
            item = _impact_entry_item(active_view, entry)
            return item if item is not None and item.commentable else None
        return None

    def split_view_fragments(self):
        active_view = self.controller.current_view()
        navigation = self.controller.session_navigation
        config = self.config
        if self.controller.viewer_content["kind"] == "REVIEW":
            return _viewer_focus_fragments(
                resolution_review_fragments(
                    active_view,
                    self.controller.local_drafts,
                    config.global_strategies,
                    self.controller.strategy["index"],
                    self.controller.review_action(),
                    self.viewer_section_index(),
                    content_width=self.pane_content_width(),
                    review_title=self.controller.final_review_title["value"],
                    command_review=self.controller.final_command_review["value"],
                ),
                focused=navigation.pane == "viewer",
            )
        if self.controller.viewer_content["kind"] == "REPORT":
            if config.split_report_text is not None:
                return _viewer_focus_fragments(
                    resolution_seeded_report_fragments(
                        active_view,
                        config.split_report_text,
                        report_fragments=config.split_report_fragments,
                        strategies=config.global_strategies,
                        drafts=self.controller.local_drafts,
                        report_item_badges=config.split_report_item_badges,
                        report_conflicts_remaining=(
                            config.split_report_conflicts_remaining
                        ),
                        selected_strategy_index=self.controller.strategy["index"],
                        focused_section=self.viewer_section_index(),
                        review_and_apply=config.review_and_apply,
                        read_only=config.read_only,
                        impact_controller=config.impact_controller,
                        content_width=self.pane_content_width(),
                    ),
                    focused=navigation.pane == "viewer",
                )
            return _viewer_focus_fragments(
                resolution_report_fragments(
                    active_view,
                    strategies=config.global_strategies,
                    drafts=self.controller.local_drafts,
                    focused_section=self.viewer_section_index(),
                    review_and_apply=config.review_and_apply,
                    read_only=config.read_only,
                    impact_controller=config.impact_controller,
                    expanded_impact_section_uid=(
                        self.controller.impact_reason_expanded["uid"]
                    ),
                    content_width=self.pane_content_width(),
                ),
                focused=navigation.pane == "viewer",
            )
        return _viewer_focus_fragments(
            resolution_viewer_fragments(
                active_view,
                self.controller.navigation,
                focused_section=self.viewer_section_index(),
                other_direction_editing=(
                    self.controller.other_direction_editor["open"]
                ),
                expanded_memory_section_uid=(
                    self.controller.expanded_memory_section_uid["uid"]
                ),
                nested_source_memory_uid=self.viewer_controller.nested_uid,
                nested_source_memory_line=self.viewer_controller.nested_index,
                include_response_sections=False,
                content_width=self.pane_content_width(),
            ),
            focused=navigation.pane == "viewer",
        )

    def set_viewer_content(self, kind: str) -> None:
        self.controller.viewer_content["kind"] = kind
        if self.viewer_frame is not None:
            self.viewer_frame.title = "" if kind == "REVIEW" else "VIEWER"

    def current_viewer_plain_text(self, *, whole_document: bool) -> str:
        fragments = (
            self.split_view_fragments()
            if self.config.split_viewer_items
            else resolution_workbench_fragments(
                self.controller.current_view(),
                self.controller.navigation,
                other_direction_focused=self.controller.other_direction["focused"],
            )
        )
        return plain_text_from_fragments(
            fragments,
            whole_document=whole_document,
        )

    def responses_fragments(self) -> list[tuple[str, str]]:
        target = self.controller.sync_response_state()
        if target is None:
            return [("", " No response target is open.\n")]
        return response_frame_fragments(
            target,
            self.controller.current_response_draft(target),
            self.controller.response_state,
            focused=self.controller.session_navigation.pane == "responses",
            content_width=self.pane_content_width(),
        )

    def item_fragments(self):
        active_view = self.controller.current_view()
        navigation = self.controller.session_navigation
        return _session_items_fragments(
            active_view,
            selected_index=navigation.row_index,
            focused=navigation.pane == "items",
            content_width=self.pane_content_width(),
            report_label=f"Complete {active_view.operation.title()} report",
        )

    def todo_fragments(self) -> list[tuple[str, str]]:
        todo = self.controller.displayed_todo()
        focused = self.controller.session_navigation.pane == "todo"
        display_kind = (
            "APPLY CONFIRMATION" if todo.kind == "REVIEW AND APPLY" else todo.kind
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
                    max(10, self.pane_content_width() - len(display_kind) - 8),
                ),
            ),
        ]

    def destination_fragments(self) -> list[tuple[str, str]]:
        destination = self.config.destination
        if destination is None:
            return []
        return save_location_row_fragments(
            destination,
            focused=self.controller.session_navigation.pane == "save_location",
            content_width=self.pane_content_width(),
        )

    def destination_tree_fragments(self) -> list[tuple[str, str]]:
        state = self.controller.destination_editor_state["value"]
        if state is None:
            return []
        return save_location_tree_fragments(
            state,
            focused=get_app().layout.has_focus(self.destination_tree_control),
        )

    def destination_frame_content(self):
        if not self.controller.destination_editing["value"]:
            return self.destination_window
        if self.controller.destination_editor_state["value"] is None:
            return self.destination_input
        return self._destination_editor_with_tree

    def destination_tree_is_focused(self) -> bool:
        return (
            self.controller.destination_editing["value"]
            and self.controller.destination_editor_state["value"] is not None
            and get_app().layout.has_focus(self.destination_tree_control)
        )
