"""Typed presentation contract for provider-free required resolutions."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.interfaces.tui.components.exact_command_review import (
    ExactCommandReview,
)
from memcommit.interfaces.tui.viewers.semantic import SemanticViewerDocument
from memcommit.resolution import (
    ResolutionAttempt,
    ResolutionCase,
    ResolutionSubmission,
    require_resolution_ready,
)


@dataclass(frozen=True)
class ResolutionChoice:
    """One operation-owned deterministic choice shown by the shared shell."""

    uid: str
    label: str
    description: str

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, str) or not value
            for value in (self.uid, self.label, self.description)
        ):
            raise ValueError("Resolution choices require complete text values.")


@dataclass(frozen=True)
class ResolutionItem:
    """One required review target and its deterministic choice vocabulary."""

    uid: str
    label: str
    classification: str
    detail: SemanticViewerDocument
    choices: tuple[ResolutionChoice, ...]

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, str) or not value
            for value in (self.uid, self.label, self.classification)
        ):
            raise ValueError("Resolution items require complete identity text.")
        if not isinstance(self.detail, SemanticViewerDocument):
            raise TypeError("Resolution item detail must be a semantic document.")
        if not self.choices or len({choice.uid for choice in self.choices}) != len(
            self.choices
        ):
            raise ValueError("Resolution items require distinct real choices.")


@dataclass(frozen=True)
class ResolutionBulkStrategy:
    """One explicit whole-set choice and its fused exact approval card."""

    key: str
    choice_uid: str
    label: str
    review: ExactCommandReview

    def __post_init__(self) -> None:
        if (
            not isinstance(self.key, str)
            or len(self.key) != 1
            or not self.key.isalpha()
            or not self.choice_uid
            or not self.label
            or not isinstance(self.review, ExactCommandReview)
        ):
            raise ValueError("Resolution bulk strategy is invalid.")


@dataclass(frozen=True)
class ResolutionWorkbenchSpec:
    """Complete operation projection consumed by the shared Resolution shell."""

    case: ResolutionCase
    title: str
    subtitle: str
    report: SemanticViewerDocument
    items: tuple[ResolutionItem, ...]
    exact_review: ExactCommandReview
    bulk_strategies: tuple[ResolutionBulkStrategy, ...] = ()
    detail_title: str = "VIEWER · REQUIRED CONFLICT DETAIL"
    responses_title: str = "RESPONSES · REQUIRED · DETERMINISTIC ONLY"
    items_title: str = "ITEMS · REQUIRED CONFLICTS ONLY"

    def __post_init__(self) -> None:
        if not isinstance(self.case, ResolutionCase):
            raise TypeError("Resolution workbench requires a frozen case.")
        if not self.title or not self.subtitle:
            raise ValueError("Resolution workbench requires visible headings.")
        if not isinstance(self.report, SemanticViewerDocument):
            raise TypeError("Resolution report must be a semantic document.")
        if not self.items or len({item.uid for item in self.items}) != len(self.items):
            raise ValueError("Resolution workbench requires distinct required items.")
        if not isinstance(self.exact_review, ExactCommandReview):
            raise TypeError("Resolution workbench exact review is invalid.")
        if any(
            not isinstance(value, str) or not value
            for value in (
                self.detail_title,
                self.responses_title,
                self.items_title,
            )
        ):
            raise ValueError("Resolution workbench frame titles must be nonempty.")
        bulk_uids = tuple(strategy.choice_uid for strategy in self.bulk_strategies)
        bulk_keys = tuple(strategy.key.casefold() for strategy in self.bulk_strategies)
        if len(set(bulk_uids)) != len(bulk_uids):
            raise ValueError("Resolution bulk strategies must be distinct.")
        if len(set(bulk_keys)) != len(bulk_keys):
            raise ValueError("Resolution bulk strategy keys must be distinct.")
        if any(
            any(
                strategy.choice_uid not in {choice.uid for choice in item.choices}
                for item in self.items
            )
            for strategy in self.bulk_strategies
        ):
            raise ValueError("Resolution bulk strategy is unavailable for one item.")

        requirements = self.case.requirements
        if tuple(item.uid for item in self.items) != tuple(
            requirement.item_uid for requirement in requirements
        ):
            raise ValueError(
                "Resolution workbench items must exactly project the frozen case."
            )
        for item, requirement in zip(self.items, requirements, strict=True):
            if requirement.obligation != "REQUIRED" or requirement.comment_allowed:
                raise ValueError(
                    "The deterministic workbench supports choice-only required items."
                )
            if tuple(choice.uid for choice in item.choices) != requirement.choice_uids:
                raise ValueError(
                    "Resolution workbench choices must exactly project the frozen case."
                )

    def validate_outcome(self, outcome: "ResolutionOutcome") -> "ResolutionOutcome":
        """Bind one UI outcome to this exact case and canonical frozen order."""

        if not isinstance(outcome, ResolutionOutcome):
            raise TypeError("Resolution workbench outcome is invalid.")
        if outcome.bulk_uid is None:
            attempt = ResolutionAttempt(
                binding=self.case.binding,
                submissions=tuple(
                    ResolutionSubmission(item_uid, choice_uid=choice_uid)
                    for item_uid, choice_uid in outcome.decisions
                ),
            )
        else:
            attempt = ResolutionAttempt(
                binding=self.case.binding,
                bulk_choice_uid=outcome.bulk_uid,
            )
        progress = require_resolution_ready(self.case, attempt)
        canonical = tuple(
            (submission.item_uid, submission.choice_uid)
            for submission in progress.submissions
            if submission.choice_uid is not None
        )
        if len(canonical) != len(progress.submissions):
            raise ValueError(
                "The deterministic workbench cannot return free responses."
            )
        if outcome.bulk_uid is not None and outcome.decisions != canonical:
            raise ValueError(
                "Resolution bulk outcome does not match its frozen expansion."
            )
        return ResolutionOutcome(canonical, bulk_uid=outcome.bulk_uid)


@dataclass(frozen=True)
class ResolutionOutcome:
    """Exact item-ordered decisions returned after reviewed application."""

    decisions: tuple[tuple[str, str], ...]
    bulk_uid: str | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.decisions, tuple)
            or not self.decisions
            or any(
                not isinstance(decision, tuple)
                or len(decision) != 2
                or not isinstance(decision[0], str)
                or not decision[0]
                or not isinstance(decision[1], str)
                or not decision[1]
                for decision in self.decisions
            )
            or len({uid for uid, _choice in self.decisions}) != len(self.decisions)
        ):
            raise ValueError("Resolution outcome requires distinct item decisions.")
        if self.bulk_uid is not None and (
            not isinstance(self.bulk_uid, str) or not self.bulk_uid
        ):
            raise ValueError("Resolution outcome bulk choice is invalid.")
