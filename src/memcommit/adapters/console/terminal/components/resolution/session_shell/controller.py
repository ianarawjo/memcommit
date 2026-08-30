"""Process-local state and semantic actions for a Resolution Session."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from memcommit.adapters.console.terminal.components.command_editor.command_review.model import CommandReview
from memcommit.adapters.console.terminal.components.responses.model import (
    ResponseDraft,
    ResponseTarget,
)
from memcommit.adapters.console.terminal.components.responses.resolution import (
    response_target_from_item,
)
from memcommit.adapters.console.terminal.components.responses.state import (
    ResponseFrameState,
)
from memcommit.adapters.console.terminal.components.save_location import (
    SaveLocationEditorState,
)
from memcommit.application.capabilities.resolution.workbench import (
    ResolutionNavigation,
    ResolutionWorkbenchAction,
    ResolutionWorkbenchError,
    ResolutionWorkbenchView,
)
from memcommit.application.capabilities.review_policy import DecisionFreeBehavior
from memcommit.application.capabilities.reviewing.session_navigation import (
    SessionWorkbenchNavigation,
    WorkbenchPane,
)

from memcommit.adapters.console.terminal.components.resolution.session_shell.presentation import (
    ResolutionDestination,
    ResolutionGlobalStrategy,
    SessionTodoView,
    _item_draft,
    _item_is_answered,
    session_review_action_view,
    session_todo_view,
)


@dataclass(frozen=True)
class FinalReviewOrigin:
    """Exact process-local focus state restored after final review."""

    viewer_kind: str
    pane: WorkbenchPane
    row_index: int
    viewer_row_index: int
    section_uid: str | None


@dataclass
class ResolutionSessionController:
    """Own mutable session state and validated semantic action construction.

    Prompt-toolkit widgets and key events remain outside this controller. Its
    state uses small mutable cells because live render callbacks retain stable
    references for the lifetime of one terminal Application.
    """

    supplier: Callable[[], ResolutionWorkbenchView]
    navigation: ResolutionNavigation
    session_navigation: SessionWorkbenchNavigation
    global_strategies: tuple[ResolutionGlobalStrategy, ...] = ()
    review_and_apply: bool = False
    read_only: bool = False
    read_only_handoff: SessionTodoView | None = None
    item_handoff: SessionTodoView | Callable[[], SessionTodoView | None] | None = None
    destination: ResolutionDestination | None = None
    draft_saver_available: bool = False

    status: dict[str, str] = field(default_factory=lambda: {"value": ""})
    global_comment: dict[str, bool] = field(default_factory=lambda: {"value": False})
    strategy: dict[str, int] = field(default_factory=lambda: {"index": 0})
    viewer_content: dict[str, str] = field(default_factory=lambda: {"kind": "REPORT"})
    final_review_title: dict[str, str] = field(
        default_factory=lambda: {"value": "APPLY CONFIRMATION"}
    )
    final_review_origin: dict[str, FinalReviewOrigin | None] = field(
        default_factory=lambda: {"value": None}
    )
    final_command_review: dict[str, CommandReview | None] = field(
        default_factory=lambda: {"value": None}
    )
    impact_reason_expanded: dict[str, str | None] = field(
        default_factory=lambda: {"uid": None}
    )
    other_direction: dict[str, bool] = field(default_factory=lambda: {"focused": False})
    other_direction_editor: dict[str, bool] = field(
        default_factory=lambda: {"open": False}
    )
    response_state: ResponseFrameState = field(default_factory=ResponseFrameState)
    global_response_draft: dict[str, ResponseDraft] = field(
        default_factory=lambda: {"value": ResponseDraft()}
    )
    expanded_memory_section_uid: dict[str, str | None] = field(
        default_factory=lambda: {"uid": None}
    )
    destination_editing: dict[str, bool] = field(
        default_factory=lambda: {"value": False}
    )
    destination_editor_state: dict[str, SaveLocationEditorState | None] = field(
        init=False
    )
    input_heading: dict[str, str] = field(
        default_factory=lambda: {"value": "COMMENT ON SELECTED ITEM"}
    )
    local_drafts: dict[str, ResponseDraft] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.destination_editor_state = {
            "value": (
                SaveLocationEditorState.create(self.destination)
                if self.destination is not None
                else None
            )
        }

    def current_view(self) -> ResolutionWorkbenchView:
        view = self.supplier()
        self.navigation.sync(view)
        return view

    def current_item_handoff(self) -> SessionTodoView | None:
        """Resolve operation-owned dynamic handoffs from current draft state."""

        if callable(self.item_handoff):
            return self.item_handoff()
        return self.item_handoff

    def seed_drafts(
        self,
        draft_loader: Callable[[str], tuple[str | None, str]] | None,
    ) -> None:
        """Freeze the operation's current durable response projection locally."""

        for item in self.current_view().items:
            if draft_loader is None:
                option_uid, comment = item.selected_option_uid, item.response_text
            else:
                option_uid, comment = draft_loader(item.uid)
            if option_uid is not None:
                item.option(option_uid)
            self.local_drafts[item.uid] = ResponseDraft(option_uid, comment)

    def current_response_target(self) -> ResponseTarget | None:
        """Project only the response context currently visible to the person."""

        active_view = self.current_view()
        if self.global_comment["value"]:
            return ResponseTarget(
                item_uid="WHOLE_SET",
                item_label=f"Complete {active_view.operation.title()} proposal",
                obligation="NONE",
                state=(
                    "ANSWERED"
                    if self.global_response_draft["value"].answered
                    else "OPEN"
                ),
                mode="COMMENT",
                editable=(
                    not self.read_only
                    and not active_view.input_locked
                    and "SUBMIT_ALL" in active_view.capabilities
                ),
            )
        if self.viewer_content["kind"] != "ITEM" and not self.response_state.editing:
            return None
        item = self.navigation.current_item(active_view)
        if item is None:
            return None
        return response_target_from_item(
            active_view,
            item,
            read_only=self.read_only,
            stage_locally=self.review_and_apply or self.draft_saver_available,
        )

    def current_response_draft(self, target: ResponseTarget) -> ResponseDraft:
        if target.item_uid == "WHOLE_SET":
            return self.global_response_draft["value"]
        item = self.navigation.current_item(self.current_view())
        if item is None or item.uid != target.item_uid:
            return ResponseDraft()
        return _item_draft(item, self.local_drafts)

    def sync_response_state(self) -> ResponseTarget | None:
        target = self.current_response_target()
        if target is None:
            return None
        self.response_state.sync(
            target,
            self.current_response_draft(target),
            frame_focused=self.session_navigation.pane == "responses",
        )
        return target

    def response_visible(self, *, split_viewer_items: bool) -> bool:
        target = self.current_response_target()
        if not split_viewer_items or target is None:
            return False
        # Read-only review retains saved evidence but never shows an empty
        # response surface that could imply the applied session is editable.
        return not self.read_only or self.current_response_draft(target).answered

    def set_status(self, message: str) -> None:
        self.status["value"] = message

    def semantic_action(
        self,
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
            return self.current_view().validate_action(action)
        except ResolutionWorkbenchError as error:
            self.set_status(str(error))
            return None

    def incorporate_responses_action(
        self,
        active_view: ResolutionWorkbenchView,
        *,
        action_kind: str = "SUBMIT_ALL",
    ) -> ResolutionWorkbenchAction | None:
        """Build the complete reviewed-response turn used by both surfaces."""

        if not self.global_strategies:
            self.set_status("No remaining-item policies are available.")
            return None
        selected_strategy = self.global_strategies[self.strategy["index"]]
        lines = ["Use these reviewed issue resolutions:"]
        unresolved_counts: dict[str, int] = {}
        unresolved_required: list[str] = []
        for item in active_view.items:
            obligation = item.effective_obligation
            draft = _item_draft(item, self.local_drafts)
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
        return self.semantic_action(action_kind, comment="\n".join(lines))

    def destination_action(self, value: str) -> ResolutionWorkbenchAction | None:
        if self.destination is None:
            self.set_status("Save-location editing is unavailable here.")
            return None
        try:
            self.destination.validate_value(value)
            return ResolutionWorkbenchAction(
                kind="CHANGE_DESTINATION",
                destination=value,
            )
        except (OSError, TypeError, ValueError) as error:
            self.set_status(str(error))
            return None

    def review_action(self) -> SessionTodoView:
        if self.final_review_title["value"] == "RESOLVE ALL":
            if not self.global_strategies:
                return SessionTodoView(
                    "COMPLETE",
                    "No whole-set strategy available",
                    "Return and review an individual item.",
                )
            selected_strategy = self.global_strategies[self.strategy["index"]]
            return SessionTodoView(
                "RESOLVE ALL",
                selected_strategy.label,
                selected_strategy.comment
                or "Enter to run the selected whole-set strategy.",
            )
        return session_review_action_view(
            self.current_view(),
            self.local_drafts,
            whole_set_available=bool(self.global_strategies),
        )

    def displayed_todo(self) -> SessionTodoView:
        """Describe review entry before opening and confirmation after it."""

        active_view = self.current_view()
        if self.viewer_content["kind"] == "REVIEW":
            action = self.review_action()
            return SessionTodoView(
                self.final_review_title["value"],
                f"Confirm final {active_view.operation.title()} action",
                f"{action.kind} is ready. Enter to {action.kind.lower()} now.",
            )
        return session_todo_view(
            active_view,
            self.local_drafts,
            review_and_apply=self.review_and_apply,
            read_only=self.read_only,
            whole_set_available=bool(self.global_strategies),
            read_only_handoff=self.read_only_handoff,
            item_handoff=self.current_item_handoff(),
        )

    def decision_free_apply_available(self) -> bool:
        if self.read_only or not self.review_and_apply:
            return False
        active_view = self.current_view()
        unresolved_required = any(
            item.effective_obligation == "REQUIRED"
            and not _item_is_answered(item, self.local_drafts)
            for item in active_view.items
        )
        if unresolved_required:
            return False
        todo = session_todo_view(
            active_view,
            self.local_drafts,
            review_and_apply=self.review_and_apply,
            read_only=self.read_only,
            whole_set_available=bool(self.global_strategies),
            read_only_handoff=self.read_only_handoff,
            item_handoff=self.current_item_handoff(),
        )
        if todo.kind != "REVIEW AND APPLY":
            return False
        review_action = session_review_action_view(
            active_view,
            self.local_drafts,
            whole_set_available=bool(self.global_strategies),
        )
        return review_action.kind in {"APPLY", "APPLY AS IS"}


def normalize_decision_free_behavior(
    behavior: DecisionFreeBehavior | None,
    *,
    start_final_review_when_no_required: bool,
) -> DecisionFreeBehavior:
    """Normalize the legacy flag into the explicit decision-free policy."""

    if behavior is None:
        return "FINAL_REVIEW" if start_final_review_when_no_required else "REPORT_FIRST"
    if start_final_review_when_no_required:
        raise ValueError(
            "Use either the legacy final-review flag or decision-free behavior."
        )
    if behavior not in {"REPORT_FIRST", "FINAL_REVIEW", "AUTO_ACCEPT"}:
        raise ValueError("Unsupported decision-free application behavior.")
    return behavior
