"""Process-local state for one named Ground workbench."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from memcommit.adapters.console.terminal.components.background_turn import (
    BackgroundExecutorTurn,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.application.operations.fit.ground_report import FitReport
from memcommit.application.operations.fit.store import GroundFitReceipt
from memcommit.application.operations.ground.model import GroundItem, GroundSession
from memcommit.application.operations.ground.turn_dialogue import GroundTurnDraft

from memcommit.adapters.console.commands.ground.named_shell.proposal import (
    GroundCommandProposal,
    NamedGroundShellResult,
    _aliased_items,
)

GroundShellMode = Literal[
    "INPUT",
    "INTERPRETING",
    "APPROVAL",
    "APPLYING",
    "ERROR",
    "APPLY_ERROR",
]
GroundShellExitStatus = Literal["CLOSED", "BACK_TO_PICKER"]
GroundInlineTarget = Literal["GOAL", "RULE", "MEMORY"]
GroundPaneLayer = Literal["GOAL", "CONTEXTS", "RULES", "MEMORIES", "CHAT"]


@dataclass
class NamedGroundShellState:
    """Own mutable UI and turn state for one terminal Application.

    Prompt-toolkit render and key callbacks retain this object for the lifetime
    of the Application. Durable Ground mutation remains behind the injected
    application callbacks; every field here is only a process-local projection.
    """

    current: GroundSession
    fit_receipt: GroundFitReceipt | None
    placement_catalog_names: tuple[str, ...]

    pending: GroundCommandProposal | None = None
    draft_queue: tuple[GroundTurnDraft, ...] = ()
    draft_index: int = 0
    draft_queue_stale: bool = False
    draft_source_submission: str = ""
    pending_draft_index: int | None = None
    mode: GroundShellMode = "INPUT"
    review_view: Literal["COMMAND", "EFFECTS"] = "COMMAND"
    error_message: str = ""
    status_message: str = ""
    last_submission: str = ""

    inline_target: GroundInlineTarget | None = None
    inline_selector: str = ""
    inline_original: str = ""
    inline_direct_locked: bool = False
    panel_comment_target: GroundPaneLayer | None = None
    panel_comment_focus: str = ""
    pending_inline_edit: (
        tuple[
            GroundInlineTarget,
            str,
            str,
            str,
            str,
        ]
        | None
    ) = None
    suspended_message: str = ""

    selected_rule_index: int = 0
    selected_memory_index: int = 0
    memory_detail_open: bool = False

    placement_choice: dict[str, str] = field(default_factory=dict)
    placement_overridden: dict[str, bool] = field(default_factory=dict)
    pane_notifications: dict[str, bool] = field(default_factory=dict)

    cycle_dialogue: list[str] = field(default_factory=list)
    all_submitted_turns: list[str] = field(default_factory=list)
    applied_argvs: list[tuple[str, ...]] = field(default_factory=list)
    conversation: list[str] = field(default_factory=list)

    fit_turn: BackgroundExecutorTurn[FitReport] = field(
        default_factory=BackgroundExecutorTurn
    )
    auto_fit_pending: bool = False
    auto_fit_enabled: bool = False
    deferred_exit_status: GroundShellExitStatus = "CLOSED"

    @classmethod
    def create(
        cls,
        session: GroundSession,
        *,
        fit_receipt: GroundFitReceipt | None,
        placement_catalog_names: tuple[str, ...],
        context_hints: tuple[str, ...],
        initial_question: str,
        initial_receipt: str,
        auto_fit_enabled: bool,
    ) -> NamedGroundShellState:
        bound_target_names = tuple(
            frame.context_name
            for frame in session.frames
            if frame.role in {"PUBLICATION_TARGET", "PLACEMENT_TARGET"}
        )
        initial_placement_options = bound_target_names or placement_catalog_names
        default_placement = next(
            (
                frame.context_name
                for frame in session.frames
                if frame.role == "PUBLICATION_TARGET"
            ),
            context_hints[0]
            if context_hints and context_hints[0] in initial_placement_options
            else initial_placement_options[0]
            if initial_placement_options
            else "",
        )
        conversation = [initial_question]
        if initial_receipt:
            conversation.insert(0, "APPLIED\n  " + safe_terminal_text(initial_receipt))
        return cls(
            current=session,
            fit_receipt=fit_receipt,
            placement_catalog_names=placement_catalog_names,
            placement_choice={
                "CONTEXTS": default_placement,
                "RULES": default_placement,
                "MEMORIES": default_placement,
            },
            placement_overridden={
                "CONTEXTS": False,
                "RULES": False,
                "MEMORIES": False,
            },
            pane_notifications={
                "GOAL": False,
                "CONTEXTS": False,
                "RULES": False,
                "MEMORIES": False,
                "CHAT": False,
            },
            conversation=conversation,
            auto_fit_enabled=auto_fit_enabled,
        )

    def current_placement_options(self) -> tuple[str, ...]:
        bound = tuple(
            frame.context_name
            for frame in self.current.frames
            if frame.role in {"PUBLICATION_TARGET", "PLACEMENT_TARGET"}
        )
        return bound or self.placement_catalog_names

    def mark_pane_updates(self, *layers: str) -> None:
        for layer in layers:
            self.pane_notifications[layer] = True

    def acknowledge_pane(self, layer: str) -> None:
        self.pane_notifications[layer] = False

    def dialogue_text(self) -> str:
        return "\n\n".join(self.cycle_dialogue)

    def selected_saved_item(
        self,
        kind: Literal["RULE", "CASE"],
        index: int,
    ) -> tuple[str, GroundItem] | None:
        items = _aliased_items(self.current, kind)
        if not items:
            return None
        return items[min(max(index, 0), len(items) - 1)]

    @staticmethod
    def changed_pane_layers(
        previous: GroundSession,
        refreshed: GroundSession,
    ) -> tuple[str, ...]:
        """Identify saved layers that visibly changed after a reload/apply."""

        changed: list[str] = []
        if previous.goal != refreshed.goal:
            changed.append("GOAL")
        if (previous.schema_version, previous.frames) != (
            refreshed.schema_version,
            refreshed.frames,
        ):
            changed.append("CONTEXTS")
        for kind, layer in (("RULE", "RULES"), ("CASE", "MEMORIES")):
            before = tuple(item for item in previous.items if item.kind == kind)
            after = tuple(item for item in refreshed.items if item.kind == kind)
            if before != after:
                changed.append(layer)
        return tuple(changed)

    def result(self, status: GroundShellExitStatus) -> NamedGroundShellResult:
        return NamedGroundShellResult(
            status=status,
            session=self.current,
            applied_argvs=tuple(self.applied_argvs),
            submitted_turns=tuple(self.all_submitted_turns),
        )
