"""Conflict requests, frozen inputs, analysis and receipt values."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal

from memcommit.application.capabilities.resolution.workbench import ResolutionOption
from memcommit.application.operations.audit.model import (
    QualityAuditSession,
    AuditTarget,
)


CONFLICT_RESOLUTION_CONTRACT_VERSION = "conflict-resolution-v1"
ConflictResolutionIssueKind = Literal["CONFLICT"]
ConflictResolutionStatus = Literal[
    "NO_ISSUES",
    "NEEDS_INPUT",
]


class ConflictResolutionError(RuntimeError):
    """A Conflict request, semantic result, or Apply boundary is invalid."""


class ConflictTargetChangedError(ConflictResolutionError):
    """A frozen Context or exact Conflict choice changed before Apply."""


@dataclass(frozen=True)
class ConflictResolutionSourcePrecondition:
    """Finder-owned direct Memory source whose identity and content must still back Conflict."""

    context_uid: str
    display_name: str
    direct_memory_digest: str

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, str) or not value
            for value in (self.context_uid, self.display_name)
        ):
            raise ConflictResolutionError(
                "Conflict source precondition requires a Context identity."
            )
        if (
            not isinstance(self.direct_memory_digest, str)
            or len(self.direct_memory_digest) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.direct_memory_digest
            )
        ):
            raise ConflictResolutionError(
                "Conflict source precondition requires a SHA-256 Memory digest."
            )


@dataclass(frozen=True)
class ConflictResolutionRequest:
    """Conflict the whole Context through reviewed additions, edits and removals."""

    context_name: str | None = None
    source_precondition: ConflictResolutionSourcePrecondition | None = None

    def __post_init__(self) -> None:
        if self.context_name is not None and (
            not isinstance(self.context_name, str) or not self.context_name.strip()
        ):
            raise ConflictResolutionError(
                "Conflict Context name must be nonblank when supplied."
            )
        if self.source_precondition is not None and not isinstance(
            self.source_precondition,
            ConflictResolutionSourcePrecondition,
        ):
            raise ConflictResolutionError(
                "Conflict source precondition must use the typed contract."
            )


@dataclass(frozen=True)
class ConflictResolutionTarget:
    """Exact whole-Context source and freshness boundary for Conflict."""

    request: ConflictResolutionRequest
    display_name: str
    source: AuditTarget
    revision: str
    actionable_uids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.request, ConflictResolutionRequest):
            raise TypeError("Conflict frame requires a typed request.")
        if not isinstance(self.source, AuditTarget):
            raise ConflictResolutionError("Conflict requires a frozen Audit Source.")
        for value, label in (
            (self.display_name, "display name"),
            (self.revision, "revision"),
        ):
            if not isinstance(value, str) or not value:
                raise ConflictResolutionError(
                    f"Conflict frame {label} must be nonempty text."
                )
        item_uids = {item.uid for item in self.source.items}
        if (
            (not self.actionable_uids and item_uids)
            or len(set(self.actionable_uids)) != len(self.actionable_uids)
            or set(self.actionable_uids) != item_uids
        ):
            raise ConflictResolutionError(
                "Conflict must include every Memory in the Context."
            )


@dataclass(frozen=True, slots=True)
class AuditResolutionIssue:
    """One Audit finding projected for suggestion generation and reinspection."""

    audit_snapshot_digest: str
    audit_key: str
    kind: ConflictResolutionIssueKind
    classification: str
    item_uids: tuple[str, ...]
    reason: str
    question: str
    detail: dict[str, object]
    item_kind: str = "MEMORY"

    @property
    def uid(self) -> str:
        encoded = json.dumps(
            {"audit": self.audit_snapshot_digest, "item": self.audit_key},
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return "audit-item-" + hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ConflictResolutionIssue:
    """One immutable Audit item plus its separately derived Conflict direction."""

    uid: str
    audit_key: str
    audit_snapshot_digest: str
    kind: ConflictResolutionIssueKind
    classification: str
    item_uids: tuple[str, ...]
    proposed_direction: str
    reason: str
    question: str = ""
    item_kind: str = "MEMORY"
    choices: tuple[ResolutionOption, ...] = ()
    default_choice: str | None = None

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, str) or not value
            for value in (
                self.uid,
                self.audit_key,
                self.audit_snapshot_digest,
                self.kind,
                self.classification,
                self.proposed_direction,
                self.reason,
            )
        ):
            raise ConflictResolutionError(
                "Conflict Issues require complete text values."
            )
        if self.kind != "CONFLICT":
            raise ConflictResolutionError("Conflict Issue kind is invalid.")
        if (
            not isinstance(self.item_uids, tuple)
            or len(set(self.item_uids)) != len(self.item_uids)
            or any(not isinstance(value, str) or not value for value in self.item_uids)
            or not self.item_uids
        ):
            raise ConflictResolutionError("Conflict Issue members are invalid.")
        if self.item_kind not in {"MEMORY"}:
            raise ConflictResolutionError("Conflict Issue item kind is invalid.")
        if not isinstance(self.choices, tuple) or any(
            not isinstance(choice, ResolutionOption) for choice in self.choices
        ):
            raise ConflictResolutionError(
                "Conflict fixed choices must be typed options."
            )
        if self.choices and (
            len({choice.uid for choice in self.choices}) != len(self.choices)
            or any(
                choice.uid
                not in {
                    "CONFIRM",
                    "INTENT",
                    "FORCE",
                    "KEEP_TARGET",
                    "TAKE_SOURCE",
                    "KEEP_BOTH",
                    "KEEP_AS_IS",
                }
                for choice in self.choices
            )
        ):
            raise ConflictResolutionError("Conflict fixed choice contract is invalid.")
        if self.default_choice is not None and self.default_choice not in {
            choice.uid for choice in self.choices
        }:
            raise ConflictResolutionError("Conflict default choice must be available.")
        if not isinstance(self.question, str):
            raise TypeError("Conflict Issue question must be text.")


@dataclass(frozen=True)
class ConflictResolutionAnalysis:
    """One exact Audit and its answerable directions over a frozen revision."""

    frame: ConflictResolutionTarget
    status: ConflictResolutionStatus
    audit: QualityAuditSession | None = None
    question: str = ""
    issues: tuple[ConflictResolutionIssue, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.frame, ConflictResolutionTarget):
            raise TypeError("Conflict analysis requires a frozen frame.")
        if self.status not in {
            "NO_ISSUES",
            "NEEDS_INPUT",
        }:
            raise ConflictResolutionError("Conflict analysis status is invalid.")
        if not isinstance(self.question, str):
            raise TypeError("Conflict analysis question must be text.")
        if (
            not isinstance(self.issues, tuple)
            or any(
                not isinstance(issue, ConflictResolutionIssue) for issue in self.issues
            )
            or len({issue.uid for issue in self.issues}) != len(self.issues)
        ):
            raise ConflictResolutionError("Conflict review Issues are invalid.")
        frame_uids = {item.uid for item in self.frame.source.items}
        if any(not set(issue.item_uids) <= frame_uids for issue in self.issues):
            raise ConflictResolutionError(
                "Conflict review Issues name Memories outside the frame."
            )
        kinds = {item.uid: item.kind for item in self.frame.source.items}
        if any(
            any(kinds[uid] != issue.item_kind for uid in issue.item_uids)
            for issue in self.issues
        ):
            raise ConflictResolutionError(
                "Conflict Issue role does not match its Source items."
            )
        if not isinstance(self.audit, QualityAuditSession):
            raise ConflictResolutionError(
                "Conflict analysis requires one completed Audit."
            )
        if self.audit.source != self.frame.source:
            raise ConflictResolutionError(
                "Conflict Audit does not match its frozen Context."
            )
        if any(
            issue.audit_snapshot_digest != self.audit.snapshot_digest
            for issue in self.issues
        ):
            raise ConflictResolutionError(
                "Conflict direction does not match its Audit snapshot."
            )
        if self.status == "NO_ISSUES" and self.issues:
            raise ConflictResolutionError(
                "A no-Issues Conflict analysis cannot contain decisions."
            )
        if self.status == "NEEDS_INPUT" and not self.issues:
            raise ConflictResolutionError(
                "Conflict needs input only when Audit items exist."
            )


@dataclass(frozen=True)
class ConflictResolutionReceipt:
    """Durable receipt for one exact Conflict-owned Update application."""

    context_uid: str
    context_name: str
    revision: str
    plan_uid: str
    checkpoint_uid: str
    created_uids: tuple[str, ...]
    updated_uids: tuple[str, ...]
    deleted_uids: tuple[str, ...]
    unresolved_issue_uids: tuple[str, ...] = ()
    checkpoints: tuple[tuple[str, str], ...] = ()
