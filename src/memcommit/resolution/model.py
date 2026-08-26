"""Pure values shared by deterministic and semantic resolution hosts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ResolutionObligation = Literal["REQUIRED", "OPTIONAL"]


def _one_line(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or any(character in value for character in "\r\n")
    ):
        raise ValueError(f"Resolution {label} must be nonempty one-line text.")
    return value


@dataclass(frozen=True)
class ResolutionBinding:
    """Identity of the exact frozen artifact revision being resolved."""

    operation: str
    artifact_uid: str
    revision: str

    def __post_init__(self) -> None:
        _one_line(self.operation, "operation")
        _one_line(self.artifact_uid, "artifact uid")
        _one_line(self.revision, "revision")


@dataclass(frozen=True)
class ResolutionRequirement:
    """One operation-owned item and the response forms legal for that item."""

    item_uid: str
    choice_uids: tuple[str, ...]
    obligation: ResolutionObligation = "REQUIRED"
    comment_allowed: bool = False

    def __post_init__(self) -> None:
        _one_line(self.item_uid, "requirement item uid")
        if (
            not isinstance(self.choice_uids, tuple)
            or any(
                not isinstance(choice_uid, str)
                or not choice_uid
                or any(character in choice_uid for character in "\r\n")
                for choice_uid in self.choice_uids
            )
            or len(set(self.choice_uids)) != len(self.choice_uids)
        ):
            raise ValueError(
                "Resolution requirement choices must be distinct one-line text."
            )
        if self.obligation not in {"REQUIRED", "OPTIONAL"}:
            raise ValueError("Resolution requirement obligation is invalid.")
        if not isinstance(self.comment_allowed, bool):
            raise TypeError("Resolution comment availability must be a boolean.")
        if not self.choice_uids and not self.comment_allowed:
            raise ValueError(
                "Resolution requirement needs a choice or a free response."
            )


@dataclass(frozen=True)
class ResolutionCase:
    """Complete operation-neutral decision surface for one frozen revision."""

    binding: ResolutionBinding
    requirements: tuple[ResolutionRequirement, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.binding, ResolutionBinding):
            raise TypeError("Resolution case requires a frozen binding.")
        if not isinstance(self.requirements, tuple) or any(
            not isinstance(requirement, ResolutionRequirement)
            for requirement in self.requirements
        ):
            raise TypeError("Resolution case requirements are invalid.")
        item_uids = tuple(requirement.item_uid for requirement in self.requirements)
        if len(set(item_uids)) != len(item_uids):
            raise ValueError("Resolution case repeats an item uid.")

    def requirement(self, item_uid: str) -> ResolutionRequirement:
        """Return one exact requirement without interpreting visible ordinals."""

        matches = [
            requirement
            for requirement in self.requirements
            if requirement.item_uid == item_uid
        ]
        if len(matches) != 1:
            raise KeyError(item_uid)
        return matches[0]


@dataclass(frozen=True)
class ResolutionSubmission:
    """One UID-bound staged answer; it does not imply Apply authority."""

    item_uid: str
    choice_uid: str | None = None
    comment: str = ""

    def __post_init__(self) -> None:
        _one_line(self.item_uid, "submission item uid")
        if self.choice_uid is not None:
            _one_line(self.choice_uid, "submission choice uid")
        if not isinstance(self.comment, str):
            raise TypeError("Resolution submission comment must be text.")
        if self.choice_uid is None and not self.comment.strip():
            raise ValueError(
                "Resolution submission requires a choice or a free response."
            )


@dataclass(frozen=True)
class ResolutionAttempt:
    """One expected frozen binding and its staged item or bulk answers."""

    binding: ResolutionBinding
    submissions: tuple[ResolutionSubmission, ...] = ()
    bulk_choice_uid: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.binding, ResolutionBinding):
            raise TypeError("Resolution attempt requires a frozen binding.")
        if not isinstance(self.submissions, tuple) or any(
            not isinstance(submission, ResolutionSubmission)
            for submission in self.submissions
        ):
            raise TypeError("Resolution attempt submissions are invalid.")
        if self.bulk_choice_uid is not None:
            _one_line(self.bulk_choice_uid, "attempt bulk choice uid")


@dataclass(frozen=True)
class ResolutionProgress:
    """Canonical staged answers and the REQUIRED items still unresolved."""

    binding: ResolutionBinding
    submissions: tuple[ResolutionSubmission, ...]
    unresolved_required_uids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.binding, ResolutionBinding):
            raise TypeError("Resolution progress requires a frozen binding.")
        if not isinstance(self.submissions, tuple) or any(
            not isinstance(submission, ResolutionSubmission)
            for submission in self.submissions
        ):
            raise TypeError("Resolution progress submissions are invalid.")
        if not isinstance(self.unresolved_required_uids, tuple) or any(
            not isinstance(item_uid, str) or not item_uid
            for item_uid in self.unresolved_required_uids
        ):
            raise TypeError("Resolution unresolved identities are invalid.")
        if len({item.item_uid for item in self.submissions}) != len(self.submissions):
            raise ValueError("Resolution progress repeats a staged item.")
        if len(set(self.unresolved_required_uids)) != len(
            self.unresolved_required_uids
        ):
            raise ValueError("Resolution progress repeats an unresolved item.")

    @property
    def ready(self) -> bool:
        """Whether every REQUIRED item has an exact staged answer."""

        return not self.unresolved_required_uids
