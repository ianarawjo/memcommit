"""Draft states and transitions for one blank-Ground terminal session."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from memcommit.adapters.console.commands.ground.shell.proposal import (
    GroundShellContextSuggestion,
    GroundShellMemoryDraft,
    GroundShellNewContextSuggestion,
    GroundShellProposal,
    GroundShellRuleDraft,
)
from memcommit.adapters.console.commands.ground.shell.runtime.grounding_drafting.response import (
    GroundingDraftResponse,
)

GroundPane = Literal["LOCATION", "GOAL", "CONTEXTS", "RULES", "MEMORIES", "CHAT"]
GroundReviewMode = Literal[
    "INPUT", "CONTEXT_SELECTION", "APPROVAL", "APPLYING", "APPLY_ERROR"
]
GroundShellMode = Literal[GroundReviewMode, "INTERPRETING", "ERROR"]


@dataclass(frozen=True)
class DraftRequest:
    text: str
    target: GroundPane
    display: str
    append_user: bool = False
    initial: bool = False
    planned_ground_name: str | None = None
    required_direct_goal: str | None = None


@dataclass
class DraftSelection:
    context_names: tuple[str, ...] = ()
    new_context_name: str = ""
    context_candidate_index: int = 0
    context_selection_finished: bool = False
    memory_row: int = 0
    memory_column: int = 0


@dataclass
class DraftReview:
    mode: GroundReviewMode = "INPUT"
    pending: GroundShellProposal | None = None
    suspended_context_proposal: GroundShellProposal | None = None


@dataclass(frozen=True, kw_only=True)
class DraftInput:
    """Local editing is possible before the first provider response."""

    selection: DraftSelection = field(default_factory=DraftSelection)
    review: DraftReview = field(default_factory=DraftReview)


@dataclass(frozen=True, kw_only=True)
class DraftCompleted(DraftInput):
    request: DraftRequest
    response: GroundingDraftResponse


@dataclass(frozen=True)
class DraftThinking:
    request: DraftRequest
    new_context_name: str = ""


@dataclass(frozen=True)
class DraftFailed:
    request: DraftRequest
    message: str


DraftState = DraftInput | DraftThinking | DraftCompleted | DraftFailed


class GroundDraftLifecycle:
    def __init__(self, state: DraftState | None = None) -> None:
        self.state = state if state is not None else DraftInput()
        self.closed = False
        self.on_change: Callable[[DraftState], None] | None = None

    def begin(
        self, request: DraftRequest, *, new_context_name: str = ""
    ) -> DraftThinking:
        if self.closed:
            raise RuntimeError("The Ground workbench is closed.")
        turn = DraftThinking(request, new_context_name)
        self.publish(turn)
        return turn

    def complete(self, turn: DraftThinking, response: GroundingDraftResponse) -> None:
        if not self.is_current(turn):
            return
        review = DraftReview()
        if response.kind == "PROPOSE":
            review = DraftReview(
                mode=(
                    "CONTEXT_SELECTION"
                    if response.context_suggestions or response.new_context_suggestions
                    else "APPROVAL"
                ),
                pending=response.proposal,
            )
        self.publish(
            DraftCompleted(
                request=turn.request,
                response=response,
                selection=DraftSelection(new_context_name=turn.new_context_name),
                review=review,
            )
        )

    def fail(self, turn: DraftThinking, error: Exception) -> None:
        if self.is_current(turn):
            self.publish(DraftFailed(turn.request, f"{type(error).__name__}: {error}"))

    def return_to_input(self) -> None:
        if isinstance(self.state, DraftInput):
            # Refinement retains previews and the person's Context plan; a new
            # provider attempt, in contrast, owns a fresh selection from begin().
            self.state.review.mode = "INPUT"
            self.state.review.pending = None
            self.state.review.suspended_context_proposal = None
        else:
            self.state = DraftInput()

    def is_current(self, turn: DraftThinking) -> bool:
        # Object identity binds both success and failure to their originating
        # attempt, including when an older provider thread finishes last.
        return not self.closed and self.state is turn

    def publish(self, state: DraftState) -> None:
        self.state = state
        if self.on_change is not None:
            self.on_change(state)

    def close(self) -> None:
        self.closed = True

    @property
    def editable(self) -> DraftInput:
        if not isinstance(self.state, DraftInput):
            raise RuntimeError(
                "This drafting state has no editable selection or receipt."
            )
        return self.state

    @property
    def mode(self) -> GroundShellMode:
        if isinstance(self.state, DraftThinking):
            return "INTERPRETING"
        if isinstance(self.state, DraftFailed):
            return "ERROR"
        return self.state.review.mode

    @property
    def pending(self) -> GroundShellProposal | None:
        return self.state.review.pending if isinstance(self.state, DraftInput) else None

    @property
    def suspended_context_proposal(self) -> GroundShellProposal | None:
        return (
            self.state.review.suspended_context_proposal
            if isinstance(self.state, DraftInput)
            else None
        )

    @property
    def selection(self) -> DraftSelection | None:
        return self.state.selection if isinstance(self.state, DraftInput) else None

    @property
    def new_context_name(self) -> str:
        if isinstance(self.state, DraftThinking):
            return self.state.new_context_name
        selection = self.selection
        return selection.new_context_name if selection is not None else ""

    @property
    def error_message(self) -> str:
        return self.state.message if isinstance(self.state, DraftFailed) else ""

    @property
    def discovery_complete(self) -> bool:
        return isinstance(self.state, DraftCompleted)

    @property
    def discovery_in_progress(self) -> bool:
        return isinstance(self.state, DraftThinking)

    @property
    def context_suggestions(self) -> tuple[GroundShellContextSuggestion, ...]:
        return (
            self.state.response.context_suggestions
            if isinstance(self.state, DraftCompleted)
            else ()
        )

    @property
    def new_context_suggestions(self) -> tuple[GroundShellNewContextSuggestion, ...]:
        return (
            self.state.response.new_context_suggestions
            if isinstance(self.state, DraftCompleted)
            else ()
        )

    @property
    def rule_drafts(self) -> tuple[GroundShellRuleDraft, ...]:
        return (
            self.state.response.rule_drafts
            if isinstance(self.state, DraftCompleted)
            else ()
        )

    @property
    def memory_drafts(self) -> tuple[GroundShellMemoryDraft, ...]:
        return (
            self.state.response.memory_drafts
            if isinstance(self.state, DraftCompleted)
            else ()
        )

    @classmethod
    def resumed(
        cls, proposal: GroundShellProposal, request: DraftRequest
    ) -> GroundDraftLifecycle:
        # A saved receipt restores its Rule/Memory previews, not old Context
        # recommendations or local checked choices.
        response = GroundingDraftResponse(
            kind="PROPOSE",
            understanding=proposal.understanding,
            question=proposal.question,
            proposal=proposal,
            context_suggestions=(),
            new_context_suggestions=(),
            rule_drafts=proposal.rule_drafts,
            memory_drafts=proposal.memory_drafts,
        )
        return cls(
            DraftCompleted(
                request=request,
                response=response,
                review=DraftReview(mode="APPROVAL", pending=proposal),
            )
        )
