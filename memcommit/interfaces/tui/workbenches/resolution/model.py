"""Typed presentation contract for provider-free required resolutions."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.interfaces.tui.components.exact_command_review import (
    ExactCommandReview,
)
from memcommit.interfaces.tui.viewers.semantic import SemanticViewerDocument


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

    title: str
    subtitle: str
    report: SemanticViewerDocument
    items: tuple[ResolutionItem, ...]
    exact_review: ExactCommandReview
    bulk_strategies: tuple[ResolutionBulkStrategy, ...] = ()

    def __post_init__(self) -> None:
        if not self.title or not self.subtitle:
            raise ValueError("Resolution workbench requires visible headings.")
        if not isinstance(self.report, SemanticViewerDocument):
            raise TypeError("Resolution report must be a semantic document.")
        if not self.items or len({item.uid for item in self.items}) != len(self.items):
            raise ValueError("Resolution workbench requires distinct required items.")
        if not isinstance(self.exact_review, ExactCommandReview):
            raise TypeError("Resolution workbench exact review is invalid.")
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


@dataclass(frozen=True)
class ResolutionOutcome:
    """Exact item-ordered decisions returned after reviewed application."""

    decisions: tuple[tuple[str, str], ...]
    bulk_uid: str | None = None

    def __post_init__(self) -> None:
        if not self.decisions or len({uid for uid, _choice in self.decisions}) != len(
            self.decisions
        ):
            raise ValueError("Resolution outcome requires distinct item decisions.")
